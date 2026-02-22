"""Transfer business logic service for Symbol Quick Wallet."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class WalletProtocol(Protocol):
    """Protocol defining wallet interface needed for transfers."""

    address: str | None
    network_name: str
    node_url: str

    def get_balance(self, address: str | None = None) -> list[dict[str, int]]: ...
    def get_mosaic_name(self, mosaic_id: int) -> str: ...


class TransactionManagerProtocol(Protocol):
    """Protocol defining transaction manager interface."""

    def estimate_fee(
        self, recipient_address: str, mosaics: list[dict], message: str
    ) -> float: ...

    def create_sign_and_announce(
        self, recipient_address: str, mosaics: list[dict], message: str
    ) -> dict[str, Any]: ...


class TransferService:
    """Service for handling transfer-related business logic."""

    def __init__(
        self, wallet: WalletProtocol, transaction_manager: TransactionManagerProtocol
    ):
        self.wallet = wallet
        self.transaction_manager = transaction_manager

    def get_available_mosaics(self) -> list[dict[str, Any]]:
        """Get list of available mosaics for transfer."""
        mosaics = self.wallet.get_balance()
        result = []
        for m in mosaics:
            mosaic_id = m.get("id")
            amount = m.get("amount", 0)
            mosaic_name = self.wallet.get_mosaic_name(mosaic_id)
            result.append(
                {
                    "id": mosaic_id,
                    "name": mosaic_name,
                    "amount": amount,
                    "human_amount": amount / 1_000_000,
                    "divisibility": 6,
                }
            )
        return result

    def estimate_transfer_fee(
        self, recipient: str, mosaics: list[dict], message: str = ""
    ) -> float:
        """Estimate the fee for a transfer transaction."""
        return self.transaction_manager.estimate_fee(recipient, mosaics, message)

    def send_transfer(
        self, recipient: str, mosaics: list[dict], message: str = ""
    ) -> dict[str, Any]:
        """Send a transfer transaction."""
        return self.transaction_manager.create_sign_and_announce(
            recipient, mosaics, message
        )

    def validate_recipient_address(self, address: str) -> bool:
        """Validate a recipient address format."""
        if not address or not address.strip():
            return False
        normalized = address.strip().replace("-", "").upper()
        if len(normalized) < 39 or len(normalized) > 40:
            return False
        if normalized[0] not in ("T", "N"):
            return False
        return True
