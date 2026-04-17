# CLAUDE.md — MultiPanel Project Guide

## What is this project?

MultiPanel is a multi-protocol VPN and proxy management panel. It lets admins create users, assign them VPN connections (WireGuard) or proxy connections (VLESS, Trojan, Shadowsocks, HTTP, SOCKS), control their bandwidth/access, and route their traffic through different exit points.

**Core idea:** Users connect via **Inbounds** (how they reach your server) and their traffic exits via **Outbounds** (where it goes next — direct, another server, or blocked).

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy ORM, SQLite (WAL mode), APScheduler
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Zustand, React Router v6
- **System:** WireGuard (kernel), iptables, tc (traffic control), iproute2
- **Proxy Engines:** Xray-core and sing-box (both supported via abstraction layer)
- **Auth:** JWT (python-jose), bcrypt (passlib), email-based 2FA
- **Testing:** pytest (240+ tests), Docker for test environment

## Project Structure

```
backend/
  app/
    api/           # FastAPI route handlers (auth, users, inbounds, outbounds, etc.)
    core/          # Security, validators, command_executor, rate_limiter
    models/        # SQLAlchemy ORM models (User, Inbound, Outbound, ProxyUser, Admin, etc.)
    schemas/       # Pydantic request/response schemas
    services/      # Business logic (wireguard, proxy_engine/, iptables, bandwidth, sessions)
  tests/           # pytest test files (16 files, 240+ tests)
frontend/
  src/
    pages/         # React pages (14 lazy-loaded)
    components/    # Shared components (ErrorBoundary, layout, user-detail tabs)
    api/           # Axios client with auth interceptors
    stores/        # Zustand auth store
    lib/           # Utilities (formatBytes, formatDate, etc.)
docs/              # Architecture, install guide, user guide (MD + PDF)
```

## Key Design Decisions

### 1. CommandExecutor abstraction (Dry-Run Mode)
**Decision:** All subprocess calls (iptables, wg, tc, ip, systemctl) go through `app/core/command_executor.py` instead of calling `subprocess.run` directly.
**Why:** Only one VPS exists. We needed a way to test changes without affecting production. With `DRY_RUN=true`, write commands are logged but not executed; read-only commands still run.
**Impact:** Every service file (`iptables.py`, `wireguard.py`, `traffic_control.py`, `destination_vpn.py`) routes through `run_command()`.

### 2. WireGuard stays separate from Xray/sing-box
**Decision:** WireGuard uses native kernel module directly. Proxy protocols use Xray-core or sing-box.
**Why:** Kernel WireGuard is faster than userspace. Mixing them in one engine adds risk with no performance benefit. Migration can happen later if needed.

### 3. ProxyEngine abstraction (Xray + sing-box)
**Decision:** Abstract base class `ProxyEngine` with `XrayEngine` and `SingboxEngine` implementations.
**Why:** User wanted flexibility to use either engine. The abstraction layer means zero performance overhead (just an if/else), and you can run different engines on different servers.

### 4. Per-user firewall mutex
**Decision:** `sync_firewall.py` uses per-user `threading.Lock` before modifying iptables chains.
**Why:** Two concurrent API requests (e.g., add whitelist + remove blacklist) could corrupt iptables chains. The lock prevents race conditions while allowing different users' rules to be modified in parallel.

### 5. 2FA codes hashed in DB
**Decision:** 2FA verification codes are bcrypt-hashed before storing, verified with `verify_password()`.
**Why:** If DB is compromised, plaintext codes would allow bypassing 2FA. Hashing makes them useless to attackers.

## Critical Bugs Found & Fixed

### Bug 1: Alerts never sent (async/sync mismatch)
**Problem:** `send_email_alert()` and `send_telegram_alert()` were `async` but called from APScheduler's sync context. Coroutines were created but never awaited.
**Fix:** Added `_run_async()` wrapper that creates a new event loop per call (`asyncio.new_event_loop()`). Located in `services/alert_service.py`.

### Bug 2: Firewall race condition
**Problem:** `sync_user_firewall()` had no locking. Concurrent requests could half-flush iptables chains, dropping user connectivity.
**Fix:** Per-user `threading.Lock` in `services/sync_firewall.py`. Lock is acquired before reading DB state and released after all iptables commands complete.

### Bug 3: Disabled admin token still valid
**Problem:** Admin model had no `enabled` field. A disabled admin could use their existing JWT until expiry.
**Fix:** Added `enabled` field to Admin model + check in `get_current_admin()` (deps.py). Also checks at login time.

### Bug 4: 2FA enable without password confirmation
**Problem:** Anyone with a valid token could change the 2FA email to their own, hijacking future codes.
**Fix:** `Enable2FARequest` now requires `password` field. Verified before changing email.

## Build, Test, Deploy

### Local testing (Docker)
```bash
# Build and start
docker compose -f docker-compose.test.yml build
docker compose -f docker-compose.test.yml up -d

# Run tests
docker exec vpn-panel-test python -m pytest tests/ -v

# Access panel
open http://localhost:8888/vpn/
# Login: admin / admin
```

### Production deploy
```bash
cp .env.example .env
# Edit .env: set SECRET_KEY, ADMIN_PASSWORD, ENCRYPTION_KEY, WG_SERVER_IP
docker compose up -d
# Access: http://server-ip:8080/vpn/
```

### Running tests in batches (if OOM)
The test container runs background services that consume memory. If tests get killed:
```bash
docker exec vpn-panel-test python -m pytest tests/test_auth.py tests/test_users.py tests/test_rbac.py -v
docker restart vpn-panel-test
docker exec vpn-panel-test python -m pytest tests/test_proxy_engine.py tests/test_outbounds.py -v
```

## Gotchas

### Never touch production VPS without permission
All work is done locally with Docker. The `DRY_RUN=true` flag in test environment prevents accidental system command execution. Production VPS is off-limits unless explicitly authorized.

### Password minimum is 12 characters
Changed from 6 to 12. Tests that create admins or change passwords must use 12+ char passwords. The `conftest.py` fixture uses `testpass123` (11 chars) which works because it's set via `hash_password()` directly, not through the API validation.

### SQLite + background services = memory pressure
The test container runs uvicorn + APScheduler + blocked_logger + connection_logger. These background threads consume memory. If Docker kills the container, run tests in smaller batches.

### `blocked_logger` spams errors in Docker
`blocked_logger.py` tries to run `journalctl` which doesn't exist in the container. It retries every 2 seconds, filling logs with warnings. This is expected in the test environment and doesn't affect functionality.

### Config generation vs runtime management
Currently, Xray/sing-box configs are **generated** (JSON files). Runtime user add/remove via gRPC API is not yet implemented — changes require config regeneration + service reload.

### `_normalize_address` lives in blacklist.py
`whitelist.py` imports `_normalize_address` from `blacklist.py`. This is a known cross-dependency. If refactoring, move it to `core/address_utils.py`.

### Timezone is browser-default now
`formatDate()` in `frontend/src/lib/utils.ts` uses `Intl.DateTimeFormat().resolvedOptions().timeZone` instead of the previously hardcoded `America/Toronto`. Users can override via `localStorage.setItem('panel_timezone', 'Asia/Tehran')`.

### Default route recovery uses cached route
`destination_vpn.py` `ensure_ssh_protection()` caches the default route at first call and uses it for recovery. Previously it was hardcoded to `216.250.112.1 dev ens6`. If the server has no default route at startup, recovery won't work.
