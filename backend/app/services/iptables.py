"""
IPTables Service

Manages per-user iptables rules for:
- Whitelist enforcement (per-user chains)
- Time-based access schedules
- Connection logging (NFLOG)
- Blocking disabled/expired users
"""
import logging
import subprocess

from app.config import settings

logger = logging.getLogger(__name__)

WG_IFACE = settings.wg_interface


def _run(cmd: str, check: bool = True) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=10
    )
    if check and result.returncode != 0:
        logger.warning(f"iptables command failed: {cmd} -> {result.stderr.strip()}")
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _chain_name(user_id: int) -> str:
    return f"vpn_user_{user_id}"


def _chain_exists(chain: str) -> bool:
    rc, _, _ = _run(f"iptables -L {chain} -n", check=False)
    return rc == 0


# ─── Whitelist ───────────────────────────────────────────────

def setup_user_whitelist(user_id: int, user_ip: str, entries: list[dict]):
    """Create per-user iptables chain with whitelist rules.

    entries: list of {"address": str, "port": int|None, "protocol": str}
    """
    chain = _chain_name(user_id)
    ip_addr = user_ip.split("/")[0]

    # Remove existing chain
    remove_user_whitelist(user_id, user_ip)

    if not entries:
        return

    # Create chain
    _run(f"iptables -N {chain}")

    # Add whitelist entries
    for entry in entries:
        rule = f"iptables -A {chain}"
        if entry.get("protocol") and entry["protocol"] != "any":
            rule += f" -p {entry['protocol']}"
        rule += f" -d {entry['address']}"
        if entry.get("port"):
            proto = entry.get("protocol", "tcp")
            if proto == "any":
                proto = "tcp"
            rule += f" -p {proto} --dport {entry['port']}"
        rule += " -j ACCEPT"
        _run(rule)

    # Allow established/related connections back
    _run(f"iptables -A {chain} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT")

    # Default DROP (deny everything not whitelisted)
    _run(f"iptables -A {chain} -j DROP")

    # Jump to user chain from FORWARD
    _run(f"iptables -I FORWARD -i {WG_IFACE} -s {ip_addr}/32 -j {chain}")

    logger.info(f"Set up whitelist for user {user_id} with {len(entries)} entries")


def remove_user_whitelist(user_id: int, user_ip: str):
    """Remove per-user whitelist chain."""
    chain = _chain_name(user_id)
    ip_addr = user_ip.split("/")[0]

    if not _chain_exists(chain):
        return

    # Remove jump rule
    _run(f"iptables -D FORWARD -i {WG_IFACE} -s {ip_addr}/32 -j {chain}", check=False)
    # Flush and delete chain
    _run(f"iptables -F {chain}", check=False)
    _run(f"iptables -X {chain}", check=False)

    logger.info(f"Removed whitelist for user {user_id}")


# ─── Time Schedule ───────────────────────────────────────────

def apply_time_schedule(user_id: int, user_ip: str, schedules: list[dict]):
    """Apply time-based access rules using iptables time match.

    schedules: list of {"day_of_week": int, "start_time": str, "end_time": str}
    """
    ip_addr = user_ip.split("/")[0]
    tag = f"vpn_sched_{user_id}"

    # Remove existing schedule rules
    remove_time_schedule(user_id, user_ip)

    if not schedules:
        return

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Group schedules by time range
    for sched in schedules:
        day = day_names[sched["day_of_week"]]
        start = sched["start_time"]
        end = sched["end_time"]

        # ACCEPT during allowed time
        _run(
            f"iptables -A FORWARD -i {WG_IFACE} -s {ip_addr}/32 "
            f'-m time --timestart {start} --timestop {end} --weekdays {day} '
            f'-m comment --comment "{tag}" -j ACCEPT'
        )

    # DROP at all other times
    _run(
        f"iptables -A FORWARD -i {WG_IFACE} -s {ip_addr}/32 "
        f'-m comment --comment "{tag}_deny" -j DROP'
    )

    logger.info(f"Applied time schedule for user {user_id}: {len(schedules)} rules")


def remove_time_schedule(user_id: int, user_ip: str):
    """Remove time-based schedule rules for a user."""
    ip_addr = user_ip.split("/")[0]
    tag = f"vpn_sched_{user_id}"

    # Delete all rules with this comment tag
    while True:
        rc, _, _ = _run(
            f'iptables -D FORWARD -i {WG_IFACE} -s {ip_addr}/32 '
            f'-m comment --comment "{tag}" -j ACCEPT',
            check=False,
        )
        if rc != 0:
            break

    _run(
        f'iptables -D FORWARD -i {WG_IFACE} -s {ip_addr}/32 '
        f'-m comment --comment "{tag}_deny" -j DROP',
        check=False,
    )


# ─── Connection Logging ─────────────────────────────────────

def enable_connection_logging(user_id: int, user_ip: str):
    """Enable NFLOG logging for NEW connections from a user."""
    ip_addr = user_ip.split("/")[0]

    # Check if rule already exists
    rc, _, _ = _run(
        f'iptables -C FORWARD -i {WG_IFACE} -s {ip_addr}/32 '
        f'-m conntrack --ctstate NEW '
        f'-j NFLOG --nflog-group 100 --nflog-prefix "user:{user_id}:"',
        check=False,
    )
    if rc == 0:
        return  # Already exists

    _run(
        f'iptables -I FORWARD -i {WG_IFACE} -s {ip_addr}/32 '
        f'-m conntrack --ctstate NEW '
        f'-j NFLOG --nflog-group 100 --nflog-prefix "user:{user_id}:"'
    )
    logger.info(f"Enabled connection logging for user {user_id}")


def disable_connection_logging(user_id: int, user_ip: str):
    """Disable NFLOG logging for a user."""
    ip_addr = user_ip.split("/")[0]
    _run(
        f'iptables -D FORWARD -i {WG_IFACE} -s {ip_addr}/32 '
        f'-m conntrack --ctstate NEW '
        f'-j NFLOG --nflog-group 100 --nflog-prefix "user:{user_id}:"',
        check=False,
    )


# ─── Block/Unblock User ─────────────────────────────────────

def block_user(user_ip: str):
    """Block all traffic for a user."""
    ip_addr = user_ip.split("/")[0]
    _run(f"iptables -I FORWARD -i {WG_IFACE} -s {ip_addr}/32 -j DROP")


def unblock_user(user_ip: str):
    """Unblock a user."""
    ip_addr = user_ip.split("/")[0]
    _run(f"iptables -D FORWARD -i {WG_IFACE} -s {ip_addr}/32 -j DROP", check=False)


# ─── Destination VPN Routing ─────────────────────────────────

def setup_destination_routing(user_ip: str, fwmark: int):
    """Mark user's packets with fwmark for policy routing to destination VPN."""
    ip_addr = user_ip.split("/")[0]
    _run(
        f"iptables -t mangle -A PREROUTING -i {WG_IFACE} -s {ip_addr}/32 "
        f"-j MARK --set-mark {fwmark}"
    )


def remove_destination_routing(user_ip: str, fwmark: int):
    ip_addr = user_ip.split("/")[0]
    _run(
        f"iptables -t mangle -D PREROUTING -i {WG_IFACE} -s {ip_addr}/32 "
        f"-j MARK --set-mark {fwmark}",
        check=False,
    )


def setup_nat_for_destination(dest_interface: str):
    """Set up NAT masquerade for a destination VPN interface."""
    _run(
        f"iptables -t nat -A POSTROUTING -o {dest_interface} -j MASQUERADE"
    )


def setup_ip_rule(fwmark: int, table: int):
    """Add ip rule for policy routing."""
    _run(f"ip rule add fwmark {fwmark} table {table}", check=False)


def setup_default_route(table: int, dest_interface: str):
    """Set default route in routing table for destination VPN."""
    _run(f"ip route add default dev {dest_interface} table {table}", check=False)


# ─── Init / Cleanup ─────────────────────────────────────────

def initialize_logging_for_all(db_session):
    """Enable connection logging for all enabled users."""
    from app.models.user import User
    users = db_session.query(User).filter(User.enabled == True).all()  # noqa: E712
    for user in users:
        enable_connection_logging(user.id, user.assigned_ip)
    logger.info(f"Enabled logging for {len(users)} users")
