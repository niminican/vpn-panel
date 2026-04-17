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


def _resolve_domain(domain: str) -> str | None:
    """Resolve domain to a single IP address.

    Uses _resolve_domain_all and returns first result.
    """
    results = _resolve_domain_all(domain)
    return results[0] if results else None


def _resolve_domain_all(domain: str) -> list[str]:
    """Resolve a domain name to ALL A record IPs.

    Uses `dig` command first (handles CNAME chains), falls back to
    socket.getaddrinfo (portable, no manual packet parsing).
    """
    from app.core.command_executor import run_command

    # 1) Try dig command (most reliable, handles CNAME chains properly)
    for server in ["8.8.8.8", "1.1.1.1"]:
        try:
            result = run_command(
                ["dig", "+short", domain, f"@{server}"],
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                ips = []
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ipaddress.ip_address(line)
                        ips.append(line)
                    except ValueError:
                        continue
                if ips:
                    return ips
        except Exception:
            continue

    # 2) Fallback: socket.getaddrinfo (portable, no manual UDP parsing)
    import socket
    try:
        results = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
        ips = list({r[4][0] for r in results})
        if ips:
            return ips
    except (socket.gaierror, OSError):
        pass

    return []


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


def resolve_all_ips(addr: str) -> list[str]:
    """Resolve a domain to ALL its IP addresses.

    Returns list of IPs. For IP/CIDR input, returns single-element list.
    """
    addr = addr.strip()
    for prefix in ("https://", "http://"):
        if addr.lower().startswith(prefix):
            addr = addr[len(prefix):]
    addr = addr.split("/")[0] if "/" in addr and not _is_cidr(addr) else addr

    # IP or CIDR - return as-is
    try:
        if '/' in addr:
            ipaddress.ip_network(addr, strict=False)
        else:
            ipaddress.ip_address(addr)
        return [addr]
    except ValueError:
        pass

    # Domain - resolve all IPs using direct DNS queries
    _DOMAIN_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$')
    if not _DOMAIN_RE.match(addr):
        return []
    # Use direct DNS queries to get all A records
    results = _resolve_domain_all(addr)
    if results:
        return results
    # Fallback to single resolve
    resolved = _resolve_domain(addr)
    return [resolved] if resolved else []


def validate_address(addr: str) -> str:
    """Validate a destination address (IP, CIDR, or domain name).

    Accepts:
      - IP addresses: 1.2.3.4
      - CIDR: 1.2.3.0/24
      - Domain names: example.com (resolved to IP via DNS)
      - URLs: http://example.com or https://example.com (prefix stripped)
    """
    addr = addr.strip()

    # Strip URL scheme if present
    for prefix in ("https://", "http://"):
        if addr.lower().startswith(prefix):
            addr = addr[len(prefix):]
    # Strip trailing path/slash
    addr = addr.split("/")[0] if "/" in addr and not _is_cidr(addr) else addr

    # Try as IP or CIDR first
    try:
        if '/' in addr:
            ipaddress.ip_network(addr, strict=False)
        else:
            ipaddress.ip_address(addr)
        return addr
    except ValueError:
        pass

    # Try as domain name — resolve to IP using direct DNS query
    _DOMAIN_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$')
    if not _DOMAIN_RE.match(addr):
        raise ValueError(f"Invalid address or domain: {addr}")
    resolved = _resolve_domain(addr)
    if resolved:
        return resolved
    raise ValueError(f"Cannot resolve domain: {addr}")


def _is_cidr(addr: str) -> bool:
    """Check if address looks like CIDR notation."""
    try:
        ipaddress.ip_network(addr, strict=False)
        return True
    except ValueError:
        return False
