"""Tests for multi-protocol proxy engine: models, API, config generation, share links."""
import json
import pytest

from app.core.command_executor import clear_command_history
from app.services.proxy_engine.share_links import generate_share_link


class TestShareLinks:
    """Test share link generation for all protocols."""

    def test_vless_link(self):
        link = generate_share_link(
            "vless",
            uuid="5783a3e7-e373-51cd-8642-c83782b807c5",
            host="example.com", port=443,
            remark="test",
            transport="tcp", security="reality",
            security_settings={"sni": "www.google.com", "public_key": "abc123", "short_ids": ["def"]},
            flow="xtls-rprx-vision",
        )
        assert link.startswith("vless://5783a3e7")
        assert "example.com:443" in link
        assert "security=reality" in link
        assert "flow=xtls-rprx-vision" in link

    def test_trojan_link(self):
        link = generate_share_link(
            "trojan",
            password="my-secret-password",
            host="example.com", port=443,
            remark="test",
            security="tls",
            security_settings={"sni": "example.com"},
        )
        assert link.startswith("trojan://")
        assert "example.com:443" in link
        assert "security=tls" in link

    def test_shadowsocks_link(self):
        link = generate_share_link(
            "shadowsocks",
            password="ss-password",
            host="example.com", port=8388,
            remark="test",
            method="aes-256-gcm",
        )
        assert link.startswith("ss://")
        assert "example.com:8388" in link

    def test_http_link(self):
        link = generate_share_link(
            "http",
            uuid="user1",
            password="pass1",
            host="example.com", port=8080,
        )
        assert "user1:pass1@example.com:8080" in link

    def test_socks_link(self):
        link = generate_share_link(
            "socks",
            uuid="user1",
            password="pass1",
            host="example.com", port=1080,
        )
        assert "socks5://" in link
        assert "user1:pass1@example.com:1080" in link


class TestXrayConfigGeneration:
    """Test Xray config generation."""

    def test_generate_vless_config(self):
        from app.services.proxy_engine.xray import XrayEngine
        engine = XrayEngine()

        inbounds = [{
            "tag": "vless-tcp",
            "protocol": "vless",
            "port": 443,
            "listen": "0.0.0.0",
            "transport": "tcp",
            "security": "none",
            "enabled": True,
            "transport_settings": "{}",
            "security_settings": "{}",
            "settings": "{}",
        }]
        users = [{
            "inbound_tag": "vless-tcp",
            "uuid": "test-uuid-1234",
            "email": "user1@vless-tcp",
            "enabled": True,
            "flow": "xtls-rprx-vision",
        }]

        config = engine.generate_config(inbounds, users)

        assert "inbounds" in config
        assert "outbounds" in config
        assert "stats" in config
        assert "api" in config

        # Find our inbound (skip API inbound)
        vless_inb = [i for i in config["inbounds"] if i["tag"] == "vless-tcp"]
        assert len(vless_inb) == 1
        assert vless_inb[0]["protocol"] == "vless"
        assert vless_inb[0]["port"] == 443
        assert len(vless_inb[0]["settings"]["clients"]) == 1
        assert vless_inb[0]["settings"]["clients"][0]["id"] == "test-uuid-1234"

    def test_generate_trojan_config(self):
        from app.services.proxy_engine.xray import XrayEngine
        engine = XrayEngine()

        inbounds = [{
            "tag": "trojan-tcp",
            "protocol": "trojan",
            "port": 1080,
            "listen": "0.0.0.0",
            "transport": "tcp",
            "security": "tls",
            "enabled": True,
            "transport_settings": "{}",
            "security_settings": json.dumps({"sni": "example.com"}),
            "settings": "{}",
        }]
        users = [{
            "inbound_tag": "trojan-tcp",
            "password": "secret123",
            "email": "user1@trojan-tcp",
            "enabled": True,
        }]

        config = engine.generate_config(inbounds, users)
        trojan_inb = [i for i in config["inbounds"] if i["tag"] == "trojan-tcp"]
        assert len(trojan_inb) == 1
        assert trojan_inb[0]["settings"]["clients"][0]["password"] == "secret123"
        assert trojan_inb[0]["streamSettings"]["security"] == "tls"

    def test_disabled_inbound_excluded(self):
        from app.services.proxy_engine.xray import XrayEngine
        engine = XrayEngine()

        inbounds = [{
            "tag": "disabled-inb",
            "protocol": "vless",
            "port": 9999,
            "enabled": False,
            "transport_settings": "{}",
            "security_settings": "{}",
            "settings": "{}",
        }]

        config = engine.generate_config(inbounds, [])
        tags = [i["tag"] for i in config["inbounds"]]
        assert "disabled-inb" not in tags

    def test_disabled_user_excluded(self):
        from app.services.proxy_engine.xray import XrayEngine
        engine = XrayEngine()

        inbounds = [{
            "tag": "test-inb",
            "protocol": "vless",
            "port": 443,
            "enabled": True,
            "transport_settings": "{}",
            "security_settings": "{}",
            "settings": "{}",
        }]
        users = [
            {"inbound_tag": "test-inb", "uuid": "active-uuid", "email": "active@test", "enabled": True},
            {"inbound_tag": "test-inb", "uuid": "disabled-uuid", "email": "disabled@test", "enabled": False},
        ]

        config = engine.generate_config(inbounds, users)
        test_inb = [i for i in config["inbounds"] if i["tag"] == "test-inb"][0]
        assert len(test_inb["settings"]["clients"]) == 1
        assert test_inb["settings"]["clients"][0]["id"] == "active-uuid"


class TestSingboxConfigGeneration:
    """Test sing-box config generation."""

    def test_generate_vless_config(self):
        from app.services.proxy_engine.singbox import SingboxEngine
        engine = SingboxEngine()

        inbounds = [{
            "tag": "vless-tcp",
            "protocol": "vless",
            "port": 443,
            "listen": "0.0.0.0",
            "transport": "tcp",
            "security": "none",
            "enabled": True,
            "transport_settings": "{}",
            "security_settings": "{}",
            "settings": "{}",
        }]
        users = [{
            "inbound_tag": "vless-tcp",
            "uuid": "test-uuid",
            "email": "user1@vless",
            "enabled": True,
            "flow": "",
        }]

        config = engine.generate_config(inbounds, users)
        assert "inbounds" in config
        assert "outbounds" in config
        assert config["inbounds"][0]["type"] == "vless"
        assert config["inbounds"][0]["users"][0]["uuid"] == "test-uuid"


class TestInboundAPI:
    """Test Inbound CRUD API endpoints."""

    def test_create_inbound(self, client, auth_headers):
        res = client.post("/api/inbounds", json={
            "tag": "test-vless",
            "protocol": "vless",
            "port": 10443,
            "engine": "xray",
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["tag"] == "test-vless"
        assert data["protocol"] == "vless"
        assert data["port"] == 10443

    def test_create_duplicate_tag(self, client, auth_headers):
        client.post("/api/inbounds", json={
            "tag": "dup-tag", "protocol": "vless", "port": 10444,
        }, headers=auth_headers)
        res = client.post("/api/inbounds", json={
            "tag": "dup-tag", "protocol": "trojan", "port": 10445,
        }, headers=auth_headers)
        assert res.status_code == 409

    def test_create_duplicate_port(self, client, auth_headers):
        client.post("/api/inbounds", json={
            "tag": "tag1", "protocol": "vless", "port": 10446,
        }, headers=auth_headers)
        res = client.post("/api/inbounds", json={
            "tag": "tag2", "protocol": "trojan", "port": 10446,
        }, headers=auth_headers)
        assert res.status_code == 409

    def test_list_inbounds(self, client, auth_headers):
        client.post("/api/inbounds", json={
            "tag": "list-test", "protocol": "shadowsocks", "port": 10447,
        }, headers=auth_headers)

        res = client.get("/api/inbounds", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_delete_inbound(self, client, auth_headers):
        create_res = client.post("/api/inbounds", json={
            "tag": "del-test", "protocol": "http", "port": 10448,
        }, headers=auth_headers)
        inb_id = create_res.json()["id"]

        res = client.delete(f"/api/inbounds/{inb_id}", headers=auth_headers)
        assert res.status_code == 204

    def test_toggle_inbound(self, client, auth_headers):
        create_res = client.post("/api/inbounds", json={
            "tag": "toggle-test", "protocol": "socks", "port": 10449,
        }, headers=auth_headers)
        inb_id = create_res.json()["id"]
        assert create_res.json()["enabled"] is True

        res = client.post(f"/api/inbounds/{inb_id}/toggle", headers=auth_headers)
        assert res.json()["enabled"] is False

    def test_invalid_protocol(self, client, auth_headers):
        res = client.post("/api/inbounds", json={
            "tag": "bad", "protocol": "invalid", "port": 10450,
        }, headers=auth_headers)
        assert res.status_code == 400


class TestProxyUserAPI:
    """Test Proxy User API endpoints."""

    def _create_user_and_inbound(self, client, auth_headers):
        user_res = client.post("/api/users", json={"username": "proxyuser1"}, headers=auth_headers)
        user_id = user_res.json()["id"]

        inb_res = client.post("/api/inbounds", json={
            "tag": "proxy-vless", "protocol": "vless", "port": 10500,
        }, headers=auth_headers)
        inb_id = inb_res.json()["id"]
        return user_id, inb_id

    def test_create_proxy_user(self, client, auth_headers):
        user_id, inb_id = self._create_user_and_inbound(client, auth_headers)

        res = client.post(f"/api/users/{user_id}/proxy", json={
            "inbound_id": inb_id,
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["user_id"] == user_id
        assert data["inbound_id"] == inb_id
        assert data["uuid"] is not None  # auto-generated
        assert data["inbound_protocol"] == "vless"

    def test_list_proxy_users(self, client, auth_headers):
        user_id, inb_id = self._create_user_and_inbound(client, auth_headers)
        client.post(f"/api/users/{user_id}/proxy", json={"inbound_id": inb_id}, headers=auth_headers)

        res = client.get(f"/api/users/{user_id}/proxy", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_get_proxy_config(self, client, auth_headers):
        user_id, inb_id = self._create_user_and_inbound(client, auth_headers)
        create_res = client.post(f"/api/users/{user_id}/proxy", json={"inbound_id": inb_id}, headers=auth_headers)
        proxy_id = create_res.json()["id"]

        res = client.get(f"/api/users/{user_id}/proxy/{proxy_id}/config", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["protocol"] == "vless"
        assert data["share_link"].startswith("vless://")

    def test_delete_proxy_user(self, client, auth_headers):
        user_id, inb_id = self._create_user_and_inbound(client, auth_headers)
        create_res = client.post(f"/api/users/{user_id}/proxy", json={"inbound_id": inb_id}, headers=auth_headers)
        proxy_id = create_res.json()["id"]

        res = client.delete(f"/api/users/{user_id}/proxy/{proxy_id}", headers=auth_headers)
        assert res.status_code == 204

    def test_toggle_proxy_user(self, client, auth_headers):
        user_id, inb_id = self._create_user_and_inbound(client, auth_headers)
        create_res = client.post(f"/api/users/{user_id}/proxy", json={"inbound_id": inb_id}, headers=auth_headers)
        proxy_id = create_res.json()["id"]

        res = client.post(f"/api/users/{user_id}/proxy/{proxy_id}/toggle", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["enabled"] is False

    def test_trojan_auto_generates_password(self, client, auth_headers):
        user_res = client.post("/api/users", json={"username": "trojanuser"}, headers=auth_headers)
        user_id = user_res.json()["id"]

        inb_res = client.post("/api/inbounds", json={
            "tag": "trojan-inb", "protocol": "trojan", "port": 10501,
        }, headers=auth_headers)
        inb_id = inb_res.json()["id"]

        res = client.post(f"/api/users/{user_id}/proxy", json={"inbound_id": inb_id}, headers=auth_headers)
        assert res.status_code == 201
        assert res.json()["password"] is not None
        assert len(res.json()["password"]) > 10
