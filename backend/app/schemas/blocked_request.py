from datetime import datetime
from pydantic import BaseModel


class BlockedRequestResponse(BaseModel):
    id: int
    user_id: int
    dest_ip: str
    dest_hostname: str | None = None
    dest_port: int | None = None
    protocol: str | None = None
    count: int
    first_seen: datetime
    last_seen: datetime

    model_config = {"from_attributes": True}


class BlockedRequestListResponse(BaseModel):
    blocked: list[BlockedRequestResponse]
    total: int
