"""Tests for outbound management API."""
import pytest


class TestOutboundCRUD:
    def test_create_direct_outbound(self, client, auth_headers):
        res = client.post("/api/outbounds", json={
            "tag": "my-direct",
            "protocol": "direct",
        }, headers=auth_headers)
        assert res.status_code == 201
        assert res.json()["protocol"] == "direct"

    def test_create_vless_outbound(self, client, auth_headers):
        res = client.post("/api/outbounds", json={
            "tag": "vless-germany",
            "protocol": "vless",
            "server": "1.2.3.4",
            "server_port": 443,
            "uuid": "test-uuid-1234",
            "security": "tls",
        }, headers=auth_headers)
        assert res.status_code == 201
        assert res.json()["tag"] == "vless-germany"
        assert res.json()["server"] == "1.2.3.4"

    def test_create_trojan_outbound(self, client, auth_headers):
        res = client.post("/api/outbounds", json={
            "tag": "trojan-nl",
            "protocol": "trojan",
            "server": "5.6.7.8",
            "server_port": 443,
            "password": "secret123",
        }, headers=auth_headers)
        assert res.status_code == 201

    def test_create_wireguard_outbound(self, client, auth_headers):
        res = client.post("/api/outbounds", json={
            "tag": "wg-finland",
            "protocol": "wireguard",
            "server": "9.10.11.12",
            "server_port": 51820,
            "private_key": "test-priv-key",
            "peer_public_key": "test-pub-key",
            "local_address": "10.0.0.2/32",
        }, headers=auth_headers)
        assert res.status_code == 201

    def test_create_proxy_outbound_requires_server(self, client, auth_headers):
        res = client.post("/api/outbounds", json={
            "tag": "no-server",
            "protocol": "vless",
        }, headers=auth_headers)
        assert res.status_code == 400

    def test_create_duplicate_tag(self, client, auth_headers):
        client.post("/api/outbounds", json={"tag": "dup", "protocol": "direct"}, headers=auth_headers)
        res = client.post("/api/outbounds", json={"tag": "dup", "protocol": "direct"}, headers=auth_headers)
        assert res.status_code == 409

    def test_list_outbounds(self, client, auth_headers):
        client.post("/api/outbounds", json={"tag": "list1", "protocol": "direct"}, headers=auth_headers)
        res = client.get("/api/outbounds", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_delete_outbound(self, client, auth_headers):
        create = client.post("/api/outbounds", json={"tag": "del-me", "protocol": "direct"}, headers=auth_headers)
        res = client.delete(f"/api/outbounds/{create.json()['id']}", headers=auth_headers)
        assert res.status_code == 204

    def test_toggle_outbound(self, client, auth_headers):
        create = client.post("/api/outbounds", json={"tag": "toggle-me", "protocol": "direct"}, headers=auth_headers)
        ob_id = create.json()["id"]
        assert create.json()["enabled"] is True

        res = client.post(f"/api/outbounds/{ob_id}/toggle", headers=auth_headers)
        assert res.json()["enabled"] is False

    def test_invalid_protocol(self, client, auth_headers):
        res = client.post("/api/outbounds", json={"tag": "bad", "protocol": "invalid"}, headers=auth_headers)
        assert res.status_code == 400


class TestProxyUserWithOutbound:
    def test_create_proxy_user_with_outbound(self, client, auth_headers):
        """Proxy user can be linked to a specific outbound."""
        # Create user
        user = client.post("/api/users", json={"username": "obuser"}, headers=auth_headers)
        user_id = user.json()["id"]

        # Create inbound
        inb = client.post("/api/inbounds", json={"tag": "ob-vless", "protocol": "vless", "port": 11443}, headers=auth_headers)
        inb_id = inb.json()["id"]

        # Create outbound
        ob = client.post("/api/outbounds", json={
            "tag": "ob-wg", "protocol": "wireguard",
            "server": "1.2.3.4", "server_port": 51820,
            "private_key": "pk", "peer_public_key": "ppk", "local_address": "10.0.0.2/32",
        }, headers=auth_headers)
        ob_id = ob.json()["id"]

        # Create proxy user with outbound
        res = client.post(f"/api/users/{user_id}/proxy", json={
            "inbound_id": inb_id,
            "outbound_id": ob_id,
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["outbound_id"] == ob_id
        assert data["outbound_tag"] == "ob-wg"
        assert data["outbound_protocol"] == "wireguard"

    def test_proxy_user_default_outbound_is_direct(self, client, auth_headers):
        """Without outbound_id, default should be 'direct'."""
        user = client.post("/api/users", json={"username": "defuser"}, headers=auth_headers)
        inb = client.post("/api/inbounds", json={"tag": "def-vless", "protocol": "vless", "port": 11444}, headers=auth_headers)

        res = client.post(f"/api/users/{user.json()['id']}/proxy", json={
            "inbound_id": inb.json()["id"],
        }, headers=auth_headers)
        assert res.status_code == 201
        assert res.json()["outbound_tag"] == "direct"


class TestXrayOutboundConfig:
    def test_xray_generates_outbound_config(self):
        from app.services.proxy_engine.xray import XrayEngine
        engine = XrayEngine()

        config = engine.generate_config(
            inbounds=[{
                "tag": "v-in", "protocol": "vless", "port": 443,
                "enabled": True, "transport_settings": "{}", "security_settings": "{}", "settings": "{}",
            }],
            proxy_users=[{
                "inbound_tag": "v-in", "uuid": "u1", "email": "u@v",
                "enabled": True, "outbound_tag": "wg-out",
            }],
            outbounds=[{
                "tag": "wg-out", "protocol": "wireguard", "enabled": True,
                "server": "1.2.3.4", "server_port": 51820,
                "private_key": "pk", "peer_public_key": "ppk",
                "local_address": "10.0.0.2/32", "mtu": 1420,
            }],
        )

        # Should have direct + blackhole + wg-out
        tags = [o["tag"] for o in config["outbounds"]]
        assert "direct" in tags
        assert "wg-out" in tags

        # Should have routing rule for user → wg-out
        user_rules = [r for r in config["routing"]["rules"] if r.get("outboundTag") == "wg-out"]
        assert len(user_rules) == 1
        assert "u@v" in user_rules[0]["user"]
