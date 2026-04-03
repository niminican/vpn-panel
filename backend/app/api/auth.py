from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, ChangePasswordRequest
from app.core.security import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import AuthenticationError
from app.core.rate_limiter import login_limiter
from app.services.audit_logger import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_client_info(request: Request) -> tuple[str, str | None]:
    """Extract client IP and User-Agent from request."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")
    return client_ip, user_agent


@router.post("/login", response_model=TokenResponse)
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

    login_limiter.record_success(client_ip)
    log_action(
        db, admin, "login",
        details=f"Admin {admin.username} logged in",
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

    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

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
