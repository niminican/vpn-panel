"""
Input validation utilities for system commands.

Validates and sanitizes inputs before they are passed to subprocess calls
to prevent command injection attacks.
"""
import re
import ipaddress


# Valid interface name: alphanumeric, dash, underscore, max 15 chars (Linux limit)
_IFACE_RE = re.compile(r'^[a-zA-Z0-9_-]{1,15}$')

# Valid WireGuard public key: base64, exactly 44 chars
_WG_KEY_RE = re.compile(r'^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=$')

# Valid chain name: alphanumeric and underscore
_CHAIN_RE = re.compile(r'^[a-zA-Z0-9_]{1,28}$')

# Valid iptables protocol
_VALID_PROTOCOLS = {'tcp', 'udp', 'icmp', 'any', 'all'}

# Valid tc handle/classid component
_TC_ID_RE = re.compile(r'^[0-9a-fA-F]{1,4}$')

# Valid comment for iptables (no shell metacharacters)
_COMMENT_RE = re.compile(r'^[a-zA-Z0-9_:. -]{1,256}$')

# Day names for iptables time match
_VALID_DAYS = {'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'}

# Time format HH:MM or HH:MM:SS
_TIME_RE = re.compile(r'^\d{2}:\d{2}(:\d{2})?$')


def validate_ip(ip: str) -> str:
    """Validate and return a clean IP address (with optional /mask)."""
    ip = ip.strip()
    if '/' in ip:
        addr, mask = ip.split('/', 1)
        ipaddress.ip_address(addr)  # Raises ValueError if invalid
        mask_int = int(mask)
        if not (0 <= mask_int <= 128):
            raise ValueError(f"Invalid mask: {mask}")
        return f"{addr}/{mask}"
    else:
        ipaddress.ip_address(ip)
        return ip


def validate_ip_network(network: str) -> str:
    """Validate an IP network/subnet."""
    network = network.strip()
    ipaddress.ip_network(network, strict=False)
    return network


def validate_interface(name: str) -> str:
    """Validate a network interface name."""
    name = name.strip()
    if not _IFACE_RE.match(name):
        raise ValueError(f"Invalid interface name: {name}")
    return name


def validate_chain_name(name: str) -> str:
    """Validate an iptables chain name."""
    if not _CHAIN_RE.match(name):
        raise ValueError(f"Invalid chain name: {name}")
    return name


def validate_protocol(proto: str) -> str:
    """Validate an iptables protocol."""
    proto = proto.strip().lower()
    if proto not in _VALID_PROTOCOLS:
        raise ValueError(f"Invalid protocol: {proto}")
    return proto


def validate_port(port: int) -> int:
    """Validate a port number."""
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise ValueError(f"Invalid port: {port}")
    return port


def validate_fwmark(mark: int) -> int:
    """Validate a firewall mark value."""
    if not isinstance(mark, int) or mark < 0 or mark > 0xFFFFFFFF:
        raise ValueError(f"Invalid fwmark: {mark}")
    return mark


def validate_table_id(table: int) -> int:
    """Validate a routing table ID."""
    if not isinstance(table, int) or table < 0 or table > 252:
        raise ValueError(f"Invalid table ID: {table}")
    return table


def validate_comment(comment: str) -> str:
    """Validate an iptables comment string."""
    if not _COMMENT_RE.match(comment):
        raise ValueError(f"Invalid comment: {comment}")
    return comment


def validate_day(day: str) -> str:
    """Validate a day name for iptables time match."""
    if day not in _VALID_DAYS:
        raise ValueError(f"Invalid day: {day}")
    return day


def validate_time(t: str) -> str:
    """Validate a time string (HH:MM or HH:MM:SS)."""
    t = t.strip()
    if not _TIME_RE.match(t):
        raise ValueError(f"Invalid time format: {t}")
    return t


def validate_wg_key(key: str) -> str:
    """Validate a WireGuard public key."""
    key = key.strip()
    if not _WG_KEY_RE.match(key):
        raise ValueError(f"Invalid WireGuard key format")
    return key


def validate_address(addr: str) -> str:
    """Validate a destination address (IP or CIDR)."""
    addr = addr.strip()
    try:
        if '/' in addr:
            ipaddress.ip_network(addr, strict=False)
        else:
            ipaddress.ip_address(addr)
        return addr
    except ValueError:
        raise ValueError(f"Invalid address: {addr}")
