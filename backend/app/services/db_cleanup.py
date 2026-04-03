"""
Database Cleanup Service

Periodically cleans up old records to prevent unbounded DB growth.
- Connection logs: keep last 30 days
- Bandwidth history: keep last 90 days
- Admin audit logs: keep last 180 days
- User sessions: keep last 90 days
"""
import logging
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.connection_log import ConnectionLog
from app.models.bandwidth import BandwidthHistory
from app.models.admin_audit_log import AdminAuditLog
from app.models.user_session import UserSession

logger = logging.getLogger(__name__)

# Retention periods (days)
CONNECTION_LOG_RETENTION = 30
BANDWIDTH_HISTORY_RETENTION = 90
AUDIT_LOG_RETENTION = 180
SESSION_RETENTION = 90


def cleanup_old_records() -> None:
    """Delete records older than their retention period."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        total_deleted = 0

        # Connection logs (30 days)
        cutoff = now - timedelta(days=CONNECTION_LOG_RETENTION)
        count = db.query(ConnectionLog).filter(ConnectionLog.started_at < cutoff).delete()
        total_deleted += count
        if count:
            logger.info(f"Cleaned up {count} connection log entries older than {CONNECTION_LOG_RETENTION} days")

        # Bandwidth history (90 days)
        cutoff = now - timedelta(days=BANDWIDTH_HISTORY_RETENTION)
        count = db.query(BandwidthHistory).filter(BandwidthHistory.timestamp < cutoff).delete()
        total_deleted += count
        if count:
            logger.info(f"Cleaned up {count} bandwidth history entries older than {BANDWIDTH_HISTORY_RETENTION} days")

        # Audit logs (180 days)
        cutoff = now - timedelta(days=AUDIT_LOG_RETENTION)
        count = db.query(AdminAuditLog).filter(AdminAuditLog.created_at < cutoff).delete()
        total_deleted += count
        if count:
            logger.info(f"Cleaned up {count} audit log entries older than {AUDIT_LOG_RETENTION} days")

        # User sessions (90 days)
        cutoff = now - timedelta(days=SESSION_RETENTION)
        count = db.query(UserSession).filter(UserSession.connected_at < cutoff).delete()
        total_deleted += count
        if count:
            logger.info(f"Cleaned up {count} session entries older than {SESSION_RETENTION} days")

        db.commit()

        if total_deleted:
            logger.info(f"Database cleanup complete: {total_deleted} total records removed")

    except Exception as e:
        logger.error(f"Database cleanup error: {e}")
        db.rollback()
    finally:
        db.close()
