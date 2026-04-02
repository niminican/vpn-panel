#!/bin/bash
set -e

echo "=== Setting up VPN Panel Development Environment ==="

# Install WireGuard tools
sudo apt-get update && sudo apt-get install -y wireguard-tools iptables iproute2

# Backend setup
cd /workspaces/vpn-panel/backend
python -m pip install --upgrade pip
pip install -r requirements.txt

# Frontend setup
cd /workspaces/vpn-panel/frontend
npm install

# Create data directory
mkdir -p /workspaces/vpn-panel/backend/data

# Create .env if not exists
if [ ! -f /workspaces/vpn-panel/.env ]; then
  cp /workspaces/vpn-panel/.env.example /workspaces/vpn-panel/.env
  # Generate secrets
  SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  FERNET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  sed -i "s|your-secret-key-change-this|${SECRET}|" /workspaces/vpn-panel/.env
  sed -i "s|your-fernet-key-here|${FERNET}|" /workspaces/vpn-panel/.env
  sed -i "s|SERVER_HOST=.*|SERVER_HOST=0.0.0.0|" /workspaces/vpn-panel/.env
  sed -i "s|WG_CONFIG_DIR=.*|WG_CONFIG_DIR=/etc/wireguard|" /workspaces/vpn-panel/.env
  sed -i "s|DATABASE_URL=.*|DATABASE_URL=sqlite:///./data/vpnpanel.db|" /workspaces/vpn-panel/.env
fi

# Create WireGuard config directory
sudo mkdir -p /etc/wireguard

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the backend:"
echo "  cd /workspaces/vpn-panel/backend"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"
echo ""
echo "To start the frontend (dev mode):"
echo "  cd /workspaces/vpn-panel/frontend"
echo "  npm run dev -- --host 0.0.0.0"
echo ""
echo "Default admin login: admin / admin"
echo ""
