# MultiPanel Architecture Documentation v2.0

## Overview

MultiPanel is a comprehensive VPN management platform supporting WireGuard (native) and multi-protocol proxy (via Xray-core/sing-box) with web-based admin panel.

## System Architecture

```
+------------------+     +----------------+     +------------------+
|   React Frontend |<--->|  FastAPI Backend|<--->|   SQLite DB      |
|   (Vite + TS)    |     |  (Python 3.12) |     |   (WAL mode)     |
+------------------+     +-------+--------+     +------------------+
                                 |
                    +------------+------------+
                    |            |            |
              +-----+---+  +----+----+  +----+----+
              |WireGuard |  |iptables |  |Xray-core|
              |(kernel)  |  |firewall |  |sing-box  |
              +----------+  +---------+  +---------+
```

## Backend Architecture

### API Layer (`/backend/app/api/`)
- **auth.py** - Authentication: login, 2FA verification, token refresh, password change
- **users.py** - User CRUD, toggle, bandwidth reset, config generation
- **inbounds.py** - Proxy inbound management (port + protocol + transport)
- **proxy_users.py** - Proxy account management per user with share links
- **destinations.py** - Destination VPN management (WG/OpenVPN)
- **whitelist.py / blacklist.py** - Per-user access control rules
- **schedules.py** - Time-based access windows
- **logs.py** - Connection log queries with GeoIP enrichment
- **alerts.py** - Alert management and acknowledgment
- **packages.py** - Service plan management
- **dashboard.py** - System stats aggregation
- **settings.py** - Global settings + dry-run history
- **admins.py** - Admin RBAC management + audit logs

### Service Layer (`/backend/app/services/`)
- **wireguard.py** - Key generation, peer management, config generation
- **proxy_engine/** - Multi-protocol proxy management
  - **base.py** - Abstract ProxyEngine interface
  - **xray.py** - Xray-core config generation + process management
  - **singbox.py** - sing-box config generation + process management
  - **share_links.py** - Protocol-specific share link generation
- **iptables.py** - Firewall rules (whitelist/blacklist chains, logging)
- **sync_firewall.py** - Centralized firewall sync with per-user mutex
- **bandwidth_tracker.py** - WireGuard traffic polling with thread safety
- **session_tracker.py** - Connection session lifecycle with thread safety
- **traffic_control.py** - Speed limiting via Linux tc
- **connection_logger.py** - Kernel log parsing + DNS sniffer
- **alert_service.py** - Alert dispatch (panel, email, Telegram)
- **scheduler.py** - Background jobs (APScheduler)
- **destination_vpn.py** - Health monitoring, SSH protection

### Core Layer (`/backend/app/core/`)
- **command_executor.py** - Central subprocess abstraction with dry-run mode
- **security.py** - Password hashing (bcrypt), JWT tokens, Fernet encryption
- **validators.py** - Input sanitization for all system commands
- **rate_limiter.py** - Login attempt rate limiting
- **device_detector.py** - User-Agent parsing
- **exceptions.py** - Custom HTTP exceptions

### Data Layer (`/backend/app/models/`)
- **User** - VPN user with WireGuard keys, bandwidth limits, config overrides
- **Inbound** - Proxy listener (protocol + port + transport + security)
- **ProxyUser** - Proxy credentials per user per inbound
- **Admin** - Admin account with RBAC, 2FA, enabled flag
- **DestinationVPN** - Upstream VPN endpoint
- **UserSession** - Connection sessions with GeoIP/OS enrichment
- **ConnectionLog** - Connection attempts (allowed/blocked/visited)
- **Alert** - System alerts (bandwidth, expiry, destination status)

## Frontend Architecture

### Tech Stack
- React 18 + TypeScript + Vite
- Tailwind CSS for styling
- Zustand for state management
- React Router v6 with code splitting (React.lazy)
- Error Boundary for crash recovery

### Pages (13 lazy-loaded)
- Dashboard, Users, UserNew, UserDetail (7 tabs), Destinations
- Inbounds (NEW), Logs, Packages, Settings, Alerts
- AdminManagement, AuditLog, Login

## Security Features
- JWT authentication with refresh tokens
- Email-based 2FA (codes hashed with bcrypt in DB)
- RBAC: super_admin + admin with granular permissions
- Rate limiting on login and 2FA endpoints
- Input validation on all system commands (iptables, wg, tc, ip)
- Dry-run mode for safe testing
- Admin enabled/disabled flag checked on every request
- Security headers (X-Content-Type-Options, X-Frame-Options, etc.)

## Supported Protocols

| Protocol | Engine | Credentials |
|----------|--------|-------------|
| WireGuard | Native (kernel) | Key pair + PSK |
| VLESS | Xray-core / sing-box | UUID + flow |
| Trojan | Xray-core / sing-box | Password |
| Shadowsocks | Xray-core / sing-box | Method + password |
| HTTP Proxy | Xray-core / sing-box | Username + password |
| SOCKS Proxy | Xray-core / sing-box | Username + password |

## Testing
- 227 automated tests (pytest)
- Test environment: Docker with DRY_RUN=true
- Coverage: auth, users, RBAC, validators, command executor, proxy engine, inbounds, proxy users, packages, alerts, schedules, logs, dashboard, admins
