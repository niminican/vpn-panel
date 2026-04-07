"""Inbound model — defines a proxy listener (port + protocol + transport)."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Inbound(Base):
    __tablename__ = "inbounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    # protocol: vless, trojan, shadowsocks, http, socks

    port: Mapped[int] = mapped_column(Integer, nullable=False)
    listen: Mapped[str] = mapped_column(String(50), default="0.0.0.0")

    # Transport: tcp, ws, grpc, http2
    transport: Mapped[str] = mapped_column(String(20), default="tcp")
    transport_settings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON: {path: "/ws", host: "example.com", ...}

    # Security: none, tls, reality
    security: Mapped[str] = mapped_column(String(20), default="none")
    security_settings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON: {sni: "...", cert_path: "...", key_path: "...", ...}

    # Engine: xray, singbox
    engine: Mapped[str] = mapped_column(String(20), default="xray")

    # Protocol-specific settings (JSON)
    # e.g. shadowsocks: {method: "aes-256-gcm"}, http: {allow_transparent: true}
    settings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    proxy_users: Mapped[list["ProxyUser"]] = relationship(
        "ProxyUser", back_populates="inbound", cascade="all, delete-orphan"
    )
