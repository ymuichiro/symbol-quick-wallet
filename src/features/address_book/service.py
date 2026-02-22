"""Address book business logic service for Symbol Quick Wallet."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class WalletProtocol(Protocol):
    """Protocol defining wallet interface needed for address book."""

    address_book: dict[str, dict[str, Any]]
    contact_groups: dict[str, dict[str, str]]

    def add_address(
        self, address: str, name: str, note: str = "", group_id: str | None = None
    ) -> None: ...
    def update_address(
        self, address: str, name: str, note: str, group_id: str | None = None
    ) -> None: ...
    def remove_address(self, address: str) -> None: ...
    def get_addresses(self) -> dict[str, dict[str, Any]]: ...
    def get_address_info(self, address: str) -> dict[str, Any]: ...
    def create_contact_group(self, name: str, color: str = "") -> str: ...
    def update_contact_group(
        self, group_id: str, name: str, color: str = ""
    ) -> bool: ...
    def delete_contact_group(self, group_id: str) -> bool: ...
    def get_contact_groups(self) -> dict[str, dict[str, str]]: ...
    def get_contact_group(self, group_id: str) -> dict[str, str] | None: ...
    def get_addresses_by_group(
        self, group_id: str | None
    ) -> dict[str, dict[str, str]]: ...


class AddressBookService:
    """Service for handling address book-related business logic."""

    def __init__(self, wallet: WalletProtocol):
        self.wallet = wallet

    def get_all_addresses(self) -> dict[str, dict[str, Any]]:
        """Get all addresses in the address book."""
        return self.wallet.get_addresses()

    def get_address(self, address: str) -> dict[str, Any] | None:
        """Get a specific address by its value."""
        return self.wallet.get_address_info(address)

    def add_address(
        self, address: str, name: str, note: str = "", group_id: str | None = None
    ) -> None:
        """Add a new address to the address book."""
        self.wallet.add_address(address, name, note, group_id)

    def update_address(
        self, address: str, name: str, note: str, group_id: str | None = None
    ) -> None:
        """Update an existing address in the address book."""
        self.wallet.update_address(address, name, note, group_id)

    def remove_address(self, address: str) -> None:
        """Remove an address from the address book."""
        self.wallet.remove_address(address)

    def get_all_groups(self) -> dict[str, dict[str, str]]:
        """Get all contact groups."""
        return self.wallet.get_contact_groups()

    def get_group(self, group_id: str) -> dict[str, str] | None:
        """Get a specific group by ID."""
        return self.wallet.get_contact_group(group_id)

    def create_group(self, name: str, color: str = "") -> str:
        """Create a new contact group."""
        return self.wallet.create_contact_group(name, color)

    def update_group(self, group_id: str, name: str, color: str = "") -> bool:
        """Update an existing contact group."""
        return self.wallet.update_contact_group(group_id, name, color)

    def delete_group(self, group_id: str) -> bool:
        """Delete a contact group."""
        return self.wallet.delete_contact_group(group_id)

    def get_addresses_in_group(self, group_id: str | None) -> dict[str, dict[str, str]]:
        """Get all addresses in a specific group."""
        return self.wallet.get_addresses_by_group(group_id)

    def search_addresses(self, query: str) -> dict[str, dict[str, Any]]:
        """Search addresses by name or address."""
        query_lower = query.lower()
        addresses = self.get_all_addresses()
        return {
            addr: info
            for addr, info in addresses.items()
            if query_lower in info.get("name", "").lower()
            or query_lower in addr.lower()
        }
