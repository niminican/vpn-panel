# MultiPanel Installation Guide v2.0

## Requirements
- Linux server (Ubuntu 20.04+ / Debian 11+)
- Docker + Docker Compose
- WireGuard kernel module
- Domain name (optional, for TLS)
- Xray-core binary (for multi-protocol proxy)

## Quick Install (Docker)

### 1. Clone the repository
```bash
git clone https://github.com/your-repo/MultiPanel.git
cd MultiPanel
```

### 2. Configure environment
```bash
cp .env.example .env
nano .env
```

Essential settings:
```
SECRET_KEY=<random-32-char-string>
ADMIN_PASSWORD=<strong-password-12+-chars>
ENCRYPTION_KEY=<fernet-key>
WG_SERVER_IP=<your-server-public-ip>
```

Generate a Fernet key:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Start the panel
```bash
docker compose up -d
```

### 4. Access the panel
Open `http://your-server-ip:8080/vpn/` in your browser.
Login with the credentials set in `.env`.

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| PANEL_PORT | 8080 | Panel web port |
| SECRET_KEY | (required) | JWT signing key |
| ADMIN_USERNAME | admin | Default admin username |
| ADMIN_PASSWORD | admin | Default admin password |
| WG_INTERFACE | wg0 | WireGuard interface name |
| WG_PORT | 51820 | WireGuard listen port |
| WG_SUBNET | 10.8.0.0/24 | Client IP range |
| WG_DNS | 1.1.1.1,8.8.8.8 | DNS for VPN clients |
| WG_SERVER_IP | (required) | Server public IP |
| ENCRYPTION_KEY | (required) | Fernet key for encrypting WG keys |
| DRY_RUN | false | Log commands without executing |
| DEMO_MODE | false | Skip WireGuard commands |
| TELEGRAM_BOT_TOKEN | (optional) | Telegram bot for notifications |

## Nginx Reverse Proxy (Optional)

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location /vpn/ {
        proxy_pass http://127.0.0.1:8080/vpn/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Multi-Protocol Setup (Xray-core)

### Install Xray-core
```bash
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
```

### Create Inbound in Panel
1. Go to Inbounds page
2. Click "New Inbound"
3. Select protocol (VLESS/Trojan/Shadowsocks/HTTP/SOCKS)
4. Set port, transport, and security options
5. Create proxy accounts for users

## Backup & Restore

### Backup
```bash
cp data/vpnpanel.db backup/
cp .env backup/
cp -r /etc/wireguard/ backup/
```

### Restore
```bash
docker compose down
cp backup/vpnpanel.db data/
cp backup/.env .
docker compose up -d
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Can't login | Check ADMIN_PASSWORD in .env |
| WireGuard not working | Check `wg show` and firewall rules |
| Panel not accessible | Check PANEL_PORT and firewall |
| 2FA email not received | Configure SMTP settings in panel |
| Health check degraded | Check `/vpn/api/health` for details |
