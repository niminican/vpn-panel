from datetime import datetime

from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConnectionLog(Base):
    __tablename__ = "connection_logs"
    __table_args__ = (
        Index("idx_connlog_user_time", "user_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dest_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dest_hostname: Mapped[str | None] = mapped_column(String(255))
    dest_port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str | None] = mapped_column(String(10))  # tcp/udp/icmp
    bytes_sent: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_received: Mapped[int] = mapped_column(BigInteger, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
