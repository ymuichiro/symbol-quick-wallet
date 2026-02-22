"""Account management business logic service for Symbol Quick Wallet."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class AccountInfo:
    """Data class representing account information."""

    index: int
    address: str
    label: str
    address_book_shared: bool


class WalletProtocolForAccount(Protocol):
    """Protocol defining wallet interface needed for account management."""

    def get_accounts(self) -> list[Any]: ...
    def get_current_account_index(self) -> int: ...
    def get_current_account(self) -> Any | None: ...
    def switch_account(self, index: int) -> bool: ...
    def load_current_account(self) -> None: ...
    def create_account(self, label: str, address_book_shared: bool = False) -> None: ...
    def import_account(
        self, private_key: str, label: str, address_book_shared: bool = False
    ) -> None: ...
    def update_account_label(self, index: int, label: str) -> None: ...
    def update_account_address_book_shared(self, index: int, shared: bool) -> None: ...
    def delete_account(self, index: int) -> bool: ...
    def export_private_key(self, password: str) -> dict[str, Any]: ...
    def import_encrypted_private_key(
        self, encrypted_data: dict[str, Any], password: str
    ) -> None: ...


class AccountService:
    """Service for handling account-related business logic."""

    def __init__(self, wallet: WalletProtocolForAccount):
        self.wallet = wallet

    def get_all_accounts(self) -> list[AccountInfo]:
        """Get all accounts with their information."""
        accounts = self.wallet.get_accounts()
        result = []
        for idx, acc in enumerate(accounts):
            result.append(
                AccountInfo(
                    index=idx,
                    address=acc.address,
                    label=acc.label,
                    address_book_shared=acc.address_book_shared,
                )
            )
        return result

    def get_current_account_info(self) -> AccountInfo | None:
        """Get current account information."""
        current = self.wallet.get_current_account()
        if not current:
            return None
        current_idx = self.wallet.get_current_account_index()
        return AccountInfo(
            index=current_idx,
            address=current.address,
            label=current.label,
            address_book_shared=current.address_book_shared,
        )

    def switch_to_account(self, index: int) -> bool:
        """Switch to the specified account."""
        return self.wallet.switch_account(index)

    def create_new_account(self, label: str, address_book_shared: bool = False) -> None:
        """Create a new account."""
        self.wallet.create_account(label, address_book_shared)

    def import_existing_account(
        self, private_key: str, label: str, address_book_shared: bool = False
    ) -> None:
        """Import an account from private key."""
        self.wallet.import_account(private_key, label, address_book_shared)

    def update_account(self, index: int, label: str, address_book_shared: bool) -> None:
        """Update account label and address book sharing setting."""
        self.wallet.update_account_label(index, label)
        self.wallet.update_account_address_book_shared(index, address_book_shared)

    def delete_account_by_index(self, index: int) -> bool:
        """Delete an account by index."""
        return self.wallet.delete_account(index)

    def can_delete_account(self, index: int) -> bool:
        """Check if an account can be deleted (must have more than one account)."""
        accounts = self.wallet.get_accounts()
        return len(accounts) > 1

    def export_key(self, password: str) -> dict[str, Any]:
        """Export encrypted private key."""
        return self.wallet.export_private_key(password)

    def import_key(self, encrypted_data: dict[str, Any], password: str) -> None:
        """Import encrypted private key."""
        self.wallet.import_encrypted_private_key(encrypted_data, password)
