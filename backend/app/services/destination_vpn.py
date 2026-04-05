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


def ensure_ssh_protection():
    """Ensure SSH (port 22) and server default route are ALWAYS preserved.

    Called before any routing/iptables changes to guarantee the admin
    never loses access to the server.
    """
    import subprocess as _sp

    # 1. Ensure iptables INPUT allows SSH on port 22 (idempotent)
    check = _sp.run(
        ["iptables", "-C", "INPUT", "-p", "tcp", "--dport", "22", "-j", "ACCEPT"],
        capture_output=True, timeout=5,
    )
    if check.returncode != 0:
        _sp.run(
            ["iptables", "-I", "INPUT", "1", "-p", "tcp", "--dport", "22", "-j", "ACCEPT"],
            capture_output=True, timeout=5,
        )
        logger.info("SSH protection: added INPUT ACCEPT rule for port 22")

    # 2. Ensure ESTABLISHED connections are always allowed (keeps current SSH alive)
    check2 = _sp.run(
        ["iptables", "-C", "INPUT", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
        capture_output=True, timeout=5,
    )
    if check2.returncode != 0:
        _sp.run(
            ["iptables", "-I", "INPUT", "1", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
            capture_output=True, timeout=5,
        )

    # 3. Verify the default route in main table still exists
    result = _sp.run(
        ["ip", "route", "show", "default"],
        capture_output=True, text=True, timeout=5,
    )
    if "default" not in result.stdout:
        logger.critical("SSH protection: DEFAULT ROUTE IS MISSING! Attempting recovery...")
        # Try to restore default route via the first detected gateway
        _sp.run(
            ["ip", "route", "add", "default", "via", "216.250.112.1", "dev", "ens6"],
            capture_output=True, timeout=5,
        )


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


def check_wg_handshake(interface: str) -> bool:
    """Check if WireGuard interface has a recent handshake (within 3 minutes)."""
    rc, output = _run_cmd(["wg", "show", interface, "latest-handshakes"])
    if rc != 0:
        return False
    for line in output.split("\n"):
        parts = line.strip().split("\t")
        if len(parts) == 2:
            try:
                handshake_time = int(parts[1])
                if handshake_time == 0:
                    continue
                age = int(time.time()) - handshake_time
                if age < 180:  # 3 minutes
                    return True
            except ValueError:
                pass
    return False


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

        # Check interface exists
        result["interface_exists"] = check_interface_exists(interface)
        if not result["interface_exists"]:
            dest.is_running = False
            db.commit()
            return result

        # For WireGuard: check handshake instead of ping (since Table=off)
        if dest.protocol == "wireguard":
            result["is_running"] = check_wg_handshake(interface)
        else:
            # For OpenVPN: use ping
            latency = ping_through_interface(interface)
            result["latency_ms"] = latency
            result["is_running"] = latency is not None

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
                    dest.is_running = False
                    db.commit()
                elif health.get("is_running") and not dest.is_running:
                    logger.info(f"Destination VPN '{dest.name}' came UP")
                    dest.is_running = True
                    db.commit()
            except Exception as e:
                logger.error(f"Health check failed for {dest.name}: {e}")
    finally:
        db.close()


def manage_auto_destinations():
    """Manage auto-start/on-demand destination VPNs. Called every 30 seconds.

    on_demand: Start when users are online, stop after 2 min idle.
    auto_restart: Restart if stopped unexpectedly (not manually).
    """
    from app.services.wireguard import get_peers_status
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        dests = db.query(DestinationVPN).filter(DestinationVPN.enabled == True).all()  # noqa: E712
        peers = get_peers_status()

        for dest in dests:
            if dest.start_mode == "manual":
                continue

            # Count online users for this destination
            online_count = 0
            for user in dest.users:
                if not user.enabled:
                    continue
                for peer in peers:
                    if peer["public_key"] == user.wg_public_key:
                        if peer.get("latest_handshake") and (
                            datetime.now(timezone.utc).timestamp() - peer["latest_handshake"] < 120
                        ):
                            online_count += 1
                        break

            if dest.start_mode == "on_demand":
                if online_count > 0 and not dest.is_running:
                    # Users online, start the destination
                    logger.info(f"On-demand: Starting '{dest.name}' ({online_count} users online)")
                    _start_destination_internal(dest, db)
                elif online_count == 0 and dest.is_running and not dest.manually_stopped:
                    # No users online for 2 min, stop it
                    logger.info(f"On-demand: Stopping '{dest.name}' (no users online)")
                    _stop_destination_internal(dest, db)

            elif dest.start_mode == "auto_restart":
                if not dest.is_running and not dest.manually_stopped:
                    # Stopped unexpectedly, restart it
                    logger.info(f"Auto-restart: Restarting '{dest.name}'")
                    _start_destination_internal(dest, db)

    except Exception as e:
        logger.error(f"manage_auto_destinations error: {e}")
    finally:
        db.close()


def _start_destination_internal(dest, db):
    """Internal helper to start a destination without API context.

    Uses isolated routing tables and Table=off to NEVER touch the server's
    default route.  SSH connectivity is preserved at all times.
    """
    import subprocess
    from pathlib import Path
    from app.config import settings

    try:
        iface = dest.interface_name
        wg_subnet = settings.wg_subnet

        # ── Safety: protect SSH before touching anything ──
        ensure_ssh_protection()

        if dest.protocol == "wireguard":
            config_path = dest.config_file_path or iface

            # Ensure Table = off so wg-quick never hijacks the default route
            if config_path and Path(config_path).exists():
                config_content = Path(config_path).read_text()
                if "Table" not in config_content:
                    config_content = config_content.replace(
                        "[Interface]",
                        "[Interface]\nTable = off",
                    )
                    Path(config_path).write_text(config_content)

            subprocess.run(
                ["wg-quick", "up", config_path],
                capture_output=True, timeout=30, check=True,
            )

            # Set up isolated routing (same logic as API start endpoint)
            table_id = str(51820 + dest.id)
            subprocess.run(
                ["ip", "route", "add", "default", "dev", iface, "table", table_id],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["ip", "rule", "add", "from", wg_subnet, "lookup", table_id, "priority", "100"],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", wg_subnet, "-o", iface, "-j", "MASQUERADE"],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["iptables", "-A", "FORWARD", "-i", "wg0", "-o", iface, "-j", "ACCEPT"],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["iptables", "-A", "FORWARD", "-i", iface, "-o", "wg0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                capture_output=True, timeout=10,
            )

        elif dest.protocol == "openvpn":
            subprocess.run(
                ["systemctl", "start", f"openvpn@{iface}"],
                capture_output=True, timeout=30, check=True,
            )

        dest.is_running = True
        dest.manually_stopped = False
        db.commit()
        logger.info(f"Auto-started destination '{dest.name}'")
    except Exception as e:
        logger.error(f"Failed to auto-start '{dest.name}': {e}")


def _stop_destination_internal(dest, db):
    """Internal helper to stop a destination without API context.

    Cleans up isolated routing rules before tearing down the interface.
    """
    import subprocess
    from app.config import settings

    try:
        iface = dest.interface_name
        wg_subnet = settings.wg_subnet

        if dest.protocol == "wireguard":
            # Clean up routing rules first (mirror of start logic)
            table_id = str(51820 + dest.id)
            subprocess.run(
                ["ip", "rule", "del", "from", wg_subnet, "lookup", table_id],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["ip", "route", "del", "default", "dev", iface, "table", table_id],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["iptables", "-t", "nat", "-D", "POSTROUTING", "-s", wg_subnet, "-o", iface, "-j", "MASQUERADE"],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["iptables", "-D", "FORWARD", "-i", "wg0", "-o", iface, "-j", "ACCEPT"],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["iptables", "-D", "FORWARD", "-i", iface, "-o", "wg0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                capture_output=True, timeout=10,
            )

            config_path = dest.config_file_path or iface
            subprocess.run(
                ["wg-quick", "down", config_path],
                capture_output=True, timeout=15, check=True,
            )
        elif dest.protocol == "openvpn":
            subprocess.run(
                ["systemctl", "stop", f"openvpn@{iface}"],
                capture_output=True, timeout=15, check=True,
            )

        dest.is_running = False
        db.commit()
        logger.info(f"Auto-stopped destination '{dest.name}'")
    except Exception as e:
        logger.error(f"Failed to auto-stop '{dest.name}': {e}")


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
