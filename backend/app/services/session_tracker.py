"""
Session Tracker Service

Monitors WireGuard handshakes to track user connection sessions.
Called periodically by the scheduler (every 60s alongside bandwidth polling).

A session starts when a peer has a recent handshake (< 3 min).
A session ends when the handshake goes stale (> 3 min).

Enriches sessions with:
- GeoIP data (country, city, ISP) from the client's public IP
- OS detection (TTL fingerprinting) from the client's VPN IP
"""
import logging
import threading
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
_session_lock = threading.Lock()

HANDSHAKE_TIMEOUT = 180  # 3 minutes


def close_orphan_sessions():
    """Close any sessions left open from a previous process (e.g. after restart).

    When the service restarts, _active_sessions is empty so the tracker
    won't know about previously open sessions. This finds and closes them.
    """
    db = SessionLocal()
    try:
        open_sessions = db.query(UserSession).filter(
            UserSession.disconnected_at == None  # noqa: E711
        ).all()
        if open_sessions:
            now = datetime.now(timezone.utc)
            for session in open_sessions:
                session.disconnected_at = now
            db.commit()
            logger.info(f"Closed {len(open_sessions)} orphan sessions from previous run")
    except Exception as e:
        logger.error(f"Failed to close orphan sessions: {e}")
        db.rollback()
    finally:
        db.close()


def _enrich_session(session: UserSession, client_ip: str | None, user) -> None:
    """Add GeoIP and OS info to a new session."""
    # GeoIP lookup
    if client_ip:
        try:
            from app.services.geoip import lookup_ip
            geo = lookup_ip(client_ip)
            session.country = geo.get("country")
            session.country_code = geo.get("country_code")
            session.city = geo.get("city")
            session.isp = geo.get("isp")
            session.asn = geo.get("asn")
        except Exception as e:
            logger.debug(f"GeoIP lookup failed for {client_ip}: {e}")

    # TTL / OS detection (ping through wg0 to user's VPN IP)
    vpn_ip = user.assigned_ip.split("/")[0] if user.assigned_ip else None
    if vpn_ip:
        try:
            from app.services.os_detect import detect_os_for_ip
            ttl, os_hint = detect_os_for_ip(vpn_ip)
            session.ttl = ttl
            session.os_hint = os_hint
        except Exception as e:
            logger.debug(f"OS detection failed for {vpn_ip}: {e}")


def track_sessions():
    """Check WireGuard peers and update session records."""
    with _session_lock:
        _track_sessions_locked()


def _track_sessions_locked():
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
                    # Enrich with GeoIP + OS detection
                    _enrich_session(session, client_ip, user)

                    db.add(session)
                    db.flush()
                    _active_sessions[pubkey] = session.id
                    _session_transfer[pubkey] = (current_rx, current_tx)
                    logger.debug(
                        f"Session started for {user.username} from {endpoint} "
                        f"[{session.country or '?'}, {session.city or '?'}, "
                        f"{session.isp or '?'}, OS: {session.os_hint or '?'}]"
                    )
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
                            # Update GeoIP if IP changed
                            if client_ip and session.country is None:
                                _enrich_session(session, client_ip, user)
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
