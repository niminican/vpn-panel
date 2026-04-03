"""
IPTables Service

Manages per-user iptables rules for:
- Whitelist enforcement (per-user chains)
- Time-based access schedules
- Connection logging (LOG)
- Blocking disabled/expired users
"""
import logging
import subprocess

from app.config import settings
from app.core.validators import (
    validate_ip,
    validate_ip_network,
    validate_interface,
    validate_chain_name,
    validate_protocol,
    validate_port,
    validate_fwmark,
    validate_table_id,
    validate_comment,
    validate_day,
    validate_time,
    validate_address,
)

logger = logging.getLogger(__name__)

WG_IFACE = validate_interface(settings.wg_interface)


def _run(cmd: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run a command as a list (no shell). Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=10
    )
    if check and result.returncode != 0:
        logger.warning(f"iptables command failed: {' '.join(cmd)} -> {result.stderr.strip()}")
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _chain_name(user_id: int) -> str:
    return f"vpn_user_{int(user_id)}"


def _chain_exists(chain: str) -> bool:
    chain = validate_chain_name(chain)
    rc, _, _ = _run(["iptables", "-L", chain, "-n"], check=False)
    return rc == 0


# ─── Whitelist ───────────────────────────────────────────────

def setup_user_whitelist(user_id: int, user_ip: str, entries: list[dict]):
    """Create per-user iptables chain with whitelist rules.

    entries: list of {"address": str, "port": int|None, "protocol": str}
    """
    chain = _chain_name(user_id)
    ip_addr = validate_ip(user_ip.split("/")[0])

    # Remove existing chain
    remove_user_whitelist(user_id, user_ip)

    if not entries:
        return

    # Create chain
    validate_chain_name(chain)
    _run(["iptables", "-N", chain])

    # Add whitelist entries
    for entry in entries:
        cmd = ["iptables", "-A", chain]
        if entry.get("protocol") and entry["protocol"] != "any":
            proto = validate_protocol(entry["protocol"])
            cmd.extend(["-p", proto])
        dest = validate_address(entry["address"])
        cmd.extend(["-d", dest])
        if entry.get("port"):
            proto = entry.get("protocol", "tcp")
            if proto == "any":
                proto = "tcp"
            proto = validate_protocol(proto)
            port = validate_port(int(entry["port"]))
            cmd.extend(["-p", proto, "--dport", str(port)])
        cmd.extend(["-j", "ACCEPT"])
        _run(cmd)

    # Allow established/related connections back
    _run(["iptables", "-A", chain, "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"])

    # Default DROP (deny everything not whitelisted)
    _run(["iptables", "-A", chain, "-j", "DROP"])

    # Jump to user chain from FORWARD
    _run(["iptables", "-I", "FORWARD", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", chain])

    logger.info(f"Set up whitelist for user {user_id} with {len(entries)} entries")


def remove_user_whitelist(user_id: int, user_ip: str):
    """Remove per-user whitelist chain."""
    chain = _chain_name(user_id)
    ip_addr = validate_ip(user_ip.split("/")[0])

    if not _chain_exists(chain):
        return

    # Remove jump rule
    _run(["iptables", "-D", "FORWARD", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", chain], check=False)
    # Flush and delete chain
    _run(["iptables", "-F", chain], check=False)
    _run(["iptables", "-X", chain], check=False)

    logger.info(f"Removed whitelist for user {user_id}")


# ─── Time Schedule ───────────────────────────────────────────

def apply_time_schedule(user_id: int, user_ip: str, schedules: list[dict]):
    """Apply time-based access rules using iptables time match.

    schedules: list of {"day_of_week": int, "start_time": str, "end_time": str}
    """
    ip_addr = validate_ip(user_ip.split("/")[0])
    tag = f"vpn_sched_{int(user_id)}"

    # Remove existing schedule rules
    remove_time_schedule(user_id, user_ip)

    if not schedules:
        return

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for sched in schedules:
        day = validate_day(day_names[sched["day_of_week"]])
        start = validate_time(sched["start_time"])
        end = validate_time(sched["end_time"])
        comment = validate_comment(tag)

        # ACCEPT during allowed time
        _run([
            "iptables", "-A", "FORWARD",
            "-i", WG_IFACE, "-s", f"{ip_addr}/32",
            "-m", "time", "--timestart", start, "--timestop", end, "--weekdays", day,
            "-m", "comment", "--comment", comment,
            "-j", "ACCEPT",
        ])

    # DROP at all other times
    deny_comment = validate_comment(f"{tag}_deny")
    _run([
        "iptables", "-A", "FORWARD",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-m", "comment", "--comment", deny_comment,
        "-j", "DROP",
    ])

    logger.info(f"Applied time schedule for user {user_id}: {len(schedules)} rules")


def remove_time_schedule(user_id: int, user_ip: str):
    """Remove time-based schedule rules for a user."""
    ip_addr = validate_ip(user_ip.split("/")[0])
    tag = validate_comment(f"vpn_sched_{int(user_id)}")

    # Delete all rules with this comment tag
    while True:
        rc, _, _ = _run([
            "iptables", "-D", "FORWARD",
            "-i", WG_IFACE, "-s", f"{ip_addr}/32",
            "-m", "comment", "--comment", tag,
            "-j", "ACCEPT",
        ], check=False)
        if rc != 0:
            break

    _run([
        "iptables", "-D", "FORWARD",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-m", "comment", "--comment", f"{tag}_deny",
        "-j", "DROP",
    ], check=False)


# ─── Connection Logging ─────────────────────────────────────

def enable_connection_logging(user_id: int, user_ip: str):
    """Enable LOG logging for NEW connections from a user.

    Always removes and re-inserts at position 1 to ensure LOG rules
    stay above ACCEPT rules in the FORWARD chain.
    """
    ip_addr = validate_ip(user_ip.split("/")[0])
    log_prefix = f"user:{int(user_id)}: "

    # Remove old NFLOG rule if exists
    _run([
        "iptables", "-D", "FORWARD",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-m", "conntrack", "--ctstate", "NEW",
        "-j", "NFLOG", "--nflog-group", "100", "--nflog-prefix", f"user:{int(user_id)}:",
    ], check=False)

    # Always delete existing LOG rule first (may be at wrong position)
    _run([
        "iptables", "-D", "FORWARD",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-m", "conntrack", "--ctstate", "NEW",
        "-j", "LOG", "--log-prefix", log_prefix, "--log-level", "4",
    ], check=False)

    # Re-insert at position 1 (must be before ACCEPT rules)
    _run([
        "iptables", "-I", "FORWARD", "1",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-m", "conntrack", "--ctstate", "NEW",
        "-j", "LOG", "--log-prefix", log_prefix, "--log-level", "4",
    ])
    logger.info(f"Enabled connection logging for user {user_id}")


def disable_connection_logging(user_id: int, user_ip: str):
    """Disable LOG logging for a user."""
    ip_addr = validate_ip(user_ip.split("/")[0])
    log_prefix = f"user:{int(user_id)}: "

    # Remove LOG rule
    _run([
        "iptables", "-D", "FORWARD",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-m", "conntrack", "--ctstate", "NEW",
        "-j", "LOG", "--log-prefix", log_prefix, "--log-level", "4",
    ], check=False)
    # Also remove old NFLOG rule if exists
    _run([
        "iptables", "-D", "FORWARD",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-m", "conntrack", "--ctstate", "NEW",
        "-j", "NFLOG", "--nflog-group", "100", "--nflog-prefix", f"user:{int(user_id)}:",
    ], check=False)


# ─── Block/Unblock User ─────────────────────────────────────

def block_user(user_ip: str):
    """Block all traffic for a user."""
    ip_addr = validate_ip(user_ip.split("/")[0])
    _run(["iptables", "-I", "FORWARD", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", "DROP"])


def unblock_user(user_ip: str):
    """Unblock a user."""
    ip_addr = validate_ip(user_ip.split("/")[0])
    _run(["iptables", "-D", "FORWARD", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", "DROP"], check=False)


# ─── Destination VPN Routing ─────────────────────────────────

def setup_destination_routing(user_ip: str, fwmark: int):
    """Mark user's packets with fwmark for policy routing to destination VPN."""
    ip_addr = validate_ip(user_ip.split("/")[0])
    fwmark = validate_fwmark(fwmark)
    _run([
        "iptables", "-t", "mangle", "-A", "PREROUTING",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-j", "MARK", "--set-mark", str(fwmark),
    ])


def remove_destination_routing(user_ip: str, fwmark: int):
    ip_addr = validate_ip(user_ip.split("/")[0])
    fwmark = validate_fwmark(fwmark)
    _run([
        "iptables", "-t", "mangle", "-D", "PREROUTING",
        "-i", WG_IFACE, "-s", f"{ip_addr}/32",
        "-j", "MARK", "--set-mark", str(fwmark),
    ], check=False)


def setup_nat_for_destination(dest_interface: str):
    """Set up NAT masquerade for a destination VPN interface."""
    iface = validate_interface(dest_interface)
    _run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", iface, "-j", "MASQUERADE"])


def setup_ip_rule(fwmark: int, table: int):
    """Add ip rule for policy routing."""
    fwmark = validate_fwmark(fwmark)
    table = validate_table_id(table)
    _run(["ip", "rule", "add", "fwmark", str(fwmark), "table", str(table)], check=False)


def setup_default_route(table: int, dest_interface: str):
    """Set default route in routing table for destination VPN."""
    table = validate_table_id(table)
    iface = validate_interface(dest_interface)
    _run(["ip", "route", "add", "default", "dev", iface, "table", str(table)], check=False)


# ─── Init / Cleanup ─────────────────────────────────────────

def initialize_logging_for_all(db_session):
    """Enable connection logging for all enabled users."""
    from app.models.user import User
    users = db_session.query(User).filter(User.enabled == True).all()  # noqa: E712
    for user in users:
        enable_connection_logging(user.id, user.assigned_ip)
    logger.info(f"Enabled logging for {len(users)} users")
