from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.user import User
from app.models.whitelist import UserWhitelist
from app.schemas.whitelist import WhitelistCreate, WhitelistResponse
from app.core.exceptions import NotFoundError
from app.services.iptables import setup_user_whitelist, remove_user_whitelist

router = APIRouter(prefix="/api/users/{user_id}/whitelist", tags=["whitelist"])


def _sync_whitelist_rules(user: User, db: Session):
    """Sync iptables whitelist rules for a user."""
    entries = db.query(UserWhitelist).filter(UserWhitelist.user_id == user.id).all()
    if entries:
        rules = [
            {"address": e.address, "port": e.port, "protocol": e.protocol}
            for e in entries
        ]
        try:
            setup_user_whitelist(user.id, user.assigned_ip, rules)
        except Exception:
            pass  # WireGuard/iptables may not be available in dev
    else:
        try:
            remove_user_whitelist(user.id, user.assigned_ip)
        except Exception:
            pass


@router.get("", response_model=list[WhitelistResponse])
def list_whitelist(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")
    return db.query(UserWhitelist).filter(UserWhitelist.user_id == user_id).all()


@router.post("", response_model=WhitelistResponse, status_code=201)
def add_whitelist_entry(
    user_id: int,
    req: WhitelistCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    entry = UserWhitelist(
        user_id=user_id,
        address=req.address,
        port=req.port,
        protocol=req.protocol,
        description=req.description,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _sync_whitelist_rules(user, db)
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_whitelist_entry(
    user_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    entry = db.query(UserWhitelist).filter(
        UserWhitelist.id == entry_id,
        UserWhitelist.user_id == user_id,
    ).first()
    if not entry:
        raise NotFoundError("Whitelist entry")

    db.delete(entry)
    db.commit()

    _sync_whitelist_rules(user, db)
