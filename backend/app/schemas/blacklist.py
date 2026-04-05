from pydantic import BaseModel


class BlacklistCreate(BaseModel):
    address: str  # IP, CIDR, domain, or * (block all except whitelist)
    port: int | None = None
    protocol: str = "any"
    description: str | None = None


class BlacklistResponse(BaseModel):
    id: int
    user_id: int
    address: str
    port: int | None
    protocol: str
    description: str | None

    model_config = {"from_attributes": True}
