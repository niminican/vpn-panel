"""
Simple in-memory rate limiter for login attempts.
"""
import time
import threading
from collections import defaultdict


class RateLimiter:
    """Rate limiter that tracks failed attempts per key (IP or username)."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300, lockout_seconds: int = 900):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lockouts: dict[str, float] = {}
        self._lock = threading.Lock()

    def is_locked(self, key: str) -> bool:
        """Check if a key is currently locked out."""
        with self._lock:
            lockout_until = self._lockouts.get(key)
            if lockout_until and time.time() < lockout_until:
                return True
            elif lockout_until:
                del self._lockouts[key]
            return False

    def record_failure(self, key: str):
        """Record a failed attempt. Returns True if now locked out."""
        now = time.time()
        with self._lock:
            # Clean old attempts
            self._attempts[key] = [t for t in self._attempts[key] if now - t < self.window_seconds]
            self._attempts[key].append(now)

            if len(self._attempts[key]) >= self.max_attempts:
                self._lockouts[key] = now + self.lockout_seconds
                self._attempts[key].clear()
                return True
        return False

    def record_success(self, key: str):
        """Clear attempts on successful login."""
        with self._lock:
            self._attempts.pop(key, None)
            self._lockouts.pop(key, None)

    def remaining_lockout(self, key: str) -> int:
        """Seconds remaining in lockout, or 0."""
        with self._lock:
            lockout_until = self._lockouts.get(key)
            if lockout_until:
                remaining = int(lockout_until - time.time())
                return max(0, remaining)
            return 0


# Global login rate limiter: 5 failed attempts → 15 min lockout
login_limiter = RateLimiter(max_attempts=5, window_seconds=300, lockout_seconds=900)
