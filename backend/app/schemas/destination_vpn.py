from datetime import datetime
from pydantic import BaseModel


class DestinationVPNCreate(BaseModel):
    name: str
    protocol: str  # wireguard, openvpn
    interface_name: str
    config_text: str | None = None
    start_mode: str = "manual"  # manual, on_demand, auto_restart


class DestinationVPNUpdate(BaseModel):
    name: str | None = None
    protocol: str | None = None
    interface_name: str | None = None
    config_text: str | None = None
    enabled: bool | None = None
    start_mode: str | None = None


class DestinationVPNResponse(BaseModel):
    id: int
    name: str
    protocol: str
    interface_name: str
    config_text: str | None
    config_file_path: str | None
    enabled: bool
    is_running: bool
    start_mode: str = "manual"
    user_count: int = 0
    total_upload: int = 0
    total_download: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DestinationUserStats(BaseModel):
    id: int
    username: str
    is_online: bool = False
    bandwidth_used_up: int = 0
    bandwidth_used_down: int = 0

    model_config = {"from_attributes": True}


class DestinationVPNStatus(BaseModel):
    id: int
    name: str
    is_running: bool
    latency_ms: float | None = None
    external_ip: str | None = None
