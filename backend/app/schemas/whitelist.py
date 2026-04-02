from pydantic import BaseModel


class WhitelistCreate(BaseModel):
    address: str
    port: int | None = None
    protocol: str = "any"
    description: str | None = None


class WhitelistResponse(BaseModel):
    id: int
    user_id: int
    address: str
    port: int | None
    protocol: str
    description: str | None

    model_config = {"from_attributes": True}
