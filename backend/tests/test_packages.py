"""Tests for package management API."""
import pytest


class TestPackageCRUD:
    def test_create_package(self, client, auth_headers):
        res = client.post("/api/packages", json={
            "name": "Basic Plan",
            "duration_days": 30,
            "bandwidth_limit": 10737418240,
            "speed_limit": 5000,
            "max_connections": 2,
            "price": 50000,
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Basic Plan"
        assert data["duration_days"] == 30
        assert data["bandwidth_limit"] == 10737418240

    def test_list_packages(self, client, auth_headers):
        client.post("/api/packages", json={"name": "Pkg1", "duration_days": 30}, headers=auth_headers)
        client.post("/api/packages", json={"name": "Pkg2", "duration_days": 60}, headers=auth_headers)

        res = client.get("/api/packages", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) >= 2

    def test_update_package(self, client, auth_headers):
        create_res = client.post("/api/packages", json={"name": "Old Name", "duration_days": 30}, headers=auth_headers)
        pkg_id = create_res.json()["id"]

        res = client.put(f"/api/packages/{pkg_id}", json={"name": "New Name"}, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["name"] == "New Name"

    def test_update_nonexistent_package(self, client, auth_headers):
        res = client.put("/api/packages/99999", json={"name": "X"}, headers=auth_headers)
        assert res.status_code == 404

    def test_delete_package(self, client, auth_headers):
        create_res = client.post("/api/packages", json={"name": "DeleteMe", "duration_days": 30}, headers=auth_headers)
        pkg_id = create_res.json()["id"]

        res = client.delete(f"/api/packages/{pkg_id}", headers=auth_headers)
        assert res.status_code == 204

    def test_delete_nonexistent_package(self, client, auth_headers):
        res = client.delete("/api/packages/99999", headers=auth_headers)
        assert res.status_code == 404

    def test_limited_admin_cannot_manage_packages(self, client, limited_auth_headers):
        res = client.post("/api/packages", json={"name": "X", "duration_days": 30}, headers=limited_auth_headers)
        assert res.status_code == 403
