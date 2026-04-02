import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.user import User
from app.models.admin import Admin
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserConfigResponse, UserListResponse
from app.core.security import encrypt_key
from app.core.exceptions import NotFoundError, ConflictError
from app.services import wireguard
from app.services.qr_generator import generate_qr_base64

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

    return UserResponse(
        id=user.id,
        username=user.username,
        note=user.note,
        enabled=user.enabled,
        destination_vpn_id=user.destination_vpn_id,
        destination_vpn_name=dest_name,
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
    _admin: Admin = Depends(get_current_admin),
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
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
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
    _admin: Admin = Depends(get_current_admin),
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
    _admin: Admin = Depends(get_current_admin),
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
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    try:
        wireguard.remove_peer(user.wg_public_key)
    except RuntimeError:
        pass

    db.delete(user)
    db.commit()


@router.post("/{user_id}/toggle", response_model=UserResponse)
def toggle_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    user.enabled = not user.enabled
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
    _admin: Admin = Depends(get_current_admin),
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
    _admin: Admin = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    config_text = wireguard.generate_client_config(user)
    qr_base64 = generate_qr_base64(config_text)

    return UserConfigResponse(
        config_text=config_text,
        qr_code_base64=qr_base64,
    )
