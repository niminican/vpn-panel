# PROJECT BLUEPRINT — MultiPanel

> This document contains everything needed to rebuild this project from scratch.
> Give this file to Claude Code and it can recreate the entire project.

---

## 1. Project Specification

**What it does**: MultiPanel is a multi-protocol VPN and proxy management platform. Admins create users and assign them VPN connections (WireGuard) or proxy connections (VLESS, Trojan, Shadowsocks, HTTP, SOCKS). Each user connects via an **Inbound** (how they reach the server) and traffic exits via an **Outbound** (where it goes — direct internet, another proxy server, or blocked). The panel handles bandwidth tracking, access control (whitelist/blacklist/schedules), GeoIP session tracking, alerts, and multi-admin RBAC.

**Core features**:
1. **Multi-Protocol Proxy**: Inbound (VLESS, Trojan, SS, HTTP, SOCKS) + Outbound (direct, blackhole, WG, VLESS, Trojan, SS chain) via Xray-core or sing-box
2. **WireGuard VPN**: Native kernel WireGuard with key management, peer control, QR config
3. **User Management**: Bandwidth limits, speed limits, expiry dates, connection limits, per-user config overrides
4. **Access Control**: Per-user whitelist (allow-only), blacklist (block), wildcard block (`*`), time-based schedules via iptables
5. **Destination VPN Routing**: Route user traffic through upstream WireGuard/OpenVPN servers with isolated routing tables
6. **Connection Monitoring**: Real-time sessions with GeoIP (country, city, ISP), OS detection (TTL), visited/blocked destination tracking
7. **Admin Panel**: RBAC (super_admin + admin with granular permissions), email-based 2FA, audit logging
8. **Alerts**: Bandwidth threshold warnings, expiry alerts, destination down — panel + email + Telegram
9. **Dry-Run Mode**: Test system commands safely — write commands logged but not executed

---

## 2. Tech Stack (with exact versions)

```
Language:        Python 3.12
Framework:       FastAPI >=0.109.0
Database:        SQLite (WAL mode) via SQLAlchemy >=2.0.25
ORM:             SQLAlchemy 2.0+ (Mapped types)
Frontend:        React 18.3 + TypeScript 5.7 + Vite 6.0
CSS:             Tailwind CSS 3.4
State:           Zustand 5.0
Charts:          Recharts 2.15
Icons:           Lucide React 0.468
Auth:            JWT via python-jose + bcrypt via passlib
Encryption:      Fernet (cryptography >=41.0)
Proxy Engines:   Xray-core + sing-box (via abstraction layer)
System:          WireGuard (kernel), iptables, tc, iproute2
Scheduling:      APScheduler >=3.10.0
Email:           aiosmtplib >=3.0
Telegram:        aiogram >=3.4
GeoIP:           geoip2 >=4.8 (MaxMind GeoLite2)
Testing:         pytest >=8.0
Package Manager: pip + requirements.txt / npm + package.json
```

---

## 3. Database Schema

### Users
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    note TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    package_id INTEGER REFERENCES packages(id) ON DELETE SET NULL,
    destination_vpn_id INTEGER REFERENCES destination_vpns(id) ON DELETE SET NULL,
    wg_private_key TEXT NOT NULL,          -- Fernet encrypted
    wg_public_key VARCHAR(44) NOT NULL,
    wg_preshared_key TEXT,                 -- Fernet encrypted
    assigned_ip VARCHAR(18) UNIQUE NOT NULL,
    bandwidth_limit_up BIGINT,             -- bytes, NULL=unlimited
    bandwidth_limit_down BIGINT,
    bandwidth_used_up BIGINT DEFAULT 0,
    bandwidth_used_down BIGINT DEFAULT 0,
    bandwidth_reset_day INTEGER,           -- 1-28
    speed_limit_up INTEGER,                -- kbps
    speed_limit_down INTEGER,
    max_connections INTEGER DEFAULT 1,
    expiry_date DATETIME,
    alert_enabled BOOLEAN DEFAULT TRUE,
    alert_threshold INTEGER DEFAULT 80,
    alert_sent BOOLEAN DEFAULT FALSE,
    config_dns VARCHAR(200),
    config_allowed_ips VARCHAR(500),
    config_endpoint VARCHAR(200),
    config_mtu INTEGER,
    config_keepalive INTEGER,
    telegram_chat_id BIGINT,
    telegram_username VARCHAR(100),
    telegram_link_code VARCHAR(20) UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_users_enabled ON users(enabled);
CREATE INDEX ix_users_destination_vpn_id ON users(destination_vpn_id);
```

### Admins
```sql
CREATE TABLE admins (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,   -- bcrypt
    totp_secret VARCHAR(32),
    role VARCHAR(20) DEFAULT 'super_admin', -- super_admin | admin
    permissions TEXT,                        -- JSON: ["users.view", "logs.view", ...]
    enabled BOOLEAN DEFAULT TRUE,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    two_factor_email VARCHAR(255),
    two_factor_code VARCHAR(255),           -- bcrypt hash of 6-digit code
    two_factor_code_expires DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Inbounds
```sql
CREATE TABLE inbounds (
    id INTEGER PRIMARY KEY,
    tag VARCHAR(50) UNIQUE NOT NULL,
    protocol VARCHAR(20) NOT NULL,          -- vless|trojan|shadowsocks|http|socks
    port INTEGER NOT NULL,
    listen VARCHAR(50) DEFAULT '0.0.0.0',
    transport VARCHAR(20) DEFAULT 'tcp',    -- tcp|ws|grpc|http2
    transport_settings TEXT,                -- JSON
    security VARCHAR(20) DEFAULT 'none',    -- none|tls|reality
    security_settings TEXT,                 -- JSON
    engine VARCHAR(20) DEFAULT 'xray',      -- xray|singbox
    settings TEXT,                           -- protocol-specific JSON
    enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Outbounds
```sql
CREATE TABLE outbounds (
    id INTEGER PRIMARY KEY,
    tag VARCHAR(50) UNIQUE NOT NULL,
    protocol VARCHAR(20) NOT NULL,          -- direct|blackhole|vless|trojan|shadowsocks|wireguard|http|socks
    server VARCHAR(255),
    server_port INTEGER,
    uuid VARCHAR(36),                       -- VLESS
    password VARCHAR(255),                  -- Trojan/SS/HTTP/SOCKS
    flow VARCHAR(50),                       -- VLESS flow
    method VARCHAR(50),                     -- SS cipher
    private_key TEXT,                       -- WireGuard
    public_key VARCHAR(44),
    peer_public_key VARCHAR(44),
    local_address VARCHAR(50),              -- e.g. 10.0.0.2/32
    mtu INTEGER,
    transport VARCHAR(20) DEFAULT 'tcp',
    transport_settings TEXT,
    security VARCHAR(20) DEFAULT 'none',
    security_settings TEXT,
    engine VARCHAR(20) DEFAULT 'xray',
    enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### ProxyUsers
```sql
CREATE TABLE proxy_users (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    inbound_id INTEGER NOT NULL REFERENCES inbounds(id) ON DELETE CASCADE,
    outbound_id INTEGER REFERENCES outbounds(id) ON DELETE SET NULL,
    uuid VARCHAR(36),
    password VARCHAR(255),
    email VARCHAR(100) NOT NULL,            -- "username@inbound_tag" for Xray stats
    flow VARCHAR(50),
    method VARCHAR(50),
    enabled BOOLEAN DEFAULT TRUE,
    traffic_up BIGINT DEFAULT 0,
    traffic_down BIGINT DEFAULT 0,
    traffic_limit BIGINT,                   -- NULL=unlimited
    expire_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Other Tables
```sql
-- destination_vpns: WireGuard/OpenVPN upstream servers
-- user_sessions: Connection sessions with GeoIP + OS detection
-- connection_logs: iptables LOG entries (indexed: user_id + started_at)
-- alerts: Bandwidth/expiry/destination warnings
-- packages: Service plans with limits/pricing
-- settings: Key-value global config
-- admin_audit_logs: Admin action audit trail (indexed: admin_id + created_at)
-- bandwidth_history: Hourly snapshots (indexed: user_id + timestamp)
-- active_sessions: Current WireGuard handshake state
-- user_whitelist: Per-user allow rules (unique: user_id + address + port + protocol)
-- user_blacklist: Per-user block rules (unique: user_id + address + port + protocol)
-- user_schedules: Time-based access windows
-- blocked_requests: Aggregated blocked traffic per user+dest
```

**Relationships**:
- User has many ProxyUsers, WhitelistEntries, BlacklistEntries, Schedules, Sessions
- ProxyUser belongs to User + Inbound + Outbound (optional)
- Inbound has many ProxyUsers
- User optionally belongs to Package and DestinationVPN

---

## 4. API Endpoints / Routes

### Auth (`/api/auth`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | /login | Login, returns tokens or requires_2fa | No |
| POST | /verify-2fa | Verify 2FA code | No |
| POST | /refresh | Refresh access token | No |
| POST | /change-password | Change password (min 12 chars) | Yes |
| POST | /2fa/enable | Enable 2FA (requires password) | Yes |
| POST | /2fa/disable | Disable 2FA (requires password) | Yes |
| GET | /2fa/status | Get 2FA status | Yes |

### Users (`/api/users`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | / | List users (paginated, searchable) | users.view |
| POST | / | Create user | users.create |
| GET | /{id} | Get user detail | users.view |
| PUT | /{id} | Update user | users.edit |
| DELETE | /{id} | Delete user | users.delete |
| POST | /{id}/toggle | Enable/disable | users.edit |
| POST | /{id}/reset-bandwidth | Reset counters | users.edit |
| GET | /{id}/config | WireGuard config + QR | users.view |
| PUT | /{id}/config | Update custom config | users.edit |
| GET | /{id}/sessions | List sessions | users.view |

### Proxy Users (`/api/users/{id}/proxy`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | / | List proxy accounts | users.view |
| POST | / | Create proxy account (inbound + outbound) | users.edit |
| DELETE | /{proxy_id} | Delete proxy account | users.delete |
| GET | /{proxy_id}/config | Get share link | users.view |
| POST | /{proxy_id}/toggle | Enable/disable | users.edit |

### Inbounds (`/api/inbounds`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | / | List inbounds | destinations.view |
| POST | / | Create inbound | destinations.manage |
| PUT | /{id} | Update | destinations.manage |
| DELETE | /{id} | Delete | destinations.manage |
| POST | /{id}/toggle | Enable/disable | destinations.manage |

### Outbounds (`/api/outbounds`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | / | List outbounds | destinations.view |
| POST | / | Create outbound | destinations.manage |
| PUT | /{id} | Update | destinations.manage |
| DELETE | /{id} | Delete | destinations.manage |
| POST | /{id}/toggle | Enable/disable | destinations.manage |

### Destinations (`/api/destinations`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | / | List destination VPNs | destinations.view |
| POST | / | Create destination | destinations.manage |
| POST | /{id}/start | Start VPN | destinations.manage |
| POST | /{id}/stop | Stop VPN | destinations.manage |

### Other
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /api/packages | List packages | packages.manage |
| GET | /api/alerts | List alerts | alerts.view |
| GET | /api/logs | Connection logs | logs.view |
| GET | /api/dashboard | System stats | any admin |
| GET | /api/settings | Global settings | settings.manage |
| GET | /api/settings/dry-run-history | Command history | settings.manage |
| GET | /api/admins | List admins | super_admin |
| GET | /api/admins/audit-logs | Audit trail | super_admin |
| GET | /api/health | Health check (DB, WG, scheduler) | No |

---

## 5. Folder Structure (Complete)

```
MultiPanel/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, lifespan, middleware, routes
│   │   ├── config.py                  # Pydantic Settings (env vars)
│   │   ├── database.py                # SQLAlchemy engine, session, Base
│   │   ├── api/
│   │   │   ├── auth.py                # Login, 2FA, password change
│   │   │   ├── deps.py                # get_current_admin, require_permission
│   │   │   ├── users.py               # User CRUD + config + sessions
│   │   │   ├── proxy_users.py         # Proxy account CRUD + share links
│   │   │   ├── inbounds.py            # Inbound CRUD
│   │   │   ├── outbounds.py           # Outbound CRUD
│   │   │   ├── destinations.py        # Destination VPN start/stop
│   │   │   ├── whitelist.py           # Per-user whitelist + visited
│   │   │   ├── blacklist.py           # Per-user blacklist + blocked
│   │   │   ├── schedules.py           # Time-based access
│   │   │   ├── logs.py                # Connection log queries
│   │   │   ├── alerts.py              # Alert list + acknowledge
│   │   │   ├── packages.py            # Service plan CRUD
│   │   │   ├── dashboard.py           # System stats aggregation
│   │   │   ├── settings.py            # Global settings + dry-run history
│   │   │   └── admins.py              # Admin CRUD + audit logs
│   │   ├── models/
│   │   │   ├── __init__.py            # Exports all models
│   │   │   ├── user.py                # User with WG keys, bandwidth, config
│   │   │   ├── admin.py               # Admin with RBAC, 2FA, enabled
│   │   │   ├── inbound.py             # Proxy listener definition
│   │   │   ├── outbound.py            # Traffic exit definition
│   │   │   ├── proxy_user.py          # User→Inbound→Outbound mapping
│   │   │   ├── destination_vpn.py     # Upstream VPN server
│   │   │   ├── user_session.py        # Connection session + GeoIP
│   │   │   ├── connection_log.py      # iptables LOG entries
│   │   │   ├── alert.py               # System alerts
│   │   │   ├── package.py             # Service plans
│   │   │   ├── setting.py             # Key-value settings
│   │   │   ├── admin_audit_log.py     # Admin action audit
│   │   │   ├── bandwidth.py           # Hourly bandwidth snapshots
│   │   │   ├── active_session.py      # Current WG handshake state
│   │   │   ├── whitelist.py           # User whitelist rules
│   │   │   ├── blacklist.py           # User blacklist rules
│   │   │   ├── schedule.py            # Time-based access rules
│   │   │   └── blocked_request.py     # Aggregated blocked traffic
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── wireguard.py           # Key gen, peer mgmt, config gen
│   │   │   ├── proxy_engine/
│   │   │   │   ├── __init__.py        # get_engine() factory
│   │   │   │   ├── base.py            # ProxyEngine ABC
│   │   │   │   ├── xray.py            # Xray-core config + process mgmt
│   │   │   │   ├── singbox.py         # sing-box config + process mgmt
│   │   │   │   └── share_links.py     # vless://, trojan://, ss:// generators
│   │   │   ├── iptables.py            # Firewall rules (chains, LOG, NAT)
│   │   │   ├── sync_firewall.py       # Centralized sync with per-user mutex
│   │   │   ├── bandwidth_tracker.py   # WG traffic polling with thread lock
│   │   │   ├── session_tracker.py     # Session lifecycle with thread lock
│   │   │   ├── traffic_control.py     # Speed limits via tc (HTB + IFB)
│   │   │   ├── connection_logger.py   # Kernel log parser + DNS sniffer
│   │   │   ├── blocked_logger.py      # Blocked request aggregator
│   │   │   ├── alert_service.py       # Alert dispatch (panel/email/telegram)
│   │   │   ├── scheduler.py           # APScheduler background jobs
│   │   │   ├── destination_vpn.py     # Health checks, SSH protection
│   │   │   ├── geoip.py               # MaxMind GeoLite2 lookups
│   │   │   ├── os_detect.py           # TTL fingerprinting
│   │   │   ├── audit_logger.py        # Admin action logging
│   │   │   ├── qr_generator.py        # QR code generation
│   │   │   ├── system_monitor.py      # CPU/RAM/disk via psutil
│   │   │   └── db_cleanup.py          # Retention policy cleanup
│   │   └── core/
│   │       ├── command_executor.py     # Subprocess abstraction + dry-run
│   │       ├── security.py            # Password hash, JWT, Fernet encryption
│   │       ├── validators.py          # Input sanitization for system commands
│   │       ├── rate_limiter.py        # Login rate limiting
│   │       ├── device_detector.py     # User-Agent parsing
│   │       └── exceptions.py          # Custom HTTP exceptions
│   └── tests/                         # 16 test files, 240+ tests
├── frontend/
│   ├── src/
│   │   ├── main.tsx                   # Entry point
│   │   ├── App.tsx                    # Routes (React.lazy + ErrorBoundary)
│   │   ├── pages/                     # 14 lazy-loaded pages
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Users.tsx / UserNew.tsx / UserDetail.tsx
│   │   │   ├── Inbounds.tsx / Outbounds.tsx
│   │   │   ├── Destinations.tsx
│   │   │   ├── Logs.tsx / Alerts.tsx / Packages.tsx / Settings.tsx
│   │   │   └── AdminManagement.tsx / AuditLog.tsx
│   │   ├── components/
│   │   │   ├── ErrorBoundary.tsx       # React error boundary
│   │   │   ├── layout/ (MainLayout, Sidebar, Header)
│   │   │   └── user-detail/ (SessionsTab, ProxyTab)
│   │   ├── api/client.ts              # Axios + auth interceptors
│   │   ├── stores/authStore.ts        # Zustand auth state
│   │   └── lib/utils.ts              # formatBytes, formatDate (configurable TZ)
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── docs/                              # Architecture, Install, User Guide (MD + PDF)
├── Dockerfile                         # Multi-stage (Node + Python)
├── docker-compose.yml                 # Production
├── docker-compose.test.yml            # Local testing (DRY_RUN=true)
├── .env.example
├── CLAUDE.md                          # Project guide for AI
└── CHANGELOG.md
```

---

## 6. Key Business Logic

### Traffic Flow: Inbound → Outbound
Users connect via an **Inbound** (protocol + port + transport + security) and their traffic exits via an **Outbound** (direct, proxy chain, or blocked). The ProxyEngine generates config.json for Xray-core or sing-box with:
1. Inbound listeners with per-user credentials
2. Outbound definitions (direct + custom exits)
3. Routing rules mapping user emails to their outbound tags

### CommandExecutor (Dry-Run Mode)
Every system command (iptables, wg, tc, ip, systemctl) goes through `core/command_executor.py`. Commands are classified as read-only (always execute) or write (skip in dry-run). Each command is recorded in a deque(maxlen=1000) for audit.

### Firewall Sync (Per-User Mutex)
`sync_firewall.py` is the ONLY entry point for iptables rule changes. It acquires a per-user `threading.Lock` before reading DB state and writing rules. This prevents race conditions when concurrent API requests modify the same user's chains.

### Bandwidth Tracking
Every 60 seconds, `bandwidth_tracker.py` polls `wg show dump`, calculates deltas from last poll (with thread lock), and updates user records. When limits are exceeded, the user's WireGuard peer is removed. Monthly reset re-enables users on their reset day.

### Session Enrichment
When a new WireGuard handshake is detected, `session_tracker.py` creates a UserSession and enriches it with:
- GeoIP (country, city, ISP, ASN) from client's public IP
- OS detection via TTL fingerprinting (ping through VPN interface)

### Share Link Generation
`proxy_engine/share_links.py` generates protocol-specific URIs:
- VLESS: `vless://uuid@host:port?type=tcp&security=reality&...#remark`
- Trojan: `trojan://password@host:port?...#remark`
- Shadowsocks: `ss://base64(method:password)@host:port#remark`
- HTTP/SOCKS: `protocol://user:pass@host:port`

### RBAC Permission System
- **super_admin**: Full access to everything
- **admin**: Granular permissions checked via `require_permission()` dependency
- Permissions: users.view/create/edit/delete, destinations.view/manage, logs.view, packages.manage, settings.manage, alerts.view

---

## 7. Critical Bug Fixes (DO NOT SKIP)

### Bug #1: Async Alerts Never Sent
- **Symptom**: Telegram/email alerts created in DB but never delivered
- **Root Cause**: `send_telegram_alert()` and `send_email_alert()` are `async` but called from APScheduler's sync thread pool. Coroutines created but never awaited.
- **Solution**: Added `_run_async()` wrapper in `services/alert_service.py` that creates a new event loop per call: `loop = asyncio.new_event_loop(); loop.run_until_complete(coro); loop.close()`
- **Prevention**: Never call async functions from sync scheduler context without a wrapper

### Bug #2: Firewall Race Condition
- **Symptom**: Users intermittently lose connectivity when whitelist/blacklist modified
- **Root Cause**: `sync_user_firewall()` had no locking. Two concurrent API requests could half-flush iptables chains.
- **Solution**: Per-user `threading.Lock` in `services/sync_firewall.py`. Lock dict protected by its own meta-lock.
- **Prevention**: Always use `_get_user_lock(user_id)` before any iptables modification

### Bug #3: Disabled Admin Token Still Valid
- **Symptom**: Admin disabled via panel but can still access API with existing JWT
- **Root Cause**: No `enabled` field on Admin model, no check in `get_current_admin()`
- **Solution**: Added `enabled: bool = True` to Admin model + `if not admin.enabled: raise AuthenticationError()` in `api/deps.py`
- **Prevention**: Always check account status on every authenticated request, not just at login

### Bug #4: 2FA Enable Without Password
- **Symptom**: Attacker with stolen token could change 2FA email to their own
- **Root Cause**: `Enable2FARequest` only required email, not password confirmation
- **Solution**: Added `password` field to schema, verified with `verify_password()` before changing email
- **Prevention**: Any security-changing operation must require re-authentication

### Bug #5: 2FA Codes Stored Plaintext
- **Symptom**: DB breach would expose active 2FA codes
- **Root Cause**: 6-digit codes stored as plaintext in `two_factor_code` field
- **Solution**: Hash with bcrypt before storing (`hash_password(code)`), verify with `verify_password(code, hash)`. Field enlarged to VARCHAR(255).
- **Prevention**: Never store secrets in plaintext, even temporary ones

### Bug #6: Manual DNS Packet Parsing
- **Symptom**: DNS resolution fragile, fails on unusual responses
- **Root Cause**: 60-line hand-coded UDP DNS packet builder/parser in `validators.py`
- **Solution**: Replaced with `socket.getaddrinfo()` as fallback after `dig` command. Portable, no manual struct packing.
- **Prevention**: Use standard library or established libraries for protocol parsing

---

## 8. Environment Setup

```bash
# 1. Clone and install
git clone https://github.com/niminican/vpn-panel.git
cd vpn-panel

# 2. Configure environment
cp .env.example .env
# Edit .env with these REQUIRED values:
#   SECRET_KEY          - random 32+ char string for JWT signing
#   ADMIN_PASSWORD      - strong password (12+ chars)
#   ENCRYPTION_KEY      - Fernet key for WG key encryption
#   WG_SERVER_IP        - server's public IP address

# Generate Fernet key:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 3. Local testing with Docker
docker compose -f docker-compose.test.yml build
docker compose -f docker-compose.test.yml up -d

# 4. Run tests
docker exec vpn-panel-test python -m pytest tests/ -v

# 5. Access panel
open http://localhost:8888/vpn/
# Login: admin / admin (change immediately)
```

**Required environment variables**:
| Variable | Description |
|----------|-------------|
| SECRET_KEY | JWT signing key (random 32+ chars) |
| ADMIN_PASSWORD | Default admin password (12+ chars) |
| ENCRYPTION_KEY | Fernet key for encrypting WG private keys |
| WG_SERVER_IP | Server's public IP address |
| PANEL_PORT | Web panel port (default: 8080) |
| WG_INTERFACE | WireGuard interface name (default: wg0) |
| WG_PORT | WireGuard listen port (default: 51820) |
| WG_SUBNET | Client IP range (default: 10.8.0.0/24) |
| DRY_RUN | true/false — log write commands without executing (default: false) |
| DEMO_MODE | true/false — skip actual WG commands (default: false) |

---

## 9. Deployment Instructions

```bash
# Production deployment:
cp .env.example .env
nano .env  # Set all required variables with real values

docker compose up -d

# Access: http://server-ip:8080/vpn/
```

**Optional: Nginx reverse proxy with SSL**:
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
    }
}
```

**Backup**:
```bash
cp data/vpnpanel.db backup/
cp .env backup/
cp -r /etc/wireguard/ backup/
```

---

## 10. Third-party Integrations

| Service | Purpose | Config Location |
|---------|---------|-----------------|
| Xray-core | Multi-protocol proxy engine | services/proxy_engine/xray.py |
| sing-box | Alternative proxy engine | services/proxy_engine/singbox.py |
| MaxMind GeoLite2 | IP geolocation | services/geoip.py (auto-downloaded) |
| Telegram Bot | Alert notifications | aiogram, config: TELEGRAM_BOT_TOKEN |
| SMTP Email | Alert notifications + 2FA codes | aiosmtplib, config: SMTP_* vars |

---

## 11. Rebuild Instructions for Claude

> Claude: If you're reading this to rebuild the project, follow these steps IN ORDER:

1. Set up project structure as described in Section 5
2. Implement `core/command_executor.py` FIRST — all subprocess calls must go through it
3. Implement database models from Section 3 (all 18 tables)
4. Implement `core/security.py` (bcrypt, JWT, Fernet) and `core/validators.py`
5. Implement WireGuard service (`services/wireguard.py`)
6. Implement proxy engine abstraction (`services/proxy_engine/`)
7. Build API endpoints from Section 4 with RBAC from the start
8. Apply ALL bug fixes from Section 7 during implementation (not after!)
9. Implement background jobs (`services/scheduler.py`)
10. Build React frontend with code splitting and ErrorBoundary
11. Write tests (240+ covering all endpoints)
12. Configure Docker deployment

**Important constraints**:
- ALL subprocess calls must go through `command_executor.run_command()` — never call `subprocess.run` directly
- Per-user mutex in `sync_firewall.py` — never modify iptables without lock
- 2FA codes must be bcrypt-hashed in DB
- Password minimum 12 characters for admins
- `async` alert functions need `_run_async()` wrapper when called from sync context
- WireGuard stays separate from Xray/sing-box (native kernel vs userspace)
- Frontend uses React.lazy for ALL pages + ErrorBoundary at root
- Timezone in frontend reads from localStorage, falls back to browser default
- Default route for SSH recovery is cached at startup, not hardcoded
