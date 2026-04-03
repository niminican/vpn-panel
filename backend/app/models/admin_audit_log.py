from datetime import datetime

from sqlalchemy import String, Text, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminAuditLog(Base):
    """Logs all admin actions for accountability."""
    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("idx_audit_admin_time", "admin_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_username: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. create_user, delete_user, login
    resource_type: Mapped[str | None] = mapped_column(String(50))  # e.g. user, destination, admin
    resource_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)  # JSON or free text
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)  # Raw User-Agent string
    device_info: Mapped[str | None] = mapped_column(String(200))  # Parsed: "iPhone (iOS 17.2) Safari"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
