"""Tests for authentication endpoints."""
import pytest


class TestLogin:
    def test_login_success(self, client, admin_user):
        res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client, admin_user):
        res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "wrongpass",
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self, client):
        res = client.post("/api/auth/login", json={
            "username": "nobody",
            "password": "pass",
        })
        assert res.status_code == 401

    def test_login_rate_limiting(self, client, admin_user):
        """After 5 failed attempts, should return 429."""
        for i in range(5):
            client.post("/api/auth/login", json={
                "username": "testadmin",
                "password": "wrongpass",
            })

        res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "wrongpass",
        })
        assert res.status_code == 429
        assert "Too many failed attempts" in res.json()["detail"]


class TestTokenRefresh:
    def test_refresh_token(self, client, admin_user):
        # Login first
        login_res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        refresh_token = login_res.json()["refresh_token"]

        # Refresh
        res = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_refresh_invalid_token(self, client):
        res = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid-token",
        })
        assert res.status_code == 401


class TestChangePassword:
    def test_change_password_success(self, client, auth_headers):
        res = client.post("/api/auth/change-password", json={
            "current_password": "testpass123",
            "new_password": "newpass456",
        }, headers=auth_headers)
        assert res.status_code == 200

        # Login with new password
        res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "newpass456",
        })
        assert res.status_code == 200

    def test_change_password_wrong_current(self, client, auth_headers):
        res = client.post("/api/auth/change-password", json={
            "current_password": "wrongpass",
            "new_password": "newpass456",
        }, headers=auth_headers)
        assert res.status_code == 400

    def test_change_password_too_short(self, client, auth_headers):
        res = client.post("/api/auth/change-password", json={
            "current_password": "testpass123",
            "new_password": "short",
        }, headers=auth_headers)
        assert res.status_code == 400

    def test_change_password_unauthenticated(self, client):
        res = client.post("/api/auth/change-password", json={
            "current_password": "pass",
            "new_password": "newpass456",
        })
        assert res.status_code == 422  # Missing auth header
