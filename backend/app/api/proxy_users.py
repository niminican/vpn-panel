"""Proxy user management API — manage proxy accounts per user."""
import json
import logging
import uuid as uuid_lib
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.config import settings
from app.models.admin import Admin
from app.models.user import User
from app.models.inbound import Inbound
from app.models.proxy_user import ProxyUser
from app.schemas.proxy_user import ProxyUserCreate, ProxyUserResponse, ProxyUserConfigResponse
from app.core.exceptions import NotFoundError
from app.services.proxy_engine.share_links import generate_share_link

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users/{user_id}/proxy", tags=["proxy"])


def _to_response(pu: ProxyUser) -> ProxyUserResponse:
    return ProxyUserResponse(
        id=pu.id,
        user_id=pu.user_id,
        inbound_id=pu.inbound_id,
        uuid=pu.uuid,
        password=pu.password,
        email=pu.email,
        flow=pu.flow,
        method=pu.method,
        enabled=pu.enabled,
        traffic_up=pu.traffic_up,
        traffic_down=pu.traffic_down,
        traffic_limit=pu.traffic_limit,
        expire_date=pu.expire_date,
        created_at=pu.created_at,
        inbound_tag=pu.inbound.tag if pu.inbound else None,
        inbound_protocol=pu.inbound.protocol if pu.inbound else None,
        inbound_port=pu.inbound.port if pu.inbound else None,
    )


def _generate_credentials(protocol: str) -> tuple[str | None, str | None]:
    """Generate default credentials for a protocol."""
    if protocol in ("vless",):
        return str(uuid_lib.uuid4()), None
    elif protocol in ("trojan",):
        return None, secrets.token_urlsafe(24)
    elif protocol == "shadowsocks":
        return None, secrets.token_urlsafe(16)
    elif protocol in ("http", "socks"):
        return secrets.token_hex(8), secrets.token_urlsafe(16)
    return None, None


@router.get("", response_model=list[ProxyUserResponse])
def list_proxy_users(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.view")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    proxy_users = db.query(ProxyUser).filter(ProxyUser.user_id == user_id).all()
    return [_to_response(pu) for pu in proxy_users]


@router.post("", response_model=ProxyUserResponse, status_code=201)
def create_proxy_user(
    user_id: int,
    req: ProxyUserCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User")

    inbound = db.query(Inbound).filter(Inbound.id == req.inbound_id).first()
    if not inbound:
        raise NotFoundError("Inbound")

    # Generate credentials if not provided
    default_uuid, default_password = _generate_credentials(inbound.protocol)
    final_uuid = req.uuid or default_uuid
    final_password = req.password or default_password

    # Generate email for stats tracking
    email = f"{user.username}@{inbound.tag}"

    proxy_user = ProxyUser(
        user_id=user_id,
        inbound_id=req.inbound_id,
        uuid=final_uuid,
        password=final_password,
        email=email,
        flow=req.flow,
        method=req.method,
        traffic_limit=req.traffic_limit,
        expire_date=req.expire_date,
    )
    db.add(proxy_user)
    db.commit()
    db.refresh(proxy_user)

    logger.info(f"Created proxy account for {user.username} on {inbound.tag}")
    return _to_response(proxy_user)


@router.delete("/{proxy_id}", status_code=204)
def delete_proxy_user(
    user_id: int,
    proxy_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.delete")),
):
    proxy_user = db.query(ProxyUser).filter(
        ProxyUser.id == proxy_id,
        ProxyUser.user_id == user_id,
    ).first()
    if not proxy_user:
        raise NotFoundError("Proxy account")

    db.delete(proxy_user)
    db.commit()
    logger.info(f"Deleted proxy account {proxy_id} for user {user_id}")


@router.get("/{proxy_id}/config", response_model=ProxyUserConfigResponse)
def get_proxy_config(
    user_id: int,
    proxy_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.view")),
):
    proxy_user = db.query(ProxyUser).filter(
        ProxyUser.id == proxy_id,
        ProxyUser.user_id == user_id,
    ).first()
    if not proxy_user:
        raise NotFoundError("Proxy account")

    inbound = proxy_user.inbound
    user = proxy_user.user

    # Determine server host
    host = settings.wg_server_ip or "127.0.0.1"

    # Parse JSON settings
    transport_settings = json.loads(inbound.transport_settings or "{}")
    security_settings = json.loads(inbound.security_settings or "{}")

    link = generate_share_link(
        protocol=inbound.protocol,
        uuid=proxy_user.uuid,
        password=proxy_user.password,
        host=host,
        port=inbound.port,
        remark=f"{user.username}-{inbound.tag}",
        transport=inbound.transport,
        transport_settings=transport_settings,
        security=inbound.security,
        security_settings=security_settings,
        flow=proxy_user.flow,
        method=proxy_user.method,
    )

    return ProxyUserConfigResponse(
        share_link=link,
        protocol=inbound.protocol,
        remark=f"{user.username}-{inbound.tag}",
    )


@router.post("/{proxy_id}/toggle", response_model=ProxyUserResponse)
def toggle_proxy_user(
    user_id: int,
    proxy_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("users.edit")),
):
    proxy_user = db.query(ProxyUser).filter(
        ProxyUser.id == proxy_id,
        ProxyUser.user_id == user_id,
    ).first()
    if not proxy_user:
        raise NotFoundError("Proxy account")

    proxy_user.enabled = not proxy_user.enabled
    db.commit()
    db.refresh(proxy_user)
    return _to_response(proxy_user)
