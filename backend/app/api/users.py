import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.user import User
from app.models.admin import Admin
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserConfigResponse, UserConfigUpdate, UserListResponse
from app.core.security import encrypt_key
from app.core.exceptions import NotFoundError, ConflictError
from app.services import wireguard
from app.services.qr_generator import generate_qr_base64
from app.services.audit_logger import log_action
from app.models.user_session import UserSession
from app.models.connection_log import ConnectionLog
from app.models.blocked_request import BlockedRequest
from app.schemas.session import UserSessionResponse, SessionListResponse
from app.schemas.visited import VisitedDestination, VisitedListResponse
from app.schemas.blocked_request import BlockedRequestResponse, BlockedRequestListResponse
from sqlalchemy import func

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_to_response(user: User, peers_status: list[dict] | None = None) -> UserResponse:
    is_online = False
    sessions_count = 0
    if peers_status:
        for peer in peers_status:
            if peer["public_key"] == user.wg_public_key:
                # Online if handshake within last 3 minutes
                if peer["latest_handshake"] and (
                    datetime.now(timezone.utc).timestamp() - peer["latest_handshake"] < 180
                ):
                    is_online = True
                    sessions_count = 1
                break

    dest_name = None
    if user.destination_vpn:
        dest_name = user.destination_vpn.name

    pkg_name = None
    if user.package:
        pkg_name = user.package.name

    return UserResponse(
        id=user.id,
        username=user.username,
        note=user.note,
        enabled=user.enabled,
        destination_vpn_id=user.destination_vpn_id,
        destination_vpn_name=dest_name,
        package_id=user.package_id,
        package_name=pkg_name,
        assigned_ip=user.assigned_ip,
        bandwidth_limit_up=user.bandwidth_limit_up,
        bandwidth_limit_down=user.bandwidth_limit_down,
        bandwidth_used_up=user.bandwidth_used_up,
        bandwidth_used_down=user.bandwidth_used_down,
        speed_limit_up=user.speed_limit_up,
        speed_limit_down=user.speed_limit_down,
        max_connections=user.max_connections,
        expiry_date=user.expiry_date,
        alert_enabled=user.alert_enabled,
        alert_threshold=user.alert_threshold,
        telegram_username=user.telegram_username,
        telegram_link_code=user.telegram_link_code,
        is_online=is_online,
        active_sessions_count=sessions_count,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=UserListResponse)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str = Query("", max_length=100),
    enabled: bool | None = None,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.view")),
):
    query = db.query(User)
    if search:
        query = query.filter(User.username.ilike(f"%{search}%"))
    if enabled is not None:
        query = query.filter(User.enabled == enabled)

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    peers = wireguard.get_peers_status()
    return UserListResponse(
        users=[_user_to_response(u, peers) for u in users],
        total=total,
    )


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    req: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.create")),
):
    if db.query(User).filter(User.username == req.username).first():
        raise ConflictError("Username already exists")

    private_key, public_key = wireguard.generate_keypair()
    preshared_key = wireguard.generate_preshared_key()
    assigned_ip = wireguard.get_next_available_ip(db)

    user = User(
        username=req.username,
        note=req.note,
        destination_vpn_id=req.destination_vpn_id,
        package_id=req.package_id,
        wg_private_key=encrypt_key(private_key),
        wg_public_key=public_key,
        wg_preshared_key=encrypt_key(preshared_key),
        assigned_ip=assigned_ip,
        bandwidth_limit_up=req.bandwidth_limit_up,
        bandwidth_limit_down=req.bandwidth_limit_down,
        speed_limit_up=req.speed_limit_up,
        speed_limit_down=req.speed_limit_down,
        max_connections=req.max_connections,
        expiry_date=req.expiry_date,
        alert_enabled=req.alert_enabled,
        alert_threshold=req.alert_threshold,
        telegram_link_code=secrets.token_urlsafe(12),
    )
    db.add(user)
    log_action(db, _admin, "create_user", "user", details=f"Created user {req.username}",
               ip_address=request.client.host if request.client else None,
               user_agent=request.headers.get("user-agent"))
    db.commit()
    db.refresh(user)

    # Add peer to WireGuard
    try:
        wireguard.add_peer(user)
    except RuntimeError:
        pass  # WireGuard may not be running in dev

    return _user_to_response(user)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.view")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    peers = wireguard.get_peers_status()
    return _user_to_response(user, peers)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    if req.username and req.username != user.username:
        existing = db.query(User).filter(User.username == req.username).first()
        if existing:
            raise ConflictError("Username already exists")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return _user_to_response(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.delete")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    try:
        wireguard.remove_peer(user.wg_public_key)
    except RuntimeError:
        pass

    log_action(db, _admin, "delete_user", "user", resource_id=user_id,
               details=f"Deleted user {user.username}",
               ip_address=request.client.host if request.client else None,
               user_agent=request.headers.get("user-agent"))
    db.delete(user)
    db.commit()


@router.post("/{user_id}/toggle", response_model=UserResponse)
def toggle_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    user.enabled = not user.enabled
    log_action(db, _admin, "toggle_user", "user", resource_id=user_id,
               details=f"{'Enabled' if user.enabled else 'Disabled'} user {user.username}",
               ip_address=request.client.host if request.client else None,
               user_agent=request.headers.get("user-agent"))
    if user.enabled:
        try:
            wireguard.add_peer(user)
        except RuntimeError:
            pass
    else:
        try:
            wireguard.remove_peer(user.wg_public_key)
        except RuntimeError:
            pass

    db.commit()
    db.refresh(user)
    return _user_to_response(user)


@router.post("/{user_id}/reset-bandwidth", response_model=UserResponse)
def reset_bandwidth(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    user.bandwidth_used_up = 0
    user.bandwidth_used_down = 0
    user.alert_sent = False
    db.commit()
    db.refresh(user)
    return _user_to_response(user)


@router.get("/{user_id}/config", response_model=UserConfigResponse)
def get_user_config(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.view")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    from app.config import settings as app_settings
    config_text = wireguard.generate_client_config(user)
    qr_base64 = generate_qr_base64(config_text)

    return UserConfigResponse(
        config_text=config_text,
        qr_code_base64=qr_base64,
        dns=user.config_dns or app_settings.wg_dns,
        allowed_ips=user.config_allowed_ips or "0.0.0.0/0, ::/0",
        endpoint=user.config_endpoint or f"{app_settings.wg_server_ip}:{app_settings.wg_port}",
        mtu=user.config_mtu,
        persistent_keepalive=user.config_keepalive if user.config_keepalive is not None else 25,
    )


@router.get("/{user_id}/sessions", response_model=SessionListResponse)
def list_user_sessions(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.view")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    query = db.query(UserSession).filter(UserSession.user_id == user_id)
    total = query.count()
    sessions = query.order_by(UserSession.connected_at.desc()).offset(skip).limit(limit).all()

    result = []
    for s in sessions:
        duration = None
        if s.disconnected_at and s.connected_at:
            duration = int((s.disconnected_at - s.connected_at).total_seconds())
        resp = UserSessionResponse.model_validate(s)
        resp.duration_seconds = duration
        result.append(resp)

    return SessionListResponse(sessions=result, total=total)


@router.get("/{user_id}/sessions/{session_id}/visited", response_model=VisitedListResponse)
def list_session_visited(
    user_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.view")),
):
    """List visited destinations during a specific session."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")
    session_obj = db.query(UserSession).filter(
        UserSession.id == session_id, UserSession.user_id == user_id
    ).first()
    if not session_obj:
        raise NotFoundError("Session")

    query = db.query(
        ConnectionLog.dest_ip,
        ConnectionLog.dest_hostname,
        func.count().label("count"),
        func.max(ConnectionLog.started_at).label("last_seen"),
    ).filter(
        ConnectionLog.user_id == user_id,
        ConnectionLog.started_at >= session_obj.connected_at,
    )
    if session_obj.disconnected_at:
        query = query.filter(ConnectionLog.started_at <= session_obj.disconnected_at)

    rows = query.group_by(
        ConnectionLog.dest_ip, ConnectionLog.dest_hostname
    ).order_by(func.count().desc()).limit(200).all()

    # Deduplicate by hostname
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


@router.get("/{user_id}/sessions/{session_id}/blocked", response_model=BlockedRequestListResponse)
def list_session_blocked(
    user_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.view")),
):
    """List blocked requests during a specific session."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")
    session_obj = db.query(UserSession).filter(
        UserSession.id == session_id, UserSession.user_id == user_id
    ).first()
    if not session_obj:
        raise NotFoundError("Session")

    query = db.query(BlockedRequest).filter(
        BlockedRequest.user_id == user_id,
        BlockedRequest.first_seen >= session_obj.connected_at,
    )
    if session_obj.disconnected_at:
        query = query.filter(BlockedRequest.first_seen <= session_obj.disconnected_at)

    blocked = query.order_by(BlockedRequest.count.desc()).limit(200).all()

    return BlockedRequestListResponse(
        blocked=[BlockedRequestResponse.model_validate(b) for b in blocked],
        total=len(blocked),
    )


@router.put("/{user_id}/config", response_model=UserConfigResponse)
def update_user_config(
    user_id: int,
    req: UserConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    """Update a user's WireGuard config (DNS, AllowedIPs, etc.)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    # Update allowed fields
    if req.dns is not None:
        user.config_dns = req.dns
    if req.allowed_ips is not None:
        user.config_allowed_ips = req.allowed_ips
    if req.endpoint is not None:
        user.config_endpoint = req.endpoint
    if req.mtu is not None:
        user.config_mtu = req.mtu
    if req.persistent_keepalive is not None:
        user.config_keepalive = req.persistent_keepalive

    log_action(db, _admin, "update_config", "user", resource_id=user_id,
               details=f"Updated config for user {user.username}",
               ip_address=request.client.host if request.client else None,
               user_agent=request.headers.get("user-agent"))
    db.commit()
    db.refresh(user)

    config_text = wireguard.generate_client_config(user)
    qr_base64 = generate_qr_base64(config_text)
    return UserConfigResponse(config_text=config_text, qr_code_base64=qr_base64)
