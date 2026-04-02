"""
Scheduler Service

APScheduler jobs for periodic tasks:
- Bandwidth polling (every 60s)
- Bandwidth limit check (every 60s)
- Bandwidth threshold alerts (every 5 min)
- Hourly bandwidth snapshots
- Monthly bandwidth reset (daily at midnight)
- Connection log flush (every 5s)
- Destination VPN health check (every 60s)
- Expiry check (every 5 min)
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    """Start all scheduled jobs."""
    from app.services.bandwidth_tracker import (
        poll_bandwidth,
        check_bandwidth_limits,
        record_hourly_snapshot,
        reset_monthly_bandwidth,
    )
    from app.services.alert_service import (
        check_bandwidth_thresholds,
        check_expiry_dates,
        check_destination_vpn_status,
    )
    from app.services.destination_vpn import check_all_destinations
    from app.services.connection_logger import flush as flush_logs

    # Bandwidth polling
    scheduler.add_job(poll_bandwidth, "interval", seconds=60, id="poll_bandwidth")
    scheduler.add_job(check_bandwidth_limits, "interval", seconds=60, id="check_bw_limits")

    # Hourly snapshots
    scheduler.add_job(record_hourly_snapshot, "cron", minute=0, id="hourly_snapshot")

    # Monthly reset
    scheduler.add_job(reset_monthly_bandwidth, "cron", hour=0, minute=5, id="monthly_reset")

    # Alerts
    scheduler.add_job(check_bandwidth_thresholds, "interval", minutes=5, id="check_bw_alerts")
    scheduler.add_job(check_expiry_dates, "interval", minutes=5, id="check_expiry")
    scheduler.add_job(check_destination_vpn_status, "interval", minutes=2, id="check_dest_vpn")

    # Destination VPN health
    scheduler.add_job(check_all_destinations, "interval", seconds=60, id="dest_health")

    # Connection log flush
    scheduler.add_job(flush_logs, "interval", seconds=5, id="flush_conn_logs")

    scheduler.start()
    logger.info("Scheduler started with all jobs")


def stop_scheduler():
    """Stop the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
