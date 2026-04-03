"""
Traffic Control Service

Uses Linux tc (traffic control) with HTB qdiscs to enforce per-user speed limits.
Egress limiting on wg0, ingress limiting via IFB device.
"""
import logging
import subprocess

from app.config import settings
from app.core.validators import validate_ip, validate_interface

logger = logging.getLogger(__name__)

WG_IFACE = validate_interface(settings.wg_interface)
IFB_IFACE = "ifb0"


def _run(cmd: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run a command as a list (no shell). Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=10
    )
    if check and result.returncode != 0:
        logger.warning(f"tc command failed: {' '.join(cmd)} -> {result.stderr.strip()}")
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _ip_to_classid(ip: str) -> int:
    """Convert IP's last octet to a tc class ID (2-254)."""
    last_octet = int(ip.split("/")[0].split(".")[-1])
    return max(2, last_octet)


def initialize():
    """Set up root qdiscs on wg interface and IFB device.
    Called once at startup.
    """
    logger.info("Initializing traffic control...")

    # Clean existing rules
    _run(["tc", "qdisc", "del", "dev", WG_IFACE, "root"], check=False)
    _run(["tc", "qdisc", "del", "dev", WG_IFACE, "ingress"], check=False)
    _run(["tc", "qdisc", "del", "dev", IFB_IFACE, "root"], check=False)

    # --- Egress (server -> user = download for user) ---
    _run(["tc", "qdisc", "add", "dev", WG_IFACE, "root", "handle", "1:", "htb", "default", "9999"])
    _run(["tc", "class", "add", "dev", WG_IFACE, "parent", "1:", "classid", "1:1", "htb", "rate", "10gbit"])
    # Default class - unlimited
    _run(["tc", "class", "add", "dev", WG_IFACE, "parent", "1:1", "classid", "1:9999", "htb", "rate", "10gbit"])

    # --- Ingress (user -> server = upload for user) via IFB ---
    _run(["modprobe", "ifb", "numifbs=1"], check=False)
    _run(["ip", "link", "set", "dev", IFB_IFACE, "up"], check=False)

    # Redirect wg0 ingress to ifb0
    _run(["tc", "qdisc", "add", "dev", WG_IFACE, "handle", "ffff:", "ingress"])
    _run([
        "tc", "filter", "add", "dev", WG_IFACE, "parent", "ffff:", "protocol", "ip", "u32",
        "match", "u32", "0", "0", "action", "mirred", "egress", "redirect", "dev", IFB_IFACE,
    ])

    _run(["tc", "qdisc", "add", "dev", IFB_IFACE, "root", "handle", "1:", "htb", "default", "9999"])
    _run(["tc", "class", "add", "dev", IFB_IFACE, "parent", "1:", "classid", "1:1", "htb", "rate", "10gbit"])
    _run(["tc", "class", "add", "dev", IFB_IFACE, "parent", "1:1", "classid", "1:9999", "htb", "rate", "10gbit"])

    logger.info("Traffic control initialized")


def apply_speed_limit(user_ip: str, down_kbps: int | None, up_kbps: int | None):
    """Apply speed limit for a user. Pass None to remove limit."""
    ip_addr = validate_ip(user_ip.split("/")[0])
    classid = _ip_to_classid(user_ip)

    if down_kbps:
        rate = f"{int(down_kbps)}kbit"
        cid = str(classid)
        handle = f"{classid}0:"
        # Remove existing class if any
        _run(["tc", "class", "del", "dev", WG_IFACE, "classid", f"1:{cid}"], check=False)
        _run(["tc", "class", "add", "dev", WG_IFACE, "parent", "1:1", "classid", f"1:{cid}", "htb", "rate", rate, "ceil", rate])
        # Add FQ-CoDel for fairness
        _run(["tc", "qdisc", "del", "dev", WG_IFACE, "parent", f"1:{cid}"], check=False)
        _run(["tc", "qdisc", "add", "dev", WG_IFACE, "parent", f"1:{cid}", "handle", handle, "fq_codel"])
        # Filter: match destination IP
        _run([
            "tc", "filter", "del", "dev", WG_IFACE, "parent", "1:", "protocol", "ip", "prio", "1", "u32",
            "match", "ip", "dst", f"{ip_addr}/32", "classid", f"1:{cid}",
        ], check=False)
        _run([
            "tc", "filter", "add", "dev", WG_IFACE, "parent", "1:", "protocol", "ip", "prio", "1", "u32",
            "match", "ip", "dst", f"{ip_addr}/32", "classid", f"1:{cid}",
        ])
        logger.info(f"Applied download limit {rate} for {ip_addr}")
    else:
        remove_speed_limit_download(user_ip)

    if up_kbps:
        rate = f"{int(up_kbps)}kbit"
        cid = str(classid)
        handle = f"{classid}0:"
        _run(["tc", "class", "del", "dev", IFB_IFACE, "classid", f"1:{cid}"], check=False)
        _run(["tc", "class", "add", "dev", IFB_IFACE, "parent", "1:1", "classid", f"1:{cid}", "htb", "rate", rate, "ceil", rate])
        _run(["tc", "qdisc", "del", "dev", IFB_IFACE, "parent", f"1:{cid}"], check=False)
        _run(["tc", "qdisc", "add", "dev", IFB_IFACE, "parent", f"1:{cid}", "handle", handle, "fq_codel"])
        _run([
            "tc", "filter", "del", "dev", IFB_IFACE, "parent", "1:", "protocol", "ip", "prio", "1", "u32",
            "match", "ip", "src", f"{ip_addr}/32", "classid", f"1:{cid}",
        ], check=False)
        _run([
            "tc", "filter", "add", "dev", IFB_IFACE, "parent", "1:", "protocol", "ip", "prio", "1", "u32",
            "match", "ip", "src", f"{ip_addr}/32", "classid", f"1:{cid}",
        ])
        logger.info(f"Applied upload limit {rate} for {ip_addr}")
    else:
        remove_speed_limit_upload(user_ip)


def remove_speed_limit_download(user_ip: str):
    ip_addr = validate_ip(user_ip.split("/")[0])
    classid = _ip_to_classid(user_ip)
    cid = str(classid)
    _run([
        "tc", "filter", "del", "dev", WG_IFACE, "parent", "1:", "protocol", "ip", "prio", "1", "u32",
        "match", "ip", "dst", f"{ip_addr}/32", "classid", f"1:{cid}",
    ], check=False)
    _run(["tc", "qdisc", "del", "dev", WG_IFACE, "parent", f"1:{cid}"], check=False)
    _run(["tc", "class", "del", "dev", WG_IFACE, "classid", f"1:{cid}"], check=False)


def remove_speed_limit_upload(user_ip: str):
    ip_addr = validate_ip(user_ip.split("/")[0])
    classid = _ip_to_classid(user_ip)
    cid = str(classid)
    _run([
        "tc", "filter", "del", "dev", IFB_IFACE, "parent", "1:", "protocol", "ip", "prio", "1", "u32",
        "match", "ip", "src", f"{ip_addr}/32", "classid", f"1:{cid}",
    ], check=False)
    _run(["tc", "qdisc", "del", "dev", IFB_IFACE, "parent", f"1:{cid}"], check=False)
    _run(["tc", "class", "del", "dev", IFB_IFACE, "classid", f"1:{cid}"], check=False)


def remove_speed_limit(user_ip: str):
    """Remove all speed limits for a user."""
    remove_speed_limit_download(user_ip)
    remove_speed_limit_upload(user_ip)
    logger.info(f"Removed speed limits for {user_ip}")


def rebuild_all(db_session):
    """Rebuild all tc rules from DB. Called at startup."""
    from app.models.user import User

    initialize()

    users = db_session.query(User).filter(
        User.enabled == True,  # noqa: E712
    ).all()

    for user in users:
        if user.speed_limit_down or user.speed_limit_up:
            apply_speed_limit(user.assigned_ip, user.speed_limit_down, user.speed_limit_up)

    logger.info(f"Rebuilt tc rules for {len(users)} users")


def cleanup():
    """Remove all tc rules. Called at shutdown."""
    _run(["tc", "qdisc", "del", "dev", WG_IFACE, "root"], check=False)
    _run(["tc", "qdisc", "del", "dev", WG_IFACE, "ingress"], check=False)
    _run(["tc", "qdisc", "del", "dev", IFB_IFACE, "root"], check=False)
    logger.info("Traffic control cleaned up")
