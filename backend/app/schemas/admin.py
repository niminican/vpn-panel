from datetime import datetime
from pydantic import BaseModel


class AdminCreate(BaseModel):
    username: str
    password: str
    role: str = "admin"  # admin or super_admin
    permissions: list[str] = []


class AdminUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    role: str | None = None
    permissions: list[str] | None = None


class AdminResponse(BaseModel):
    id: int
    username: str
    role: str
    permissions: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminAuditLogResponse(BaseModel):
    id: int
    admin_id: int
    admin_username: str
    action: str
    resource_type: str | None
    resource_id: int | None
    details: str | None
    ip_address: str | None
    user_agent: str | None = None
    device_info: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    logs: list[AdminAuditLogResponse]
    total: int
