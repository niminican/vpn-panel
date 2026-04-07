"""Tests for schedule management API."""
import pytest


class TestScheduleCRUD:
    def _create_user(self, client, auth_headers, username="scheduser"):
        res = client.post("/api/users", json={"username": username}, headers=auth_headers)
        return res.json()["id"]

    def test_list_schedules_empty(self, client, auth_headers):
        user_id = self._create_user(client, auth_headers)
        res = client.get(f"/api/users/{user_id}/schedules", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_create_schedule(self, client, auth_headers):
        user_id = self._create_user(client, auth_headers)
        res = client.post(f"/api/users/{user_id}/schedules", json={
            "day_of_week": 0,
            "start_time": "09:00",
            "end_time": "17:00",
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["day_of_week"] == 0
        assert data["start_time"] == "09:00"
        assert data["end_time"] == "17:00"
        assert data["enabled"] is True

    def test_create_schedule_user_not_found(self, client, auth_headers):
        res = client.post("/api/users/99999/schedules", json={
            "day_of_week": 0, "start_time": "09:00", "end_time": "17:00",
        }, headers=auth_headers)
        assert res.status_code == 404

    def test_update_schedule(self, client, auth_headers):
        user_id = self._create_user(client, auth_headers)
        create_res = client.post(f"/api/users/{user_id}/schedules", json={
            "day_of_week": 0, "start_time": "09:00", "end_time": "17:00",
        }, headers=auth_headers)
        sched_id = create_res.json()["id"]

        res = client.put(f"/api/users/{user_id}/schedules/{sched_id}", json={
            "day_of_week": 1, "start_time": "10:00", "end_time": "18:00",
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["day_of_week"] == 1

    def test_delete_schedule(self, client, auth_headers):
        user_id = self._create_user(client, auth_headers)
        create_res = client.post(f"/api/users/{user_id}/schedules", json={
            "day_of_week": 0, "start_time": "09:00", "end_time": "17:00",
        }, headers=auth_headers)
        sched_id = create_res.json()["id"]

        res = client.delete(f"/api/users/{user_id}/schedules/{sched_id}", headers=auth_headers)
        assert res.status_code == 204

    def test_delete_nonexistent_schedule(self, client, auth_headers):
        user_id = self._create_user(client, auth_headers)
        res = client.delete(f"/api/users/{user_id}/schedules/99999", headers=auth_headers)
        assert res.status_code == 404
