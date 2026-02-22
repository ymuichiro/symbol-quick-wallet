"""Mosaic business logic service for Symbol Quick Wallet."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class WalletProtocol(Protocol):
    """Protocol defining wallet interface needed for mosaic operations."""

    address: str | None
    network_name: str
    node_url: str

    def get_mosaic_info(self, mosaic_id: int) -> dict[str, Any] | None: ...
    def get_mosaic_full_info(self, mosaic_id: int) -> dict[str, Any]: ...
    def get_mosaic_name(self, mosaic_id: int) -> str: ...
    def get_mosaic_namespace_name(self, mosaic_id: int) -> str | None: ...
    def get_mosaic_metadata(self, mosaic_id: int) -> list[dict[str, Any]]: ...
    def create_mosaic_transaction(
        self,
        supply: int,
        divisibility: int = 0,
        transferable: bool = True,
        supply_mutable: bool = False,
        revokable: bool = False,
    ) -> Any: ...


class TransactionManagerProtocol(Protocol):
    """Protocol defining transaction manager interface."""

    def create_sign_and_announce_mosaic(
        self,
        supply: int,
        divisibility: int = 0,
        transferable: bool = True,
        supply_mutable: bool = False,
        revokable: bool = False,
    ) -> dict[str, Any]: ...


class MosaicService:
    """Service for handling mosaic-related business logic."""

    def __init__(
        self,
        wallet: WalletProtocol,
        transaction_manager: TransactionManagerProtocol | None = None,
    ):
        self.wallet = wallet
        self.transaction_manager = transaction_manager

    def get_mosaic_info(self, mosaic_id: int) -> dict[str, Any] | None:
        """Get basic mosaic information."""
        return self.wallet.get_mosaic_info(mosaic_id)

    def get_mosaic_full_info(self, mosaic_id: int) -> dict[str, Any]:
        """Get comprehensive mosaic information including metadata."""
        return self.wallet.get_mosaic_full_info(mosaic_id)

    def get_mosaic_name(self, mosaic_id: int) -> str:
        """Get the display name for a mosaic."""
        return self.wallet.get_mosaic_name(mosaic_id)

    def create_mosaic(
        self,
        supply: int,
        divisibility: int = 0,
        transferable: bool = True,
        supply_mutable: bool = False,
        revokable: bool = False,
    ) -> dict[str, Any]:
        """Create a new mosaic."""
        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required to create mosaics")
        return self.transaction_manager.create_sign_and_announce_mosaic(
            supply=supply,
            divisibility=divisibility,
            transferable=transferable,
            supply_mutable=supply_mutable,
            revokable=revokable,
        )

    def is_mosaic_owner(self, mosaic_info: dict[str, Any], address: str) -> bool:
        """Check if the given address is the owner of the mosaic."""
        owner_address = mosaic_info.get("owner_address", "")
        return owner_address.upper() == address.upper().replace("-", "")

    def format_mosaic_amount(self, amount: int, divisibility: int) -> str:
        """Format a mosaic amount for display."""
        if divisibility == 0:
            return f"{amount:,}"
        human_amount = amount / (10**divisibility)
        return f"{human_amount:,.{divisibility}f}"
