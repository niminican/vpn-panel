from datetime import datetime

from sqlalchemy import String, Text, DateTime, Boolean, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Package assignment
    package_id: Mapped[int | None] = mapped_column(ForeignKey("packages.id", ondelete="SET NULL"))
    package: Mapped["Package | None"] = relationship("Package")

    # Destination VPN assignment
    destination_vpn_id: Mapped[int | None] = mapped_column(ForeignKey("destination_vpns.id", ondelete="SET NULL"))
    destination_vpn: Mapped["DestinationVPN | None"] = relationship("DestinationVPN", back_populates="users")

    # WireGuard identity
    wg_private_key: Mapped[str] = mapped_column(Text, nullable=False)  # encrypted at rest
    wg_public_key: Mapped[str] = mapped_column(String(44), nullable=False)
    wg_preshared_key: Mapped[str | None] = mapped_column(Text)
    assigned_ip: Mapped[str] = mapped_column(String(18), unique=True, nullable=False)

    # Bandwidth limits (bytes, NULL = unlimited)
    bandwidth_limit_up: Mapped[int | None] = mapped_column(BigInteger)
    bandwidth_limit_down: Mapped[int | None] = mapped_column(BigInteger)
    bandwidth_used_up: Mapped[int] = mapped_column(BigInteger, default=0)
    bandwidth_used_down: Mapped[int] = mapped_column(BigInteger, default=0)
    bandwidth_reset_day: Mapped[int | None] = mapped_column(Integer)  # day of month 1-28

    # Speed limits (kbps, NULL = unlimited)
    speed_limit_up: Mapped[int | None] = mapped_column(Integer)
    speed_limit_down: Mapped[int | None] = mapped_column(Integer)

    # Concurrent connections
    max_connections: Mapped[int] = mapped_column(Integer, default=1)

    # Expiry
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime)

    # Alerts
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_threshold: Mapped[int] = mapped_column(Integer, default=80)  # percentage
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Custom config overrides (NULL = use defaults from settings)
    config_dns: Mapped[str | None] = mapped_column(String(200))  # custom DNS servers
    config_allowed_ips: Mapped[str | None] = mapped_column(String(500))  # custom AllowedIPs
    config_endpoint: Mapped[str | None] = mapped_column(String(200))  # custom Endpoint
    config_mtu: Mapped[int | None] = mapped_column(Integer)  # custom MTU
    config_keepalive: Mapped[int | None] = mapped_column(Integer)  # PersistentKeepalive

    # Telegram
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_username: Mapped[str | None] = mapped_column(String(100))
    telegram_link_code: Mapped[str | None] = mapped_column(String(20), unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    whitelist_entries: Mapped[list["UserWhitelist"]] = relationship("UserWhitelist", back_populates="user", cascade="all, delete-orphan")
    schedules: Mapped[list["UserSchedule"]] = relationship("UserSchedule", back_populates="user", cascade="all, delete-orphan")
    active_sessions: Mapped[list["ActiveSession"]] = relationship("ActiveSession", back_populates="user", cascade="all, delete-orphan")
