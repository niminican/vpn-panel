"""
OS Detection Service

Detects client OS from IP packet TTL values observed on the WireGuard interface.
Each OS family has a default initial TTL:
  - Windows: 128
  - Linux / Android: 64
  - macOS / iOS: 64
  - Some routers/unusual: 255

Since packets traverse the WireGuard tunnel, the TTL observed on the server
is the original TTL minus the hop count inside the tunnel (usually 1).
So we see: Windows → ~127, Linux/Android/macOS → ~63.
"""
import logging
import subprocess
from functools import lru_cache

logger = logging.getLogger(__name__)


def detect_ttl(client_vpn_ip: str) -> int | None:
    """Get TTL from a single ping to the client's VPN IP (via wg0).

    Returns the TTL value or None if unreachable.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", client_vpn_ip],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None

        for line in result.stdout.split("\n"):
            if "ttl=" in line.lower():
                # "64 bytes from 10.8.0.2: icmp_seq=1 ttl=63 time=1.23 ms"
                parts = line.lower().split("ttl=")
                if len(parts) >= 2:
                    ttl_str = parts[1].split()[0]
                    return int(ttl_str)
    except Exception as e:
        logger.debug(f"TTL detection failed for {client_vpn_ip}: {e}")
    return None


def guess_os(ttl: int | None) -> str | None:
    """Guess the operating system from the TTL value.

    Returns a string like "Windows", "Linux/Android", "macOS/iOS", or None.
    """
    if ttl is None:
        return None

    # TTL ranges after 1 hop through WireGuard tunnel:
    # Windows (initial 128) → 126-128
    # Linux/Android (initial 64) → 62-64
    # macOS/iOS (initial 64) → 62-64
    # Some devices (initial 255) → 253-255

    if 120 <= ttl <= 128:
        return "Windows"
    elif 56 <= ttl <= 64:
        return "Linux/Android/macOS"
    elif 248 <= ttl <= 255:
        return "Network Device"
    elif ttl < 56:
        # Multiple hops, could be anything but likely Linux-based
        return "Linux/Android"
    else:
        # Between 64 and 128, unusual - possibly Windows behind NAT
        return "Unknown"


def detect_os_for_ip(client_vpn_ip: str) -> tuple[int | None, str | None]:
    """Detect OS for a given VPN IP address.

    Returns (ttl, os_hint) tuple.
    """
    ttl = detect_ttl(client_vpn_ip)
    os_hint = guess_os(ttl)
    return ttl, os_hint
