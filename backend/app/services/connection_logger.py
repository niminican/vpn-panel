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

# Buffer for batch inserts
_log_buffer: deque[dict] = deque(maxlen=10000)
_buffer_lock = threading.Lock()
_running = False

# DNS mapping: IP -> hostname (populated by DNS sniffer)
_dns_map: dict[str, str] = {}
_dns_map_lock = threading.Lock()


def _parse_nflog_line(line: str) -> dict | None:
    """Parse a kernel log line with our LOG prefix."""
    # Example: user:2: IN=wg0 ... SRC=10.8.0.2 DST=8.8.8.8 ... PROTO=TCP DPT=443
    match = re.search(r'user:(\d+):', line)
    if not match:
        return None

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
    """Look up hostname from DNS sniffer cache."""
    with _dns_map_lock:
        return _dns_map.get(ip)


def _dns_sniffer_thread():
    """Sniff DNS responses on wg0 to build IP->hostname mapping.

    Uses tcpdump to capture DNS responses and parses the output to extract
    the queried domain and all resolved IPs, mapping each IP to the original domain.
    """
    global _running
    _ip_pattern = re.compile(r'(\d+\.\d+\.\d+\.\d+)')

    try:
        proc = subprocess.Popen(
            ["tcpdump", "-i", "wg0", "-l", "-n", "udp and src port 53", "-vv"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        logger.info("DNS sniffer started on wg0")

        while _running:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    logger.warning("DNS sniffer process exited, restarting...")
                    time.sleep(2)
                    proc = subprocess.Popen(
                        ["tcpdump", "-i", "wg0", "-l", "-n", "udp and src port 53", "-vv"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        bufsize=1,
                    )
                    continue
                time.sleep(0.1)
                continue

            # tcpdump format: ... q: A? domain.com. N/0/0 ... domain.com. A 1.2.3.4, ...
            # Extract the queried domain from "q: A? domain.com."
            q_match = re.search(r'q:\s+(?:A|AAAA)\?\s+(\S+?)\.?\s', line)
            if not q_match:
                continue

            query_domain = q_match.group(1).rstrip('.')

            # Skip DNS infrastructure queries
            if query_domain.endswith(('.arpa', '.local')):
                continue

            # Find all A record IPs in the response line
            # They appear as "domain. A x.x.x.x" patterns
            a_records = re.findall(r'\.\s+A\s+(\d+\.\d+\.\d+\.\d+)', line)

            if a_records:
                with _dns_map_lock:
                    for ip in a_records:
                        _dns_map[ip] = query_domain
                    # Keep cache reasonable size
                    if len(_dns_map) > 50000:
                        keys = list(_dns_map.keys())
                        for k in keys[:25000]:
                            del _dns_map[k]

        proc.terminate()
    except Exception as e:
        logger.error(f"DNS sniffer error: {e}")


def _flush_buffer():
    """Flush the log buffer to the database."""
    with _buffer_lock:
        if not _log_buffer:
            return
        entries = list(_log_buffer)
        _log_buffer.clear()

    if not entries:
        return

    db = SessionLocal()
    try:
        for entry in entries:
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
        logger.debug(f"Flushed {len(entries)} connection log entries")
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

            if "user:" not in line:
                continue

            entry = _parse_nflog_line(line)
            if entry:
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
