"""
Alert Service

Dispatches alerts to multiple channels: panel, email, telegram.
Checks bandwidth thresholds, expiry dates, and VPN status.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.models.alert import Alert
from app.models.destination_vpn import DestinationVPN
from app.config import settings

logger = logging.getLogger(__name__)


def _get_setting(db: Session, key: str) -> str | None:
    from app.models.setting import Setting
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s else None


async def send_email_alert(to_email: str, subject: str, body: str):
    """Send alert via email using aiosmtplib."""
    if not settings.smtp_host:
        return

    try:
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=True,
        )
        logger.info(f"Email alert sent to {to_email}")
    except Exception as e:
        logger.error(f"Email alert failed: {e}")


async def send_telegram_alert(chat_id: int, message: str):
    """Send alert via Telegram bot."""
    if not settings.telegram_bot_token:
        return

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            )
        logger.info(f"Telegram alert sent to {chat_id}")
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")


def _create_alert(db: Session, user_id: int | None, alert_type: str, message: str, channel: str):
    """Create an alert record."""
    alert = Alert(
        user_id=user_id,
        type=alert_type,
        message=message,
        channel=channel,
    )
    db.add(alert)


def check_bandwidth_thresholds():
    """Check all users for bandwidth threshold alerts."""
    db = SessionLocal()
    try:
        global_alerts = _get_setting(db, "global_alerts_enabled")
        if global_alerts == "false":
            return

        users = db.query(User).filter(
            User.enabled == True,  # noqa: E712
            User.alert_enabled == True,  # noqa: E712
            User.alert_sent == False,  # noqa: E712
        ).all()

        for user in users:
            threshold = user.alert_threshold / 100.0

            down_exceeded = (
                user.bandwidth_limit_down
                and user.bandwidth_used_down >= user.bandwidth_limit_down * threshold
            )
            up_exceeded = (
                user.bandwidth_limit_up
                and user.bandwidth_used_up >= user.bandwidth_limit_up * threshold
            )

            if down_exceeded or up_exceeded:
                direction = "download" if down_exceeded else "upload"
                message = (
                    f"User '{user.username}' has reached {user.alert_threshold}% "
                    f"of their {direction} bandwidth limit."
                )

                _create_alert(db, user.id, "bandwidth_warning", message, "panel")
                user.alert_sent = True

                # Send Telegram notification
                if user.telegram_chat_id:
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(
                                send_telegram_alert(user.telegram_chat_id, message)
                            )
                        else:
                            loop.run_until_complete(
                                send_telegram_alert(user.telegram_chat_id, message)
                            )
                    except RuntimeError:
                        asyncio.run(send_telegram_alert(user.telegram_chat_id, message))

                logger.info(f"Bandwidth alert for user {user.username}")

        db.commit()
    except Exception as e:
        logger.error(f"Bandwidth threshold check error: {e}")
        db.rollback()
    finally:
        db.close()


def check_expiry_dates():
    """Check for users about to expire or already expired."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        soon = now + timedelta(days=3)

        # About to expire
        expiring = db.query(User).filter(
            User.enabled == True,  # noqa: E712
            User.expiry_date.isnot(None),
            User.expiry_date > now,
            User.expiry_date <= soon,
        ).all()

        for user in expiring:
            days_left = (user.expiry_date - now).days
            message = f"User '{user.username}' will expire in {days_left} day(s)."

            # Check if we already sent this alert recently
            existing = db.query(Alert).filter(
                Alert.user_id == user.id,
                Alert.type == "expiry_warning",
                Alert.sent_at > now - timedelta(days=1),
            ).first()

            if not existing:
                _create_alert(db, user.id, "expiry_warning", message, "panel")

                if user.telegram_chat_id:
                    import asyncio
                    try:
                        asyncio.run(send_telegram_alert(user.telegram_chat_id, message))
                    except RuntimeError:
                        pass

        # Already expired - disable
        expired = db.query(User).filter(
            User.enabled == True,  # noqa: E712
            User.expiry_date.isnot(None),
            User.expiry_date <= now,
        ).all()

        for user in expired:
            user.enabled = False
            message = f"User '{user.username}' has expired and was disabled."
            _create_alert(db, user.id, "expired", message, "panel")

            from app.services.wireguard import remove_peer
            try:
                remove_peer(user.wg_public_key)
            except RuntimeError:
                pass

            logger.info(f"User {user.username} expired and disabled")

        db.commit()
    except Exception as e:
        logger.error(f"Expiry check error: {e}")
        db.rollback()
    finally:
        db.close()


def check_destination_vpn_status():
    """Alert if any destination VPN goes down."""
    db = SessionLocal()
    try:
        dests = db.query(DestinationVPN).filter(
            DestinationVPN.enabled == True,  # noqa: E712
            DestinationVPN.is_running == False,  # noqa: E712
        ).all()

        for dest in dests:
            existing = db.query(Alert).filter(
                Alert.type == "dest_vpn_down",
                Alert.message.contains(dest.name),
                Alert.acknowledged == False,  # noqa: E712
            ).first()

            if not existing:
                message = f"Destination VPN '{dest.name}' is DOWN!"
                _create_alert(db, None, "dest_vpn_down", message, "panel")
                logger.warning(message)

        db.commit()
    except Exception as e:
        logger.error(f"Destination VPN status check error: {e}")
        db.rollback()
    finally:
        db.close()
