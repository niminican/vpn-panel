from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.models.user import User
from app.models.destination_vpn import DestinationVPN
from app.models.alert import Alert
from app.schemas.dashboard import DashboardResponse
from app.services.system_monitor import get_system_stats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    now = datetime.now(timezone.utc)
    system = get_system_stats()

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.enabled == True).count()  # noqa: E712
    disabled_users = db.query(User).filter(User.enabled == False).count()  # noqa: E712
    expired_users = db.query(User).filter(
        User.expiry_date.isnot(None),
        User.expiry_date < now,
    ).count()

    # Bandwidth totals
    bw = db.query(
        func.coalesce(func.sum(User.bandwidth_used_up), 0),
        func.coalesce(func.sum(User.bandwidth_used_down), 0),
    ).first()

    # Destination VPN stats
    dest_total = db.query(DestinationVPN).count()
    dest_up = db.query(DestinationVPN).filter(DestinationVPN.is_running == True).count()  # noqa: E712

    # Recent alerts
    alerts_count = db.query(Alert).filter(Alert.acknowledged == False).count()  # noqa: E712

    # Online users (would need WG status check - simplified here)
    from app.services.wireguard import get_peers_status
    peers = get_peers_status()
    online_count = sum(
        1 for p in peers
        if p["latest_handshake"] and (now.timestamp() - p["latest_handshake"] < 180)
    )

    return DashboardResponse(
        system=system,
        total_users=total_users,
        active_users=active_users,
        disabled_users=disabled_users,
        expired_users=expired_users,
        online_users=online_count,
        total_bandwidth_up=bw[0],
        total_bandwidth_down=bw[1],
        destination_vpns_up=dest_up,
        destination_vpns_total=dest_total,
        recent_alerts_count=alerts_count,
    )


@router.get("/dest-vpn/{dest_id}/health")
def get_dest_vpn_health(
    dest_id: int,
    _admin: Admin = Depends(get_current_admin),
):
    """Get health status and latency for a destination VPN."""
    from app.services.destination_vpn import check_destination_health
    return check_destination_health(dest_id)


@router.post("/dest-vpn/{dest_id}/speedtest")
def run_dest_vpn_speedtest(
    dest_id: int,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Run speed test through a destination VPN (may take ~30s)."""
    dest = db.query(DestinationVPN).filter(DestinationVPN.id == dest_id).first()
    if not dest:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Destination VPN")

    from app.services.destination_vpn import run_speed_test
    result = run_speed_test(dest.interface_name)
    if not result:
        return {"error": "Speed test failed or speedtest-cli not installed"}
    return result
