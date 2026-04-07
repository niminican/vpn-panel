"""
Centralized firewall sync for a user.

Single function that reads whitelist + blacklist from DB and sets up
the correct iptables chains. Prevents duplicate/conflicting rules.
"""
import logging
from threading import Lock

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.whitelist import UserWhitelist
from app.models.blacklist import UserBlacklist
from app.services.iptables import (
    setup_user_whitelist,
    remove_user_whitelist,
    setup_user_blacklist,
    remove_user_blacklist,
)

logger = logging.getLogger(__name__)

# Per-user locks to prevent concurrent firewall modifications
_user_locks: dict[int, Lock] = {}
_locks_lock = Lock()


def _get_user_lock(user_id: int) -> Lock:
    """Get or create a lock for a specific user's firewall operations."""
    with _locks_lock:
        if user_id not in _user_locks:
            _user_locks[user_id] = Lock()
        return _user_locks[user_id]


def sync_user_firewall(user: User, db: Session):
    """Sync all iptables rules (whitelist + blacklist) for a user.

    This is the ONLY function that should be called to sync firewall rules.
    It reads both whitelist and blacklist from DB and decides the correct setup.
    Uses per-user locking to prevent race conditions.
    """
    if not user.assigned_ip:
        return

    user_lock = _get_user_lock(user.id)
    with user_lock:
        _sync_user_firewall_locked(user, db)


def _sync_user_firewall_locked(user: User, db: Session):
    """Internal: sync firewall rules while holding the user lock."""

    bl_entries = db.query(UserBlacklist).filter(UserBlacklist.user_id == user.id).all()
    wl_entries = db.query(UserWhitelist).filter(UserWhitelist.user_id == user.id).all()

    has_wildcard = any(e.address == "*" for e in bl_entries)

    bl_rules = [{"address": e.address, "port": e.port, "protocol": e.protocol} for e in bl_entries]
    wl_rules = [{"address": e.address, "port": e.port, "protocol": e.protocol} for e in wl_entries]

    if has_wildcard and wl_rules:
        # Wildcard blacklist + whitelist entries:
        # Whitelist chain handles everything (ACCEPT wl, LOG visited, LOG blocked, DROP rest)
        # No separate blacklist chain needed.
        try:
            remove_user_blacklist(user.id, user.assigned_ip)
        except Exception as e:
            logger.debug(f"Cleanup step for user {user.username}: {e}")
        try:
            setup_user_whitelist(user.id, user.assigned_ip, wl_rules, has_blacklist_wildcard=True)
        except Exception as e:
            logger.warning(f"Firewall sync failed for user {user.username}: {e}")
    elif has_wildcard and not wl_rules:
        # Wildcard blacklist without whitelist: blacklist chain blocks everything
        try:
            remove_user_whitelist(user.id, user.assigned_ip)
        except Exception as e:
            logger.debug(f"Cleanup step for user {user.username}: {e}")
        try:
            setup_user_blacklist(user.id, user.assigned_ip, bl_rules, wl_rules)
        except Exception as e:
            logger.warning(f"Firewall sync failed for user {user.username}: {e}")
    elif bl_entries:
        # Regular blacklist (specific addresses)
        # Whitelist chain separate if entries exist
        try:
            if wl_rules:
                setup_user_whitelist(user.id, user.assigned_ip, wl_rules, has_blacklist_wildcard=False)
            else:
                remove_user_whitelist(user.id, user.assigned_ip)
        except Exception as e:
            logger.debug(f"Cleanup step for user {user.username}: {e}")
        try:
            setup_user_blacklist(user.id, user.assigned_ip, bl_rules, wl_rules)
        except Exception as e:
            logger.warning(f"Firewall sync failed for user {user.username}: {e}")
    elif wl_rules:
        # Only whitelist, no blacklist
        try:
            remove_user_blacklist(user.id, user.assigned_ip)
        except Exception as e:
            logger.debug(f"Cleanup step for user {user.username}: {e}")
        try:
            setup_user_whitelist(user.id, user.assigned_ip, wl_rules, has_blacklist_wildcard=False)
        except Exception as e:
            logger.warning(f"Firewall sync failed for user {user.username}: {e}")
    else:
        # No whitelist, no blacklist - remove everything
        try:
            remove_user_whitelist(user.id, user.assigned_ip)
        except Exception as e:
            logger.debug(f"Cleanup step for user {user.username}: {e}")
        try:
            remove_user_blacklist(user.id, user.assigned_ip)
        except Exception as e:
            logger.debug(f"Cleanup step for user {user.username}: {e}")
