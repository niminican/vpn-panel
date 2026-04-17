"""Outbound model — defines how traffic exits the server to reach destinations."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Outbound(Base):
    __tablename__ = "outbounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Protocol: direct, blackhole, vless, trojan, shadowsocks, wireguard, http, socks
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)

    # Remote server (for proxy outbounds, not needed for direct/blackhole)
    server: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    server_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Credentials (protocol-dependent)
    uuid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # VLESS/VMess
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Trojan/Shadowsocks/HTTP/SOCKS

    # VLESS-specific
    flow: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Shadowsocks-specific
    method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # WireGuard-specific
    private_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    public_key: Mapped[Optional[str]] = mapped_column(String(44), nullable=True)
    peer_public_key: Mapped[Optional[str]] = mapped_column(String(44), nullable=True)
    local_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # e.g. "10.0.0.2/32"
    mtu: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Transport: tcp, ws, grpc, http2 (for proxy outbounds)
    transport: Mapped[str] = mapped_column(String(20), default="tcp")
    transport_settings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Security: none, tls, reality
    security: Mapped[str] = mapped_column(String(20), default="none")
    security_settings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Engine: xray, singbox (must match inbound engine)
    engine: Mapped[str] = mapped_column(String(20), default="xray")

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
