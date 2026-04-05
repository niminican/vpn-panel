from datetime import datetime

from sqlalchemy import String, BigInteger, DateTime, ForeignKey, Index, Integer
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

    # GeoIP info (resolved from client_ip)
    country: Mapped[str | None] = mapped_column(String(100))   # e.g. "Iran"
    country_code: Mapped[str | None] = mapped_column(String(5))  # e.g. "IR"
    city: Mapped[str | None] = mapped_column(String(100))       # e.g. "Tehran"
    isp: Mapped[str | None] = mapped_column(String(200))        # e.g. "Irancell"
    asn: Mapped[int | None] = mapped_column(Integer)            # e.g. 44244

    # OS detection (from TTL fingerprinting)
    os_hint: Mapped[str | None] = mapped_column(String(50))     # e.g. "Windows", "Linux/Android", "macOS/iOS"
    ttl: Mapped[int | None] = mapped_column(Integer)            # raw TTL value observed
