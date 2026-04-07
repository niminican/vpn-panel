"""Tests for dashboard API."""
import pytest


class TestDashboard:
    def test_get_dashboard(self, client, auth_headers):
        res = client.get("/api/dashboard", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "system" in data
        assert "total_users" in data
        assert "active_users" in data
        assert "online_users" in data
        assert "total_bandwidth_up" in data
        assert "destination_vpns_up" in data
        assert "recent_alerts_count" in data

    def test_dashboard_counts_users(self, client, auth_headers):
        # Create some users
        client.post("/api/users", json={"username": "dash1"}, headers=auth_headers)
        client.post("/api/users", json={"username": "dash2"}, headers=auth_headers)

        res = client.get("/api/dashboard", headers=auth_headers)
        assert res.json()["total_users"] >= 2

    def test_dashboard_unauthenticated(self, client):
        res = client.get("/api/dashboard")
        assert res.status_code == 422 or res.status_code == 401

    def test_dest_vpn_health_not_found(self, client, auth_headers):
        res = client.get("/api/dashboard/dest-vpn/99999/health", headers=auth_headers)
        data = res.json()
        assert "error" in data or res.status_code == 200
