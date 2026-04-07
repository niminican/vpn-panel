import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.command_executor import run_command
from app.database import get_db
from app.api.deps import require_permission
from app.models.admin import Admin
from app.models.destination_vpn import DestinationVPN
from app.models.user import User
from sqlalchemy import func
from app.schemas.destination_vpn import (
    DestinationVPNCreate,
    DestinationVPNUpdate,
    DestinationVPNResponse,
    DestinationVPNStatus,
    DestinationUserStats,
)
from app.core.exceptions import NotFoundError
from app.core.validators import validate_interface, validate_ip_network
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
    users = db.query(User).filter(User.destination_vpn_id == dest.id).all()
    total_up = sum(u.bandwidth_used_up or 0 for u in users)
    total_down = sum(u.bandwidth_used_down or 0 for u in users)
    return DestinationVPNResponse(
        id=dest.id,
        name=dest.name,
        protocol=dest.protocol,
        interface_name=dest.interface_name,
        config_text=dest.config_text,
        config_file_path=dest.config_file_path,
        enabled=dest.enabled,
        is_running=dest.is_running,
        start_mode=dest.start_mode or "manual",
        user_count=len(users),
        total_upload=total_up,
        total_download=total_down,
        created_at=dest.created_at,
        updated_at=dest.updated_at,
    )


def _run_cmd(cmd: list[str], check: bool = False, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command safely as a list (no shell)."""
    return run_command(cmd, check=check, timeout=timeout)


@router.get("", response_model=list[DestinationVPNResponse])
def list_destinations(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.view")),
):
    dests = db.query(DestinationVPN).order_by(DestinationVPN.created_at.desc()).all()
    return [_dest_to_response(d, db) for d in dests]


@router.get("/{dest_id}/users", response_model=list[DestinationUserStats])
def list_destination_users(
    dest_id: int,
    sort_by: str = "download",
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.view")),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")

    from app.services.wireguard import get_peers_status
    peers = get_peers_status()

    users = db.query(User).filter(User.destination_vpn_id == dest_id).all()

    result = []
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()
    for u in users:
        is_online = False
        for p in peers:
            if p["public_key"] == u.wg_public_key:
                if p["latest_handshake"] and (now - p["latest_handshake"] < 180):
                    is_online = True
                break
        result.append(DestinationUserStats(
            id=u.id,
            username=u.username,
            is_online=is_online,
            bandwidth_used_up=u.bandwidth_used_up or 0,
            bandwidth_used_down=u.bandwidth_used_down or 0,
        ))

    if sort_by == "upload":
        result.sort(key=lambda x: x.bandwidth_used_up, reverse=True)
    else:
        result.sort(key=lambda x: x.bandwidth_used_down, reverse=True)

    return result


@router.post("", response_model=DestinationVPNResponse, status_code=201)
def create_destination(
    req: DestinationVPNCreate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    # Validate interface name
    validate_interface(req.interface_name)

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
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    """Create a destination VPN by uploading a config file."""
    validate_interface(interface_name)

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
    _admin: Admin = Depends(require_permission("destinations.view")),
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
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")

    update_data = req.model_dump(exclude_unset=True)

    if "interface_name" in update_data:
        validate_interface(update_data["interface_name"])

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
    _admin: Admin = Depends(require_permission("destinations.manage")),
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
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")

    dest.manually_stopped = False  # Clear manual stop flag on start
    db.commit()

    # Demo mode: just toggle the status without running actual commands
    if settings.demo_mode:
        dest.is_running = True
        db.commit()
        return DestinationVPNStatus(id=dest.id, name=dest.name, is_running=True)

    iface = validate_interface(dest.interface_name)
    wg_subnet = validate_ip_network(settings.wg_subnet)

    # Check config file exists
    config_path = dest.config_file_path
    if config_path and not Path(config_path).exists():
        if dest.config_text:
            DEST_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            ext = ".conf" if dest.protocol == "wireguard" else ".ovpn"
            config_path = str(DEST_CONFIG_DIR / f"{iface}{ext}")
            Path(config_path).write_text(dest.config_text)
            dest.config_file_path = config_path
            db.commit()
        else:
            raise HTTPException(
                status_code=400,
                detail="Config file not found and no config text stored",
            )

    # Check if interface is already running
    try:
        result = _run_cmd(["ip", "link", "show", iface], timeout=5)
        if result.returncode == 0:
            dest.is_running = True
            db.commit()
            return DestinationVPNStatus(id=dest.id, name=dest.name, is_running=True)
    except Exception:
        pass

    try:
        # ── Safety: protect SSH before touching routing ──
        from app.services.destination_vpn import ensure_ssh_protection
        ensure_ssh_protection()

        # Fix permissions on config file
        if config_path:
            import os
            os.chmod(config_path, 0o600)

        if dest.protocol == "wireguard":
            # Modify config to use Table = off so wg-quick doesn't hijack all routing
            config_content = Path(config_path).read_text()
            if "Table" not in config_content:
                config_content = config_content.replace(
                    "[Interface]",
                    "[Interface]\nTable = off",
                )
                Path(config_path).write_text(config_content)

            _run_cmd(["wg-quick", "up", config_path or iface], check=True, timeout=30)

            table_id = str(51820 + dest.id)

            # Add route in a separate table (list format, no shell)
            _run_cmd(["ip", "route", "add", "default", "dev", iface, "table", table_id])
            # Only route wg0 client traffic through destination VPN
            _run_cmd(["ip", "rule", "add", "from", wg_subnet, "lookup", table_id, "priority", "100"])
            # NAT masquerade for client traffic going out through destination VPN
            _run_cmd(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", wg_subnet, "-o", iface, "-j", "MASQUERADE"])
            # Allow forwarding between wg0 and destination
            _run_cmd(["iptables", "-A", "FORWARD", "-i", "wg0", "-o", iface, "-j", "ACCEPT"])
            _run_cmd(["iptables", "-A", "FORWARD", "-i", iface, "-o", "wg0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"])

            # Re-establish LOG rules at top of FORWARD chain (they must be before ACCEPT)
            from app.services.iptables import initialize_logging_for_all
            from app.database import SessionLocal
            log_db = SessionLocal()
            try:
                initialize_logging_for_all(log_db)
            finally:
                log_db.close()

        elif dest.protocol == "openvpn":
            _run_cmd(["systemctl", "start", f"openvpn@{iface}"], check=True, timeout=30)
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
    _admin: Admin = Depends(require_permission("destinations.manage")),
):
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        raise NotFoundError("Destination VPN")

    dest.manually_stopped = True  # Mark as manually stopped
    db.commit()

    # Demo mode
    if settings.demo_mode:
        dest.is_running = False
        db.commit()
        return DestinationVPNStatus(id=dest.id, name=dest.name, is_running=False)

    iface = validate_interface(dest.interface_name)
    wg_subnet = validate_ip_network(settings.wg_subnet)

    try:
        # ── Safety: protect SSH before touching routing ──
        from app.services.destination_vpn import ensure_ssh_protection
        ensure_ssh_protection()

        if dest.protocol == "wireguard":
            table_id = str(51820 + dest.id)

            # Clean up custom routing rules (list format, no shell)
            _run_cmd(["ip", "rule", "del", "from", wg_subnet, "lookup", table_id])
            _run_cmd(["ip", "route", "del", "default", "dev", iface, "table", table_id])
            _run_cmd(["iptables", "-t", "nat", "-D", "POSTROUTING", "-s", wg_subnet, "-o", iface, "-j", "MASQUERADE"])
            _run_cmd(["iptables", "-D", "FORWARD", "-i", "wg0", "-o", iface, "-j", "ACCEPT"])
            _run_cmd(["iptables", "-D", "FORWARD", "-i", iface, "-o", "wg0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"])

            _run_cmd(["wg-quick", "down", dest.config_file_path or iface], check=True, timeout=15)
        elif dest.protocol == "openvpn":
            _run_cmd(["systemctl", "stop", f"openvpn@{iface}"], check=True, timeout=15)
        dest.is_running = False
        db.commit()
    except subprocess.CalledProcessError:
        pass

    return DestinationVPNStatus(id=dest.id, name=dest.name, is_running=dest.is_running)
