#!/bin/bash
set -e

echo "========================================"
echo "  WireGuard Setup Script"
echo "========================================"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash setup-wireguard.sh"
    exit 1
fi

# Load .env if exists
if [ -f /opt/vpn-panel/.env ]; then
    source /opt/vpn-panel/.env
fi

WG_INTERFACE="${WG_INTERFACE:-wg0}"
WG_PORT="${WG_PORT:-51820}"
WG_SUBNET="${WG_SUBNET:-10.8.0.0/24}"
SERVER_IP="${WG_SERVER_IP:-}"

if [ -z "$SERVER_IP" ]; then
    SERVER_IP=$(curl -s https://api.ipify.org)
    echo "Detected server IP: $SERVER_IP"
fi

# Generate server keys if not exists
WG_DIR="/etc/wireguard"
mkdir -p "$WG_DIR"

if [ ! -f "$WG_DIR/${WG_INTERFACE}_privatekey" ]; then
    echo "Generating WireGuard server keys..."
    wg genkey | tee "$WG_DIR/${WG_INTERFACE}_privatekey" | wg pubkey > "$WG_DIR/${WG_INTERFACE}_publickey"
    chmod 600 "$WG_DIR/${WG_INTERFACE}_privatekey"
fi

PRIVATE_KEY=$(cat "$WG_DIR/${WG_INTERFACE}_privatekey")
PUBLIC_KEY=$(cat "$WG_DIR/${WG_INTERFACE}_publickey")

# Get default network interface
DEFAULT_IFACE=$(ip route show default | awk '/default/ {print $5}' | head -1)

# Create WireGuard config
if [ ! -f "$WG_DIR/${WG_INTERFACE}.conf" ]; then
    echo "Creating WireGuard config..."
    # Extract server IP from subnet (first usable host)
    SUBNET_BASE=$(echo "$WG_SUBNET" | cut -d'/' -f1)
    SUBNET_MASK=$(echo "$WG_SUBNET" | cut -d'/' -f2)
    SERVER_WG_IP=$(echo "$SUBNET_BASE" | awk -F. '{print $1"."$2"."$3".1"}')

    cat > "$WG_DIR/${WG_INTERFACE}.conf" << EOF
[Interface]
PrivateKey = $PRIVATE_KEY
Address = ${SERVER_WG_IP}/${SUBNET_MASK}
ListenPort = $WG_PORT
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ${DEFAULT_IFACE} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ${DEFAULT_IFACE} -j MASQUERADE

# Peers are managed by VPN Panel
EOF
    chmod 600 "$WG_DIR/${WG_INTERFACE}.conf"
fi

# Enable and start WireGuard
echo "Starting WireGuard..."
systemctl enable wg-quick@${WG_INTERFACE}
systemctl start wg-quick@${WG_INTERFACE} || wg-quick up ${WG_INTERFACE}

# Open firewall port
if command -v ufw &> /dev/null; then
    ufw allow ${WG_PORT}/udp
    echo "Opened UDP port ${WG_PORT} in UFW"
fi

echo ""
echo "========================================"
echo "  WireGuard Setup Complete!"
echo "========================================"
echo ""
echo "Interface: $WG_INTERFACE"
echo "Port: $WG_PORT"
echo "Subnet: $WG_SUBNET"
echo "Server Public Key: $PUBLIC_KEY"
echo "Server IP: $SERVER_IP"
echo ""
echo "Status: $(wg show ${WG_INTERFACE} 2>/dev/null && echo 'Running' || echo 'Not running')"
echo ""
