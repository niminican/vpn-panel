from fastapi import Depends, Header
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

    return admin
