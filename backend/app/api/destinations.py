from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.models.destination_vpn import DestinationVPN
from app.models.user import User
from app.schemas.destination_vpn import (
    DestinationVPNCreate,
    DestinationVPNUpdate,
    DestinationVPNResponse,
    DestinationVPNStatus,
)
from app.core.exceptions import NotFoundError
from app.config import settings

router = APIRouter(prefix="/api/destinations", tags=["destinations"])

DEST_CONFIG_DIR = Path(settings.wg_config_dir) / "destinations"


def _detect_protocol(config_text: str) -> str:
    """Auto-detect VPN protocol from config content."""
    lower = config_text.lower()
    if "[interface]" in lower and "privatekey" in lower:
        return "wireguard"
    if "client" in lower or "remote " in lower or "proto " in lower:
        return "openvpn"
    return "unknown"


def _dest_to_response(dest: DestinationVPN, db: Session) -> DestinationVPNResponse:
    user_count = db.query(User).filter(User.destination_vpn_id == dest.id).count()
    return DestinationVPNResponse(
        id=dest.id,
        name=dest.name,
        protocol=dest.protocol,
        interface_name=dest.interface_name,
        config_text=dest.config_text,
        config_file_path=dest.config_file_path,
        enabled=dest.enabled,
        is_running=dest.is_running,
        user_count=user_count,
        created_at=dest.created_at,
        updated_at=dest.updated_at,
    )


@router.get("", response_model=list[DestinationVPNResponse])
def list_destinations(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    dests = db.query(DestinationVPN).order_by(DestinationVPN.created_at.desc()).all()
    return [_dest_to_response(d, db) for d in dests]


@router.post("", response_model=DestinationVPNResponse, status_code=201)
def create_destination(
    req: DestinationVPNCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    protocol = req.protocol
    if protocol == "auto" and req.config_text:
        protocol = _detect_protocol(req.config_text)

    # Assign unique routing table and fwmark
    max_rt = db.query(DestinationVPN).count()
    routing_table = 100 + max_rt
    fwmark = 100 + max_rt

    dest = DestinationVPN(
        name=req.name,
        protocol=protocol,
        interface_name=req.interface_name,
        config_text=req.config_text,
        routing_table=routing_table,
        fwmark=fwmark,
    )

    # Save config file to disk
    if req.config_text:
        DEST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        ext = ".conf" if protocol == "wireguard" else ".ovpn"
        config_path = DEST_CONFIG_DIR / f"{req.interface_name}{ext}"
        config_path.write_text(req.config_text)
        dest.config_file_path = str(config_path)

    db.add(dest)
    db.commit()
    db.refresh(dest)
    return _dest_to_response(dest, db)


@router.post("/upload", response_model=DestinationVPNResponse, status_code=201)
async def create_destination_upload(
    name: str,
    interface_name: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Create a destination VPN by uploading a config file."""
    content = (await file.read()).decode("utf-8")
    protocol = _detect_protocol(content)

    max_rt = db.query(DestinationVPN).count()
    routing_table = 100 + max_rt
    fwmark = 100 + max_rt

    DEST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".conf" if protocol == "wireguard" else ".ovpn"
    config_path = DEST_CONFIG_DIR / f"{interface_name}{ext}"
    config_path.write_text(content)

    dest = DestinationVPN(
        name=name,
        protocol=protocol,
        interface_name=interface_name,
        config_text=content,
        config_file_path=str(config_path),
        routing_table=routing_table,
        fwmark=fwmark,
    )
    db.add(dest)
    db.commit()
    db.refresh(dest)
    return _dest_to_response(dest, db)


@router.get("/{dest_id}", response_model=DestinationVPNResponse)
def get_destination(
    dest_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")
    return _dest_to_response(dest, db)


@router.put("/{dest_id}", response_model=DestinationVPNResponse)
def update_destination(
    dest_id: int,
    req: DestinationVPNUpdate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")

    update_data = req.model_dump(exclude_unset=True)

    if "config_text" in update_data and update_data["config_text"]:
        # Update config file on disk
        protocol = update_data.get("protocol", dest.protocol)
        if protocol == "auto":
            protocol = _detect_protocol(update_data["config_text"])
            update_data["protocol"] = protocol

        DEST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        iface = update_data.get("interface_name", dest.interface_name)
        ext = ".conf" if protocol == "wireguard" else ".ovpn"
        config_path = DEST_CONFIG_DIR / f"{iface}{ext}"
        config_path.write_text(update_data["config_text"])
        dest.config_file_path = str(config_path)

    for key, value in update_data.items():
        setattr(dest, key, value)

    db.commit()
    db.refresh(dest)
    return _dest_to_response(dest, db)


@router.delete("/{dest_id}", status_code=204)
def delete_destination(
    dest_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")

    # Remove config file
    if dest.config_file_path:
        Path(dest.config_file_path).unlink(missing_ok=True)

    db.delete(dest)
    db.commit()


@router.post("/{dest_id}/start", response_model=DestinationVPNStatus)
def start_destination(
    dest_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")

    import subprocess

    # Demo mode: just toggle the status without running actual commands
    if settings.demo_mode:
        dest.is_running = True
        db.commit()
        return DestinationVPNStatus(id=dest.id, name=dest.name, is_running=True)

    # Check config file exists
    config_path = dest.config_file_path
    if config_path and not Path(config_path).exists():
        if dest.config_text:
            DEST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            ext = ".conf" if dest.protocol == "wireguard" else ".ovpn"
            config_path = str(DEST_CONFIG_DIR / f"{dest.interface_name}{ext}")
            Path(config_path).write_text(dest.config_text)
            dest.config_file_path = config_path
            db.commit()
        else:
            raise HTTPException(
                status_code=400,
                detail="Config file not found and no config text stored",
            )

    try:
        if dest.protocol == "wireguard":
            subprocess.run(
                ["wg-quick", "up", config_path or dest.interface_name],
                check=True, capture_output=True, text=True, timeout=30,
            )
        elif dest.protocol == "openvpn":
            subprocess.run(
                ["systemctl", "start", f"openvpn@{dest.interface_name}"],
                check=True, capture_output=True, text=True, timeout=30,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown protocol: {dest.protocol}")
        dest.is_running = True
        db.commit()
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or str(e)
        raise HTTPException(status_code=500, detail=f"Failed to start VPN: {error_msg}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout: VPN took too long to start")

    return DestinationVPNStatus(id=dest.id, name=dest.name, is_running=dest.is_running)


@router.post("/{dest_id}/stop", response_model=DestinationVPNStatus)
def stop_destination(
    dest_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")

    import subprocess

    # Demo mode
    if settings.demo_mode:
        dest.is_running = False
        db.commit()
        return DestinationVPNStatus(id=dest.id, name=dest.name, is_running=False)

    try:
        if dest.protocol == "wireguard":
            subprocess.run(
                ["wg-quick", "down", dest.config_file_path or dest.interface_name],
                check=True, capture_output=True, text=True, timeout=15,
            )
        elif dest.protocol == "openvpn":
            subprocess.run(
                ["systemctl", "stop", f"openvpn@{dest.interface_name}"],
                check=True, capture_output=True, text=True, timeout=15,
            )
        dest.is_running = False
        db.commit()
    except subprocess.CalledProcessError:
        pass

    return DestinationVPNStatus(id=dest.id, name=dest.name, is_running=dest.is_running)
