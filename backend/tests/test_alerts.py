"""Tests for alerts API."""
import pytest
from app.models.alert import Alert


class TestAlerts:
    def _create_alert(self, db, user_id=None, alert_type="test", message="Test alert"):
        alert = Alert(user_id=user_id, type=alert_type, message=message, channel="panel")
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    def test_list_alerts_empty(self, client, auth_headers):
        res = client.get("/api/alerts", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_list_alerts(self, client, auth_headers, db):
        self._create_alert(db, message="Alert 1")
        self._create_alert(db, message="Alert 2")

        res = client.get("/api/alerts", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 2

    def test_list_unread_only(self, client, auth_headers, db):
        a1 = self._create_alert(db, message="Unread")
        a2 = self._create_alert(db, message="Read")
        a2.acknowledged = True
        db.commit()

        res = client.get("/api/alerts?unread_only=true", headers=auth_headers)
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["message"] == "Unread"

    def test_acknowledge_alert(self, client, auth_headers, db):
        alert = self._create_alert(db, message="Ack me")

        res = client.post(f"/api/alerts/{alert.id}/acknowledge", headers=auth_headers)
        assert res.status_code == 200

        db.refresh(alert)
        assert alert.acknowledged is True

    def test_acknowledge_nonexistent(self, client, auth_headers):
        res = client.post("/api/alerts/99999/acknowledge", headers=auth_headers)
        assert res.status_code == 404

    def test_acknowledge_all(self, client, auth_headers, db):
        self._create_alert(db, message="A1")
        self._create_alert(db, message="A2")

        res = client.post("/api/alerts/acknowledge-all", headers=auth_headers)
        assert res.status_code == 200

        unread = client.get("/api/alerts?unread_only=true", headers=auth_headers)
        assert len(unread.json()) == 0
