"""
Destination VPN Monitoring Service

Health checks and speed tests for destination VPN connections.
"""
import logging
import time
from datetime import datetime, timezone

from app.core.command_executor import run_command
from app.database import SessionLocal
from app.models.destination_vpn import DestinationVPN

logger = logging.getLogger(__name__)


def ensure_ssh_protection():
    """Ensure SSH (port 22) and server default route are ALWAYS preserved.

    Called before any routing/iptables changes to guarantee the admin
    never loses access to the server.
    """
    # 1. Ensure iptables INPUT allows SSH on port 22 (idempotent)
    check = run_command(
        ["iptables", "-C", "INPUT", "-p", "tcp", "--dport", "22", "-j", "ACCEPT"],
        timeout=5,
    )
    if check.returncode != 0:
        run_command(
            ["iptables", "-I", "INPUT", "1", "-p", "tcp", "--dport", "22", "-j", "ACCEPT"],
            timeout=5,
        )
        logger.info("SSH protection: added INPUT ACCEPT rule for port 22")

    # 2. Ensure ESTABLISHED connections are always allowed (keeps current SSH alive)
    check2 = run_command(
        ["iptables", "-C", "INPUT", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
        timeout=5,
    )
    if check2.returncode != 0:
        run_command(
            ["iptables", "-I", "INPUT", "1", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
            timeout=5,
        )

    # 3. Verify the default route in main table still exists
    result = run_command(
        ["ip", "route", "show", "default"],
        timeout=5,
    )
    if "default" not in result.stdout:
        logger.critical("SSH protection: DEFAULT ROUTE IS MISSING! Attempting recovery...")
        # Try to restore default route via the first detected gateway
        run_command(
            ["ip", "route", "add", "default", "via", "216.250.112.1", "dev", "ens6"],
            timeout=5,
        )


def _run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    result = run_command(cmd, timeout=timeout)
    return result.returncode, result.stdout.strip()


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
    """Run health check for a destination VPN.

    For WireGuard: interface existence = running (handshake may be stale
    if no traffic flows, but the tunnel is still up and functional).
    For OpenVPN: interface existence + ping reachability.
    """
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

        # Interface exists → it's running
        # For WireGuard: interface up = running (don't rely on handshake which
        # can be stale when no traffic flows)
        if dest.protocol == "wireguard":
            result["is_running"] = True
            # Handshake is supplementary info only, not used for status
            result["has_recent_handshake"] = check_wg_handshake(interface)
        else:
            # For OpenVPN: use ping as additional check
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

    on_demand: Start when users are online (connected to wg0), stop after
    5 minutes of no online users.  Uses idle_since timestamp to avoid
    chicken-egg problems (user can't connect if destination is down).
    auto_restart: Restart if stopped unexpectedly (not manually).
    """
    from app.services.wireguard import get_peers_status
    from datetime import datetime, timezone, timedelta

    IDLE_TIMEOUT = timedelta(minutes=5)

    db = SessionLocal()
    try:
        dests = db.query(DestinationVPN).filter(DestinationVPN.enabled == True).all()  # noqa: E712
        peers = get_peers_status()
        now = datetime.now(timezone.utc)

        for dest in dests:
            if dest.start_mode == "manual":
                continue

            # Count online users for this destination
            # Check if user's peer on wg0 has recent handshake (connected to server)
            online_count = 0
            for user in dest.users:
                if not user.enabled:
                    continue
                for peer in peers:
                    if peer["public_key"] == user.wg_public_key:
                        if peer.get("latest_handshake") and (
                            now.timestamp() - peer["latest_handshake"] < 180
                        ):
                            online_count += 1
                        break

            if dest.start_mode == "on_demand":
                if online_count > 0:
                    # Users online → clear idle timer, start if needed
                    if dest.idle_since is not None:
                        dest.idle_since = None
                        db.commit()
                    if not dest.is_running:
                        logger.info(f"On-demand: Starting '{dest.name}' ({online_count} users online)")
                        _start_destination_internal(dest, db)
                else:
                    # No users online
                    if dest.is_running and not dest.manually_stopped:
                        if dest.idle_since is None:
                            # Start idle timer
                            dest.idle_since = now.replace(tzinfo=None)
                            db.commit()
                            logger.debug(f"On-demand: '{dest.name}' idle timer started")
                        else:
                            # Check if idle long enough
                            idle_dt = dest.idle_since
                            if idle_dt.tzinfo is None:
                                idle_dt = idle_dt.replace(tzinfo=timezone.utc)
                            if now - idle_dt >= IDLE_TIMEOUT:
                                logger.info(f"On-demand: Stopping '{dest.name}' (idle for {IDLE_TIMEOUT})")
                                _stop_destination_internal(dest, db)
                                dest.idle_since = None
                                db.commit()

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

            run_command(
                ["wg-quick", "up", config_path],
                check=True, timeout=30,
            )

            # Set up isolated routing (same logic as API start endpoint)
            table_id = str(51820 + dest.id)
            run_command(
                ["ip", "route", "add", "default", "dev", iface, "table", table_id],
                timeout=10,
            )
            run_command(
                ["ip", "rule", "add", "from", wg_subnet, "lookup", table_id, "priority", "100"],
                timeout=10,
            )
            run_command(
                ["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", wg_subnet, "-o", iface, "-j", "MASQUERADE"],
                timeout=10,
            )
            run_command(
                ["iptables", "-A", "FORWARD", "-i", "wg0", "-o", iface, "-j", "ACCEPT"],
                timeout=10,
            )
            run_command(
                ["iptables", "-A", "FORWARD", "-i", iface, "-o", "wg0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                timeout=10,
            )

        elif dest.protocol == "openvpn":
            run_command(
                ["systemctl", "start", f"openvpn@{iface}"],
                check=True, timeout=30,
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
    from app.config import settings

    try:
        iface = dest.interface_name
        wg_subnet = settings.wg_subnet

        if dest.protocol == "wireguard":
            # Clean up routing rules first (mirror of start logic)
            table_id = str(51820 + dest.id)
            run_command(
                ["ip", "rule", "del", "from", wg_subnet, "lookup", table_id],
                timeout=10,
            )
            run_command(
                ["ip", "route", "del", "default", "dev", iface, "table", table_id],
                timeout=10,
            )
            run_command(
                ["iptables", "-t", "nat", "-D", "POSTROUTING", "-s", wg_subnet, "-o", iface, "-j", "MASQUERADE"],
                timeout=10,
            )
            run_command(
                ["iptables", "-D", "FORWARD", "-i", "wg0", "-o", iface, "-j", "ACCEPT"],
                timeout=10,
            )
            run_command(
                ["iptables", "-D", "FORWARD", "-i", iface, "-o", "wg0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                timeout=10,
            )

            config_path = dest.config_file_path or iface
            run_command(
                ["wg-quick", "down", config_path],
                check=True, timeout=15,
            )
        elif dest.protocol == "openvpn":
            run_command(
                ["systemctl", "stop", f"openvpn@{iface}"],
                check=True, timeout=15,
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
