# Changelog

All notable changes to VPN Panel will be documented in this file.

## [1.3.0] - 2026-04-05 (v0.1)

### Added
- **Session enrichment with GeoIP**: Sessions now show country, city, ISP, and ASN using MaxMind GeoLite2 databases. Country flags displayed via emoji.
- **OS detection via TTL fingerprinting**: Detects client OS (Windows, Linux/Android, macOS/iOS) by pinging the client's VPN IP and analyzing TTL values.
- **Destination start modes**: Three modes for each destination VPN:
  - **Manual**: Admin manually starts/stops (default)
  - **On-demand**: Auto-starts when users are assigned, auto-stops after 5 min idle (with chicken-egg protection)
  - **Auto-restart**: Automatically restarts if the destination goes down
- **Inline start mode selector**: Change start mode directly from destination cards without opening settings
- **PWA support**: Add to Home Screen on mobile devices with standalone display, custom icons, and app-like experience
- **Mobile responsive layout**: Sidebar becomes overlay drawer on mobile (<768px), compact headers, stacked cards, proper viewport handling (`100dvh`)
- **Per-user blacklist**: Block specific IP/CIDR ranges per user via iptables (complement to whitelist)
- **Sub-path deployment**: Panel can be served at `/vpn/` behind Nginx reverse proxy (coordinated base path across Vite, React Router, FastAPI root_path, and API client)
- **SSL/HTTPS support**: Nginx reverse proxy with Let's Encrypt SSL via Certbot
- **SSH protection**: `ensure_ssh_protection()` safeguards SSH access (port 22) and ESTABLISHED connections before any iptables/routing changes during destination start/stop
- **GeoIP database auto-download**: Downloads GeoLite2-City and GeoLite2-ASN databases from GitHub mirror on startup if missing
- New services: `geoip.py` (IP geolocation), `os_detect.py` (TTL-based OS detection)
- Start mode description text shown below destination cards for non-manual modes
- Toronto timezone support for schedules

### Changed
- **Sessions tab redesigned**: Changed from table layout to card-based layout with status badges, OS badges, country flags, ISP info, and traffic stats per session
- **Destination health check improved**: WireGuard destinations now check interface existence (not just handshake recency), making status more reliable
- **On-demand idle detection**: Uses `idle_since` database timestamp with 5-minute timeout instead of immediate stop, preventing chicken-egg problem
- FastAPI app now uses `root_path="/vpn"` for sub-path deployment
- CORS origins updated to include production domain
- Frontend uses dynamic `import.meta.env.BASE_URL` for API calls and routing
- Dashboard uses 2-column grid on mobile with smaller stat cards
- Login page optimized for mobile with `min-h-[100dvh]`

### Fixed
- **Server connectivity protection**: Destination VPN start/stop no longer risks breaking SSH access or default routes
- **Destination incorrectly showing stopped**: Fixed two bugs - health check using stale handshake data, and on-demand mode immediately stopping without idle grace period
- **AlertResponse schema**: `sent_at` field changed from `str` to `datetime` (was causing HTTP 500)
- **UserBlacklist import**: Added missing import in models `__init__.py`
- **Test suite stability**: Rate limiter now resets between tests; ENCRYPTION_KEY uses valid Fernet key
- **TypeScript `import.meta.env`**: Added Vite client type references
- **Health check endpoint 404**: Moved endpoint definition before static file catch-all mount

### Database Changes
- `destination_vpns`: Added `idle_since` (DateTime) column
- `user_sessions`: Added `country` (String), `country_code` (String), `city` (String), `isp` (String), `asn` (Integer), `os_hint` (String), `ttl` (Integer) columns

### Dependencies
- Added `geoip2>=4.8.0,<5.0.0` for MaxMind GeoIP lookups

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
