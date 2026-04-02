#!/bin/bash
########################################################
#  VPN Panel - All-in-One Deploy Script for Ubuntu
#  Run as root: sudo bash deploy.sh
########################################################
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_DIR="/opt/vpn-panel"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║       VPN Panel - Deployment Script      ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root: sudo bash deploy.sh${NC}"
    exit 1
fi

# Detect Ubuntu version
if [ ! -f /etc/os-release ]; then
    echo -e "${RED}Error: Unsupported OS${NC}"
    exit 1
fi
source /etc/os-release
echo -e "${GREEN}OS: $PRETTY_NAME${NC}"
echo ""

########################################################
# STEP 1: Install System Dependencies
########################################################
echo -e "${YELLOW}[1/8] Installing system dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq \
    wireguard wireguard-tools \
    iptables iproute2 iputils-ping curl wget \
    python3 python3-pip python3-venv python3-dev \
    build-essential \
    git >/dev/null 2>&1

# Install Node.js 20
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}   Installing Node.js 20...${NC}"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
    apt-get install -y -qq nodejs >/dev/null 2>&1
fi

echo -e "${GREEN}   ✓ Dependencies installed${NC}"
echo -e "${GREEN}   Node: $(node --version 2>/dev/null || echo 'N/A')${NC}"
echo -e "${GREEN}   Python: $(python3 --version)${NC}"

########################################################
# STEP 2: Enable IP Forwarding
########################################################
echo -e "${YELLOW}[2/8] Enabling IP forwarding...${NC}"
sysctl -w net.ipv4.ip_forward=1 >/dev/null
if ! grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf 2>/dev/null; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi
echo -e "${GREEN}   ✓ IP forwarding enabled${NC}"

########################################################
# STEP 3: Copy Application Files
########################################################
echo -e "${YELLOW}[3/8] Setting up application in ${APP_DIR}...${NC}"
mkdir -p "$APP_DIR"

# Copy project files (we're running from project directory)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/backend/app/main.py" ]; then
    cp -r "$SCRIPT_DIR/backend" "$APP_DIR/"
    cp -r "$SCRIPT_DIR/frontend" "$APP_DIR/"
    cp -r "$SCRIPT_DIR/scripts" "$APP_DIR/"
    cp "$SCRIPT_DIR/.env.example" "$APP_DIR/" 2>/dev/null || true
    echo -e "${GREEN}   ✓ Files copied from $SCRIPT_DIR${NC}"
else
    echo -e "${RED}   Error: Cannot find project files. Run this script from the project root.${NC}"
    exit 1
fi

########################################################
# STEP 4: Python Virtual Environment + Dependencies
########################################################
echo -e "${YELLOW}[4/8] Setting up Python environment...${NC}"
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r backend/requirements.txt -q
echo -e "${GREEN}   ✓ Python dependencies installed${NC}"

########################################################
# STEP 5: Build Frontend
########################################################
echo -e "${YELLOW}[5/8] Building frontend...${NC}"
cd "$APP_DIR/frontend"
npm install --silent 2>/dev/null
npm run build 2>/dev/null
echo -e "${GREEN}   ✓ Frontend built${NC}"

########################################################
# STEP 6: Configure Environment
########################################################
echo -e "${YELLOW}[6/8] Configuring environment...${NC}"
cd "$APP_DIR"

if [ ! -f .env ]; then
    cp .env.example .env

    # Generate secure keys
    source venv/bin/activate
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    SERVER_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || echo "YOUR_SERVER_IP")

    sed -i "s|change-this-to-a-fernet-key|$FERNET_KEY|g" .env
    sed -i "s|change-this-to-a-random-secret-key|$SECRET|g" .env
    sed -i "s|YOUR_SERVER_PUBLIC_IP|$SERVER_IP|g" .env

    echo -e "${GREEN}   ✓ .env created with auto-generated keys${NC}"
    echo -e "${GREEN}   Server IP detected: $SERVER_IP${NC}"
else
    echo -e "${GREEN}   ✓ .env already exists, keeping existing config${NC}"
fi

# Create data directory
mkdir -p "$APP_DIR/data"

########################################################
# STEP 7: Setup WireGuard
########################################################
echo -e "${YELLOW}[7/8] Setting up WireGuard...${NC}"

source "$APP_DIR/.env" 2>/dev/null || true
WG_IFACE="${WG_INTERFACE:-wg0}"
WG_PORT_NUM="${WG_PORT:-51820}"
WG_SUB="${WG_SUBNET:-10.8.0.0/24}"
WG_DIR="/etc/wireguard"

mkdir -p "$WG_DIR"

# Generate server keys
if [ ! -f "$WG_DIR/${WG_IFACE}_privatekey" ]; then
    wg genkey | tee "$WG_DIR/${WG_IFACE}_privatekey" | wg pubkey > "$WG_DIR/${WG_IFACE}_publickey"
    chmod 600 "$WG_DIR/${WG_IFACE}_privatekey"
    echo -e "${GREEN}   ✓ Server keys generated${NC}"
fi

PRIV_KEY=$(cat "$WG_DIR/${WG_IFACE}_privatekey")
PUB_KEY=$(cat "$WG_DIR/${WG_IFACE}_publickey")

# Detect default interface
DEFAULT_IFACE=$(ip route show default | awk '/default/ {print $5}' | head -1)

# Create WireGuard config
if [ ! -f "$WG_DIR/${WG_IFACE}.conf" ]; then
    SUBNET_MASK=$(echo "$WG_SUB" | cut -d'/' -f2)
    SERVER_WG_IP=$(echo "$WG_SUB" | awk -F'[./]' '{print $1"."$2"."$3".1"}')

    cat > "$WG_DIR/${WG_IFACE}.conf" << EOF
[Interface]
PrivateKey = $PRIV_KEY
Address = ${SERVER_WG_IP}/${SUBNET_MASK}
ListenPort = $WG_PORT_NUM
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ${DEFAULT_IFACE} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ${DEFAULT_IFACE} -j MASQUERADE

# Peers managed by VPN Panel
EOF
    chmod 600 "$WG_DIR/${WG_IFACE}.conf"
    echo -e "${GREEN}   ✓ WireGuard config created${NC}"
fi

# Start WireGuard
systemctl enable wg-quick@${WG_IFACE} 2>/dev/null || true
systemctl start wg-quick@${WG_IFACE} 2>/dev/null || wg-quick up ${WG_IFACE} 2>/dev/null || true

# Check status
if wg show ${WG_IFACE} >/dev/null 2>&1; then
    echo -e "${GREEN}   ✓ WireGuard is running on port $WG_PORT_NUM${NC}"
else
    echo -e "${YELLOW}   ⚠ WireGuard may need manual start: wg-quick up ${WG_IFACE}${NC}"
fi

# Open firewall
if command -v ufw &> /dev/null; then
    ufw allow ${WG_PORT_NUM}/udp >/dev/null 2>&1
    ufw allow 8080/tcp >/dev/null 2>&1
    echo -e "${GREEN}   ✓ Firewall ports opened (${WG_PORT_NUM}/udp, 8080/tcp)${NC}"
fi

########################################################
# STEP 8: Create Systemd Service & Start
########################################################
echo -e "${YELLOW}[8/8] Creating systemd service...${NC}"

cat > /etc/systemd/system/vpn-panel.service << 'SERVICEEOF'
[Unit]
Description=VPN Panel
After=network.target wg-quick@wg0.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/vpn-panel/backend
EnvironmentFile=/opt/vpn-panel/.env
Environment=PATH=/opt/vpn-panel/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/opt/vpn-panel/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable vpn-panel
systemctl restart vpn-panel

# Wait for service to start
sleep 3

if systemctl is-active --quiet vpn-panel; then
    echo -e "${GREEN}   ✓ VPN Panel service is running${NC}"
else
    echo -e "${YELLOW}   ⚠ Service may still be starting. Check: journalctl -u vpn-panel -f${NC}"
fi

########################################################
# DONE!
########################################################
SERVER_IP=$(grep WG_SERVER_IP "$APP_DIR/.env" | cut -d'=' -f2)
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              ${GREEN}Installation Complete!${BLUE}                  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Panel URL:${NC}       http://${SERVER_IP}:8080"
echo -e "${GREEN}Admin Login:${NC}     admin / admin"
echo -e "${GREEN}WireGuard Port:${NC}  ${WG_PORT_NUM}/udp"
echo -e "${GREEN}Server PubKey:${NC}   ${PUB_KEY}"
echo ""
echo -e "${YELLOW}Important next steps:${NC}"
echo "  1. Open http://${SERVER_IP}:8080 in your browser"
echo "  2. Login with admin/admin and change your password"
echo "  3. Go to Destinations > Add your VPN config"
echo "  4. Go to Users > Create a user"
echo "  5. Download the .conf file or scan QR code"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  sudo systemctl status vpn-panel     # Check panel status"
echo "  sudo systemctl restart vpn-panel     # Restart panel"
echo "  sudo journalctl -u vpn-panel -f      # View logs"
echo "  sudo wg show                         # WireGuard status"
echo "  sudo nano /opt/vpn-panel/.env        # Edit config"
echo ""
