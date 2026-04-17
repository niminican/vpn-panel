import random
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.schemas.auth import (
    LoginRequest, LoginResponse, TokenResponse, RefreshRequest,
    ChangePasswordRequest, Verify2FARequest, Enable2FARequest, Disable2FARequest,
)
from app.core.security import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import AuthenticationError
from app.core.rate_limiter import login_limiter
from app.services.audit_logger import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

TWO_FACTOR_CODE_EXPIRY = timedelta(minutes=5)


def _get_client_info(request: Request) -> tuple[str, str | None]:
    """Extract client IP and User-Agent from request."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")
    return client_ip, user_agent


def _generate_2fa_code() -> str:
    """Generate a 6-digit verification code."""
    return f"{random.randint(100000, 999999)}"


def _send_2fa_email(email: str, code: str):
    """Send 2FA verification code via email."""
    from app.services.alert_service import send_email_alert, _run_async
    try:
        _run_async(send_email_alert(
            email,
            "VPN Panel - Verification Code",
            f"Your login verification code is: {code}\n\nThis code expires in 5 minutes.",
        ))
    except Exception as e:
        logger.error(f"Failed to send 2FA email to {email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification email")


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip, user_agent = _get_client_info(request)

    # Check rate limit
    if login_limiter.is_locked(client_ip):
        remaining = login_limiter.remaining_lockout(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {remaining} seconds.",
        )

    admin = db.query(Admin).filter(Admin.username == req.username).first()
    if not admin or not verify_password(req.password, admin.password_hash):
        login_limiter.record_failure(client_ip)
        raise AuthenticationError()

    if not admin.enabled:
        raise AuthenticationError()

    login_limiter.record_success(client_ip)

    # Check if 2FA is enabled
    if admin.two_factor_enabled and admin.two_factor_email:
        code = _generate_2fa_code()
        admin.two_factor_code = hash_password(code)
        admin.two_factor_code_expires = datetime.now(timezone.utc) + TWO_FACTOR_CODE_EXPIRY
        db.commit()

        _send_2fa_email(admin.two_factor_email, code)
        logger.info(f"2FA code sent to {admin.two_factor_email} for {admin.username}")

        return LoginResponse(requires_2fa=True)

    # No 2FA — issue tokens directly
    log_action(
        db, admin, "login",
        details=f"Admin {admin.username} logged in",
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()

    token_data = {"sub": admin.username, "role": admin.role}
    return LoginResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/verify-2fa", response_model=TokenResponse)
def verify_2fa(req: Verify2FARequest, request: Request, db: Session = Depends(get_db)):
    """Verify 2FA code and return tokens."""
    client_ip, user_agent = _get_client_info(request)

    if login_limiter.is_locked(client_ip):
        remaining = login_limiter.remaining_lockout(client_ip)
        raise HTTPException(status_code=429, detail=f"Try again in {remaining} seconds.")

    admin = db.query(Admin).filter(Admin.username == req.username).first()
    if not admin or not admin.two_factor_enabled:
        login_limiter.record_failure(client_ip)
        raise AuthenticationError()

    # Check code validity
    if (
        not admin.two_factor_code
        or not verify_password(req.code, admin.two_factor_code)
        or not admin.two_factor_code_expires
        or datetime.now(timezone.utc) > admin.two_factor_code_expires.replace(tzinfo=timezone.utc)
    ):
        login_limiter.record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid or expired verification code")

    # Clear the code
    admin.two_factor_code = None
    admin.two_factor_code_expires = None

    log_action(
        db, admin, "login",
        details=f"Admin {admin.username} logged in (2FA verified)",
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()

    token_data = {"sub": admin.username, "role": admin.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise AuthenticationError()

    token_data = {"sub": payload["sub"], "role": payload.get("role", "super_admin")}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    if not verify_password(req.current_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(req.new_password) < 12:
        raise HTTPException(status_code=400, detail="New password must be at least 12 characters")

    client_ip, user_agent = _get_client_info(request)
    admin.password_hash = hash_password(req.new_password)
    log_action(
        db, admin, "change_password", "admin",
        resource_id=admin.id,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    return {"message": "Password changed successfully"}


@router.post("/2fa/enable")
def enable_2fa(
    req: Enable2FARequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    """Enable 2FA for the current admin. Requires password confirmation."""
    if not verify_password(req.password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect password")

    admin.two_factor_email = req.email
    admin.two_factor_enabled = True
    db.commit()
    return {"message": f"2FA enabled. Verification codes will be sent to {req.email}"}


@router.post("/2fa/disable")
def disable_2fa(
    req: Disable2FARequest,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    """Disable 2FA for the current admin. Requires password confirmation."""
    if not verify_password(req.password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect password")

    admin.two_factor_enabled = False
    admin.two_factor_email = None
    admin.two_factor_code = None
    admin.two_factor_code_expires = None
    db.commit()
    return {"message": "2FA disabled"}


@router.get("/2fa/status")
def get_2fa_status(admin: Admin = Depends(get_current_admin)):
    """Get current 2FA status for the logged-in admin."""
    return {
        "two_factor_enabled": admin.two_factor_enabled,
        "two_factor_email": admin.two_factor_email,
    }
