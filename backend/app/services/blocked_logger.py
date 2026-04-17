"""
Blocked Request Logger

Reads kernel log entries from iptables LOG (bl_drop prefix) and stores
blocked connection attempts per user. Aggregates by (user, dest_ip) to
avoid storing millions of rows.
"""
import re
import logging
import subprocess
import threading
import time
from datetime import datetime, timezone
from collections import deque

from app.database import SessionLocal
from app.models.blocked_request import BlockedRequest

logger = logging.getLogger(__name__)

_buffer: deque[dict] = deque(maxlen=5000)
_buffer_lock = threading.Lock()
_running = False


def _parse_blocked_line(line: str) -> dict | None:
    """Parse a kernel log line with bl_drop prefix."""
    # Example: bl_drop:3: IN=wg0 ... SRC=10.8.0.4 DST=142.251.41.78 ... PROTO=TCP DPT=443
    match = re.search(r'bl_drop:(\d+):', line)
    if not match:
        return None

    user_id = int(match.group(1))

    dst = re.search(r'DST=(\S+)', line)
    proto = re.search(r'PROTO=(\S+)', line)
    dpt = re.search(r'DPT=(\d+)', line)

    if not dst:
        return None

    return {
        "user_id": user_id,
        "dest_ip": dst.group(1),
        "dest_port": int(dpt.group(1)) if dpt else None,
        "protocol": proto.group(1).lower() if proto else None,
    }


def _journal_reader():
    """Read kernel log via journalctl for bl_drop entries."""
    global _running
    while _running:
        try:
            proc = subprocess.Popen(
                ["journalctl", "-k", "-f", "-o", "short", "--no-pager",
                 "--since=now", "--grep=bl_drop"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for line in proc.stdout:
                if not _running:
                    break
                parsed = _parse_blocked_line(line)
                if parsed:
                    with _buffer_lock:
                        _buffer.append(parsed)
            proc.terminate()
        except Exception as e:
            logger.warning(f"Blocked logger journal reader error: {e}")
            if _running:
                time.sleep(2)


def flush():
    """Flush buffered blocked entries to database (aggregate by user+ip)."""
    with _buffer_lock:
        if not _buffer:
            return
        entries = list(_buffer)
        _buffer.clear()

    if not entries:
        return

    # Aggregate: (user_id, dest_ip, dest_port, protocol) -> count
    agg: dict[tuple, int] = {}
    for e in entries:
        key = (e["user_id"], e["dest_ip"], e.get("dest_port"), e.get("protocol"))
        agg[key] = agg.get(key, 0) + 1

    # Resolve IPs to hostnames using DNS sniffer cache + IP→domain map from iptables
    def _resolve_hostname(ip: str) -> str | None:
        try:
            from app.services.connection_logger import get_hostname
            hostname = get_hostname(ip)
            if hostname:
                return hostname
        except Exception:
            pass
        try:
            from app.services.iptables import get_ip_domain_map
            return get_ip_domain_map().get(ip)
        except Exception:
            return None

    get_hostname = _resolve_hostname

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for (user_id, dest_ip, dest_port, protocol), count in agg.items():
            # Upsert: update count+last_seen if exists, else insert
            existing = db.query(BlockedRequest).filter(
                BlockedRequest.user_id == user_id,
                BlockedRequest.dest_ip == dest_ip,
            ).first()

            hostname = get_hostname(dest_ip) if get_hostname else None

            if existing:
                existing.count += count
                existing.last_seen = now
                if hostname and not existing.dest_hostname:
                    existing.dest_hostname = hostname
                if dest_port and not existing.dest_port:
                    existing.dest_port = dest_port
                if protocol and not existing.protocol:
                    existing.protocol = protocol
            else:
                db.add(BlockedRequest(
                    user_id=user_id,
                    dest_ip=dest_ip,
                    dest_hostname=hostname,
                    dest_port=dest_port,
                    protocol=protocol,
                    count=count,
                    first_seen=now,
                    last_seen=now,
                ))
        db.commit()
    except Exception as e:
        logger.error(f"Blocked logger flush error: {e}")
        db.rollback()
    finally:
        db.close()


def start():
    """Start the blocked request logger."""
    global _running
    if _running:
        return
    _running = True
    t = threading.Thread(target=_journal_reader, daemon=True, name="blocked-logger")
    t.start()
    logger.info("Blocked request logger started")


def stop():
    """Stop the blocked request logger."""
    global _running
    _running = False
