from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.user import User
from app.models.connection_log import ConnectionLog
from app.models.bandwidth import BandwidthHistory
from app.schemas.log import ConnectionLogResponse, LogListResponse, BandwidthHistoryResponse
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogListResponse)
def list_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: int | None = None,
    dest_ip: str | None = None,
    dest_hostname: str | None = None,
    protocol: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("logs.view")),
):
    query = db.query(ConnectionLog)

    if user_id:
        query = query.filter(ConnectionLog.user_id == user_id)
    if dest_ip:
        query = query.filter(ConnectionLog.dest_ip.like(f"%{dest_ip}%"))
    if dest_hostname:
        query = query.filter(ConnectionLog.dest_hostname.like(f"%{dest_hostname}%"))
    if protocol:
        query = query.filter(ConnectionLog.protocol == protocol)
    if date_from:
        query = query.filter(ConnectionLog.started_at >= date_from)
    if date_to:
        query = query.filter(ConnectionLog.started_at <= date_to)

    total = query.count()
    logs = query.order_by(ConnectionLog.started_at.desc()).offset(skip).limit(limit).all()

    # Enrich with username
    user_ids = {log.user_id for log in logs if log.user_id}
    users = {u.id: u.username for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    return LogListResponse(
        logs=[
            ConnectionLogResponse(
                id=log.id,
                user_id=log.user_id,
                username=users.get(log.user_id),
                source_ip=log.source_ip,
                dest_ip=log.dest_ip,
                dest_hostname=log.dest_hostname,
                dest_port=log.dest_port,
                protocol=log.protocol,
                bytes_sent=log.bytes_sent,
                bytes_received=log.bytes_received,
                started_at=log.started_at,
                ended_at=log.ended_at,
            )
            for log in logs
        ],
        total=total,
    )


@router.get("/users/{user_id}", response_model=LogListResponse)
def list_user_logs(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("logs.view")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    query = db.query(ConnectionLog).filter(ConnectionLog.user_id == user_id)
    total = query.count()
    logs = query.order_by(ConnectionLog.started_at.desc()).offset(skip).limit(limit).all()

    return LogListResponse(
        logs=[
            ConnectionLogResponse(
                id=log.id,
                user_id=log.user_id,
                username=user.username,
                source_ip=log.source_ip,
                dest_ip=log.dest_ip,
                dest_hostname=log.dest_hostname,
                dest_port=log.dest_port,
                protocol=log.protocol,
                bytes_sent=log.bytes_sent,
                bytes_received=log.bytes_received,
                started_at=log.started_at,
                ended_at=log.ended_at,
            )
            for log in logs
        ],
        total=total,
    )


@router.get("/users/{user_id}/bandwidth-history", response_model=list[BandwidthHistoryResponse])
def get_bandwidth_history(
    user_id: int,
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("logs.view")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    from datetime import timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    history = db.query(BandwidthHistory).filter(
        BandwidthHistory.user_id == user_id,
        BandwidthHistory.timestamp >= since,
    ).order_by(BandwidthHistory.timestamp.asc()).all()

    return [
        BandwidthHistoryResponse(
            timestamp=h.timestamp,
            bytes_up=h.bytes_up,
            bytes_down=h.bytes_down,
        )
        for h in history
    ]
