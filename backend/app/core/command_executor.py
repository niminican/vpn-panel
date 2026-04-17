"""
Command Executor with Dry-Run Support

Central abstraction for all system subprocess calls (iptables, wg, tc, ip, etc.).
In dry-run mode, write commands are logged but not executed; read-only commands
always execute regardless of mode.
"""
from __future__ import annotations

import logging
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_command_history: deque[dict] = deque(maxlen=1000)

# ── Read-only classification ────────────────────────────────────────────────

ALWAYS_READ_ONLY = frozenset({
    "ping", "dig", "curl", "journalctl", "tcpdump", "cat", "grep",
    "speedtest-cli", "hostname",
})

ALWAYS_WRITE = frozenset({"modprobe", "bash", "wg-quick"})

# tool -> set of read-only sub-commands / flags
_READ_ONLY_ARGS: dict[str, frozenset[str]] = {
    "iptables":  frozenset({"-C", "-L", "-S", "--list", "--check"}),
    "ip6tables": frozenset({"-C", "-L", "-S", "--list", "--check"}),
    "wg":        frozenset({"show", "genkey", "genpsk", "pubkey"}),
    "systemctl": frozenset({"status", "is-active", "is-enabled", "list-units"}),
}

# For 'ip' command: sub-object + action combos that are read-only
_IP_READ_ONLY_ACTIONS = frozenset({"show", "get", "list", "monitor"})

# For 'tc' command: read-only actions
_TC_READ_ONLY_ACTIONS = frozenset({"show", "list", "monitor"})


def is_read_only(cmd: list[str]) -> bool:
    """Classify a command as read-only (safe to always execute) or write."""
    if not cmd:
        return True

    tool = Path(cmd[0]).name  # strip path: /usr/sbin/iptables -> iptables

    if tool in ALWAYS_READ_ONLY:
        return True

    if tool in ALWAYS_WRITE:
        return False

    # iptables / ip6tables: check for -C, -L, -S flags
    if tool in _READ_ONLY_ARGS:
        ro_flags = _READ_ONLY_ARGS[tool]
        return any(arg in ro_flags for arg in cmd[1:])

    # ip link/route/rule: check sub-object + action
    if tool == "ip":
        # ip [link|route|rule|addr] [show|add|del|...]
        args = cmd[1:]
        for arg in args:
            if arg in _IP_READ_ONLY_ACTIONS:
                return True
            if arg in ("add", "del", "delete", "replace", "set", "change", "flush"):
                return False
        return True  # bare 'ip link' with no action = read-only

    # tc: check for write actions
    if tool == "tc":
        args = cmd[1:]
        for arg in args:
            if arg in _TC_READ_ONLY_ACTIONS:
                return True
            if arg in ("add", "del", "delete", "change", "replace"):
                return False
        return True

    # Unknown tool: treat as write (safe default)
    return False


# ── Command execution ────────────────────────────────────────────────────────

def run_command(
    cmd: list[str],
    *,
    check: bool = False,
    input_data: str | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Execute a system command, respecting dry-run mode.

    In dry-run mode, write commands are logged and a fake success is returned.
    Read-only commands always execute.
    """
    from app.config import settings  # deferred to avoid circular import

    read_only = is_read_only(cmd)
    cmd_str = " ".join(cmd)

    if settings.dry_run and not read_only:
        logger.info(f"[DRY-RUN] Would execute: {cmd_str}")
        _record(cmd, dry_run_skipped=True, read_only=False, returncode=0)
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    # Actually execute
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_data,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out ({timeout}s): {cmd_str}")
        _record(cmd, dry_run_skipped=False, read_only=read_only, returncode=-1)
        return subprocess.CompletedProcess(
            args=cmd, returncode=-1, stdout="", stderr="timeout"
        )

    _record(cmd, dry_run_skipped=False, read_only=read_only, returncode=result.returncode)

    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )

    return result


# ── Command history (audit / debug) ─────────────────────────────────────────

def _record(
    cmd: list[str],
    *,
    dry_run_skipped: bool,
    read_only: bool,
    returncode: int,
) -> None:
    _command_history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": cmd,
        "dry_run_skipped": dry_run_skipped,
        "read_only": read_only,
        "returncode": returncode,
    })


def get_command_history() -> list[dict]:
    """Return recent command history (newest last)."""
    return list(_command_history)


def clear_command_history() -> None:
    _command_history.clear()
