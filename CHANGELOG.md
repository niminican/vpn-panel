# Changelog

All notable changes to VPN Panel will be documented in this file.

## [1.2.0] - 2026-04-03

### Added
- **Device & IP tracking for admin logins**: All admin audit logs now capture source IP address, raw User-Agent, and parsed device info (e.g., "iPhone (iOS 17.2) Safari")
- **Client IP tracking for VPN sessions**: Each VPN user session records the client IP extracted from WireGuard endpoint
- **User config editing**: Admins can now edit per-user WireGuard config settings (DNS, AllowedIPs, Endpoint, MTU, PersistentKeepalive) with overrides saved per user
- Device detection module (`core/device_detector.py`) that parses User-Agent strings into human-readable device descriptions
- IP Address and Device columns in Activity Log page
- Client IP and Endpoint columns in User Detail Sessions tab
- Config Edit form in User Detail Config tab with save functionality
- `PUT /api/users/{id}/config` API endpoint for updating user config overrides
- `update_config` action type in audit log filters

### Changed
- Admin CRUD operations (create/update/delete) now capture IP address and User-Agent in audit logs
- Audit log table expanded from 4 to 6 columns (added IP Address, Device)
- Sessions table expanded from 6 to 7 columns (added Client IP separate from Endpoint)
- User model extended with per-user config override columns (config_dns, config_allowed_ips, config_endpoint, config_mtu, config_keepalive)
- AdminAuditLog model extended with user_agent (Text) and device_info (String) columns
- UserSession model extended with client_ip (String) column
- `generate_client_config()` now uses per-user overrides with fallback to global settings

## [1.1.0] - 2026-04-03

### Security
- **CRITICAL**: Fixed command injection vulnerabilities - converted all `shell=True` subprocess calls to list format in iptables.py, traffic_control.py, and destinations.py
- Added input validation module (`validators.py`) for IPs, interface names, ports, protocols, and chain names
- Fixed Fernet encryption key fallback - now raises error for invalid keys instead of silently generating new ones
- Fixed temp file race condition in WireGuard PSK handling (uses `tempfile.NamedTemporaryFile` instead of predictable `/tmp/wg_psk_temp`)
- Added login rate limiting (5 failed attempts → 15 min lockout)
- Added security response headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy)
- Restricted CORS to localhost origins only (was `allow_origins=["*"]`)
- Added startup warnings for insecure default secrets (SECRET_KEY, ADMIN_PASSWORD, ENCRYPTION_KEY)

### Added
- **Multi-admin RBAC system**: Super admin and limited admin roles with 10 granular permissions (users.view/create/edit/delete, destinations.view/manage, logs.view, packages.manage, settings.manage, alerts.view)
- RBAC enforcement on all API endpoints via `require_permission()` dependency
- Admin management page (create/edit/delete admins, permission toggles)
- Activity audit log with filters (admin username, action type)
- User session history (connect/disconnect times, duration, bandwidth per session)
- Sessions tab in User Detail page
- DNS hostname resolution via passive DNS sniffer (tcpdump on wg0)
- Hostname column in connection logs
- Database cleanup service with configurable retention (connection_logs: 30d, bandwidth_history: 90d, audit_logs: 180d, sessions: 90d)
- Rate limiter module (`core/rate_limiter.py`)
- Comprehensive test suite (auth, users, RBAC, validators, security)
- Enhanced backup script with SQLite online backup support

### Changed
- All subprocess calls now use list format (no shell=True)
- iptables LOG rules always re-inserted at position 1 after destination VPN start
- Destination FORWARD ACCEPT rules use `-A` (append) instead of `-I 1` (insert)
- Auth store now passes through API errors (shows rate limit messages on login)
- API client handles 403 (permission denied) and 429 (rate limit) responses globally
- Frontend error handling improved across all pages (UserDetail, Alerts, etc.)

### Fixed
- iptables rule ordering broken after destination VPN start
- DNS reverse lookup timeouts (replaced `dig` with passive DNS sniffer)
- `subprocess` import missing in connection_logger causing NameError
- Swallowed errors in bandwidth_tracker now logged

## [1.0.0] - 2026-03-28

### Added
- Initial release
- User management with WireGuard integration (key gen, peer management, config/QR)
- Multi-destination VPN support (WireGuard + OpenVPN)
- Bandwidth tracking and speed/volume limits
- Per-user whitelist (iptables chains)
- Time-based access schedules
- Connection logging
- Alert system (bandwidth, expiry, VPN status)
- System monitoring (CPU, RAM, disk)
- Destination VPN health checks and speed tests
- Package management
- Settings page
- Telegram bot integration
- Docker Compose deployment
- Direct install script
