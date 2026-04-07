"""Schemas for Inbound CRUD."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class InboundCreate(BaseModel):
    tag: str
    protocol: str  # vless, trojan, shadowsocks, http, socks
    port: int
    listen: str = "0.0.0.0"
    transport: str = "tcp"  # tcp, ws, grpc, http2
    transport_settings: Optional[str] = None  # JSON string
    security: str = "none"  # none, tls, reality
    security_settings: Optional[str] = None  # JSON string
    engine: str = "xray"  # xray, singbox
    settings: Optional[str] = None  # protocol-specific JSON
    enabled: bool = True


class InboundUpdate(BaseModel):
    tag: Optional[str] = None
    protocol: Optional[str] = None
    port: Optional[int] = None
    listen: Optional[str] = None
    transport: Optional[str] = None
    transport_settings: Optional[str] = None
    security: Optional[str] = None
    security_settings: Optional[str] = None
    engine: Optional[str] = None
    settings: Optional[str] = None
    enabled: Optional[bool] = None


class InboundResponse(BaseModel):
    id: int
    tag: str
    protocol: str
    port: int
    listen: str
    transport: str
    transport_settings: Optional[str] = None
    security: str
    security_settings: Optional[str] = None
    engine: str
    settings: Optional[str] = None
    enabled: bool
    user_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
