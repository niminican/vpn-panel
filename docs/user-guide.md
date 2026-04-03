# VPN Panel - User Guide

## Table of Contents
1. [Overview](#overview)
2. [Installation](#installation)
3. [First Login](#first-login)
4. [Dashboard](#dashboard)
5. [Destination VPNs](#destination-vpns)
6. [User Management](#user-management)
7. [Connection Logs](#connection-logs)
8. [Packages](#packages)
9. [Alerts](#alerts)
10. [Settings](#settings)
11. [Admin Management](#admin-management)
12. [Activity Log](#activity-log)
13. [Backup & Restore](#backup--restore)
14. [Troubleshooting](#troubleshooting)

---

## Overview

VPN Panel is a web-based management panel for sharing VPN connections with multiple users via WireGuard. It provides:

- **User Management**: Create/manage VPN users with bandwidth limits, speed limits, and expiry dates
- **Multi-Destination VPN**: Route users through different VPN destinations (WireGuard/OpenVPN)
- **Bandwidth Tracking**: Real-time monitoring with volume and speed limits
- **Access Control**: Per-user whitelists and time-based schedules
- **Connection Logging**: Track all connections with DNS hostname resolution
- **Alerts**: Bandwidth warnings, expiry notifications via panel/email/Telegram
- **Multi-Admin RBAC**: Role-based access control with granular permissions

---

## Installation

### Docker Compose (Recommended)

```bash
git clone <repo-url> /opt/vpn-panel
cd /opt/vpn-panel
cp .env.example .env
# Edit .env with your settings (see Configuration below)
docker compose up -d
```

### Direct Install

```bash
sudo bash scripts/install.sh
```

### Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *change this* | JWT signing key (random string) |
| `ADMIN_USERNAME` | admin | Default super admin username |
| `ADMIN_PASSWORD` | admin | Default super admin password |
| `ENCRYPTION_KEY` | *change this* | Fernet key for encrypting WG private keys |
| `WG_INTERFACE` | wg0 | WireGuard interface name |
| `WG_PORT` | 51820 | WireGuard listen port |
| `WG_SUBNET` | 10.8.0.0/24 | IP subnet for VPN users |
| `WG_SERVER_IP` | | Your server's public IP |
| `PANEL_PORT` | 8080 | Panel web port |
| `DEMO_MODE` | false | Skip actual WG/iptables commands |

Generate a Fernet key:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## First Login

1. Open `http://your-server-ip:8080` in a browser
2. Login with your configured admin credentials (default: `admin`/`admin`)
3. **Important**: Change the default password immediately via Settings > Change Password

---

## Dashboard

The dashboard provides an overview of your VPN system:

- **System Stats**: CPU, RAM, disk usage
- **User Summary**: Total, active, online, disabled, expired users
- **Bandwidth**: Total upload/download across all users
- **Destination VPNs**: Status of each destination (up/down count)
- **Alerts**: Unread alert count

---

## Destination VPNs

Destination VPNs are the upstream VPN connections that your users' traffic is routed through.

### Adding a Destination

1. Go to **Destinations** page
2. Click **New Destination**
3. Fill in:
   - **Name**: A friendly name (e.g., "Netherlands VPN")
   - **Interface Name**: Linux interface name (e.g., `wg1`, `wg-nl`)
   - **Config**: Paste the WireGuard (.conf) or OpenVPN (.ovpn) config
   - Protocol is auto-detected from the config content
4. Click **Create**

### Starting/Stopping

- Click the **Play** button to start a destination
- Click the **Stop** button to stop it
- The panel automatically sets up routing rules so only VPN user traffic goes through the destination

### Health Monitoring

- Destinations are health-checked every 60 seconds
- WireGuard: checks handshake recency
- OpenVPN: checks via ping
- Status shown as green (up) or red (down)

---

## User Management

### Creating a User

1. Go to **Users** > **New User**
2. Fill in:
   - **Username** (required)
   - **Destination VPN**: Which VPN to route this user through
   - **Bandwidth Limits**: Upload/download volume limits (bytes)
   - **Speed Limits**: Upload/download speed caps (Kbps)
   - **Max Connections**: Maximum simultaneous devices
   - **Expiry Date**: Account expiration
   - **Note**: Optional memo
3. Click **Create User**

The system automatically generates WireGuard keys and assigns an IP.

### User Detail Page

Click a user to view their detail page with tabs:

#### Overview
- Bandwidth usage bars (download/upload)
- Account details (destination, speed, limits, expiry, Telegram link)

#### Config
- WireGuard config text (copy/download)
- QR code for mobile setup
- **Edit Config**: Click the Edit button to customize per-user config settings:
  - **DNS**: Override the DNS server (default: global setting)
  - **Endpoint**: Override the server endpoint (default: global setting)
  - **AllowedIPs**: Override allowed IP ranges (default: `0.0.0.0/0, ::/0`)
  - **MTU**: Set a custom MTU value
  - **PersistentKeepalive**: Override keepalive interval (default: 25s)
  - Changes are saved per-user and reflected in the generated config/QR code

#### Sessions
- Connection history showing connect/disconnect times, duration, and per-session bandwidth
- **Client IP**: Source IP address the user connected from (extracted from WireGuard endpoint)
- **Endpoint**: Full endpoint (IP:port) of the connection
- Active sessions shown with green pulse indicator

#### Whitelist
- Add IP/CIDR entries to restrict which destinations this user can access
- When entries exist, only whitelisted destinations are allowed (everything else blocked)
- Leave empty for unrestricted access

#### Schedule
- Define time-based access windows (day of week + time range)
- Without schedules, access is 24/7
- With schedules, access is only allowed during defined windows

### Actions
- **Enable/Disable**: Toggle user's VPN access
- **Reset Bandwidth**: Zero out usage counters
- **Delete**: Remove user and their WireGuard peer

---

## Connection Logs

The Logs page shows all connections made by users:

- **Filters**: User, destination IP, hostname, protocol, date range
- **Columns**: Time, User, Source IP, Destination IP, Hostname, Port, Protocol
- Hostnames are resolved via passive DNS sniffing (captures DNS responses on the WireGuard interface)

**Note**: Hostname resolution works for IPs whose DNS queries pass through the server while the sniffer is running. Coverage is typically ~25% of connections.

---

## Packages

Packages define purchasable plans (for display in Telegram bot):

- **Name**: Package name
- **Bandwidth Limit**: Included data volume
- **Speed Limit**: Speed cap
- **Duration**: Validity period in days
- **Price**: Display price

---

## Alerts

The panel generates alerts for:

- **Bandwidth Warning**: User reached configured threshold (e.g., 80%)
- **Expiry Warning**: User account expiring soon
- **Expired**: User account has expired
- **Destination VPN Down**: A destination VPN went offline

View and acknowledge alerts on the Alerts page. Alerts can also be sent via email and Telegram.

---

## Settings

Configure panel behavior:

- **Global Alerts**: Enable/disable alert system
- **Email Alerts**: SMTP configuration
- **Telegram Alerts**: Bot notification toggle
- **Bandwidth Poll Interval**: How often to check usage (default: 60s)
- **Connection Logging**: Enable/disable connection tracking
- **Language**: Panel language

### Change Password

At the top of the Settings page, you can change your admin password.

---

## Admin Management

*Super Admin only*

### Roles

- **Super Admin**: Full access to everything including admin management
- **Admin (Limited)**: Access restricted to granted permissions

### Permissions

| Permission | Description |
|-----------|-------------|
| users.view | View user list and details |
| users.create | Create new users |
| users.edit | Edit, toggle, reset bandwidth |
| users.delete | Delete users |
| destinations.view | View destinations |
| destinations.manage | Create/edit/delete/start/stop destinations |
| logs.view | View connection logs |
| packages.manage | Manage packages |
| settings.manage | View/edit settings |
| alerts.view | View and acknowledge alerts |

### Managing Admins

1. Go to **Admins** (sidebar, super admin only)
2. Click **New Admin** to create
3. Select role and toggle permissions
4. Use the edit/delete buttons to manage existing admins

---

## Activity Log

*Super Admin only*

All admin actions are logged with full context:

- Login events
- User create/delete/toggle
- Admin create/update/delete
- Password changes
- Config updates

Each log entry includes:
- **Timestamp**: When the action occurred
- **Admin**: Who performed the action
- **Action**: What was done
- **Details**: Specifics of the action
- **IP Address**: Source IP of the admin making the request
- **Device**: Parsed device info from the User-Agent (e.g., "Chrome (Windows 10)", "Safari (macOS)")

Filter by admin username or action type. Located in the **Activity Log** sidebar item.

**Note**: Device detection uses User-Agent parsing and works for admin panel logins. VPN user connections track the client IP via WireGuard endpoints, but device type cannot be determined from the WireGuard protocol itself.

---

## Backup & Restore

### Automated Backups

Set up a cron job:
```bash
# Daily at 2:00 AM
0 2 * * * /opt/vpn-panel/scripts/backup.sh >> /var/log/vpn-panel-backup.log 2>&1
```

Backups include:
- SQLite database (using online backup for consistency)
- WireGuard configurations
- `.env` file

Backups are stored in `/opt/vpn-panel/backups/` with 30-day retention.

### Manual Backup

```bash
./scripts/backup.sh
# or with custom directory:
./scripts/backup.sh /path/to/backups
```

### Restore

```bash
# Extract backup
tar -xzf /opt/vpn-panel/backups/vpnpanel_backup_YYYYMMDD_HHMMSS.tar.gz

# Stop the panel
docker compose down  # or systemctl stop vpn-panel

# Restore database
cp vpnpanel_backup_*/vpnpanel.db /opt/vpn-panel/data/vpnpanel.db

# Restore WireGuard configs
cp -r vpnpanel_backup_*/wireguard/* /etc/wireguard/

# Restore .env
cp vpnpanel_backup_*/.env /opt/vpn-panel/.env

# Restart
docker compose up -d  # or systemctl start vpn-panel
```

---

## Troubleshooting

### Panel won't start
- Check logs: `docker compose logs` or `journalctl -u vpn-panel`
- Verify `.env` file exists and has correct values
- Check port isn't in use: `ss -tlnp | grep 8080`

### Users can't connect
- Verify WireGuard is running: `wg show`
- Check user is enabled in the panel
- Check user hasn't exceeded bandwidth limit or expiry date
- Verify destination VPN is running (green status)
- Check iptables rules: `iptables -L FORWARD -n -v`

### No hostname resolution in logs
- DNS sniffer requires tcpdump: `apt install tcpdump`
- Only resolves IPs whose DNS queries pass through the WireGuard interface
- Coverage improves over time as more queries are captured

### Destination VPN shows as down
- Check interface exists: `ip link show <interface>`
- For WireGuard: verify handshake is recent: `wg show <interface>`
- Check config file permissions: should be 600

### Rate limited on login
- After 5 failed attempts, login is locked for 15 minutes
- Wait for lockout to expire, or restart the panel to clear the limiter

### Database cleanup
- Old records are automatically cleaned up daily at 3:00 AM
- Connection logs: 30 days retention
- Bandwidth history: 90 days retention
- Audit logs: 180 days retention
- User sessions: 90 days retention
