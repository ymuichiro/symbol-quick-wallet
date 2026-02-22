"""Account management event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from src.features.account.screens import (
    AccountManagerScreen,
    AddAccountScreen,
    DeleteAccountConfirmScreen,
    EditAccountScreen,
    ExportKeyScreen,
    ImportAccountKeyScreen,
    ImportEncryptedKeyScreen,
)
from src.shared.protocols import WalletProtocol

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = logging.getLogger(__name__)


class AccountHandlersMixin:
    """Mixin class providing account-related event handlers for WalletApp."""

    wallet: WalletProtocol

    def show_account_manager(self: "WalletApp") -> None:
        accounts = self.wallet.get_accounts()
        current_index = self.wallet.get_current_account_index()
        self.push_screen(AccountManagerScreen(accounts, current_index))

    def on_account_manager_screen_account_selected(
        self: "WalletApp", event: Any
    ) -> None:
        if self.wallet.switch_account(event.index):
            self.wallet.load_current_account()
            self.update_dashboard()
            self.update_address_book()
            current_account = self.wallet.get_current_account()
            label = current_account.label if current_account else "Unknown"
            self.notify(f"Switched to: {label}", severity="information")

    def on_account_manager_screen_add_account_requested(
        self: "WalletApp", event: Any
    ) -> None:
        self.push_screen(AddAccountScreen())

    def on_account_manager_screen_edit_account_requested(
        self: "WalletApp", event: Any
    ) -> None:
        self.push_screen(
            EditAccountScreen(event.index, event.label, event.address_book_shared)
        )

    def on_account_manager_screen_delete_account_requested(
        self: "WalletApp", event: Any
    ) -> None:
        accounts = self.wallet.get_accounts()
        if event.index < len(accounts):
            acc = accounts[event.index]
            self.push_screen(
                DeleteAccountConfirmScreen(event.index, acc.label, acc.address)
            )

    def on_add_account_screen_create_account_requested(
        self: "WalletApp", event: Any
    ) -> None:
        try:
            self.wallet.create_account(event.label, event.address_book_shared)
            self.notify("New account created successfully!", severity="information")
        except Exception as e:
            self.notify(f"Error creating account: {str(e)}", severity="error")

    def on_add_account_screen_import_account_requested(
        self: "WalletApp", event: Any
    ) -> None:
        self.push_screen(ImportAccountKeyScreen(event.label, event.address_book_shared))

    def on_import_account_key_screen_import_key_submitted(
        self: "WalletApp", event: Any
    ) -> None:
        try:
            self.wallet.import_account(
                event.private_key, event.label, event.address_book_shared
            )
            self.notify("Account imported successfully!", severity="information")
        except Exception as e:
            self.notify(f"Error importing account: {str(e)}", severity="error")

    def on_edit_account_screen_edit_account_submitted(
        self: "WalletApp", event: Any
    ) -> None:
        self.wallet.update_account_label(event.index, event.label)
        self.wallet.update_account_address_book_shared(
            event.index, event.address_book_shared
        )
        if event.index == self.wallet.get_current_account_index():
            self.wallet.load_current_account()
            self.update_address_book()
        self.notify("Account updated successfully!", severity="information")

    def on_delete_account_confirm_screen_delete_confirmed(
        self: "WalletApp", event: Any
    ) -> None:
        if self.wallet.delete_account(event.index):
            self.wallet.load_current_account()
            self.update_dashboard()
            self.update_address_book()
            self.notify("Account deleted successfully!", severity="information")
        else:
            self.notify("Cannot delete the last account", severity="warning")

    def show_export_key_dialog(self: "WalletApp") -> None:
        self.push_screen(ExportKeyScreen())

    def show_import_encrypted_key_dialog(self: "WalletApp") -> None:
        self.push_screen(ImportEncryptedKeyScreen())

    def on_export_key_dialog_submitted(self: "WalletApp", event: Any) -> None:
        try:
            export_data = self.wallet.export_private_key(event.password)
            export_file = self.wallet.wallet_dir / "encrypted_private_key.json"
            with open(export_file, "w") as f:
                json.dump(export_data, f, indent=2)
            self.notify(
                f"Encrypted key exported to {export_file}", severity="information"
            )
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def on_import_encrypted_key_dialog_submitted(self: "WalletApp", event: Any) -> None:
        try:
            with open(event.file_path, "r") as f:
                encrypted_data = json.load(f)
            self.wallet.import_encrypted_private_key(encrypted_data, event.password)
            self.update_dashboard()
            self.notify("Encrypted key imported successfully!", severity="information")
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")
