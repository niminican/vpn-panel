"""
Destination VPN Monitoring Service

Health checks and speed tests for destination VPN connections.
"""
import logging
import subprocess
import time
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.destination_vpn import DestinationVPN

logger = logging.getLogger(__name__)


def _run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


def check_interface_exists(interface: str) -> bool:
    """Check if a network interface exists."""
    rc, _ = _run_cmd(["ip", "link", "show", interface])
    return rc == 0


def ping_through_interface(interface: str, target: str = "8.8.8.8", count: int = 3) -> float | None:
    """Ping through a specific interface. Returns average latency in ms or None."""
    rc, output = _run_cmd(
        ["ping", "-c", str(count), "-W", "2", "-I", interface, target],
        timeout=15,
    )
    if rc != 0:
        return None

    # Parse average latency
    for line in output.split("\n"):
        if "avg" in line:
            # rtt min/avg/max/mdev = 1.234/2.345/3.456/0.567 ms
            try:
                parts = line.split("=")[1].strip().split("/")
                return float(parts[1])
            except (IndexError, ValueError):
                pass
    return None


def get_external_ip(interface: str) -> str | None:
    """Get external IP through a specific interface."""
    rc, output = _run_cmd(
        ["curl", "--interface", interface, "-s", "--max-time", "5", "https://api.ipify.org"],
        timeout=10,
    )
    return output if rc == 0 and output else None


def check_destination_health(dest_id: int) -> dict:
    """Run health check for a destination VPN."""
    db = SessionLocal()
    try:
        dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
        if not dest:
            return {"error": "Destination not found"}

        interface = dest.interface_name
        result = {
            "id": dest.id,
            "name": dest.name,
            "interface_exists": False,
            "is_running": False,
            "latency_ms": None,
            "external_ip": None,
        }

        # Check interface
        result["interface_exists"] = check_interface_exists(interface)
        if not result["interface_exists"]:
            dest.is_running = False
            db.commit()
            return result

        # Ping test
        latency = ping_through_interface(interface)
        result["latency_ms"] = latency
        result["is_running"] = latency is not None

        # Get external IP
        if result["is_running"]:
            result["external_ip"] = get_external_ip(interface)

        # Update DB status
        dest.is_running = result["is_running"]
        db.commit()

        return result
    finally:
        db.close()


def check_all_destinations():
    """Health check all destination VPNs. Called periodically."""
    db = SessionLocal()
    try:
        dests = db.query(DestinationVPN).filter(DestinationVPN.enabled == True).all()  # noqa: E712
        for dest in dests:
            try:
                health = check_destination_health(dest.id)
                if not health.get("is_running") and dest.is_running:
                    logger.warning(f"Destination VPN '{dest.name}' went DOWN")
                elif health.get("is_running") and not dest.is_running:
                    logger.info(f"Destination VPN '{dest.name}' came UP")
            except Exception as e:
                logger.error(f"Health check failed for {dest.name}: {e}")
    finally:
        db.close()


def run_speed_test(interface: str) -> dict | None:
    """Run a speed test through a specific interface.
    Uses speedtest-cli bound to the interface.
    """
    try:
        rc, output = _run_cmd(
            ["speedtest-cli", "--simple", "--source", interface],
            timeout=60,
        )
        if rc != 0:
            return None

        result = {}
        for line in output.split("\n"):
            if line.startswith("Ping:"):
                result["ping_ms"] = float(line.split(":")[1].strip().split()[0])
            elif line.startswith("Download:"):
                result["download_mbps"] = float(line.split(":")[1].strip().split()[0])
            elif line.startswith("Upload:"):
                result["upload_mbps"] = float(line.split(":")[1].strip().split()[0])
        return result
    except Exception as e:
        logger.error(f"Speed test failed: {e}")
        return None
