from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_token
from app.core.exceptions import AuthenticationError
from app.models.admin import Admin


def get_current_admin(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> Admin:
    if not authorization.startswith("Bearer "):
        raise AuthenticationError()

    token = authorization[7:]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise AuthenticationError()

    admin = db.query(Admin).filter(Admin.username == payload.get("sub")).first()
    if not admin:
        raise AuthenticationError()

    if not admin.enabled:
        raise AuthenticationError()

    return admin


def require_permission(permission: str):
    """Dependency factory that checks if the current admin has a specific permission.
    Super admins always have all permissions.
    """
    def checker(admin: Admin = Depends(get_current_admin)) -> Admin:
        if not admin.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission} required",
            )
        return admin
    return checker
