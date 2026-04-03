"""Tests for RBAC (Role-Based Access Control) enforcement."""
import pytest


class TestRBACEnforcement:
    """Test that limited admins can only access endpoints they have permission for."""

    def test_limited_admin_can_view_users(self, client, limited_auth_headers):
        """Limited admin with users.view can list users."""
        res = client.get("/api/users", headers=limited_auth_headers)
        assert res.status_code == 200

    def test_limited_admin_cannot_create_users(self, client, limited_auth_headers):
        """Limited admin without users.create cannot create users."""
        res = client.post("/api/users", json={
            "username": "newuser",
        }, headers=limited_auth_headers)
        assert res.status_code == 403

    def test_limited_admin_cannot_delete_users(self, client, limited_auth_headers, auth_headers):
        """Limited admin without users.delete cannot delete users."""
        # Create user as super admin
        create_res = client.post("/api/users", json={"username": "testuser"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        # Try to delete as limited admin
        res = client.delete(f"/api/users/{user_id}", headers=limited_auth_headers)
        assert res.status_code == 403

    def test_limited_admin_cannot_edit_users(self, client, limited_auth_headers, auth_headers):
        """Limited admin without users.edit cannot toggle users."""
        create_res = client.post("/api/users", json={"username": "testuser"}, headers=auth_headers)
        user_id = create_res.json()["id"]

        res = client.post(f"/api/users/{user_id}/toggle", headers=limited_auth_headers)
        assert res.status_code == 403

    def test_limited_admin_can_view_logs(self, client, limited_auth_headers):
        """Limited admin with logs.view can access logs."""
        res = client.get("/api/logs", headers=limited_auth_headers)
        assert res.status_code == 200

    def test_limited_admin_cannot_manage_destinations(self, client, limited_auth_headers):
        """Limited admin without destinations.manage cannot create destinations."""
        res = client.post("/api/destinations", json={
            "name": "test",
            "interface_name": "wg1",
            "protocol": "wireguard",
        }, headers=limited_auth_headers)
        assert res.status_code == 403

    def test_limited_admin_cannot_manage_packages(self, client, limited_auth_headers):
        """Limited admin without packages.manage cannot create packages."""
        res = client.post("/api/packages", json={
            "name": "Basic",
            "bandwidth_limit": 1073741824,
            "speed_limit": 1024,
            "duration_days": 30,
            "price": 10.0,
        }, headers=limited_auth_headers)
        assert res.status_code == 403

    def test_limited_admin_cannot_manage_settings(self, client, limited_auth_headers):
        """Limited admin without settings.manage cannot update settings."""
        res = client.put("/api/settings", json=[
            {"key": "panel_language", "value": "fa"},
        ], headers=limited_auth_headers)
        assert res.status_code == 403

    def test_super_admin_can_do_everything(self, client, auth_headers):
        """Super admin should have access to all endpoints."""
        # Users
        res = client.get("/api/users", headers=auth_headers)
        assert res.status_code == 200

        # Destinations
        res = client.get("/api/destinations", headers=auth_headers)
        assert res.status_code == 200

        # Logs
        res = client.get("/api/logs", headers=auth_headers)
        assert res.status_code == 200

        # Settings
        res = client.get("/api/settings", headers=auth_headers)
        assert res.status_code == 200

        # Alerts
        res = client.get("/api/alerts", headers=auth_headers)
        assert res.status_code == 200

        # Packages
        res = client.get("/api/packages", headers=auth_headers)
        assert res.status_code == 200

    def test_unauthenticated_access_denied(self, client):
        """All protected endpoints should reject requests without auth."""
        endpoints = [
            ("GET", "/api/users"),
            ("GET", "/api/destinations"),
            ("GET", "/api/logs"),
            ("GET", "/api/settings"),
            ("GET", "/api/alerts"),
            ("GET", "/api/packages"),
            ("GET", "/api/dashboard"),
        ]
        for method, url in endpoints:
            if method == "GET":
                res = client.get(url)
            assert res.status_code == 422  # Missing auth header
