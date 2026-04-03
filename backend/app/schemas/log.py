from datetime import datetime
from pydantic import BaseModel


class ConnectionLogResponse(BaseModel):
    id: int
    user_id: int | None
    username: str | None = None
    source_ip: str
    dest_ip: str
    dest_hostname: str | None = None
    dest_port: int | None
    protocol: str | None
    bytes_sent: int
    bytes_received: int
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class LogListResponse(BaseModel):
    logs: list[ConnectionLogResponse]
    total: int


class BandwidthHistoryResponse(BaseModel):
    timestamp: datetime
    bytes_up: int
    bytes_down: int
