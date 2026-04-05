import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.user import User
from app.models.blacklist import UserBlacklist
from app.models.whitelist import UserWhitelist
from app.models.blocked_request import BlockedRequest
from app.schemas.blacklist import BlacklistCreate, BlacklistResponse
from app.schemas.blocked_request import BlockedRequestResponse, BlockedRequestListResponse
from app.core.exceptions import NotFoundError
from app.services.iptables import setup_user_blacklist, remove_user_blacklist
from app.services.sync_firewall import sync_user_firewall

router = APIRouter(prefix="/api/users/{user_id}/blacklist", tags=["blacklist"])


def _normalize_address(addr: str) -> str:
    """Normalize address: strip URL scheme and trailing path, keep domain or IP/CIDR."""
    import ipaddress
    addr = addr.strip()
    if addr == "*":
        return addr
    # Strip URL scheme
    for prefix in ("https://", "http://"):
        if addr.lower().startswith(prefix):
            addr = addr[len(prefix):]
    # Strip trailing slash/path (but not CIDR mask)
    try:
        ipaddress.ip_network(addr, strict=False)
        return addr  # Valid CIDR, keep as-is
    except ValueError:
        pass
    # Not CIDR - strip path
    addr = addr.split("/")[0]
    return addr


def _sync_blacklist_rules(user: User, db: Session):
    """Sync all firewall rules for a user (centralized)."""
    sync_user_firewall(user, db)


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

    # Normalize address: strip URL scheme/path, keep domain or IP
    clean_address = _normalize_address(req.address)

    entry = UserBlacklist(
        user_id=user_id,
        address=clean_address,
        port=req.port,
        protocol=req.protocol,
        description=req.description,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _sync_blacklist_rules(user, db)
    return entry


# ── Blocked requests (must be before /{entry_id} to avoid route conflict) ──

@router.get("/blocked", response_model=BlockedRequestListResponse)
def list_blocked_requests(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    """List blocked requests for a user (sorted by count desc)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    query = db.query(BlockedRequest).filter(BlockedRequest.user_id == user_id)
    total = query.count()
    blocked = query.order_by(BlockedRequest.count.desc()).offset(skip).limit(limit).all()

    return BlockedRequestListResponse(
        blocked=[BlockedRequestResponse.model_validate(b) for b in blocked],
        total=total,
    )


@router.delete("/blocked", status_code=204)
def clear_blocked_requests(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    """Clear all blocked requests for a user."""
    db.query(BlockedRequest).filter(BlockedRequest.user_id == user_id).delete()
    db.commit()


@router.delete("/blocked/{entry_id}", status_code=204)
def delete_blocked_request(
    user_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    """Delete a single blocked request entry."""
    entry = db.query(BlockedRequest).filter(
        BlockedRequest.id == entry_id,
        BlockedRequest.user_id == user_id,
    ).first()
    if not entry:
        raise NotFoundError("Blocked request entry")
    db.delete(entry)
    db.commit()


# ── Blacklist entry delete (after /blocked routes) ──

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
