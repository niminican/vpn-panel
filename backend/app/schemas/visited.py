from datetime import datetime
from pydantic import BaseModel


class VisitedDestination(BaseModel):
    dest_ip: str
    dest_hostname: str | None = None
    count: int
    last_seen: datetime

    model_config = {"from_attributes": True}


class VisitedListResponse(BaseModel):
    visited: list[VisitedDestination]
    total: int
