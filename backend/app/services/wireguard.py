import subprocess
import ipaddress
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.core.security import encrypt_key, decrypt_key


def _run(cmd: list[str], input_data: str | None = None) -> str:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_data,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}: {result.stderr}")
    return result.stdout.strip()


def generate_keypair() -> tuple[str, str]:
    """Generate a WireGuard private/public key pair."""
    if settings.demo_mode:
        import base64, os
        priv = base64.b64encode(os.urandom(32)).decode()
        pub = base64.b64encode(os.urandom(32)).decode()
        return priv, pub
    private_key = _run(["wg", "genkey"])
    public_key = _run(["wg", "pubkey"], input_data=private_key)
    return private_key, public_key


def generate_preshared_key() -> str:
    if settings.demo_mode:
        import base64, os
        return base64.b64encode(os.urandom(32)).decode()
    return _run(["wg", "genpsk"])


def get_next_available_ip(db: Session) -> str:
    """Find the next available IP in the WireGuard subnet."""
    network = ipaddress.ip_network(settings.wg_subnet, strict=False)
    used_ips = {row.assigned_ip.split("/")[0] for row in db.query(User.assigned_ip).all()}

    # Skip network address and server address (.1)
    hosts = list(network.hosts())
    for host in hosts[1:]:  # Skip .1 (server)
        ip_str = str(host)
        if ip_str not in used_ips:
            return f"{ip_str}/32"

    raise RuntimeError("No available IPs in subnet")


def generate_client_config(user: User) -> str:
    """Generate WireGuard client configuration.

    Uses per-user config overrides if set, otherwise falls back to global settings.
    """
    private_key = decrypt_key(user.wg_private_key)
    server_public_key = get_server_public_key()

    dns = user.config_dns or settings.wg_dns
    allowed_ips = user.config_allowed_ips or "0.0.0.0/0, ::/0"
    endpoint = user.config_endpoint or f"{settings.wg_server_ip}:{settings.wg_port}"
    keepalive = user.config_keepalive if user.config_keepalive is not None else 25

    config = f"""[Interface]
PrivateKey = {private_key}
Address = {user.assigned_ip}
DNS = {dns}
"""
    if user.config_mtu:
        config += f"MTU = {user.config_mtu}\n"

    config += f"""
[Peer]
PublicKey = {server_public_key}
"""
    if user.wg_preshared_key:
        psk = decrypt_key(user.wg_preshared_key)
        config += f"PresharedKey = {psk}\n"

    config += f"""Endpoint = {endpoint}
AllowedIPs = {allowed_ips}
PersistentKeepalive = {keepalive}
"""
    return config


def get_server_public_key() -> str:
    """Get the server's WireGuard public key."""
    if settings.demo_mode:
        import base64, os
        return base64.b64encode(os.urandom(32)).decode()
    config_path = Path(settings.wg_config_dir) / f"{settings.wg_interface}.conf"
    if config_path.exists():
        content = config_path.read_text()
        for line in content.split("\n"):
            if line.strip().startswith("PrivateKey"):
                server_private = line.split("=", 1)[1].strip()
                return _run(["wg", "pubkey"], input_data=server_private)
    # Fallback: read from running interface
    return _run(["wg", "show", settings.wg_interface, "public-key"])


def add_peer(user: User) -> None:
    """Add a WireGuard peer for the user."""
    public_key = user.wg_public_key
    allowed_ip = user.assigned_ip

    cmd = ["wg", "set", settings.wg_interface, "peer", public_key, "allowed-ips", allowed_ip]

    if user.wg_preshared_key:
        psk = decrypt_key(user.wg_preshared_key)
        # Use secure temp file with restrictive permissions
        with tempfile.NamedTemporaryFile(mode='w', suffix='.psk', delete=True) as f:
            f.write(psk)
            f.flush()
            cmd.extend(["preshared-key", f.name])
            _run(cmd)
    else:
        _run(cmd)


def remove_peer(public_key: str) -> None:
    """Remove a WireGuard peer."""
    _run(["wg", "set", settings.wg_interface, "peer", public_key, "remove"])


def sync_config() -> None:
    """Sync WireGuard config without restarting (no downtime)."""
    interface = settings.wg_interface
    _run(["bash", "-c", f"wg syncconf {interface} <(wg-quick strip {interface})"])


def get_peers_status() -> list[dict]:
    """Get status of all WireGuard peers from 'wg show dump'."""
    try:
        output = _run(["wg", "show", settings.wg_interface, "dump"])
    except RuntimeError:
        return []

    peers = []
    lines = output.strip().split("\n")
    for line in lines[1:]:  # Skip header (server line)
        parts = line.split("\t")
        if len(parts) >= 8:
            peers.append({
                "public_key": parts[0],
                "preshared_key": parts[1] if parts[1] != "(none)" else None,
                "endpoint": parts[2] if parts[2] != "(none)" else None,
                "allowed_ips": parts[3],
                "latest_handshake": int(parts[4]) if parts[4] != "0" else None,
                "transfer_rx": int(parts[5]),
                "transfer_tx": int(parts[6]),
                "persistent_keepalive": parts[7] if parts[7] != "off" else None,
            })
    return peers
