"""Tests for user management endpoints."""
import pytest


class TestUserCRUD:
    def test_create_user(self, client, auth_headers):
        res = client.post("/api/users", json={
            "username": "testuser1",
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["username"] == "testuser1"
        assert data["enabled"] is True
        assert data["assigned_ip"] is not None

    def test_create_duplicate_user(self, client, auth_headers):
        client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        assert res.status_code == 409

    def test_list_users(self, client, auth_headers):
        client.post("/api/users", json={"username": "user1"}, headers=auth_headers)
        client.post("/api/users", json={"username": "user2"}, headers=auth_headers)

        res = client.get("/api/users", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2
        assert len(data["users"]) == 2

    def test_get_user(self, client, auth_headers):
        create_res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        res = client.get(f"/api/users/{user_id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["username"] == "testuser1"

    def test_get_nonexistent_user(self, client, auth_headers):
        res = client.get("/api/users/99999", headers=auth_headers)
        assert res.status_code == 404

    def test_delete_user(self, client, auth_headers):
        create_res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        res = client.delete(f"/api/users/{user_id}", headers=auth_headers)
        assert res.status_code == 204

        # Verify deleted
        res = client.get(f"/api/users/{user_id}", headers=auth_headers)
        assert res.status_code == 404

    def test_toggle_user(self, client, auth_headers):
        create_res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        # Disable
        res = client.post(f"/api/users/{user_id}/toggle", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["enabled"] is False

        # Enable
        res = client.post(f"/api/users/{user_id}/toggle", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["enabled"] is True

    def test_reset_bandwidth(self, client, auth_headers):
        create_res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        res = client.post(f"/api/users/{user_id}/reset-bandwidth", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["bandwidth_used_up"] == 0
        assert res.json()["bandwidth_used_down"] == 0

    def test_get_user_config(self, client, auth_headers):
        create_res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        res = client.get(f"/api/users/{user_id}/config", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "config_text" in data
        assert "qr_code_base64" in data

    def test_search_users(self, client, auth_headers):
        client.post("/api/users", json={"username": "alice"}, headers=auth_headers)
        client.post("/api/users", json={"username": "bob"}, headers=auth_headers)

        res = client.get("/api/users?search=ali", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] == 1
        assert res.json()["users"][0]["username"] == "alice"


class TestUserConfig:
    def test_get_config_with_editable_fields(self, client, auth_headers):
        create_res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        res = client.get(f"/api/users/{user_id}/config", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "dns" in data
        assert "allowed_ips" in data
        assert "endpoint" in data
        assert "persistent_keepalive" in data

    def test_update_config(self, client, auth_headers):
        create_res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        res = client.put(f"/api/users/{user_id}/config", json={
            "dns": "8.8.8.8",
            "allowed_ips": "0.0.0.0/0",
            "mtu": 1400,
            "persistent_keepalive": 30,
        }, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "config_text" in data
        assert "qr_code_base64" in data

    def test_update_config_nonexistent_user(self, client, auth_headers):
        res = client.put("/api/users/99999/config", json={
            "dns": "8.8.8.8",
        }, headers=auth_headers)
        assert res.status_code == 404


class TestUserSessions:
    def test_list_user_sessions_empty(self, client, auth_headers):
        create_res = client.post("/api/users", json={"username": "testuser1"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        res = client.get(f"/api/users/{user_id}/sessions", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] == 0
        assert res.json()["sessions"] == []
