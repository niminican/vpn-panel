from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.user import User
from app.models.blacklist import UserBlacklist
from app.models.whitelist import UserWhitelist
from app.schemas.blacklist import BlacklistCreate, BlacklistResponse
from app.core.exceptions import NotFoundError
from app.services.iptables import setup_user_blacklist, remove_user_blacklist

router = APIRouter(prefix="/api/users/{user_id}/blacklist", tags=["blacklist"])


def _sync_blacklist_rules(user: User, db: Session):
    """Sync iptables blacklist rules for a user."""
    bl_entries = db.query(UserBlacklist).filter(UserBlacklist.user_id == user.id).all()
    wl_entries = db.query(UserWhitelist).filter(UserWhitelist.user_id == user.id).all()

    if bl_entries:
        bl_rules = [
            {"address": e.address, "port": e.port, "protocol": e.protocol}
            for e in bl_entries
        ]
        wl_rules = [
            {"address": e.address, "port": e.port, "protocol": e.protocol}
            for e in wl_entries
        ]
        try:
            setup_user_blacklist(user.id, user.assigned_ip, bl_rules, wl_rules)
        except Exception:
            pass
    else:
        try:
            remove_user_blacklist(user.id, user.assigned_ip)
        except Exception:
            pass


@router.get("", response_model=list[BlacklistResponse])
def list_blacklist(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")
    return db.query(UserBlacklist).filter(UserBlacklist.user_id == user_id).all()


@router.post("", response_model=BlacklistResponse, status_code=201)
def add_blacklist_entry(
    user_id: int,
    req: BlacklistCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    entry = UserBlacklist(
        user_id=user_id,
        address=req.address,
        port=req.port,
        protocol=req.protocol,
        description=req.description,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _sync_blacklist_rules(user, db)
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_blacklist_entry(
    user_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    entry = db.query(UserBlacklist).filter(
        UserBlacklist.id == entry_id,
        UserBlacklist.user_id == user_id,
    ).first()
    if not entry:
        raise NotFoundError("Blacklist entry")

    db.delete(entry)
    db.commit()

    _sync_blacklist_rules(user, db)
