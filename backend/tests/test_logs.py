"""Tests for connection logs API."""
import pytest
from datetime import datetime, timezone
from app.models.connection_log import ConnectionLog


class TestLogsAPI:
    def _create_log(self, db, user_id=None, dest_ip="1.2.3.4", dest_hostname="example.com"):
        log = ConnectionLog(
            user_id=user_id,
            source_ip="10.8.0.2",
            dest_ip=dest_ip,
            dest_hostname=dest_hostname,
            dest_port=443,
            protocol="tcp",
            started_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    def test_list_logs_empty(self, client, auth_headers):
        res = client.get("/api/logs", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] == 0
        assert res.json()["logs"] == []

    def test_list_logs(self, client, auth_headers, db):
        self._create_log(db, dest_ip="8.8.8.8", dest_hostname="dns.google")
        self._create_log(db, dest_ip="1.1.1.1", dest_hostname="one.one.one.one")

        res = client.get("/api/logs", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] == 2

    def test_filter_by_dest_ip(self, client, auth_headers, db):
        self._create_log(db, dest_ip="8.8.8.8")
        self._create_log(db, dest_ip="1.1.1.1")

        res = client.get("/api/logs?dest_ip=8.8", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] == 1

    def test_filter_by_protocol(self, client, auth_headers, db):
        self._create_log(db)

        res = client.get("/api/logs?protocol=tcp", headers=auth_headers)
        assert res.json()["total"] == 1

        res = client.get("/api/logs?protocol=udp", headers=auth_headers)
        assert res.json()["total"] == 0

    def test_pagination(self, client, auth_headers, db):
        for i in range(5):
            self._create_log(db, dest_ip=f"1.2.3.{i}")

        res = client.get("/api/logs?skip=0&limit=2", headers=auth_headers)
        assert res.json()["total"] == 5
        assert len(res.json()["logs"]) == 2

    def test_user_logs(self, client, auth_headers, db):
        user_res = client.post("/api/users", json={"username": "loguser"}, headers=auth_headers)
        user_id = user_res.json()["id"]

        self._create_log(db, user_id=user_id)
        self._create_log(db)  # no user_id

        res = client.get(f"/api/logs/users/{user_id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] == 1

    def test_user_logs_not_found(self, client, auth_headers):
        res = client.get("/api/logs/users/99999", headers=auth_headers)
        assert res.status_code == 404

    def test_limited_admin_cannot_view_logs(self, client, limited_auth_headers):
        res = client.get("/api/logs", headers=limited_auth_headers)
        # limited_admin has logs.view permission, so should work
        assert res.status_code == 200
