"""Audit logging service for admin actions."""
import logging
from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.models.admin_audit_log import AdminAuditLog
from app.core.device_detector import format_device_info

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    admin: Admin,
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    details: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Log an admin action with optional device info."""
    device_info = format_device_info(user_agent) if user_agent else None

    entry = AdminAuditLog(
        admin_id=admin.id,
        admin_username=admin.username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=device_info,
    )
    db.add(entry)
    # Don't commit - let the caller's transaction handle it
