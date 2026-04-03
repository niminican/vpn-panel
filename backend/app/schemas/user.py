from datetime import datetime
from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be empty")
        if len(v) < 2:
            raise ValueError("Username must be at least 2 characters")
        return v
    note: str | None = None
    destination_vpn_id: int | None = None
    bandwidth_limit_up: int | None = None  # bytes
    bandwidth_limit_down: int | None = None
    speed_limit_up: int | None = None  # kbps
    speed_limit_down: int | None = None
    max_connections: int = 1
    expiry_date: datetime | None = None
    alert_enabled: bool = True
    alert_threshold: int = 80


class UserUpdate(BaseModel):
    username: str | None = None
    note: str | None = None
    enabled: bool | None = None
    destination_vpn_id: int | None = None
    bandwidth_limit_up: int | None = None
    bandwidth_limit_down: int | None = None
    speed_limit_up: int | None = None
    speed_limit_down: int | None = None
    max_connections: int | None = None
    expiry_date: datetime | None = None
    alert_enabled: bool | None = None
    alert_threshold: int | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    note: str | None
    enabled: bool
    destination_vpn_id: int | None
    destination_vpn_name: str | None = None
    assigned_ip: str
    bandwidth_limit_up: int | None
    bandwidth_limit_down: int | None
    bandwidth_used_up: int
    bandwidth_used_down: int
    speed_limit_up: int | None
    speed_limit_down: int | None
    max_connections: int
    expiry_date: datetime | None
    alert_enabled: bool
    alert_threshold: int
    telegram_username: str | None
    telegram_link_code: str | None
    is_online: bool = False
    active_sessions_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserConfigResponse(BaseModel):
    config_text: str
    qr_code_base64: str
    # Config field values (for edit form)
    dns: str | None = None
    allowed_ips: str | None = None
    endpoint: str | None = None
    mtu: int | None = None
    persistent_keepalive: int | None = None


class UserConfigUpdate(BaseModel):
    """Update editable config fields for a user."""
    dns: str | None = None
    allowed_ips: str | None = None
    endpoint: str | None = None
    mtu: int | None = None
    persistent_keepalive: int | None = None


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
