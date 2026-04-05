from datetime import datetime

from pydantic import BaseModel


class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingResponse(BaseModel):
    key: str
    value: str

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    id: int
    user_id: int | None
    type: str
    message: str
    channel: str | None
    sent_at: datetime
    acknowledged: bool

    model_config = {"from_attributes": True}
