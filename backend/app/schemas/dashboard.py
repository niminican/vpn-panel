from pydantic import BaseModel


class SystemStats(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float


class DashboardResponse(BaseModel):
    system: SystemStats
    total_users: int
    active_users: int
    disabled_users: int
    expired_users: int
    online_users: int
    total_bandwidth_up: int  # bytes
    total_bandwidth_down: int  # bytes
    destination_vpns_up: int
    destination_vpns_total: int
    recent_alerts_count: int
