"""ProxyUser model — a user's proxy account linked to an inbound."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, BigInteger, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProxyUser(Base):
    __tablename__ = "proxy_users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Link to main User
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user: Mapped["User"] = relationship("User", backref="proxy_accounts")

    # Link to Inbound
    inbound_id: Mapped[int] = mapped_column(ForeignKey("inbounds.id", ondelete="CASCADE"), nullable=False)
    inbound: Mapped["Inbound"] = relationship("Inbound", back_populates="proxy_users")

    # Credentials (protocol-dependent)
    uuid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # Used by: VLESS, VMess
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Used by: Trojan, Shadowsocks, HTTP, SOCKS
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    # Used by Xray for stats tracking — typically "username@inbound_tag"

    # VLESS-specific
    flow: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g. "xtls-rprx-vision"

    # Shadowsocks-specific
    method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g. "aes-256-gcm", "chacha20-ietf-poly1305", "2022-blake3-aes-256-gcm"

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Traffic tracking (bytes)
    traffic_up: Mapped[int] = mapped_column(BigInteger, default=0)
    traffic_down: Mapped[int] = mapped_column(BigInteger, default=0)
    traffic_limit: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # NULL = unlimited

    # Expiry
    expire_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
