"""Tests for admin management API."""
import pytest


class TestAdminManagement:
    def test_get_permissions_list(self, client, auth_headers):
        res = client.get("/api/admins/permissions", headers=auth_headers)
        assert res.status_code == 200
        assert "permissions" in res.json()
        assert "users.view" in res.json()["permissions"]

    def test_get_current_admin(self, client, auth_headers):
        res = client.get("/api/admins/me", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["username"] == "testadmin"
        assert res.json()["role"] == "super_admin"

    def test_list_admins(self, client, auth_headers):
        res = client.get("/api/admins", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_list_admins_forbidden_for_limited(self, client, limited_auth_headers):
        res = client.get("/api/admins", headers=limited_auth_headers)
        assert res.status_code == 403

    def test_create_admin(self, client, auth_headers):
        res = client.post("/api/admins", json={
            "username": "newadmin",
            "password": "securepassword123",
            "role": "admin",
            "permissions": ["users.view", "logs.view"],
        }, headers=auth_headers)
        assert res.status_code == 201
        assert res.json()["username"] == "newadmin"
        assert res.json()["role"] == "admin"

    def test_create_admin_duplicate_username(self, client, auth_headers):
        client.post("/api/admins", json={
            "username": "dupadmin", "password": "securepassword123",
        }, headers=auth_headers)
        res = client.post("/api/admins", json={
            "username": "dupadmin", "password": "securepassword123",
        }, headers=auth_headers)
        assert res.status_code == 409

    def test_create_admin_short_password(self, client, auth_headers):
        res = client.post("/api/admins", json={
            "username": "shortpw", "password": "short",
        }, headers=auth_headers)
        assert res.status_code == 400

    def test_update_admin(self, client, auth_headers, db):
        create_res = client.post("/api/admins", json={
            "username": "updateme", "password": "securepassword123",
        }, headers=auth_headers)
        admin_id = create_res.json()["id"]

        res = client.put(f"/api/admins/{admin_id}", json={
            "permissions": ["users.view", "users.create"],
        }, headers=auth_headers)
        assert res.status_code == 200

    def test_delete_admin(self, client, auth_headers):
        create_res = client.post("/api/admins", json={
            "username": "deleteme", "password": "securepassword123",
        }, headers=auth_headers)
        admin_id = create_res.json()["id"]

        res = client.delete(f"/api/admins/{admin_id}", headers=auth_headers)
        assert res.status_code == 204

    def test_cannot_delete_self(self, client, auth_headers, admin_user):
        res = client.delete(f"/api/admins/{admin_user.id}", headers=auth_headers)
        assert res.status_code == 400

    def test_audit_logs(self, client, auth_headers):
        # Create admin to generate audit log
        client.post("/api/admins", json={
            "username": "audittest", "password": "securepassword123",
        }, headers=auth_headers)

        res = client.get("/api/admins/audit-logs", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] >= 1

    def test_limited_admin_cannot_create(self, client, limited_auth_headers):
        res = client.post("/api/admins", json={
            "username": "blocked", "password": "securepassword123",
        }, headers=limited_auth_headers)
        assert res.status_code == 403
