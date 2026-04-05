from datetime import datetime
from pydantic import BaseModel


class UserSessionResponse(BaseModel):
    id: int
    user_id: int
    endpoint: str | None
    client_ip: str | None = None
    connected_at: datetime
    disconnected_at: datetime | None
    bytes_sent: int
    bytes_received: int
    duration_seconds: int | None = None

    # GeoIP info
    country: str | None = None
    country_code: str | None = None
    city: str | None = None
    isp: str | None = None
    asn: int | None = None

    # OS detection
    os_hint: str | None = None
    ttl: int | None = None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[UserSessionResponse]
    total: int
