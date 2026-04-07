# MultiPanel User Guide v2.0

## Dashboard
The dashboard shows system overview: CPU/RAM/disk usage, user counts (total, active, online, disabled, expired), bandwidth totals, destination VPN status, and unread alerts count.

## User Management

### Creating a User
1. Go to Users > New User
2. Enter username (required)
3. Optional: set bandwidth limits, speed limits, expiry date, max connections
4. Click Create

The system auto-generates WireGuard keys and assigns an IP.

### User Detail (7 Tabs)

**Overview**: Bandwidth usage bars, connection settings, account info.

**Config**: WireGuard config text + QR code. Editable fields: DNS, AllowedIPs, Endpoint, MTU, PersistentKeepalive.

**Sessions**: Connection history with GeoIP (country, city, ISP), OS detection (via TTL), bandwidth per session. Expandable to show visited/blocked destinations per session.

**Proxy** (NEW): Manage proxy accounts. Add accounts on any inbound (VLESS, Trojan, etc.). Copy share links for client apps.

**Whitelist**: Allow-only rules. When entries exist, user can ONLY access listed destinations. Shows visited sites with quick add-to-whitelist/blacklist buttons.

**Blacklist**: Block specific IPs/domains. Use `*` to block everything except whitelist. Shows blocked request attempts with counts.

**Schedule**: Time-based access windows (day + start/end time).

## Inbounds (Multi-Protocol)

### Creating an Inbound
1. Go to Inbounds > New Inbound
2. Fill in:
   - **Tag**: unique name (e.g., "vless-tcp-reality")
   - **Protocol**: VLESS, Trojan, Shadowsocks, HTTP, SOCKS
   - **Port**: listener port
   - **Transport**: TCP, WebSocket, gRPC
   - **Security**: none, TLS, Reality
   - **Engine**: Xray-core or sing-box

### Adding Proxy Accounts to Users
1. Go to User Detail > Proxy tab
2. Click "+ Add"
3. Select an inbound
4. Credentials are auto-generated
5. Click copy icon to get share link (vless://, trojan://, ss://, etc.)

## Destinations (Outbound VPN)
Manage upstream VPN connections. Supports WireGuard and OpenVPN.

- **Start Modes**: Manual, On-demand (auto-start when users online), Auto-restart
- **Health Monitoring**: Interface check + ping/handshake
- **Routing**: Isolated routing tables per destination

## Access Control

### Whitelist
- When entries exist, user can ONLY access those destinations
- Supports: IP, CIDR, domain names
- Domains auto-resolved to IPs

### Blacklist
- Block specific addresses
- `*` = block ALL except whitelist entries
- Connection attempts logged

### Schedules
- Define allowed access windows per day
- Outside schedule: VPN access blocked via iptables time rules

## Alerts & Notifications
- **Bandwidth warnings**: When user hits threshold (default 80%)
- **Expiry warnings**: 3 days before account expires
- **Expired**: Account auto-disabled
- **Destination down**: VPN health check failure
- Channels: Panel (in-app), Email (SMTP), Telegram bot

## Admin Management (Super Admin Only)

### Roles
- **Super Admin**: Full access to everything
- **Admin**: Granular permissions (users.view, users.create, users.edit, etc.)

### 2FA (Two-Factor Authentication)
1. Go to Settings or call API: `POST /api/auth/2fa/enable`
2. Set email address + confirm password
3. On next login: enter password > receive email code > verify code

### Audit Log
All admin actions logged with IP address, user-agent, and timestamp.

## Settings
- Global alerts toggle
- Bandwidth poll interval
- Connection logging toggle
- SMTP email configuration
- Telegram bot token

## Health Check
`GET /api/health` returns real system status:
- Database connectivity
- WireGuard interface status
- Scheduler status

## Dry-Run Mode
Set `DRY_RUN=true` in `.env` to test changes safely:
- All write commands (iptables, wg, tc) are logged but NOT executed
- Read-only commands still execute
- View command history: `GET /api/settings/dry-run-history`
