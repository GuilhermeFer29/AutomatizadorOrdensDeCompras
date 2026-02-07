"""
Base connector interface — abstract class for all external integrations.

Every connector (SAP, Bling, Tiny, etc.) must subclass ``BaseConnector``
and implement the required methods.

Usage::

    from app.integrations.base import BaseConnector

    class BlingConnector(BaseConnector):
        connector_type = "bling_v3"

        async def test_connection(self) -> bool: ...
        async def sync_products(self, direction) -> SyncResult: ...
        async def sync_orders(self, direction) -> SyncResult: ...
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a single sync operation."""
    records_processed: int = 0
    records_failed: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "success"  # success | partial | error

    @property
    def is_ok(self) -> bool:
        return self.status == "success"


class BaseConnector(ABC):
    """Abstract base for external system connectors.

    Subclasses must define:
    * ``connector_type`` — unique identifier string
    * ``test_connection()`` — verify credentials work
    * ``sync_products()`` — bi-directional product sync
    * ``sync_orders()`` — bi-directional order sync

    Optional overrides:
    * ``sync_suppliers()`` — supplier data sync
    * ``on_webhook()`` — handle incoming webhooks
    """

    connector_type: str = "base"

    def __init__(
        self,
        integration_id: int,
        config: dict[str, Any] | None = None,
        credentials: dict[str, str] | None = None,
    ) -> None:
        self.integration_id = integration_id
        self.config = config or {}
        self.credentials = credentials or {}
        self.logger = logging.getLogger(f"{__name__}.{self.connector_type}")

    # ── Required methods ──

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify the integration credentials are valid.

        Returns:
            True if connection succeeds, False otherwise.
        """
        ...

    @abstractmethod
    async def sync_products(self, direction: str = "inbound") -> SyncResult:
        """Synchronize products.

        Args:
            direction: ``'inbound'`` (external→local) or ``'outbound'`` (local→external).
        """
        ...

    @abstractmethod
    async def sync_orders(self, direction: str = "inbound") -> SyncResult:
        """Synchronize purchase/sales orders."""
        ...

    # ── Optional methods (no-op defaults) ──

    async def sync_suppliers(self, direction: str = "inbound") -> SyncResult:
        """Synchronize supplier data. Override in subclass if supported."""
        return SyncResult(status="success", records_processed=0)

    async def on_webhook(self, payload: dict[str, Any]) -> None:
        """Handle a webhook callback from the external system."""
        self.logger.debug("Webhook received but not implemented for %s", self.connector_type)

    # ── Lifecycle helpers ──

    async def refresh_token(self) -> bool:
        """Refresh OAuth token if applicable. Returns True on success."""
        return True  # default: no-op (API-key connectors don't need this)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} integration_id={self.integration_id}>"
