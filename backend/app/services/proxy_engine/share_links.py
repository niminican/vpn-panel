"""Generate share links and subscription URLs for proxy protocols."""
from __future__ import annotations

import base64
import json
from urllib.parse import urlencode, quote


def generate_share_link(
    protocol: str,
    *,
    uuid: str | None = None,
    password: str | None = None,
    host: str,
    port: int,
    remark: str = "",
    transport: str = "tcp",
    transport_settings: dict | None = None,
    security: str = "none",
    security_settings: dict | None = None,
    flow: str | None = None,
    method: str | None = None,
) -> str:
    """Generate a share link for the given protocol.

    Returns a URI string like vless://..., trojan://..., ss://..., etc.
    """
    ts = transport_settings or {}
    ss = security_settings or {}
    remark_encoded = quote(remark)

    if protocol == "vless":
        return _vless_link(
            uuid=uuid or "",
            host=host, port=port, remark=remark_encoded,
            transport=transport, ts=ts,
            security=security, ss=ss,
            flow=flow,
        )
    elif protocol == "trojan":
        return _trojan_link(
            password=password or "",
            host=host, port=port, remark=remark_encoded,
            transport=transport, ts=ts,
            security=security, ss=ss,
        )
    elif protocol == "shadowsocks":
        return _ss_link(
            method=method or "aes-256-gcm",
            password=password or "",
            host=host, port=port, remark=remark_encoded,
        )
    elif protocol == "http":
        return f"http://{uuid or ''}:{password or ''}@{host}:{port}"
    elif protocol == "socks":
        return f"socks5://{uuid or ''}:{password or ''}@{host}:{port}"
    else:
        return f"{protocol}://{host}:{port}"


def _vless_link(
    uuid: str, host: str, port: int, remark: str,
    transport: str, ts: dict, security: str, ss: dict,
    flow: str | None,
) -> str:
    params: dict[str, str] = {
        "type": transport,
        "security": security,
    }
    if flow:
        params["flow"] = flow

    # Transport params
    if transport == "ws":
        params["path"] = ts.get("path", "/")
        if ts.get("host"):
            params["host"] = ts["host"]
    elif transport == "grpc":
        params["serviceName"] = ts.get("service_name", "")

    # Security params
    if security == "tls":
        if ss.get("sni"):
            params["sni"] = ss["sni"]
        params["fp"] = ss.get("fingerprint", "chrome")
    elif security == "reality":
        if ss.get("sni"):
            params["sni"] = ss["sni"]
        if ss.get("public_key"):
            params["pbk"] = ss["public_key"]
        if ss.get("short_ids"):
            params["sid"] = ss["short_ids"][0] if isinstance(ss["short_ids"], list) else ss["short_ids"]
        params["fp"] = ss.get("fingerprint", "chrome")

    query = urlencode(params)
    return f"vless://{uuid}@{host}:{port}?{query}#{remark}"


def _trojan_link(
    password: str, host: str, port: int, remark: str,
    transport: str, ts: dict, security: str, ss: dict,
) -> str:
    params: dict[str, str] = {
        "type": transport,
        "security": security,
    }

    if transport == "ws":
        params["path"] = ts.get("path", "/")
        if ts.get("host"):
            params["host"] = ts["host"]
    elif transport == "grpc":
        params["serviceName"] = ts.get("service_name", "")

    if security == "tls":
        if ss.get("sni"):
            params["sni"] = ss["sni"]

    query = urlencode(params)
    return f"trojan://{quote(password)}@{host}:{port}?{query}#{remark}"


def _ss_link(
    method: str, password: str, host: str, port: int, remark: str,
) -> str:
    # Standard ss:// format: ss://base64(method:password)@host:port#remark
    user_info = f"{method}:{password}"
    encoded = base64.urlsafe_b64encode(user_info.encode()).decode().rstrip("=")
    return f"ss://{encoded}@{host}:{port}#{remark}"
