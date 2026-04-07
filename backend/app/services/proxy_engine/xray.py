"""Xray-core engine implementation."""
from __future__ import annotations

import json
import logging
import os
import signal
from pathlib import Path
from typing import Any

from app.core.command_executor import run_command
from app.services.proxy_engine.base import ProxyEngine

logger = logging.getLogger(__name__)

XRAY_BINARY = os.environ.get("XRAY_BINARY", "/usr/local/bin/xray")
XRAY_CONFIG_DIR = Path(os.environ.get("XRAY_CONFIG_DIR", "/app/data/xray"))
XRAY_API_PORT = int(os.environ.get("XRAY_API_PORT", "10085"))

# PID file to track running process
_xray_pid: int | None = None


class XrayEngine(ProxyEngine):

    @property
    def name(self) -> str:
        return "xray"

    @property
    def binary_path(self) -> str:
        return XRAY_BINARY

    def generate_config(
        self,
        inbounds: list[dict],
        proxy_users: list[dict],
        outbounds: list[dict] | None = None,
    ) -> dict:
        """Generate Xray-core config.json."""
        outbounds = outbounds or []

        # Group users by inbound tag
        users_by_tag: dict[str, list[dict]] = {}
        for pu in proxy_users:
            tag = pu.get("inbound_tag", "")
            users_by_tag.setdefault(tag, []).append(pu)

        xray_inbounds = []
        for inb in inbounds:
            if not inb.get("enabled", True):
                continue

            tag = inb["tag"]
            protocol = inb["protocol"]
            users = users_by_tag.get(tag, [])

            xray_inbound = {
                "tag": tag,
                "port": inb["port"],
                "listen": inb.get("listen", "0.0.0.0"),
                "protocol": protocol,
                "settings": self._build_protocol_settings(protocol, users, inb),
            }

            # Stream settings (transport + security)
            stream = self._build_stream_settings(inb)
            if stream:
                xray_inbound["streamSettings"] = stream

            xray_inbounds.append(xray_inbound)

        config = {
            "log": {"loglevel": "warning"},
            "stats": {},
            "api": {
                "tag": "api",
                "services": ["HandlerService", "StatsService"],
            },
            "policy": {
                "levels": {
                    "0": {
                        "statsUserUplink": True,
                        "statsUserDownlink": True,
                    }
                },
                "system": {
                    "statsInboundUplink": True,
                    "statsInboundDownlink": True,
                },
            },
            "inbounds": [
                # API inbound (local only)
                {
                    "tag": "api",
                    "port": XRAY_API_PORT,
                    "listen": "127.0.0.1",
                    "protocol": "dokodemo-door",
                    "settings": {"address": "127.0.0.1"},
                },
                *xray_inbounds,
            ],
            "outbounds": [
                {"tag": "direct", "protocol": "freedom"},
                {"tag": "blackhole", "protocol": "blackhole"},
                *self._build_outbounds(outbounds),
            ],
            "routing": {
                "rules": [
                    {
                        "type": "field",
                        "inboundTag": ["api"],
                        "outboundTag": "api",
                    },
                    *self._build_routing_rules(proxy_users),
                ],
            },
        }
        return config

    def _build_protocol_settings(
        self, protocol: str, users: list[dict], inbound: dict
    ) -> dict:
        """Build protocol-specific settings block."""
        if protocol == "vless":
            clients = []
            for u in users:
                if not u.get("enabled", True):
                    continue
                client = {
                    "id": u["uuid"],
                    "email": u["email"],
                    "level": 0,
                }
                if u.get("flow"):
                    client["flow"] = u["flow"]
                clients.append(client)
            return {
                "clients": clients,
                "decryption": "none",
            }

        elif protocol == "trojan":
            clients = []
            for u in users:
                if not u.get("enabled", True):
                    continue
                clients.append({
                    "password": u["password"],
                    "email": u["email"],
                    "level": 0,
                })
            return {"clients": clients}

        elif protocol == "shadowsocks":
            # Xray shadowsocks supports multi-user via "clients" (2022 methods)
            # or single-user mode
            extra = json.loads(inbound.get("settings") or "{}")
            method = extra.get("method", "aes-256-gcm")

            if method.startswith("2022-"):
                # Multi-user: server key + per-user keys
                clients = []
                for u in users:
                    if not u.get("enabled", True):
                        continue
                    clients.append({
                        "password": u["password"],
                        "email": u["email"],
                        "level": 0,
                    })
                return {
                    "method": method,
                    "password": extra.get("server_password", ""),
                    "clients": clients,
                    "network": "tcp,udp",
                }
            else:
                # Legacy single-user (first user's password)
                pw = users[0]["password"] if users else "default-password"
                return {
                    "method": method,
                    "password": pw,
                    "network": "tcp,udp",
                }

        elif protocol in ("http", "socks"):
            accounts = []
            for u in users:
                if not u.get("enabled", True):
                    continue
                accounts.append({
                    "user": u.get("uuid") or u["email"].split("@")[0],
                    "pass": u["password"],
                })
            settings = {}
            if accounts:
                settings["accounts"] = accounts
            if protocol == "socks":
                settings["auth"] = "password" if accounts else "noauth"
                settings["udp"] = True
            return settings

        return {}

    def _build_stream_settings(self, inbound: dict) -> dict | None:
        """Build streamSettings from transport + security config."""
        transport = inbound.get("transport", "tcp")
        security = inbound.get("security", "none")

        stream: dict[str, Any] = {"network": transport}

        # Transport settings
        transport_json = json.loads(inbound.get("transport_settings") or "{}")
        if transport == "ws" and transport_json:
            stream["wsSettings"] = {
                "path": transport_json.get("path", "/"),
                "headers": {"Host": transport_json.get("host", "")},
            }
        elif transport == "grpc" and transport_json:
            stream["grpcSettings"] = {
                "serviceName": transport_json.get("service_name", ""),
            }

        # Security settings
        security_json = json.loads(inbound.get("security_settings") or "{}")
        if security == "tls":
            stream["security"] = "tls"
            tls = {}
            if security_json.get("sni"):
                tls["serverName"] = security_json["sni"]
            if security_json.get("cert_path") and security_json.get("key_path"):
                tls["certificates"] = [{
                    "certificateFile": security_json["cert_path"],
                    "keyFile": security_json["key_path"],
                }]
            stream["tlsSettings"] = tls
        elif security == "reality":
            stream["security"] = "reality"
            stream["realitySettings"] = {
                "show": False,
                "dest": security_json.get("dest", ""),
                "xver": 0,
                "serverNames": security_json.get("server_names", []),
                "privateKey": security_json.get("private_key", ""),
                "shortIds": security_json.get("short_ids", [""]),
            }
        elif security == "none":
            stream["security"] = "none"

        return stream

    def _build_outbounds(self, outbounds: list[dict]) -> list[dict]:
        """Build Xray outbound configs from outbound definitions."""
        result = []
        for ob in outbounds:
            if not ob.get("enabled", True):
                continue

            protocol = ob["protocol"]
            if protocol in ("direct", "blackhole"):
                continue  # Already added as defaults

            xray_ob: dict = {
                "tag": ob["tag"],
                "protocol": protocol,
            }

            if protocol == "vless":
                xray_ob["settings"] = {
                    "vnext": [{
                        "address": ob.get("server", ""),
                        "port": ob.get("server_port", 443),
                        "users": [{"id": ob.get("uuid", ""), "flow": ob.get("flow", ""), "encryption": "none"}],
                    }]
                }
            elif protocol == "trojan":
                xray_ob["settings"] = {
                    "servers": [{
                        "address": ob.get("server", ""),
                        "port": ob.get("server_port", 443),
                        "password": ob.get("password", ""),
                    }]
                }
            elif protocol == "shadowsocks":
                xray_ob["settings"] = {
                    "servers": [{
                        "address": ob.get("server", ""),
                        "port": ob.get("server_port", 443),
                        "method": ob.get("method", "aes-256-gcm"),
                        "password": ob.get("password", ""),
                    }]
                }
            elif protocol == "wireguard":
                xray_ob["settings"] = {
                    "secretKey": ob.get("private_key", ""),
                    "address": [ob.get("local_address", "10.0.0.2/32")],
                    "peers": [{
                        "publicKey": ob.get("peer_public_key", ""),
                        "endpoint": f"{ob.get('server', '')}:{ob.get('server_port', 51820)}",
                    }],
                    "mtu": ob.get("mtu", 1420),
                }
            elif protocol in ("http", "socks"):
                server = {
                    "address": ob.get("server", ""),
                    "port": ob.get("server_port", 1080),
                }
                if ob.get("uuid"):
                    server["users"] = [{"user": ob["uuid"], "pass": ob.get("password", "")}]
                xray_ob["settings"] = {"servers": [server]}

            # Stream settings
            stream = self._build_stream_settings(ob)
            if stream and protocol not in ("wireguard",):
                xray_ob["streamSettings"] = stream

            result.append(xray_ob)
        return result

    def _build_routing_rules(self, proxy_users: list[dict]) -> list[dict]:
        """Build routing rules to map users to their outbounds."""
        rules = []
        # Group users by (inbound_tag, outbound_tag)
        mapping: dict[tuple[str, str], list[str]] = {}
        for pu in proxy_users:
            if not pu.get("enabled", True):
                continue
            outbound_tag = pu.get("outbound_tag", "direct")
            if outbound_tag == "direct":
                continue  # Default, no rule needed
            inbound_tag = pu.get("inbound_tag", "")
            key = (inbound_tag, outbound_tag)
            mapping.setdefault(key, []).append(pu["email"])

        for (inbound_tag, outbound_tag), emails in mapping.items():
            rules.append({
                "type": "field",
                "inboundTag": [inbound_tag],
                "user": emails,
                "outboundTag": outbound_tag,
            })
        return rules

    def start(self, config_path: str) -> bool:
        """Start Xray-core process."""
        global _xray_pid

        if self.is_running():
            logger.info("Xray already running")
            return True

        XRAY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        result = run_command(
            [XRAY_BINARY, "run", "-config", config_path],
            timeout=10,
        )
        # In dry-run mode this returns success without starting
        logger.info(f"Xray start command issued: config={config_path}")
        return result.returncode == 0

    def stop(self) -> bool:
        """Stop Xray-core process."""
        global _xray_pid
        result = run_command(["pkill", "-f", f"{XRAY_BINARY}"], timeout=5)
        _xray_pid = None
        logger.info("Xray stop command issued")
        return True

    def restart(self, config_path: str) -> bool:
        """Restart Xray by stopping then starting."""
        self.stop()
        return self.start(config_path)

    def is_running(self) -> bool:
        """Check if Xray process is running."""
        result = run_command(["pgrep", "-f", XRAY_BINARY], timeout=5)
        return result.returncode == 0

    def get_traffic_stats(self) -> dict[str, dict[str, int]]:
        """Query Xray gRPC API for per-user traffic stats."""
        result = run_command(
            [XRAY_BINARY, "api", "statsquery",
             f"--server=127.0.0.1:{XRAY_API_PORT}", "-pattern", "user>>>"],
            timeout=10,
        )
        if result.returncode != 0:
            return {}

        stats: dict[str, dict[str, int]] = {}
        try:
            data = json.loads(result.stdout) if result.stdout.strip() else {}
            for stat in data.get("stat", []):
                # name format: "user>>>email>>>traffic>>>uplink" or "downlink"
                name = stat.get("name", "")
                value = int(stat.get("value", 0))
                parts = name.split(">>>")
                if len(parts) == 4 and parts[0] == "user" and parts[2] == "traffic":
                    email = parts[1]
                    direction = parts[3]  # "uplink" or "downlink"
                    if email not in stats:
                        stats[email] = {"up": 0, "down": 0}
                    if direction == "uplink":
                        stats[email]["up"] = value
                    elif direction == "downlink":
                        stats[email]["down"] = value
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Xray stats: {e}")

        return stats
