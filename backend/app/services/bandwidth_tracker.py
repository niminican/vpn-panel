"""
Bandwidth Tracker Service

Polls `wg show dump` every 60 seconds, calculates deltas from last poll,
updates per-user bandwidth usage in DB, and records hourly snapshots.
"""
import logging
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.user import User
from app.models.bandwidth import BandwidthHistory
from app.services.wireguard import get_peers_status

logger = logging.getLogger(__name__)

# In-memory cache of last known transfer values per public key
_last_transfer: dict[str, tuple[int, int]] = {}  # pubkey -> (rx, tx)


def poll_bandwidth():
    """Poll WireGuard for current transfer stats and update DB."""
    db = SessionLocal()
    try:
        peers = get_peers_status()
        if not peers:
            return

        # Build pubkey -> user mapping
        users = db.query(User).filter(User.enabled == True).all()  # noqa: E712
        user_by_pubkey: dict[str, User] = {u.wg_public_key: u for u in users}

        now = datetime.now(timezone.utc)

        for peer in peers:
            pubkey = peer["public_key"]
            user = user_by_pubkey.get(pubkey)
            if not user:
                continue

            current_rx = peer["transfer_rx"]  # bytes received by server = user upload
            current_tx = peer["transfer_tx"]  # bytes sent by server = user download

            if pubkey in _last_transfer:
                last_rx, last_tx = _last_transfer[pubkey]

                # Calculate deltas (handle counter reset)
                delta_rx = max(0, current_rx - last_rx) if current_rx >= last_rx else current_rx
                delta_tx = max(0, current_tx - last_tx) if current_tx >= last_tx else current_tx

                if delta_rx > 0 or delta_tx > 0:
                    user.bandwidth_used_up += delta_rx    # rx on server = upload from user
                    user.bandwidth_used_down += delta_tx  # tx on server = download by user

            _last_transfer[pubkey] = (current_rx, current_tx)

        db.commit()

    except Exception as e:
        logger.error(f"Bandwidth poll error: {e}")
        db.rollback()
    finally:
        db.close()


def record_hourly_snapshot():
    """Record hourly bandwidth snapshots for historical charts."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        for user in users:
            if user.bandwidth_used_up > 0 or user.bandwidth_used_down > 0:
                snapshot = BandwidthHistory(
                    user_id=user.id,
                    timestamp=now,
                    bytes_up=user.bandwidth_used_up,
                    bytes_down=user.bandwidth_used_down,
                )
                db.add(snapshot)

        db.commit()
    except Exception as e:
        logger.error(f"Hourly snapshot error: {e}")
        db.rollback()
    finally:
        db.close()


def check_bandwidth_limits():
    """Check if any user has exceeded their bandwidth limit and disable them."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.enabled == True).all()  # noqa: E712

        for user in users:
            exceeded = False

            if user.bandwidth_limit_down and user.bandwidth_used_down >= user.bandwidth_limit_down:
                exceeded = True
            if user.bandwidth_limit_up and user.bandwidth_used_up >= user.bandwidth_limit_up:
                exceeded = True

            if exceeded:
                logger.info(f"User {user.username} exceeded bandwidth limit, disabling")
                user.enabled = False
                # Remove WireGuard peer
                from app.services.wireguard import remove_peer
                try:
                    remove_peer(user.wg_public_key)
                except RuntimeError as e:
                    logger.warning(f"Failed to remove peer for {user.username}: {e}")

        db.commit()
    except Exception as e:
        logger.error(f"Bandwidth limit check error: {e}")
        db.rollback()
    finally:
        db.close()


def reset_monthly_bandwidth():
    """Reset bandwidth counters for users whose reset day matches today."""
    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).day
        users = db.query(User).filter(User.bandwidth_reset_day == today).all()

        for user in users:
            logger.info(f"Monthly bandwidth reset for user {user.username}")
            user.bandwidth_used_up = 0
            user.bandwidth_used_down = 0
            user.alert_sent = False

            # Re-enable if was disabled due to bandwidth
            if not user.enabled and user.expiry_date and user.expiry_date > datetime.now(timezone.utc):
                user.enabled = True
                from app.services.wireguard import add_peer
                try:
                    add_peer(user)
                except RuntimeError as e:
                    logger.warning(f"Failed to re-add peer for {user.username}: {e}")

        db.commit()
    except Exception as e:
        logger.error(f"Monthly reset error: {e}")
        db.rollback()
    finally:
        db.close()
