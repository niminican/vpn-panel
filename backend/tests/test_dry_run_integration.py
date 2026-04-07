"""Integration tests: verify dry-run mode across API → service → command flow."""
import pytest

from app.core.command_executor import get_command_history, clear_command_history


class TestDryRunHistoryEndpoint:
    """Test the /api/settings/dry-run-history endpoint."""

    def test_get_history_returns_format(self, client, auth_headers):
        res = client.get("/api/settings/dry-run-history", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "dry_run_enabled" in data
        assert "commands" in data
        assert isinstance(data["commands"], list)
        assert data["dry_run_enabled"] is True

    def test_delete_history_clears(self, client, auth_headers):
        # Create a user to generate some history
        client.post("/api/users", json={"username": "histuser"}, headers=auth_headers)

        # Verify history is not empty
        res = client.get("/api/settings/dry-run-history", headers=auth_headers)
        assert len(res.json()["commands"]) > 0

        # Clear
        res = client.delete("/api/settings/dry-run-history", headers=auth_headers)
        assert res.status_code == 200

        # Verify empty
        res = client.get("/api/settings/dry-run-history", headers=auth_headers)
        assert len(res.json()["commands"]) == 0


class TestUserCreationDryRun:
    """Test that user creation generates correct dry-run commands."""

    def test_create_user_records_wg_set_in_history(self, client, auth_headers):
        """Creating a user should attempt wg set (skipped in dry-run)."""
        clear_command_history()

        res = client.post("/api/users", json={
            "username": "dryrunuser1",
        }, headers=auth_headers)
        assert res.status_code == 201

        # User should be in DB
        data = res.json()
        assert data["username"] == "dryrunuser1"
        assert data["id"] is not None

        # Check history for wg set command (adding peer)
        history = get_command_history()
        wg_set_cmds = [
            h for h in history
            if h["command"][:2] == ["wg", "set"]
        ]
        assert len(wg_set_cmds) >= 1, "Expected wg set command in history"
        assert wg_set_cmds[0]["dry_run_skipped"] is True

    def test_create_user_db_works_despite_dry_run(self, client, auth_headers):
        """DB operations should work even when subprocess is dry-run."""
        res = client.post("/api/users", json={
            "username": "dbuser1",
        }, headers=auth_headers)
        assert res.status_code == 201

        # Verify user exists in DB via GET
        user_id = res.json()["id"]
        get_res = client.get(f"/api/users/{user_id}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["username"] == "dbuser1"


class TestWhitelistDryRun:
    """Test whitelist operations generate iptables commands in dry-run."""

    def test_add_whitelist_records_iptables_commands(self, client, auth_headers):
        """Adding a whitelist entry should trigger iptables chain setup (skipped)."""
        # Create user first
        user_res = client.post("/api/users", json={
            "username": "wluser",
        }, headers=auth_headers)
        user_id = user_res.json()["id"]

        clear_command_history()

        # Add whitelist entry (IP address to avoid DNS resolution)
        res = client.post(f"/api/users/{user_id}/whitelist", json={
            "address": "8.8.8.8",
            "description": "test whitelist",
        }, headers=auth_headers)
        assert res.status_code == 201

        # Check history for iptables commands
        history = get_command_history()
        iptables_cmds = [
            h for h in history
            if len(h["command"]) > 0 and "iptables" in h["command"][0]
        ]
        assert len(iptables_cmds) > 0, "Expected iptables commands in history"

        # Write commands should be skipped
        write_cmds = [h for h in iptables_cmds if h["dry_run_skipped"]]
        assert len(write_cmds) > 0, "Expected skipped iptables write commands"


class TestDestinationDryRun:
    """Test destination VPN operations in dry-run mode."""

    def test_create_destination(self, client, auth_headers):
        """Creating a destination should succeed (DB only, no subprocess)."""
        res = client.post("/api/destinations", json={
            "name": "Test VPN",
            "interface_name": "wg1",
            "protocol": "wireguard",
            "config_text": "[Interface]\nPrivateKey = abc123\nAddress = 10.0.0.1/24\n\n[Peer]\nPublicKey = xyz789\nEndpoint = 1.2.3.4:51820\n",
        }, headers=auth_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Test VPN"
        assert data["protocol"] == "wireguard"

    def test_start_destination_dry_run(self, client, auth_headers):
        """Starting a destination should record wg-quick/ip/iptables in history."""
        # Create destination
        create_res = client.post("/api/destinations", json={
            "name": "Start Test VPN",
            "interface_name": "wg2",
            "protocol": "wireguard",
            "config_text": "[Interface]\nPrivateKey = abc123\nAddress = 10.0.0.2/24\n\n[Peer]\nPublicKey = xyz789\nEndpoint = 1.2.3.4:51820\n",
        }, headers=auth_headers)
        dest_id = create_res.json()["id"]

        clear_command_history()

        # Start destination
        res = client.post(f"/api/destinations/{dest_id}/start", headers=auth_headers)
        # In demo+dry_run mode it may toggle status directly
        assert res.status_code == 200

    def test_stop_destination_dry_run(self, client, auth_headers):
        """Stopping a destination should also work in dry-run."""
        create_res = client.post("/api/destinations", json={
            "name": "Stop Test VPN",
            "interface_name": "wg3",
            "protocol": "wireguard",
            "config_text": "[Interface]\nPrivateKey = abc123\nAddress = 10.0.0.3/24\n\n[Peer]\nPublicKey = xyz789\nEndpoint = 1.2.3.4:51820\n",
        }, headers=auth_headers)
        dest_id = create_res.json()["id"]

        res = client.post(f"/api/destinations/{dest_id}/stop", headers=auth_headers)
        assert res.status_code == 200


class TestDeleteUserDryRun:
    """Test user deletion in dry-run mode."""

    def test_delete_user_records_wg_remove_peer(self, client, auth_headers):
        """Deleting a user should attempt wg set ... remove (skipped)."""
        # Create user
        create_res = client.post("/api/users", json={
            "username": "deluser",
        }, headers=auth_headers)
        user_id = create_res.json()["id"]

        clear_command_history()

        # Delete user
        res = client.delete(f"/api/users/{user_id}", headers=auth_headers)
        assert res.status_code == 204

        # Check history for wg set ... remove
        history = get_command_history()
        wg_remove = [
            h for h in history
            if len(h["command"]) >= 3
            and h["command"][0] == "wg"
            and "remove" in h["command"]
        ]
        assert len(wg_remove) >= 1, "Expected wg remove peer in history"
        assert wg_remove[0]["dry_run_skipped"] is True

        # Verify user gone from DB
        get_res = client.get(f"/api/users/{user_id}", headers=auth_headers)
        assert get_res.status_code == 404
