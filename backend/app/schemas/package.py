from pydantic import BaseModel


class PackageCreate(BaseModel):
    name: str
    description: str | None = None
    bandwidth_limit: int | None = None  # bytes
    speed_limit: int | None = None  # kbps
    duration_days: int
    max_connections: int = 1
    price: float | None = None
    currency: str = "IRR"
    enabled: bool = True
    destination_vpn_id: int | None = None


class PackageUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    bandwidth_limit: int | None = None
    speed_limit: int | None = None
    duration_days: int | None = None
    max_connections: int | None = None
    price: float | None = None
    currency: str | None = None
    enabled: bool | None = None
    destination_vpn_id: int | None = None


class PackageResponse(BaseModel):
    id: int
    name: str
    description: str | None
    bandwidth_limit: int | None
    speed_limit: int | None
    duration_days: int
    max_connections: int
    price: float | None
    currency: str
    enabled: bool
    destination_vpn_id: int | None = None
    destination_vpn_name: str | None = None

    model_config = {"from_attributes": True}
