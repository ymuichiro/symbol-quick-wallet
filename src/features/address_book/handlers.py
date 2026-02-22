"""Address book event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from textual.widgets import DataTable, Input, Static

from src.features.address_book.screen import (
    AddAddressScreen,
    AddressBookScreen,
    AddressBookSelectorScreen,
    ContactGroupsScreen,
    CreateGroupScreen,
    DeleteGroupConfirmScreen,
    EditAddressScreen,
    EditGroupScreen,
)
from src.shared.protocols import WalletProtocol

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = logging.getLogger(__name__)


class AddressBookHandlersMixin:
    """Mixin class providing address book-related event handlers for WalletApp."""

    wallet: WalletProtocol
    is_authenticated: bool

    def show_address_book_selector(self: "WalletApp") -> None:
        addresses = self.wallet.get_addresses()
        groups = self.wallet.get_contact_groups()
        if addresses:
            self.push_screen(AddressBookSelectorScreen(addresses, groups))
        else:
            cast(Static, self.query_one("#transfer-result")).update(
                "[yellow]No addresses in address book[/yellow]"
            )

    def show_add_address_dialog(self: "WalletApp") -> None:
        groups = self.wallet.get_contact_groups()
        self.push_screen(AddAddressScreen(groups))

    def remove_selected_address(self: "WalletApp") -> None:
        table = cast(DataTable, self.query_one("#address-book-table"))
        cursor_row = table.cursor_row
        if cursor_row is None:
            return
        try:
            selected = (
                table.get_row_at(cursor_row)
                if hasattr(table, "get_row_at")
                else table.get_row(cursor_row)
            )
        except Exception:
            selected = None
        if selected:
            self.wallet.remove_address(selected[1])
            self.update_address_book()

    def show_address_book(self: "WalletApp") -> None:
        addresses = self.wallet.get_addresses()
        groups = self.wallet.get_contact_groups()
        self.push_screen(AddressBookScreen(addresses, groups))

    def show_edit_address_dialog(
        self: "WalletApp",
        address: str,
        name: str,
        note: str,
        group_id: str | None = None,
    ) -> None:
        groups = self.wallet.get_contact_groups()
        self.push_screen(EditAddressScreen(address, name, note, groups, group_id))

    def on_add_address_dialog_submitted(self: "WalletApp", event: Any) -> None:
        group_id = getattr(event, "group_id", None)
        self.wallet.add_address(event.address, event.name, event.note, group_id)
        self.update_address_book()
        self.notify("Address added successfully", severity="information")

    def on_address_book_selected(self: "WalletApp", event: Any) -> None:
        cast(Input, self.query_one("#recipient-input")).value = event.address

    def on_send_to_address(self: "WalletApp", event: Any) -> None:
        cast(Input, self.query_one("#recipient-input")).value = event.address
        self.action_switch_tab("transfer")

    def on_edit_address(self: "WalletApp", event: Any) -> None:
        self.show_edit_address_dialog(
            event.address, event.name, event.note, getattr(event, "group_id", None)
        )

    def on_delete_address(self: "WalletApp", event: Any) -> None:
        self.wallet.remove_address(event.address)
        self.update_address_book()
        self.notify("Address deleted successfully", severity="information")

    def on_edit_address_dialog_submitted(self: "WalletApp", event: Any) -> None:
        self.wallet.update_address(
            event.address, event.name, event.note, group_id=event.group_id
        )
        self.update_address_book()
        self.notify("Address updated successfully", severity="information")

    def on_address_book_screen_manage_groups(self: "WalletApp", event: Any) -> None:
        groups = self.wallet.get_contact_groups()
        self.push_screen(ContactGroupsScreen(groups))

    def on_address_book_selector_screen_manage_groups(
        self: "WalletApp", event: Any
    ) -> None:
        groups = self.wallet.get_contact_groups()
        self.push_screen(ContactGroupsScreen(groups))

    def on_contact_groups_screen_create_group_requested(
        self: "WalletApp", event: Any
    ) -> None:
        self.push_screen(CreateGroupScreen())

    def on_contact_groups_screen_edit_group_requested(
        self: "WalletApp", event: Any
    ) -> None:
        self.push_screen(EditGroupScreen(event.group_id, event.name, event.color))

    def on_contact_groups_screen_delete_group_requested(
        self: "WalletApp", event: Any
    ) -> None:
        group = self.wallet.get_contact_group(event.group_id)
        group_name = group.get("name", "") if group else ""
        self.push_screen(DeleteGroupConfirmScreen(event.group_id, group_name))

    def on_create_group_screen_create_group_submitted(
        self: "WalletApp", event: Any
    ) -> None:
        self.wallet.create_contact_group(event.name)
        self.notify(
            f"Group '{event.name}' created successfully", severity="information"
        )

    def on_edit_group_screen_edit_group_submitted(
        self: "WalletApp", event: Any
    ) -> None:
        self.wallet.update_contact_group(event.group_id, event.name, event.color)
        self.notify(
            f"Group '{event.name}' updated successfully", severity="information"
        )

    def on_delete_group_confirm_screen_delete_group_confirmed(
        self: "WalletApp", event: Any
    ) -> None:
        self.wallet.delete_contact_group(event.group_id)
        self.notify("Group deleted successfully", severity="information")

    def update_address_book(self: "WalletApp") -> None:
        logger.info("")
        logger.info(
            "[update_address_book] ========== UPDATE ADDRESS BOOK STARTED =========="
        )
        logger.info(f"[update_address_book] is_authenticated: {self.is_authenticated}")

        logger.info("[update_address_book] Step 1: Querying address-book-table widget")
        try:
            table = cast(DataTable, self.query_one("#address-book-table"))
            logger.info("[update_address_book] Step 1: address-book-table widget found")
        except Exception as e:
            logger.error(
                f"[update_address_book] Step 1: ERROR finding address-book-table: {e}",
                exc_info=True,
            )
            return

        logger.info("[update_address_book] Step 2: Clearing table columns")
        try:
            table.clear(columns=True)
            logger.info("[update_address_book] Step 2: Table columns cleared")
        except Exception as e:
            logger.error(
                f"[update_address_book] Step 2: ERROR clearing columns: {e}",
                exc_info=True,
            )
            return

        logger.info("[update_address_book] Step 3: Adding table columns")
        try:
            table.add_column("Name", key="name")
            table.add_column("Address", key="address")
            table.add_column("Note", key="note")
            logger.info("[update_address_book] Step 3: Table columns added")
        except Exception as e:
            logger.error(
                f"[update_address_book] Step 3: ERROR adding columns: {e}",
                exc_info=True,
            )
            return

        logger.info("[update_address_book] Step 4: Getting addresses from wallet")
        try:
            addresses = self.wallet.get_addresses()
            logger.info(f"[update_address_book] Step 4: Got {len(addresses)} addresses")
        except Exception as e:
            logger.error(
                f"[update_address_book] Step 4: ERROR getting addresses: {e}",
                exc_info=True,
            )
            table.add_row(f"Error: {str(e)}", "", "")
            return

        logger.info("[update_address_book] Step 5: Adding address rows to table")
        for addr, info in addresses.items():
            logger.info(f"[update_address_book] Adding row: {info['name']} - {addr}")
            table.add_row(info["name"], addr, info["note"])

        logger.info(
            "[update_address_book] ========== UPDATE ADDRESS BOOK COMPLETED =========="
        )
        logger.info("")
