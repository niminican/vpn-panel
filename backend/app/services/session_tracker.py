"""
Session Tracker Service

Monitors WireGuard handshakes to track user connection sessions.
Called periodically by the scheduler (every 60s alongside bandwidth polling).

A session starts when a peer has a recent handshake (< 3 min).
A session ends when the handshake goes stale (> 3 min).
"""
import logging
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.user import User
from app.models.user_session import UserSession
from app.services.wireguard import get_peers_status

logger = logging.getLogger(__name__)

# In-memory state: pubkey -> active session_id
_active_sessions: dict[str, int] = {}
# Track last known transfer per pubkey for session bandwidth
_session_transfer: dict[str, tuple[int, int]] = {}  # pubkey -> (rx, tx)

HANDSHAKE_TIMEOUT = 180  # 3 minutes


def track_sessions():
    """Check WireGuard peers and update session records."""
    db = SessionLocal()
    try:
        peers = get_peers_status()
        if not peers:
            return

        users = db.query(User).filter(User.enabled == True).all()  # noqa: E712
        user_by_pubkey: dict[str, User] = {u.wg_public_key: u for u in users}

        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()

        seen_pubkeys: set[str] = set()

        for peer in peers:
            pubkey = peer["public_key"]
            user = user_by_pubkey.get(pubkey)
            if not user:
                continue

            seen_pubkeys.add(pubkey)

            handshake_ts = peer.get("latest_handshake", 0) or 0
            is_active = handshake_ts > 0 and (now_ts - handshake_ts) < HANDSHAKE_TIMEOUT

            current_rx = peer.get("transfer_rx", 0)
            current_tx = peer.get("transfer_tx", 0)
            endpoint = peer.get("endpoint", "")

            # Extract IP from endpoint (format: "IP:port")
            client_ip = None
            if endpoint and ":" in endpoint:
                client_ip = endpoint.rsplit(":", 1)[0]

            if is_active:
                if pubkey not in _active_sessions:
                    # New session - create record
                    session = UserSession(
                        user_id=user.id,
                        endpoint=endpoint,
                        client_ip=client_ip,
                        connected_at=now,
                        bytes_sent=0,
                        bytes_received=0,
                    )
                    db.add(session)
                    db.flush()
                    _active_sessions[pubkey] = session.id
                    _session_transfer[pubkey] = (current_rx, current_tx)
                    logger.debug(f"Session started for {user.username} from {endpoint}")
                else:
                    # Update existing session bandwidth
                    session_id = _active_sessions[pubkey]
                    session = db.query(UserSession).filter(UserSession.id == session_id).first()
                    if session:
                        if pubkey in _session_transfer:
                            last_rx, last_tx = _session_transfer[pubkey]
                            delta_rx = max(0, current_rx - last_rx) if current_rx >= last_rx else current_rx
                            delta_tx = max(0, current_tx - last_tx) if current_tx >= last_tx else current_tx
                            session.bytes_received += delta_rx  # rx = upload from user
                            session.bytes_sent += delta_tx      # tx = download by user
                        if endpoint:
                            session.endpoint = endpoint
                            session.client_ip = client_ip
                    _session_transfer[pubkey] = (current_rx, current_tx)
            else:
                # Peer is inactive - close session if open
                if pubkey in _active_sessions:
                    session_id = _active_sessions.pop(pubkey)
                    session = db.query(UserSession).filter(UserSession.id == session_id).first()
                    if session and not session.disconnected_at:
                        session.disconnected_at = now
                        logger.debug(f"Session ended for {user.username}")
                    _session_transfer.pop(pubkey, None)

        # Close sessions for pubkeys that disappeared entirely
        for pubkey in list(_active_sessions.keys()):
            if pubkey not in seen_pubkeys:
                session_id = _active_sessions.pop(pubkey)
                session = db.query(UserSession).filter(UserSession.id == session_id).first()
                if session and not session.disconnected_at:
                    session.disconnected_at = now
                _session_transfer.pop(pubkey, None)

        db.commit()

    except Exception as e:
        logger.error(f"Session tracker error: {e}")
        db.rollback()
    finally:
        db.close()
