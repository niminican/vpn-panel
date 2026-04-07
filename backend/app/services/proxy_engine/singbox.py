"""sing-box engine implementation."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from app.core.command_executor import run_command
from app.services.proxy_engine.base import ProxyEngine

logger = logging.getLogger(__name__)

SINGBOX_BINARY = os.environ.get("SINGBOX_BINARY", "/usr/local/bin/sing-box")
SINGBOX_CONFIG_DIR = Path(os.environ.get("SINGBOX_CONFIG_DIR", "/app/data/singbox"))
SINGBOX_API_PORT = int(os.environ.get("SINGBOX_API_PORT", "10086"))


class SingboxEngine(ProxyEngine):

    @property
    def name(self) -> str:
        return "singbox"

    @property
    def binary_path(self) -> str:
        return SINGBOX_BINARY

    def generate_config(self, inbounds: list[dict], proxy_users: list[dict]) -> dict:
        """Generate sing-box config.json."""
        users_by_tag: dict[str, list[dict]] = {}
        for pu in proxy_users:
            tag = pu.get("inbound_tag", "")
            users_by_tag.setdefault(tag, []).append(pu)

        sb_inbounds = []
        for inb in inbounds:
            if not inb.get("enabled", True):
                continue

            tag = inb["tag"]
            protocol = inb["protocol"]
            users = users_by_tag.get(tag, [])

            sb_inbound = self._build_inbound(protocol, tag, inb, users)
            if sb_inbound:
                sb_inbounds.append(sb_inbound)

        config = {
            "log": {"level": "warn"},
            "experimental": {
                "clash_api": {
                    "external_controller": f"127.0.0.1:{SINGBOX_API_PORT}",
                },
            },
            "inbounds": sb_inbounds,
            "outbounds": [
                {"type": "direct", "tag": "direct"},
                {"type": "block", "tag": "block"},
            ],
        }
        return config

    def _build_inbound(
        self, protocol: str, tag: str, inb: dict, users: list[dict]
    ) -> dict | None:
        """Build a sing-box inbound config."""
        base = {
            "type": protocol if protocol != "shadowsocks" else "shadowsocks",
            "tag": tag,
            "listen": inb.get("listen", "0.0.0.0"),
            "listen_port": inb["port"],
        }

        # Transport (sing-box uses "transport" field)
        transport = inb.get("transport", "tcp")
        if transport == "ws":
            transport_json = json.loads(inb.get("transport_settings") or "{}")
            base["transport"] = {
                "type": "ws",
                "path": transport_json.get("path", "/"),
                "headers": {"Host": transport_json.get("host", "")},
            }
        elif transport == "grpc":
            transport_json = json.loads(inb.get("transport_settings") or "{}")
            base["transport"] = {
                "type": "grpc",
                "service_name": transport_json.get("service_name", ""),
            }

        # TLS
        security = inb.get("security", "none")
        security_json = json.loads(inb.get("security_settings") or "{}")
        if security == "tls":
            base["tls"] = {
                "enabled": True,
                "server_name": security_json.get("sni", ""),
                "certificate_path": security_json.get("cert_path", ""),
                "key_path": security_json.get("key_path", ""),
            }
        elif security == "reality":
            base["tls"] = {
                "enabled": True,
                "server_name": security_json.get("sni", ""),
                "reality": {
                    "enabled": True,
                    "handshake": {
                        "server": security_json.get("dest", "").split(":")[0],
                        "server_port": int(security_json.get("dest", ":443").split(":")[-1]),
                    },
                    "private_key": security_json.get("private_key", ""),
                    "short_id": security_json.get("short_ids", [""])[0] if security_json.get("short_ids") else "",
                },
            }

        # Protocol-specific users
        active_users = [u for u in users if u.get("enabled", True)]

        if protocol == "vless":
            base["type"] = "vless"
            base["users"] = [
                {"name": u["email"], "uuid": u["uuid"], "flow": u.get("flow", "")}
                for u in active_users
            ]

        elif protocol == "trojan":
            base["type"] = "trojan"
            base["users"] = [
                {"name": u["email"], "password": u["password"]}
                for u in active_users
            ]

        elif protocol == "shadowsocks":
            extra = json.loads(inb.get("settings") or "{}")
            method = extra.get("method", "aes-256-gcm")
            base["type"] = "shadowsocks"
            base["method"] = method
            if method.startswith("2022-"):
                base["password"] = extra.get("server_password", "")
                base["users"] = [
                    {"name": u["email"], "password": u["password"]}
                    for u in active_users
                ]
            else:
                base["password"] = active_users[0]["password"] if active_users else ""

        elif protocol == "http":
            base["type"] = "http"
            base["users"] = [
                {"username": u.get("uuid") or u["email"].split("@")[0], "password": u["password"]}
                for u in active_users
            ]

        elif protocol == "socks":
            base["type"] = "socks"
            base["users"] = [
                {"username": u.get("uuid") or u["email"].split("@")[0], "password": u["password"]}
                for u in active_users
            ]

        return base

    def start(self, config_path: str) -> bool:
        """Start sing-box process."""
        SINGBOX_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        result = run_command(
            [SINGBOX_BINARY, "run", "-config", config_path],
            timeout=10,
        )
        logger.info(f"sing-box start command issued: config={config_path}")
        return result.returncode == 0

    def stop(self) -> bool:
        """Stop sing-box process."""
        result = run_command(["pkill", "-f", SINGBOX_BINARY], timeout=5)
        logger.info("sing-box stop command issued")
        return True

    def restart(self, config_path: str) -> bool:
        """Restart sing-box."""
        self.stop()
        return self.start(config_path)

    def is_running(self) -> bool:
        """Check if sing-box process is running."""
        result = run_command(["pgrep", "-f", SINGBOX_BINARY], timeout=5)
        return result.returncode == 0

    def get_traffic_stats(self) -> dict[str, dict[str, int]]:
        """Query sing-box Clash API for traffic stats.

        Note: sing-box Clash API provides connection-level stats,
        not per-user stats by default. For per-user tracking,
        we rely on database counters updated periodically.
        """
        # sing-box per-user stats requires experimental features
        # For now, return empty — traffic tracked via iptables/conntrack
        return {}
