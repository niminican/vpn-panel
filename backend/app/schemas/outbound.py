"""Schemas for Outbound CRUD."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class OutboundCreate(BaseModel):
    tag: str
    protocol: str  # direct, blackhole, vless, trojan, shadowsocks, wireguard, http, socks
    server: Optional[str] = None
    server_port: Optional[int] = None
    uuid: Optional[str] = None
    password: Optional[str] = None
    flow: Optional[str] = None
    method: Optional[str] = None
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    peer_public_key: Optional[str] = None
    local_address: Optional[str] = None
    mtu: Optional[int] = None
    transport: str = "tcp"
    transport_settings: Optional[str] = None
    security: str = "none"
    security_settings: Optional[str] = None
    engine: str = "xray"
    enabled: bool = True


class OutboundUpdate(BaseModel):
    tag: Optional[str] = None
    protocol: Optional[str] = None
    server: Optional[str] = None
    server_port: Optional[int] = None
    uuid: Optional[str] = None
    password: Optional[str] = None
    flow: Optional[str] = None
    method: Optional[str] = None
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    peer_public_key: Optional[str] = None
    local_address: Optional[str] = None
    mtu: Optional[int] = None
    transport: Optional[str] = None
    transport_settings: Optional[str] = None
    security: Optional[str] = None
    security_settings: Optional[str] = None
    engine: Optional[str] = None
    enabled: Optional[bool] = None


class OutboundResponse(BaseModel):
    id: int
    tag: str
    protocol: str
    server: Optional[str] = None
    server_port: Optional[int] = None
    transport: str
    security: str
    engine: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
