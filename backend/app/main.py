import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import *  # noqa: F401, F403 - ensure all models are registered
from app.models.admin import Admin
from app.core.security import hash_password
from app.api import auth, users, destinations, dashboard, whitelist, blacklist, schedules, logs, alerts, packages, admins
from app.api import settings as settings_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting VPN Panel...")
    from app.config import check_security_defaults
    check_security_defaults()
    Base.metadata.create_all(bind=engine)
    _create_default_admin()

    # Start background services
    _start_services()

    yield

    # Shutdown
    _stop_services()
    logger.info("VPN Panel stopped")


def _create_default_admin():
    db = SessionLocal()
    try:
        if not db.query(Admin).first():
            admin = Admin(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role="super_admin",
            )
            db.add(admin)
            db.commit()
            logger.info(f"Created default admin: {settings.admin_username}")
    finally:
        db.close()


def _start_services():
    """Start background services: scheduler, connection logger, tc, telegram."""
    # ── Safety first: ensure SSH is always protected ──
    try:
        from app.services.destination_vpn import ensure_ssh_protection
        ensure_ssh_protection()
        logger.info("SSH protection rules verified")
    except Exception as e:
        logger.warning(f"SSH protection setup failed: {e}")

    # Start scheduler (bandwidth polling, alerts, health checks)
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler start failed (non-critical): {e}")

    # Initialize traffic control
    try:
        from app.services.traffic_control import rebuild_all
        db = SessionLocal()
        rebuild_all(db)
        db.close()
    except Exception as e:
        logger.warning(f"Traffic control init failed (non-critical): {e}")

    # Start connection logger
    try:
        from app.services.connection_logger import start
        start()
    except Exception as e:
        logger.warning(f"Connection logger start failed (non-critical): {e}")

    # Initialize connection logging iptables rules
    try:
        from app.services.iptables import initialize_logging_for_all
        db = SessionLocal()
        initialize_logging_for_all(db)
        db.close()
    except Exception as e:
        logger.warning(f"iptables logging init failed (non-critical): {e}")


def _stop_services():
    """Stop background services."""
    try:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    try:
        from app.services.connection_logger import stop
        stop()
    except Exception:
        pass

    try:
        from app.services.traffic_control import cleanup
        cleanup()
    except Exception:
        pass


app = FastAPI(
    title="VPN Panel",
    version="1.2.0",
    lifespan=lifespan,
    root_path="/vpn",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.panel_port}",
        f"http://127.0.0.1:{settings.panel_port}",
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "https://mafia.namiravaei.com",
        "http://mafia.namiravaei.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# API routes
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(destinations.router)
app.include_router(dashboard.router)
app.include_router(whitelist.router)
app.include_router(blacklist.router)
app.include_router(schedules.router)
app.include_router(logs.router)
app.include_router(alerts.router)
app.include_router(packages.router)
app.include_router(settings_api.router)
app.include_router(admins.router)

# Telegram bot webhook
try:
    from app.telegram.bot import webhook_router, create_bot
    create_bot()
    app.include_router(webhook_router)
except Exception as e:
    logger.warning(f"Telegram bot setup failed: {e}")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

# Serve frontend static files (production) — must be LAST (catch-all)
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
