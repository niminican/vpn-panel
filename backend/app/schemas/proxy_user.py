"""Schemas for ProxyUser CRUD."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ProxyUserCreate(BaseModel):
    inbound_id: int
    outbound_id: Optional[int] = None  # None = direct (default)
    uuid: Optional[str] = None  # auto-generated if not provided
    password: Optional[str] = None  # auto-generated if not provided
    flow: Optional[str] = None  # VLESS flow
    method: Optional[str] = None  # SS cipher
    traffic_limit: Optional[int] = None  # bytes, None = unlimited
    expire_date: Optional[datetime] = None


class ProxyUserResponse(BaseModel):
    id: int
    user_id: int
    inbound_id: int
    uuid: Optional[str] = None
    password: Optional[str] = None
    email: str
    flow: Optional[str] = None
    method: Optional[str] = None
    enabled: bool
    traffic_up: int
    traffic_down: int
    traffic_limit: Optional[int] = None
    expire_date: Optional[datetime] = None
    created_at: datetime

    # Inbound info (populated in API)
    inbound_tag: Optional[str] = None
    inbound_protocol: Optional[str] = None
    inbound_port: Optional[int] = None

    # Outbound info
    outbound_id: Optional[int] = None
    outbound_tag: Optional[str] = None
    outbound_protocol: Optional[str] = None

    model_config = {"from_attributes": True}


class ProxyUserConfigResponse(BaseModel):
    share_link: str
    protocol: str
    remark: str
