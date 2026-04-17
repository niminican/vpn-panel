"""Tests for the CommandExecutor module (dry-run mode core)."""
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from app.core.command_executor import (
    is_read_only,
    run_command,
    get_command_history,
    clear_command_history,
    _command_history,
)


class TestIsReadOnly:
    """Test command classification: read-only vs write."""

    # ── iptables ──────────────────────────────────────────────────────

    def test_iptables_check_is_read_only(self):
        assert is_read_only(["iptables", "-C", "INPUT", "-p", "tcp"]) is True

    def test_iptables_list_is_read_only(self):
        assert is_read_only(["iptables", "-L", "FORWARD"]) is True

    def test_iptables_save_is_read_only(self):
        assert is_read_only(["iptables", "-S"]) is True

    def test_iptables_append_is_write(self):
        assert is_read_only(["iptables", "-A", "FORWARD", "-j", "ACCEPT"]) is False

    def test_iptables_delete_is_write(self):
        assert is_read_only(["iptables", "-D", "FORWARD", "-j", "DROP"]) is False

    def test_iptables_insert_is_write(self):
        assert is_read_only(["iptables", "-I", "INPUT", "1"]) is False

    def test_iptables_new_chain_is_write(self):
        assert is_read_only(["iptables", "-N", "vpn_user_1"]) is False

    def test_iptables_flush_is_write(self):
        assert is_read_only(["iptables", "-F", "vpn_user_1"]) is False

    def test_iptables_delete_chain_is_write(self):
        assert is_read_only(["iptables", "-X", "vpn_user_1"]) is False

    def test_iptables_nat_table_append_is_write(self):
        assert is_read_only(["iptables", "-t", "nat", "-A", "POSTROUTING"]) is False

    def test_iptables_mangle_is_write(self):
        assert is_read_only(["iptables", "-t", "mangle", "-A", "PREROUTING"]) is False

    # ── WireGuard ─────────────────────────────────────────────────────

    def test_wg_show_is_read_only(self):
        assert is_read_only(["wg", "show", "wg0", "dump"]) is True

    def test_wg_genkey_is_read_only(self):
        assert is_read_only(["wg", "genkey"]) is True

    def test_wg_genpsk_is_read_only(self):
        assert is_read_only(["wg", "genpsk"]) is True

    def test_wg_pubkey_is_read_only(self):
        assert is_read_only(["wg", "pubkey"]) is True

    def test_wg_set_is_write(self):
        assert is_read_only(["wg", "set", "wg0", "peer", "key"]) is False

    def test_wg_quick_up_is_write(self):
        assert is_read_only(["wg-quick", "up", "wg1"]) is False

    def test_wg_quick_down_is_write(self):
        assert is_read_only(["wg-quick", "down", "wg1"]) is False

    # ── ip command ────────────────────────────────────────────────────

    def test_ip_link_show_is_read_only(self):
        assert is_read_only(["ip", "link", "show", "wg0"]) is True

    def test_ip_route_show_is_read_only(self):
        assert is_read_only(["ip", "route", "show", "default"]) is True

    def test_ip_route_add_is_write(self):
        assert is_read_only(["ip", "route", "add", "default", "dev", "wg1"]) is False

    def test_ip_route_del_is_write(self):
        assert is_read_only(["ip", "route", "del", "default"]) is False

    def test_ip_rule_add_is_write(self):
        assert is_read_only(["ip", "rule", "add", "fwmark", "100"]) is False

    def test_ip_rule_del_is_write(self):
        assert is_read_only(["ip", "rule", "del", "fwmark", "100"]) is False

    # ── tc (traffic control) ──────────────────────────────────────────

    def test_tc_show_is_read_only(self):
        assert is_read_only(["tc", "qdisc", "show", "dev", "wg0"]) is True

    def test_tc_add_is_write(self):
        assert is_read_only(["tc", "qdisc", "add", "dev", "wg0", "root"]) is False

    def test_tc_del_is_write(self):
        assert is_read_only(["tc", "class", "del", "dev", "wg0"]) is False

    # ── systemctl ─────────────────────────────────────────────────────

    def test_systemctl_status_is_read_only(self):
        assert is_read_only(["systemctl", "status", "openvpn"]) is True

    def test_systemctl_is_active_is_read_only(self):
        assert is_read_only(["systemctl", "is-active", "openvpn"]) is True

    def test_systemctl_start_is_write(self):
        assert is_read_only(["systemctl", "start", "openvpn@wg1"]) is False

    def test_systemctl_stop_is_write(self):
        assert is_read_only(["systemctl", "stop", "openvpn@wg1"]) is False

    # ── Always read-only tools ────────────────────────────────────────

    def test_ping_is_read_only(self):
        assert is_read_only(["ping", "-c", "1", "8.8.8.8"]) is True

    def test_dig_is_read_only(self):
        assert is_read_only(["dig", "+short", "example.com"]) is True

    def test_curl_is_read_only(self):
        assert is_read_only(["curl", "-s", "https://api.ipify.org"]) is True

    def test_journalctl_is_read_only(self):
        assert is_read_only(["journalctl", "-k", "-f"]) is True

    def test_tcpdump_is_read_only(self):
        assert is_read_only(["tcpdump", "-i", "wg0"]) is True

    # ── Always write tools ────────────────────────────────────────────

    def test_modprobe_is_write(self):
        assert is_read_only(["modprobe", "ifb", "numifbs=1"]) is False

    def test_bash_is_write(self):
        assert is_read_only(["bash", "-c", "wg syncconf wg0"]) is False

    # ── Edge cases ────────────────────────────────────────────────────

    def test_empty_command_is_read_only(self):
        assert is_read_only([]) is True

    def test_unknown_tool_is_write(self):
        assert is_read_only(["unknown-tool", "--flag"]) is False

    def test_full_path_tool_recognized(self):
        assert is_read_only(["/usr/sbin/iptables", "-L"]) is True
        assert is_read_only(["/usr/sbin/iptables", "-A", "INPUT"]) is False


class TestRunCommand:
    """Test run_command behavior in dry-run vs normal mode."""

    @patch("app.core.command_executor.subprocess.run")
    def test_dry_run_skips_write_command(self, mock_run):
        """Write commands should NOT call subprocess in dry-run mode."""
        result = run_command(["iptables", "-A", "FORWARD", "-j", "ACCEPT"])

        mock_run.assert_not_called()
        assert result.returncode == 0
        assert result.stdout == ""

    @patch("app.core.command_executor.subprocess.run")
    def test_dry_run_executes_read_only_command(self, mock_run):
        """Read-only commands should still execute in dry-run mode."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["iptables", "-L"], returncode=0, stdout="Chain INPUT", stderr=""
        )

        result = run_command(["iptables", "-L"])

        mock_run.assert_called_once()
        assert result.returncode == 0
        assert result.stdout == "Chain INPUT"

    @patch("app.core.command_executor.subprocess.run")
    def test_dry_run_skips_wg_set(self, mock_run):
        """wg set should be skipped in dry-run."""
        result = run_command(["wg", "set", "wg0", "peer", "abc123"])

        mock_run.assert_not_called()
        assert result.returncode == 0

    @patch("app.core.command_executor.subprocess.run")
    def test_dry_run_executes_wg_show(self, mock_run):
        """wg show should execute even in dry-run."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["wg", "show"], returncode=0, stdout="wg0\tpeer", stderr=""
        )

        result = run_command(["wg", "show", "wg0", "dump"])

        mock_run.assert_called_once()

    @patch("app.core.command_executor.subprocess.run")
    def test_timeout_returns_minus_one(self, mock_run):
        """Timeout should return returncode=-1."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ping"], timeout=10)

        result = run_command(["ping", "-c", "1", "8.8.8.8"])

        assert result.returncode == -1
        assert result.stderr == "timeout"

    @patch("app.core.command_executor.subprocess.run")
    def test_check_raises_on_failure(self, mock_run):
        """check=True should raise CalledProcessError on non-zero rc."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["iptables", "-L"], returncode=1, stdout="", stderr="error"
        )

        with pytest.raises(subprocess.CalledProcessError):
            run_command(["iptables", "-L"], check=True)

    @patch("app.core.command_executor.subprocess.run")
    def test_check_does_not_raise_for_dry_run_skip(self, mock_run):
        """check=True should NOT raise for dry-run skipped commands (fake rc=0)."""
        # This should not raise even with check=True
        result = run_command(["iptables", "-A", "INPUT"], check=True)

        mock_run.assert_not_called()
        assert result.returncode == 0

    @patch("app.core.command_executor.subprocess.run")
    def test_input_data_passed_through(self, mock_run):
        """input_data should be forwarded to subprocess.run."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["wg", "pubkey"], returncode=0, stdout="pubkey123", stderr=""
        )

        run_command(["wg", "pubkey"], input_data="privkey123")

        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("input") == "privkey123"


class TestCommandHistory:
    """Test command history tracking."""

    def setup_method(self):
        clear_command_history()

    @patch("app.core.command_executor.subprocess.run")
    def test_write_command_recorded_in_history(self, mock_run):
        """Dry-run skipped commands should appear in history."""
        run_command(["iptables", "-A", "FORWARD"])

        history = get_command_history()
        assert len(history) == 1
        assert history[0]["dry_run_skipped"] is True
        assert history[0]["read_only"] is False
        assert history[0]["returncode"] == 0
        assert "timestamp" in history[0]

    @patch("app.core.command_executor.subprocess.run")
    def test_read_only_command_recorded_in_history(self, mock_run):
        """Executed read-only commands should also appear in history."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ping"], returncode=0, stdout="", stderr=""
        )

        run_command(["ping", "-c", "1", "127.0.0.1"])

        history = get_command_history()
        assert len(history) == 1
        assert history[0]["dry_run_skipped"] is False
        assert history[0]["read_only"] is True

    def test_clear_history(self):
        """clear_command_history should empty the history."""
        _command_history.append({"test": True})
        assert len(get_command_history()) > 0

        clear_command_history()
        assert len(get_command_history()) == 0

    def test_history_max_size(self):
        """History should be bounded to 1000 entries."""
        assert _command_history.maxlen == 1000

    @patch("app.core.command_executor.subprocess.run")
    def test_multiple_commands_tracked(self, mock_run):
        """Multiple commands should all appear in history."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        run_command(["iptables", "-A", "FORWARD"])  # write → skip
        run_command(["iptables", "-L"])              # read → exec
        run_command(["wg", "set", "wg0", "peer"])    # write → skip

        history = get_command_history()
        assert len(history) == 3
        assert history[0]["dry_run_skipped"] is True
        assert history[1]["dry_run_skipped"] is False
        assert history[2]["dry_run_skipped"] is True
