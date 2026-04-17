"""Inbound management API — CRUD for proxy inbounds (ports + protocols)."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.inbound import Inbound
from app.models.proxy_user import ProxyUser
from app.schemas.inbound import InboundCreate, InboundUpdate, InboundResponse
from app.core.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbounds", tags=["inbounds"])


def _to_response(inb: Inbound, db: Session) -> InboundResponse:
    user_count = db.query(ProxyUser).filter(
        ProxyUser.inbound_id == inb.id,
        ProxyUser.enabled == True,  # noqa: E712
    ).count()
    return InboundResponse(
        id=inb.id,
        tag=inb.tag,
        protocol=inb.protocol,
        port=inb.port,
        listen=inb.listen,
        transport=inb.transport,
        transport_settings=inb.transport_settings,
        security=inb.security,
        security_settings=inb.security_settings,
        engine=inb.engine,
        settings=inb.settings,
        enabled=inb.enabled,
        user_count=user_count,
        created_at=inb.created_at,
        updated_at=inb.updated_at,
    )


@router.get("", response_model=list[InboundResponse])
def list_inbounds(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.view")),
):
    inbounds = db.query(Inbound).order_by(Inbound.created_at.desc()).all()
    return [_to_response(inb, db) for inb in inbounds]


@router.post("", response_model=InboundResponse, status_code=201)
def create_inbound(
    req: InboundCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    # Validate unique tag
    if db.query(Inbound).filter(Inbound.tag == req.tag).first():
        raise ConflictError("Inbound tag already exists")

    # Validate protocol
    valid_protocols = {"vless", "trojan", "shadowsocks", "http", "socks"}
    if req.protocol not in valid_protocols:
        raise HTTPException(400, f"Invalid protocol. Must be one of: {valid_protocols}")

    # Validate engine
    if req.engine not in ("xray", "singbox"):
        raise HTTPException(400, "Engine must be 'xray' or 'singbox'")

    # Validate port
    if not 1 <= req.port <= 65535:
        raise HTTPException(400, "Port must be between 1 and 65535")

    # Check port not already used
    if db.query(Inbound).filter(Inbound.port == req.port).first():
        raise ConflictError("Port already in use by another inbound")

    inbound = Inbound(**req.model_dump())
    db.add(inbound)
    db.commit()
    db.refresh(inbound)

    logger.info(f"Created inbound: {inbound.tag} ({inbound.protocol}:{inbound.port})")
    return _to_response(inbound, db)


@router.get("/{inbound_id}", response_model=InboundResponse)
def get_inbound(
    inbound_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.view")),
):
    inbound = db.query(Inbound).filter(Inbound.id == inbound_id).first()
    if not inbound:
        raise NotFoundError("Inbound")
    return _to_response(inbound, db)


@router.put("/{inbound_id}", response_model=InboundResponse)
def update_inbound(
    inbound_id: int,
    req: InboundUpdate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    inbound = db.query(Inbound).filter(Inbound.id == inbound_id).first()
    if not inbound:
        raise NotFoundError("Inbound")

    update_data = req.model_dump(exclude_unset=True)

    if "tag" in update_data:
        existing = db.query(Inbound).filter(Inbound.tag == update_data["tag"], Inbound.id != inbound_id).first()
        if existing:
            raise ConflictError("Inbound tag already exists")

    if "port" in update_data:
        existing = db.query(Inbound).filter(Inbound.port == update_data["port"], Inbound.id != inbound_id).first()
        if existing:
            raise ConflictError("Port already in use")

    for key, value in update_data.items():
        setattr(inbound, key, value)

    db.commit()
    db.refresh(inbound)
    return _to_response(inbound, db)


@router.delete("/{inbound_id}", status_code=204)
def delete_inbound(
    inbound_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    inbound = db.query(Inbound).filter(Inbound.id == inbound_id).first()
    if not inbound:
        raise NotFoundError("Inbound")

    db.delete(inbound)
    db.commit()
    logger.info(f"Deleted inbound: {inbound.tag}")


@router.post("/{inbound_id}/toggle", response_model=InboundResponse)
def toggle_inbound(
    inbound_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    inbound = db.query(Inbound).filter(Inbound.id == inbound_id).first()
    if not inbound:
        raise NotFoundError("Inbound")

    inbound.enabled = not inbound.enabled
    db.commit()
    db.refresh(inbound)
    return _to_response(inbound, db)
