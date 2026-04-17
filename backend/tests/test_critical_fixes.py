"""Tests for Phase 1 critical fixes: alerts, firewall mutex, admin enabled, 2FA."""
import asyncio
import threading
from unittest.mock import patch, AsyncMock

import pytest

from app.core.command_executor import clear_command_history


class TestAlertSyncWrapper:
    """Bug 1: Verify _run_async properly executes async coroutines."""

    def test_run_async_executes_coroutine(self):
        from app.services.alert_service import _run_async

        result = []

        async def sample_coro():
            result.append("executed")

        _run_async(sample_coro())
        assert result == ["executed"]

    def test_run_async_handles_exception(self):
        from app.services.alert_service import _run_async

        async def failing_coro():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            _run_async(failing_coro())

    @patch("app.services.alert_service.send_telegram_alert", new_callable=AsyncMock)
    def test_bandwidth_check_calls_telegram(self, mock_telegram, db):
        """Telegram alert should actually be called (not just coroutine created)."""
        from app.models.user import User
        from app.models.setting import Setting

        # Enable alerts
        db.add(Setting(key="global_alerts_enabled", value="true"))

        # Create user near bandwidth limit with telegram
        user = User(
            username="alertuser",
            wg_public_key="test_key",
            wg_private_key="test",
            assigned_ip="10.8.0.2",
            enabled=True,
            alert_enabled=True,
            alert_sent=False,
            alert_threshold=80,
            bandwidth_limit_down=1000,
            bandwidth_used_down=900,  # 90% > 80% threshold
            telegram_chat_id=12345,
        )
        db.add(user)
        db.commit()

        from app.services.alert_service import check_bandwidth_thresholds
        check_bandwidth_thresholds()

        # Telegram should have been called
        mock_telegram.assert_called_once()
        call_args = mock_telegram.call_args
        assert call_args[0][0] == 12345  # chat_id


class TestFirewallMutex:
    """Bug 2: Verify per-user locking exists in sync_firewall."""

    def test_get_user_lock_returns_lock(self):
        from app.services.sync_firewall import _get_user_lock
        lock = _get_user_lock(999)
        assert isinstance(lock, type(threading.Lock()))

    def test_same_user_gets_same_lock(self):
        from app.services.sync_firewall import _get_user_lock
        lock1 = _get_user_lock(42)
        lock2 = _get_user_lock(42)
        assert lock1 is lock2

    def test_different_users_get_different_locks(self):
        from app.services.sync_firewall import _get_user_lock
        lock1 = _get_user_lock(100)
        lock2 = _get_user_lock(200)
        assert lock1 is not lock2


class TestDisabledAdmin:
    """Bug 3: Verify disabled admin tokens are rejected."""

    def test_disabled_admin_cannot_authenticate(self, client, db, admin_user, auth_headers):
        """After disabling an admin, their token should be rejected."""
        # Verify token works
        res = client.get("/api/users", headers=auth_headers)
        assert res.status_code == 200

        # Disable the admin
        admin_user.enabled = False
        db.commit()

        # Same token should now fail
        res = client.get("/api/users", headers=auth_headers)
        assert res.status_code == 401

    def test_enabled_admin_works_normally(self, client, auth_headers):
        """Enabled admin should authenticate normally."""
        res = client.get("/api/users", headers=auth_headers)
        assert res.status_code == 200


class TestTwoFactorAuth:
    """Bug 4: 2FA email authentication flow."""

    def test_login_without_2fa_returns_tokens(self, client, admin_user):
        """Normal login (no 2FA) should return tokens directly."""
        res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["requires_2fa"] is False
        assert data["access_token"] is not None

    @patch("app.api.auth._send_2fa_email")
    def test_login_with_2fa_requires_code(self, mock_email, client, db, admin_user):
        """Login with 2FA enabled should return requires_2fa=True."""
        admin_user.two_factor_enabled = True
        admin_user.two_factor_email = "admin@test.com"
        db.commit()

        res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["requires_2fa"] is True
        assert data["access_token"] is None
        mock_email.assert_called_once()

    @patch("app.api.auth._send_2fa_email")
    @patch("app.api.auth._generate_2fa_code", return_value="123456")
    def test_verify_2fa_with_correct_code(self, mock_code, mock_email, client, db, admin_user):
        """Correct 2FA code should return tokens."""
        admin_user.two_factor_enabled = True
        admin_user.two_factor_email = "admin@test.com"
        db.commit()

        # Login first to get code generated (code is "123456" from mock)
        client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })

        # Verify with the known code
        res = client.post("/api/auth/verify-2fa", json={
            "username": "testadmin",
            "code": "123456",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["access_token"] is not None
        assert data["refresh_token"] is not None

    @patch("app.api.auth._send_2fa_email")
    def test_verify_2fa_with_wrong_code(self, mock_email, client, db, admin_user):
        """Wrong 2FA code should be rejected."""
        admin_user.two_factor_enabled = True
        admin_user.two_factor_email = "admin@test.com"
        db.commit()

        client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })

        res = client.post("/api/auth/verify-2fa", json={
            "username": "testadmin",
            "code": "000000",
        })
        assert res.status_code == 401

    def test_enable_2fa(self, client, auth_headers, db, admin_user):
        """Enable 2FA endpoint should set email and flag."""
        res = client.post("/api/auth/2fa/enable", json={
            "email": "test@example.com",
            "password": "testpass123",
        }, headers=auth_headers)
        assert res.status_code == 200

        db.refresh(admin_user)
        assert admin_user.two_factor_enabled is True
        assert admin_user.two_factor_email == "test@example.com"

    def test_disable_2fa(self, client, auth_headers, db, admin_user):
        """Disable 2FA should clear all 2FA fields."""
        # Enable first
        admin_user.two_factor_enabled = True
        admin_user.two_factor_email = "test@example.com"
        db.commit()

        res = client.post("/api/auth/2fa/disable", json={
            "password": "testpass123",
        }, headers=auth_headers)
        assert res.status_code == 200

        db.refresh(admin_user)
        assert admin_user.two_factor_enabled is False
        assert admin_user.two_factor_email is None

    def test_disable_2fa_wrong_password(self, client, auth_headers):
        """Disable 2FA with wrong password should fail."""
        res = client.post("/api/auth/2fa/disable", json={
            "password": "wrongpassword",
        }, headers=auth_headers)
        assert res.status_code == 400

    def test_2fa_status(self, client, auth_headers):
        """2FA status endpoint should return current state."""
        res = client.get("/api/auth/2fa/status", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "two_factor_enabled" in data
        assert "two_factor_email" in data

    def test_disabled_admin_cannot_login(self, client, db, admin_user):
        """Disabled admin should fail at login, not just token check."""
        admin_user.enabled = False
        db.commit()

        res = client.post("/api/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert res.status_code == 401
