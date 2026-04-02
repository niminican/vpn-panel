"""
Connection Logger Service

Reads NFLOG packets from iptables and logs connection details to the database.
Uses a background thread to continuously read from the NFLOG group.

Falls back to reading /var/log/kern.log if NFLOG Python bindings aren't available.
"""
import re
import logging
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


def _parse_nflog_line(line: str) -> dict | None:
    """Parse a kernel log line with our NFLOG prefix."""
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
            log = ConnectionLog(
                user_id=entry["user_id"],
                source_ip=entry["source_ip"],
                dest_ip=entry["dest_ip"],
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
    """Read from /var/log/kern.log for NFLOG entries (fallback method)."""
    global _running

    log_file = "/var/log/kern.log"
    try:
        with open(log_file, "r") as f:
            # Seek to end
            f.seek(0, 2)

            while _running:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                if "user:" not in line:
                    continue

                entry = _parse_nflog_line(line)
                if entry:
                    with _buffer_lock:
                        _log_buffer.append(entry)
    except FileNotFoundError:
        logger.warning(f"{log_file} not found, trying /var/log/syslog")
        try:
            with open("/var/log/syslog", "r") as f:
                f.seek(0, 2)
                while _running:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    if "user:" not in line:
                        continue
                    entry = _parse_nflog_line(line)
                    if entry:
                        with _buffer_lock:
                            _log_buffer.append(entry)
        except FileNotFoundError:
            logger.error("No kernel log file found for connection logging")
    except Exception as e:
        logger.error(f"Connection logger error: {e}")


def start():
    """Start the connection logger background thread."""
    global _running
    if _running:
        return

    _running = True
    thread = threading.Thread(target=_ulog_reader_thread, daemon=True)
    thread.start()
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
