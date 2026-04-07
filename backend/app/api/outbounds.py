"""Outbound management API — CRUD for proxy outbounds (how traffic exits)."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.outbound import Outbound
from app.schemas.outbound import OutboundCreate, OutboundUpdate, OutboundResponse
from app.core.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/outbounds", tags=["outbounds"])

VALID_PROTOCOLS = {"direct", "blackhole", "vless", "trojan", "shadowsocks", "wireguard", "http", "socks"}


@router.get("", response_model=list[OutboundResponse])
def list_outbounds(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.view")),
):
    return db.query(Outbound).order_by(Outbound.created_at.desc()).all()


@router.post("", response_model=OutboundResponse, status_code=201)
def create_outbound(
    req: OutboundCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    if db.query(Outbound).filter(Outbound.tag == req.tag).first():
        raise ConflictError("Outbound tag already exists")

    if req.protocol not in VALID_PROTOCOLS:
        raise HTTPException(400, f"Invalid protocol. Must be one of: {VALID_PROTOCOLS}")

    if req.engine not in ("xray", "singbox"):
        raise HTTPException(400, "Engine must be 'xray' or 'singbox'")

    # Validate server is required for proxy outbounds
    if req.protocol not in ("direct", "blackhole") and not req.server:
        raise HTTPException(400, "Server address is required for proxy outbounds")

    outbound = Outbound(**req.model_dump())
    db.add(outbound)
    db.commit()
    db.refresh(outbound)

    logger.info(f"Created outbound: {outbound.tag} ({outbound.protocol})")
    return outbound


@router.get("/{outbound_id}", response_model=OutboundResponse)
def get_outbound(
    outbound_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.view")),
):
    outbound = db.query(Outbound).filter(Outbound.id == outbound_id).first()
    if not outbound:
        raise NotFoundError("Outbound")
    return outbound


@router.put("/{outbound_id}", response_model=OutboundResponse)
def update_outbound(
    outbound_id: int,
    req: OutboundUpdate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    outbound = db.query(Outbound).filter(Outbound.id == outbound_id).first()
    if not outbound:
        raise NotFoundError("Outbound")

    update_data = req.model_dump(exclude_unset=True)

    if "tag" in update_data:
        existing = db.query(Outbound).filter(Outbound.tag == update_data["tag"], Outbound.id != outbound_id).first()
        if existing:
            raise ConflictError("Outbound tag already exists")

    for key, value in update_data.items():
        setattr(outbound, key, value)

    db.commit()
    db.refresh(outbound)
    return outbound


@router.delete("/{outbound_id}", status_code=204)
def delete_outbound(
    outbound_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    outbound = db.query(Outbound).filter(Outbound.id == outbound_id).first()
    if not outbound:
        raise NotFoundError("Outbound")

    db.delete(outbound)
    db.commit()
    logger.info(f"Deleted outbound: {outbound.tag}")


@router.post("/{outbound_id}/toggle", response_model=OutboundResponse)
def toggle_outbound(
    outbound_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    outbound = db.query(Outbound).filter(Outbound.id == outbound_id).first()
    if not outbound:
        raise NotFoundError("Outbound")

    outbound.enabled = not outbound.enabled
    db.commit()
    db.refresh(outbound)
    return outbound
