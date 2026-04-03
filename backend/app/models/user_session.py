from datetime import datetime

from sqlalchemy import String, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserSession(Base):
    """Tracks individual VPN connection sessions per user."""
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_session_user_time", "user_id", "connected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(50))  # real IP:port from WireGuard
    client_ip: Mapped[str | None] = mapped_column(String(45))  # parsed IP (without port)
    connected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime)
    bytes_sent: Mapped[int] = mapped_column(BigInteger, default=0)  # server->client (download)
    bytes_received: Mapped[int] = mapped_column(BigInteger, default=0)  # client->server (upload)
