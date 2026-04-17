"""
Connection Logger Service

Reads kernel log entries (iptables LOG) and logs connection details to the database.
Also sniffs DNS responses to map IPs to hostnames.
"""
import re
import logging
import subprocess
import threading
import time
from datetime import datetime, timezone
from collections import deque

from app.database import SessionLocal
from app.models.connection_log import ConnectionLog

logger = logging.getLogger(__name__)

# Buffer for batch inserts (visited + general connections only)
# Blocked requests are handled by blocked_logger.py
_log_buffer: deque[dict] = deque(maxlen=10000)
_buffer_lock = threading.Lock()
_running = False

# DNS mapping: IP -> hostname (populated by DNS sniffer)
_dns_map: dict[str, str] = {}
_dns_map_lock = threading.Lock()


def _parse_log_line(line: str) -> tuple[dict | None, str]:
    """Parse a kernel log line with our LOG prefix.

    Returns (parsed_dict, log_type) where log_type is:
      - "visited" for wl_visit:X: lines (allowed by whitelist)
      - "blocked" for bl_drop:X: lines (blocked by blacklist/wildcard)
      - "connection" for user:X: lines (general connection log from FORWARD)
    """
    # Check for blocked traffic first (bl_drop:X:)
    bl_match = re.search(r'bl_drop:(\d+):', line)
    if bl_match:
        entry = _extract_fields(bl_match, line)
        return entry, "blocked"

    # Check for whitelisted visited traffic (wl_visit:X:)
    wl_match = re.search(r'wl_visit:(\d+):', line)
    if wl_match:
        entry = _extract_fields(wl_match, line)
        return entry, "visited"

    # General connection log (user:X:) from FORWARD chain
    user_match = re.search(r'user:(\d+):', line)
    if user_match:
        entry = _extract_fields(user_match, line)
        return entry, "connection"

    return None, ""


def _extract_fields(match, line: str) -> dict | None:
    """Extract common fields from a kernel log line."""
    user_id = int(match.group(1))

    src = re.search(r'SRC=(\S+)', line)
    dst = re.search(r'DST=(\S+)', line)
    proto = re.search(r'PROTO=(\S+)', line)
    dpt = re.search(r'DPT=(\d+)', line)

    if not src or not dst:
        return None

    return {
        "user_id": user_id,
        "source_ip": src.group(1),
        "dest_ip": dst.group(1),
        "protocol": proto.group(1).lower() if proto else None,
        "dest_port": int(dpt.group(1)) if dpt else None,
        "started_at": datetime.now(timezone.utc),
    }


def _get_hostname(ip: str) -> str | None:
    """Look up hostname from DNS sniffer cache, then IP→domain map from iptables."""
    # 1. DNS sniffer cache (captures live DNS queries)
    with _dns_map_lock:
        hostname = _dns_map.get(ip)
    if hostname:
        return hostname

    # 2. IP→domain map from iptables setup (always available for wl/bl entries)
    try:
        from app.services.iptables import get_ip_domain_map
        ip_map = get_ip_domain_map()
        return ip_map.get(ip)
    except Exception:
        return None


def get_hostname(ip: str) -> str | None:
    """Public API: look up hostname."""
    return _get_hostname(ip)


def _dns_sniffer_thread():
    """Sniff DNS queries on wg0 to build IP->hostname mapping.

    Captures DNS queries (dst port 53) from users, extracts the queried domain,
    resolves it ourselves, and maps all resulting IPs to the domain.
    """
    global _running
    import struct

    def _parse_dns_query(data: bytes) -> str | None:
        """Parse a raw DNS query packet to extract the queried domain."""
        if len(data) < 12:
            return None

        flags = struct.unpack(">H", data[2:4])[0]
        is_response = (flags >> 15) & 1
        if is_response:
            return None  # We only want queries

        qdcount = struct.unpack(">H", data[4:6])[0]
        if qdcount == 0:
            return None

        # Parse question section
        idx = 12
        domain_parts = []
        while idx < len(data) and data[idx] != 0:
            if data[idx] & 0xC0 == 0xC0:
                idx += 2
                break
            length = data[idx]
            idx += 1
            if idx + length > len(data):
                return None
            domain_parts.append(data[idx:idx + length].decode('ascii', errors='ignore'))
            idx += length

        if not domain_parts:
            return None

        domain = ".".join(domain_parts)

        # Check QTYPE (2 bytes after null terminator)
        idx += 1  # skip null
        if idx + 2 <= len(data):
            qtype = struct.unpack(">H", data[idx:idx + 2])[0]
            # Only process A (1) and AAAA (28) queries
            if qtype not in (1, 28):
                return None

        return domain

    # Track recently resolved domains to avoid re-resolving
    _resolved_cache: dict[str, float] = {}  # domain -> timestamp
    CACHE_TTL = 300  # 5 minutes

    try:
        # Capture DNS queries as raw pcap
        proc = subprocess.Popen(
            ["tcpdump", "-i", "wg0", "-n", "-U", "-w", "-", "udp and dst port 53"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        logger.info("DNS sniffer started on wg0 (query capture mode)")

        # Read pcap global header (24 bytes)
        pcap_header = proc.stdout.read(24)
        if not pcap_header or len(pcap_header) < 24:
            logger.error("DNS sniffer: failed to read pcap header")
            return

        while _running:
            pkt_header = proc.stdout.read(16)
            if not pkt_header or len(pkt_header) < 16:
                if proc.poll() is not None:
                    logger.warning("DNS sniffer process exited, restarting...")
                    time.sleep(2)
                    proc = subprocess.Popen(
                        ["tcpdump", "-i", "wg0", "-n", "-U", "-w", "-", "udp and dst port 53"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        bufsize=0,
                    )
                    pcap_header = proc.stdout.read(24)
                    continue
                time.sleep(0.1)
                continue

            _, _, incl_len, _ = struct.unpack("<IIII", pkt_header)
            pkt_data = proc.stdout.read(incl_len)
            if not pkt_data or len(pkt_data) < incl_len:
                continue

            # Raw IP packet (no ethernet on wg0)
            if len(pkt_data) < 20:
                continue
            ihl = (pkt_data[0] & 0x0F) * 4
            if len(pkt_data) < ihl + 8:
                continue

            dns_data = pkt_data[ihl + 8:]  # Skip IP + UDP headers
            domain = _parse_dns_query(dns_data)
            if not domain:
                continue

            # Skip infrastructure
            if domain.endswith(('.arpa', '.local', '.internal')):
                continue

            # Skip if recently resolved
            now = time.time()
            if domain in _resolved_cache and (now - _resolved_cache[domain]) < CACHE_TTL:
                continue

            _resolved_cache[domain] = now

            # Clean old cache entries
            if len(_resolved_cache) > 5000:
                cutoff = now - CACHE_TTL
                _resolved_cache.clear()

            # Resolve domain to IPs using dig
            try:
                from app.core.validators import resolve_all_ips
                ips = resolve_all_ips(domain)
                if ips:
                    with _dns_map_lock:
                        for ip in ips:
                            _dns_map[ip] = domain
                        # Keep cache reasonable
                        if len(_dns_map) > 50000:
                            keys = list(_dns_map.keys())
                            for k in keys[:25000]:
                                del _dns_map[k]
            except Exception:
                pass

        proc.terminate()
    except Exception as e:
        logger.error(f"DNS sniffer error: {e}")


def _flush_buffer():
    """Flush the log buffer (visited + general connections) to the database.

    Note: Blocked requests are handled by blocked_logger.py separately.
    """
    with _buffer_lock:
        conn_entries = list(_log_buffer)
        _log_buffer.clear()

    if not conn_entries:
        return

    db = SessionLocal()
    try:
        for entry in conn_entries:
            hostname = _get_hostname(entry["dest_ip"])
            log = ConnectionLog(
                user_id=entry["user_id"],
                source_ip=entry["source_ip"],
                dest_ip=entry["dest_ip"],
                dest_hostname=hostname,
                dest_port=entry["dest_port"],
                protocol=entry["protocol"],
                started_at=entry["started_at"],
            )
            db.add(log)

        db.commit()
        logger.info(f"Flushed {len(conn_entries)} connection log entries")
    except Exception as e:
        logger.error(f"Failed to flush connection logs: {e}")
        db.rollback()
    finally:
        db.close()


def _ulog_reader_thread():
    """Read kernel log entries using journalctl for reliable output."""
    global _running

    try:
        # Use journalctl to follow kernel messages - bypasses rate limiting
        proc = subprocess.Popen(
            ["journalctl", "-k", "-f", "-o", "short", "--no-pager", "--since=now"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        logger.info("Connection logger using journalctl -k")

        while _running:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    logger.warning("journalctl process exited, restarting...")
                    time.sleep(1)
                    proc = subprocess.Popen(
                        ["journalctl", "-k", "-f", "-o", "short", "--no-pager", "--since=now"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        bufsize=1,
                    )
                    continue
                time.sleep(0.1)
                continue

            # Only process wl_visit (visited) and user (general connection) lines
            # bl_drop (blocked) is handled by blocked_logger.py
            if "wl_visit:" not in line and "user:" not in line:
                continue

            entry, log_type = _parse_log_line(line)
            if entry and log_type in ("visited", "connection"):
                with _buffer_lock:
                    _log_buffer.append(entry)

        proc.terminate()
    except Exception as e:
        logger.error(f"Connection logger error: {e}")


def start():
    """Start the connection logger background threads."""
    global _running
    if _running:
        return

    _running = True

    # Start kernel log reader
    thread = threading.Thread(target=_ulog_reader_thread, daemon=True)
    thread.start()

    # Start DNS sniffer
    dns_thread = threading.Thread(target=_dns_sniffer_thread, daemon=True)
    dns_thread.start()

    logger.info("Connection logger started")


def stop():
    """Stop the connection logger."""
    global _running
    _running = False
    _flush_buffer()
    logger.info("Connection logger stopped")


def flush():
    """Manual flush trigger (called by scheduler)."""
    _flush_buffer()
