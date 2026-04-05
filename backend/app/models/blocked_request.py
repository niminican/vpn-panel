"""Blocked request log - tracks packets dropped by blacklist rules."""
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BlockedRequest(Base):
    __tablename__ = "blocked_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    dest_ip: Mapped[str] = mapped_column(String(45))
    dest_hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dest_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(10), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=1)  # aggregate count
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", backref="blocked_requests")
