from pydantic import BaseModel, field_validator


class ScheduleCreate(BaseModel):
    day_of_week: int  # 0=Mon, 6=Sun
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    enabled: bool = True

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: int) -> int:
        if v < 0 or v > 6:
            raise ValueError("day_of_week must be 0-6")
        return v


class ScheduleResponse(BaseModel):
    id: int
    user_id: int
    day_of_week: int
    start_time: str
    end_time: str
    enabled: bool

    model_config = {"from_attributes": True}
