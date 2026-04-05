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
    resolve_all_ips,
)

logger = logging.getLogger(__name__)

WG_IFACE = validate_interface(settings.wg_interface)

# IP → domain mapping populated during whitelist/blacklist setup
# Used by connection_logger to resolve hostnames without DNS sniffer
_ip_domain_map: dict[str, str] = {}

def get_ip_domain_map() -> dict[str, str]:
    """Get the IP→domain mapping (used by connection_logger)."""
    return _ip_domain_map


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

def setup_user_whitelist(user_id: int, user_ip: str, entries: list[dict], has_blacklist_wildcard: bool = False):
    """Create per-user iptables chain with whitelist rules.

    Pre-resolves all DNS (slow part) before touching iptables,
    then flush-and-rebuild chain in-place (fast, milliseconds).
    """
    chain = _chain_name(user_id)
    ip_addr = validate_ip(user_ip.split("/")[0])

    if not entries:
        remove_user_whitelist(user_id, user_ip)
        return

    # ── Phase 1: Pre-resolve all DNS (slow, but no iptables touched) ──
    resolved_entries = []
    for entry in entries:
        all_ips = resolve_all_ips(entry["address"])
        if not all_ips:
            try:
                all_ips = [validate_address(entry["address"])]
            except Exception:
                logger.warning(f"Cannot resolve whitelist address: {entry['address']}")
                continue
        # Store IP→domain mapping for hostname resolution
        for ip in all_ips:
            _ip_domain_map[ip] = entry["address"]
        resolved_entries.append({
            "ips": all_ips,
            "port": entry.get("port"),
            "protocol": entry.get("protocol"),
        })

    if not resolved_entries:
        logger.warning(f"No resolvable whitelist entries for user {user_id}")
        return

    # ── Phase 2: Fast iptables rebuild (no DNS delays) ──
    # Clean up any leftover temp chains from previous failed attempts
    temp_chain = f"{chain}_new"
    if _chain_exists(temp_chain):
        _run(["iptables", "-F", temp_chain], check=False)
        _run(["iptables", "-X", temp_chain], check=False)

    # Create or flush chain
    if _chain_exists(chain):
        _run(["iptables", "-F", chain])
    else:
        validate_chain_name(chain)
        rc, _, err = _run(["iptables", "-N", chain])
        if rc != 0:
            logger.error(f"Failed to create chain {chain}: {err}")
            return

    # Ensure FORWARD jump exists (use -C to check)
    rc, _, _ = _run(["iptables", "-C", "FORWARD", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", chain], check=False)
    if rc != 0:
        _run(["iptables", "-I", "FORWARD", "1", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", chain])

    # Build chain rules (all fast - DNS already resolved)
    _run(["iptables", "-A", chain, "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"])
    _run(["iptables", "-A", chain, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
    _run(["iptables", "-A", chain, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"])

    log_prefix = f"wl_visit:{int(user_id)}: "
    for re_entry in resolved_entries:
        for dest_ip in re_entry["ips"]:
            match_args = []
            if re_entry.get("protocol") and re_entry["protocol"] != "any":
                proto = validate_protocol(re_entry["protocol"])
                match_args.extend(["-p", proto])
            match_args.extend(["-d", dest_ip])
            if re_entry.get("port"):
                proto = re_entry.get("protocol", "tcp")
                if proto == "any":
                    proto = "tcp"
                proto = validate_protocol(proto)
                port = validate_port(int(re_entry["port"]))
                match_args.extend(["-p", proto, "--dport", str(port)])

            _run(["iptables", "-A", chain] + match_args + [
                "-m", "conntrack", "--ctstate", "NEW",
                "-j", "LOG", "--log-prefix", log_prefix, "--log-level", "4"])
            _run(["iptables", "-A", chain] + match_args + ["-j", "ACCEPT"])

    if has_blacklist_wildcard:
        _run(["iptables", "-A", chain, "-m", "limit", "--limit", "10/sec", "--limit-burst", "50",
              "-j", "LOG", "--log-prefix", f"bl_drop:{user_id}: ", "--log-level", "4"])

    _run(["iptables", "-A", chain, "-j", "DROP"])

    logger.info(f"Set up whitelist for user {user_id} with {len(resolved_entries)} entries (bl_wildcard={has_blacklist_wildcard})")


def remove_user_whitelist(user_id: int, user_ip: str):
    """Remove per-user whitelist chain (and any temp chain)."""
    chain = _chain_name(user_id)
    ip_addr = validate_ip(user_ip.split("/")[0])

    for ch in [chain, f"{chain}_new"]:
        # Remove ALL FORWARD jumps to this chain
        for _ in range(20):
            rc, _, _ = _run(["iptables", "-D", "FORWARD", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", ch], check=False)
            if rc != 0:
                break
        # Flush and delete chain if it exists
        if _chain_exists(ch):
            _run(["iptables", "-F", ch], check=False)
            _run(["iptables", "-X", ch], check=False)

    logger.info(f"Removed whitelist for user {user_id}")


# ─── Blacklist ──────────────────────────────────────────────

def setup_user_blacklist(user_id: int, user_ip: str, bl_entries: list[dict], wl_entries: list[dict] | None = None):
    """Create per-user blacklist chain.

    Pre-resolves all DNS first, then flush-and-rebuild chain in-place.
    """
    chain = f"vpn_bl_{int(user_id)}"
    ip_addr = validate_ip(user_ip.split("/")[0])

    if not bl_entries:
        remove_user_blacklist(user_id, user_ip)
        return

    has_wildcard = any(e["address"] == "*" for e in bl_entries)

    # ── Phase 1: Pre-resolve all DNS (slow, no iptables touched) ──
    resolved_bl = []
    for entry in bl_entries:
        if entry["address"] == "*":
            resolved_bl.append({"ips": ["*"], "port": entry.get("port"), "protocol": entry.get("protocol")})
            continue
        all_ips = resolve_all_ips(entry["address"])
        if not all_ips:
            try:
                all_ips = [validate_address(entry["address"])]
            except Exception:
                logger.warning(f"Cannot resolve blacklist address: {entry['address']}")
                continue
        for ip in all_ips:
            _ip_domain_map[ip] = entry["address"]
        resolved_bl.append({"ips": all_ips, "port": entry.get("port"), "protocol": entry.get("protocol")})

    resolved_wl = []
    if wl_entries:
        for entry in wl_entries:
            all_ips = resolve_all_ips(entry["address"])
            if not all_ips:
                try:
                    all_ips = [validate_address(entry["address"])]
                except Exception:
                    continue
            for ip in all_ips:
                _ip_domain_map[ip] = entry["address"]
            resolved_wl.append({"ips": all_ips, "port": entry.get("port"), "protocol": entry.get("protocol")})

    # ── Phase 2: Fast iptables rebuild ──
    # Clean up any leftover temp chains
    temp_chain = f"{chain}_new"
    if _chain_exists(temp_chain):
        _run(["iptables", "-F", temp_chain], check=False)
        _run(["iptables", "-X", temp_chain], check=False)

    # Create or flush chain
    if _chain_exists(chain):
        _run(["iptables", "-F", chain])
    else:
        validate_chain_name(chain)
        rc, _, err = _run(["iptables", "-N", chain])
        if rc != 0:
            logger.error(f"Failed to create chain {chain}: {err}")
            return

    # Ensure FORWARD jump exists
    rc, _, _ = _run(["iptables", "-C", "FORWARD", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", chain], check=False)
    if rc != 0:
        _run(["iptables", "-I", "FORWARD", "1", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", chain])

    # Allow established/related first
    _run(["iptables", "-A", chain, "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"])

    if has_wildcard:
        _run(["iptables", "-A", chain, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
        _run(["iptables", "-A", chain, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"])
        if resolved_wl:
            for re_entry in resolved_wl:
                for dest_ip in re_entry["ips"]:
                    cmd = ["iptables", "-A", chain]
                    if re_entry.get("protocol") and re_entry["protocol"] != "any":
                        proto = validate_protocol(re_entry["protocol"])
                        cmd.extend(["-p", proto])
                    cmd.extend(["-d", dest_ip])
                    if re_entry.get("port"):
                        proto = re_entry.get("protocol", "tcp")
                        if proto == "any":
                            proto = "tcp"
                        proto = validate_protocol(proto)
                        port = validate_port(int(re_entry["port"]))
                        cmd.extend(["-p", proto, "--dport", str(port)])
                    cmd.extend(["-j", "ACCEPT"])
                    _run(cmd)
        _run(["iptables", "-A", chain, "-m", "limit", "--limit", "10/sec", "--limit-burst", "50",
              "-j", "LOG", "--log-prefix", f"bl_drop:{user_id}: ", "--log-level", "4"])
        _run(["iptables", "-A", chain, "-j", "DROP"])
    else:
        for re_entry in resolved_bl:
            for dest_ip in re_entry["ips"]:
                cmd = ["iptables", "-A", chain]
                if re_entry.get("protocol") and re_entry["protocol"] != "any":
                    proto = validate_protocol(re_entry["protocol"])
                    cmd.extend(["-p", proto])
                cmd.extend(["-d", dest_ip])
                if re_entry.get("port"):
                    proto = re_entry.get("protocol", "tcp")
                    if proto == "any":
                        proto = "tcp"
                    proto = validate_protocol(proto)
                    port = validate_port(int(re_entry["port"]))
                    cmd.extend(["-p", proto, "--dport", str(port)])
                cmd.extend(["-j", "DROP"])
                _run(cmd)

    logger.info(f"Set up blacklist for user {user_id} with {len(bl_entries)} entries (wildcard={'yes' if has_wildcard else 'no'})")


def remove_user_blacklist(user_id: int, user_ip: str):
    """Remove per-user blacklist chain (and any temp chain)."""
    chain = f"vpn_bl_{int(user_id)}"
    ip_addr = validate_ip(user_ip.split("/")[0])

    for ch in [chain, f"{chain}_new"]:
        # Remove ALL FORWARD jumps to this chain
        for _ in range(20):
            rc, _, _ = _run(["iptables", "-D", "FORWARD", "-i", WG_IFACE, "-s", f"{ip_addr}/32", "-j", ch], check=False)
            if rc != 0:
                break
        # Flush and delete chain if it exists
        if _chain_exists(ch):
            _run(["iptables", "-F", ch], check=False)
            _run(["iptables", "-X", ch], check=False)

    logger.info(f"Removed blacklist for user {user_id}")


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
    """Enable FORWARD chain connection logging for users WITHOUT firewall chains.

    Users with whitelist/blacklist chains already have wl_visit/bl_drop LOGs
    inside their chain — no need for the FORWARD LOG (which would double-count).
    """
    from app.models.user import User
    from app.models.whitelist import UserWhitelist
    from app.models.blacklist import UserBlacklist

    users = db_session.query(User).filter(User.enabled == True).all()  # noqa: E712

    # Find users that have whitelist or blacklist entries
    wl_user_ids = {r[0] for r in db_session.query(UserWhitelist.user_id).distinct().all()}
    bl_user_ids = {r[0] for r in db_session.query(UserBlacklist.user_id).distinct().all()}
    firewall_user_ids = wl_user_ids | bl_user_ids

    enabled_count = 0
    skipped_count = 0
    for user in users:
        if user.id in firewall_user_ids:
            # User has firewall chains with built-in wl_visit/bl_drop LOGs
            # Remove any existing FORWARD LOG to avoid double-counting
            disable_connection_logging(user.id, user.assigned_ip)
            skipped_count += 1
        else:
            # No firewall chain — use FORWARD LOG for general connection logging
            enable_connection_logging(user.id, user.assigned_ip)
            enabled_count += 1

    logger.info(f"Connection logging: {enabled_count} enabled, {skipped_count} skipped (have firewall chains)")
