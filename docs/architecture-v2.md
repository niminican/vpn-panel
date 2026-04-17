# MultiPanel Architecture Documentation v2.1

## System Overview

MultiPanel is a multi-protocol VPN and proxy management platform. It supports WireGuard (native kernel), and proxy protocols (VLESS, Trojan, Shadowsocks, HTTP, SOCKS) via Xray-core or sing-box engines.

## Traffic Flow Diagram

```
                        INBOUND                          OUTBOUND
                    (How users connect)             (Where traffic goes)

  +--------+     +-------------------+           +--------------------+
  | Client | --> | VLESS :443 (TLS)  | --------> | WG Germany :51820  | --> Internet
  +--------+     +-------------------+   |       +--------------------+
                                         |
  +--------+     +-------------------+   |       +--------------------+
  | Client | --> | Trojan :1080      | --+-----> | VLESS NL :443      | --> Internet
  +--------+     +-------------------+   |       +--------------------+
                                         |
  +--------+     +-------------------+   |       +--------------------+
  | Client | --> | SS :8388          | --+-----> | Direct             | --> Internet
  +--------+     +-------------------+           +--------------------+

  +--------+     +-------------------+
  | Client | --> | WireGuard :51820  | ---------> Internet (native kernel)
  +--------+     +-------------------+
```

## Module Architecture

```
+================================================================+
|                     MULTIPANEL BACKEND                          |
|================================================================|
|                                                                 |
|  +------------------+  +------------------+  +---------------+  |
|  |   API Layer      |  |  Service Layer   |  |  Data Layer   |  |
|  |  (FastAPI)       |  |  (Business Logic)|  |  (SQLAlchemy) |  |
|  +------------------+  +------------------+  +---------------+  |
|  |                  |  |                  |  |               |  |
|  | auth.py          |  | wireguard.py     |  | User          |  |
|  | users.py         |  | proxy_engine/    |  | Inbound       |  |
|  | inbounds.py      |  |   xray.py        |  | Outbound      |  |
|  | outbounds.py     |  |   singbox.py     |  | ProxyUser     |  |
|  | proxy_users.py   |  |   share_links.py |  | Admin         |  |
|  | destinations.py  |  | iptables.py      |  | DestinationVPN|  |
|  | whitelist.py     |  | sync_firewall.py |  | UserSession   |  |
|  | blacklist.py     |  | bandwidth_tracker|  | ConnectionLog |  |
|  | schedules.py     |  | session_tracker  |  | Alert         |  |
|  | logs.py          |  | traffic_control  |  | Package       |  |
|  | alerts.py        |  | alert_service    |  | Setting       |  |
|  | packages.py      |  | connection_logger|  | AuditLog      |  |
|  | dashboard.py     |  | scheduler        |  | Whitelist     |  |
|  | settings.py      |  | destination_vpn  |  | Blacklist     |  |
|  | admins.py        |  | system_monitor   |  | Schedule      |  |
|  |                  |  | geoip            |  | Bandwidth     |  |
|  +------------------+  +------------------+  +---------------+  |
|                                                                 |
|  +------------------+  +------------------+                     |
|  |   Core Layer     |  | Background Jobs  |                     |
|  +------------------+  +------------------+                     |
|  | command_executor |  | APScheduler:     |                     |
|  | security (JWT)   |  |  poll_bandwidth  |                     |
|  | validators       |  |  track_sessions  |                     |
|  | rate_limiter     |  |  check_alerts    |                     |
|  | device_detector  |  |  health_checks   |                     |
|  | exceptions       |  |  auto_dest_mgmt  |                     |
|  +------------------+  +------------------+                     |
|                                                                 |
+================================================================+

+================================================================+
|                     MULTIPANEL FRONTEND                         |
|================================================================|
|  React 18 + TypeScript + Vite + Tailwind CSS                   |
|  Code Splitting (React.lazy) + Error Boundary                  |
|                                                                 |
|  Pages: Dashboard | Users | UserDetail (7 tabs)                |
|         Inbounds | Outbounds | Destinations                    |
|         Logs | Alerts | Packages | Settings                    |
|         AdminManagement | AuditLog | Login                     |
+================================================================+

+================================================================+
|                     SYSTEM SERVICES                             |
|================================================================|
|  WireGuard (kernel)  |  Xray-core  |  sing-box  |  iptables   |
|  tc (traffic control)|  journalctl |  tcpdump   |  GeoIP DB   |
+================================================================+
```

## Entity Relationship Diagram

```
+----------+       +----------+       +-----------+
|   User   |------>| ProxyUser|------>|  Inbound  |
|----------|  1:N  |----------|  N:1  |-----------|
| id       |       | id       |       | id        |
| username |       | user_id  |       | tag       |
| wg_keys  |       | inbound_id       | protocol  |
| assigned_ip      | outbound_id      | port      |
| bandwidth |      | uuid     |       | transport |
| enabled  |       | password |       | security  |
+----------+       | email    |       | engine    |
     |             | traffic  |       +-----------+
     |             +----------+
     |                  |
     |                  v
     |             +----------+
     |             | Outbound |
     |             |----------|
     |             | id       |
     |             | tag      |
     |             | protocol |
     |             | server   |
     |             | credentials
     |             | engine   |
     |             +----------+
     |
     +------> Whitelist, Blacklist, Schedule, Session, Alert
```

## Supported Protocols

### Inbound (User Connection)
| Protocol | Engine | Transport | Security | Credentials |
|----------|--------|-----------|----------|-------------|
| WireGuard | Native | UDP | Crypto | Key pair + PSK |
| VLESS | Xray/sing-box | TCP/WS/gRPC | TLS/Reality/none | UUID |
| Trojan | Xray/sing-box | TCP/WS/gRPC | TLS | Password |
| Shadowsocks | Xray/sing-box | TCP/UDP | Cipher | Method + Password |
| HTTP Proxy | Xray/sing-box | TCP | TLS/none | User + Password |
| SOCKS Proxy | Xray/sing-box | TCP | TLS/none | User + Password |

### Outbound (Traffic Exit)
| Protocol | Use Case |
|----------|----------|
| Direct | Traffic goes straight to internet |
| Blackhole | Traffic is blocked |
| VLESS | Chain to another VLESS server |
| Trojan | Chain to another Trojan server |
| Shadowsocks | Chain to another SS server |
| WireGuard | Tunnel through WG server |
| HTTP/SOCKS | Proxy through HTTP/SOCKS server |

## Security Architecture
- JWT authentication with bcrypt password hashing
- Email-based 2FA with hashed codes (bcrypt)
- RBAC: super_admin + admin with granular permissions
- Rate limiting on login and 2FA endpoints
- Input validation on all system commands
- Dry-run mode for safe testing
- Per-user firewall mutex (threading locks)
- Command executor abstraction (no direct subprocess calls)

## Testing
- 240+ automated tests across 16 test files
- Test environment: Docker with DRY_RUN=true and DEMO_MODE=true
- Coverage: all API endpoints, proxy engine, security, validators, command executor
