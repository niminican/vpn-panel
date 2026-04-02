#!/bin/bash
set -e

echo "========================================"
echo "  VPN Panel - Direct Install Script"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash install.sh"
    exit 1
fi

# Detect OS
if [ ! -f /etc/os-release ]; then
    echo "Unsupported OS"
    exit 1
fi
source /etc/os-release
echo "Detected OS: $PRETTY_NAME"

# Install system dependencies
echo ""
echo "[1/6] Installing system dependencies..."
apt-get update
apt-get install -y wireguard wireguard-tools iptables iproute2 \
    python3 python3-pip python3-venv \
    nodejs npm \
    curl iputils-ping

# Enable IP forwarding
echo ""
echo "[2/6] Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi

# Set up application directory
APP_DIR="/opt/vpn-panel"
echo ""
echo "[3/6] Setting up application in $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/"
cd "$APP_DIR"

# Install Python dependencies
echo ""
echo "[4/6] Installing Python dependencies..."
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# Build frontend
echo ""
echo "[5/6] Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate encryption key
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s|change-this-to-a-fernet-key|$FERNET_KEY|g" .env
    sed -i "s|change-this-to-a-random-secret-key|$SECRET|g" .env
    echo ""
    echo "Generated .env file. Please edit /opt/vpn-panel/.env to set:"
    echo "  - WG_SERVER_IP (your server's public IP)"
    echo "  - ADMIN_PASSWORD (change from default)"
fi

# Create systemd service
echo ""
echo "[6/6] Creating systemd service..."
cat > /etc/systemd/system/vpn-panel.service << 'EOF'
[Unit]
Description=VPN Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/vpn-panel/backend
Environment=PATH=/opt/vpn-panel/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EnvironmentFile=/opt/vpn-panel/.env
ExecStart=/opt/vpn-panel/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vpn-panel
systemctl start vpn-panel

# Create data directory
mkdir -p "$APP_DIR/data"

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "Panel is running at: http://$(hostname -I | awk '{print $1}'):8080"
echo "Default login: admin / admin"
echo ""
echo "Important next steps:"
echo "  1. Edit /opt/vpn-panel/.env and set WG_SERVER_IP"
echo "  2. Change the default admin password"
echo "  3. Set up WireGuard: sudo bash /opt/vpn-panel/scripts/setup-wireguard.sh"
echo ""
echo "Service commands:"
echo "  sudo systemctl status vpn-panel"
echo "  sudo systemctl restart vpn-panel"
echo "  sudo journalctl -u vpn-panel -f"
echo ""
