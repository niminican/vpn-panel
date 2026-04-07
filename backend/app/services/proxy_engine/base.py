"""Abstract base class for proxy engines (Xray-core, sing-box)."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class ProxyEngine(ABC):
    """Interface that all proxy engines must implement."""

    @abstractmethod
    def generate_config(self, inbounds: list[dict], proxy_users: list[dict], outbounds: list[dict] | None = None) -> dict:
        """Generate the engine's config from inbounds and their users.

        Args:
            inbounds: List of inbound dicts with protocol, port, transport, etc.
            proxy_users: List of proxy user dicts grouped by inbound_tag.

        Returns:
            Complete config dict ready to be written as JSON.
        """

    @abstractmethod
    def start(self, config_path: str) -> bool:
        """Start the engine with the given config file. Returns True on success."""

    @abstractmethod
    def stop(self) -> bool:
        """Stop the running engine. Returns True on success."""

    @abstractmethod
    def restart(self, config_path: str) -> bool:
        """Restart (or reload) the engine with updated config."""

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the engine process is currently running."""

    @abstractmethod
    def get_traffic_stats(self) -> dict[str, dict[str, int]]:
        """Get per-user traffic stats.

        Returns:
            Dict mapping email → {"up": bytes, "down": bytes}
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name (e.g. 'xray', 'singbox')."""

    @property
    @abstractmethod
    def binary_path(self) -> str:
        """Path to the engine binary."""
