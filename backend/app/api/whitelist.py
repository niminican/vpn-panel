from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.user import User
from app.models.whitelist import UserWhitelist
from app.models.connection_log import ConnectionLog
from app.schemas.whitelist import WhitelistCreate, WhitelistResponse
from app.schemas.visited import VisitedDestination, VisitedListResponse
from app.core.exceptions import NotFoundError
from app.services.sync_firewall import sync_user_firewall
from app.api.blacklist import _normalize_address

router = APIRouter(prefix="/api/users/{user_id}/whitelist", tags=["whitelist"])


def _sync_whitelist_rules(user: User, db: Session):
    """Sync all firewall rules for a user (centralized)."""
    sync_user_firewall(user, db)


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

    clean_address = _normalize_address(req.address)

    entry = UserWhitelist(
        user_id=user_id,
        address=clean_address,
        port=req.port,
        protocol=req.protocol,
        description=req.description,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    _sync_whitelist_rules(user, db)
    return entry


# ── Visited destinations (must be before /{entry_id}) ──

@router.get("/visited", response_model=VisitedListResponse)
def list_visited_destinations(
    user_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    """List unique destinations this user has visited (from connection logs)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    # Aggregate: group by dest_hostname (prefer) or dest_ip
    rows = (
        db.query(
            ConnectionLog.dest_ip,
            ConnectionLog.dest_hostname,
            func.count().label("count"),
            func.max(ConnectionLog.started_at).label("last_seen"),
        )
        .filter(ConnectionLog.user_id == user_id)
        .group_by(ConnectionLog.dest_ip, ConnectionLog.dest_hostname)
        .order_by(func.count().desc())
        .limit(limit)
        .all()
    )

    # Deduplicate by hostname: merge IPs with same hostname
    merged: dict[str, dict] = {}
    for row in rows:
        key = row.dest_hostname or row.dest_ip
        if key in merged:
            merged[key]["count"] += row.count
            if row.last_seen > merged[key]["last_seen"]:
                merged[key]["last_seen"] = row.last_seen
        else:
            merged[key] = {
                "dest_ip": row.dest_ip,
                "dest_hostname": row.dest_hostname,
                "count": row.count,
                "last_seen": row.last_seen,
            }

    visited = sorted(merged.values(), key=lambda x: x["count"], reverse=True)

    return VisitedListResponse(
        visited=[VisitedDestination(**v) for v in visited],
        total=len(visited),
    )


@router.delete("/visited", status_code=204)
def clear_visited_destinations(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    """Clear connection logs for a user."""
    db.query(ConnectionLog).filter(ConnectionLog.user_id == user_id).delete()
    db.commit()


@router.delete("/all", status_code=204)
def clear_whitelist(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    """Clear all whitelist entries for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")
    db.query(UserWhitelist).filter(UserWhitelist.user_id == user_id).delete()
    db.commit()
    _sync_whitelist_rules(user, db)


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
