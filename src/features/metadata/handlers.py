"""Metadata event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from src.shared.logging import get_logger
from src.features.metadata.service import (
    MetadataInfo,
    MetadataService,
    MetadataTargetType,
)
from src.features.metadata.screen import (
    AddMetadataScreen,
    AddMetadataSubmitted,
    MetadataListScreen,
    RemoveMetadataScreen,
    RemoveMetadataSubmitted,
)
from src.screens import LoadingScreen, TransactionResultScreen
from src.shared.protocols import WalletProtocol
from src.transaction import TransactionManager

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = get_logger(__name__)


class MetadataHandlersMixin:
    """Mixin class providing metadata-related event handlers for WalletApp."""

    wallet: WalletProtocol
    is_authenticated: bool
    _metadata_service: MetadataService | None = None

    def show_metadata_menu(self: "WalletApp") -> None:
        class MetadataMenuScreen(ModalScreen):
            BINDINGS = [("escape", "app.pop_screen", "Close")]

            def compose(self):
                yield Label("📝 Metadata Management")
                yield Vertical(
                    Button("View Account Metadata", id="view-account-meta-btn"),
                    Button("Add Account Metadata", id="add-account-meta-btn"),
                    Button("Add Mosaic Metadata", id="add-mosaic-meta-btn"),
                    Button("Add Namespace Metadata", id="add-namespace-meta-btn"),
                    Button("Remove Metadata", id="remove-meta-btn"),
                    Button("Close", id="close-meta-menu-btn"),
                )

            def on_button_pressed(self, event):
                if not isinstance(event.button, Button):
                    return
                button_id = event.button.id
                if button_id == "view-account-meta-btn":
                    self.app.pop_screen()
                    self.app.show_account_metadata()
                elif button_id == "add-account-meta-btn":
                    self.app.pop_screen()
                    self.app.show_add_account_metadata()
                elif button_id == "add-mosaic-meta-btn":
                    self.app.pop_screen()
                    self.app.show_add_mosaic_metadata()
                elif button_id == "add-namespace-meta-btn":
                    self.app.pop_screen()
                    self.app.show_add_namespace_metadata()
                elif button_id == "remove-meta-btn":
                    self.app.pop_screen()
                    self.app.show_remove_metadata()
                elif button_id == "close-meta-menu-btn":
                    self.app.pop_screen()

        self.push_screen(MetadataMenuScreen())

    def _get_metadata_service(self: "WalletApp") -> MetadataService:
        if self._metadata_service is None:
            tm = TransactionManager(self.wallet, self.wallet.node_url)
            self._metadata_service = MetadataService(
                self.wallet, self.wallet._network_client, tm
            )
        return self._metadata_service

    def show_account_metadata(self: "WalletApp") -> None:
        loading_screen = LoadingScreen("Fetching metadata...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_metadata_service()
                metadata_list = service.fetch_all_metadata_for_account()
                self.call_from_thread(
                    self._on_account_metadata_loaded, metadata_list, None
                )
            except Exception as e:
                self.call_from_thread(self._on_account_metadata_loaded, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_account_metadata_loaded(
        self: "WalletApp",
        metadata_list: list[MetadataInfo] | None,
        error: str | None,
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to fetch metadata: {error}", severity="error")
            return

        if not metadata_list:
            self.notify("No metadata found for this account", severity="information")
            return

        self.push_screen(MetadataListScreen(metadata_list))

    def show_add_account_metadata(self: "WalletApp") -> None:
        self.push_screen(
            AddMetadataScreen(
                target_type=MetadataTargetType.ACCOUNT,
                target_address=str(self.wallet.address),
            )
        )

    def show_add_mosaic_metadata(self: "WalletApp") -> None:
        self.push_screen(
            AddMetadataScreen(
                target_type=MetadataTargetType.MOSAIC,
                target_address=str(self.wallet.address),
            )
        )

    def show_add_namespace_metadata(self: "WalletApp") -> None:
        self.push_screen(
            AddMetadataScreen(
                target_type=MetadataTargetType.NAMESPACE,
                target_address=str(self.wallet.address),
            )
        )

    def on_add_metadata_submitted(
        self: "WalletApp", event: AddMetadataSubmitted
    ) -> None:
        loading_screen = LoadingScreen("Registering metadata...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_metadata_service()
                if event.target_type == MetadataTargetType.ACCOUNT:
                    result = service.assign_account_metadata(
                        key_string=event.key,
                        value=event.value,
                        target_address=event.target_address,
                    )
                elif event.target_type == MetadataTargetType.MOSAIC:
                    if event.target_id is None:
                        raise ValueError("Mosaic ID is required")
                    result = service.assign_mosaic_metadata(
                        key_string=event.key,
                        value=event.value,
                        mosaic_id=event.target_id,
                        owner_address=event.target_address,
                    )
                elif event.target_type == MetadataTargetType.NAMESPACE:
                    if event.target_id is None:
                        raise ValueError("Namespace ID is required")
                    result = service.assign_namespace_metadata(
                        key_string=event.key,
                        value=event.value,
                        namespace_id=event.target_id,
                        owner_address=event.target_address,
                    )
                else:
                    raise ValueError(f"Unknown target type: {event.target_type}")

                self.call_from_thread(self._on_metadata_registered, result, None)
            except Exception as e:
                self.call_from_thread(self._on_metadata_registered, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_metadata_registered(
        self: "WalletApp", result: dict | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to register metadata: {error}", severity="error")
            return

        if result:
            self.push_screen(
                TransactionResultScreen(result["hash"], self.wallet.network_name)
            )
            self.notify("Metadata registered!", severity="information")

    def show_remove_metadata(self: "WalletApp") -> None:
        loading_screen = LoadingScreen("Fetching metadata...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_metadata_service()
                metadata_list = service.fetch_all_metadata_for_account()
                self.call_from_thread(
                    self._on_remove_metadata_loaded, metadata_list, None
                )
            except Exception as e:
                self.call_from_thread(self._on_remove_metadata_loaded, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_remove_metadata_loaded(
        self: "WalletApp",
        metadata_list: list[MetadataInfo] | None,
        error: str | None,
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to fetch metadata: {error}", severity="error")
            return

        if not metadata_list:
            self.notify("No metadata found to remove", severity="information")
            return

        self.push_screen(RemoveMetadataScreen(metadata_list))

    def on_remove_metadata_submitted(
        self: "WalletApp", event: RemoveMetadataSubmitted
    ) -> None:
        loading_screen = LoadingScreen("Removing metadata...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_metadata_service()
                result = service.remove_metadata(
                    key_string=event.key,
                    target_type=event.target_type,
                    target_address=event.target_address,
                    target_id=event.target_id,
                )
                self.call_from_thread(self._on_metadata_removed, result, None)
            except Exception as e:
                self.call_from_thread(self._on_metadata_removed, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_metadata_removed(
        self: "WalletApp", result: dict | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to remove metadata: {error}", severity="error")
            return

        if result:
            self.push_screen(
                TransactionResultScreen(result["hash"], self.wallet.network_name)
            )
            self.notify("Metadata removed!", severity="information")
