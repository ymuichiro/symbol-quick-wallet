"""Namespace event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label

from src.shared.logging import get_logger
from src.features.namespace.screen import (
    LinkAddressAliasScreen,
    LinkAddressAliasSubmitted,
    LinkMosaicAliasScreen,
    LinkMosaicAliasSubmitted,
    NamespaceInfoScreen,
    RegisterRootNamespaceScreen,
    RegisterRootNamespaceSubmitted,
    RegisterSubNamespaceScreen,
    RegisterSubNamespaceSubmitted,
    ResolveNamespaceScreen,
    ResolveNamespaceSubmitted,
)
from src.features.namespace.service import NamespaceService
from src.screens import LoadingScreen, TransactionResultScreen
from src.shared.protocols import WalletProtocol
from src.transaction import TransactionManager

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = get_logger(__name__)


class NamespaceHandlersMixin:
    """Mixin class providing namespace-related event handlers for WalletApp."""

    wallet: WalletProtocol
    is_authenticated: bool
    _namespace_service: NamespaceService | None = None

    def show_namespace_menu(self: "WalletApp") -> None:
        from textual.containers import Vertical
        from textual.screen import ModalScreen

        class NamespaceMenuScreen(ModalScreen):
            BINDINGS = [("escape", "app.pop_screen", "Close")]

            def compose(self):
                from textual.widgets import Button

                yield Label("📛 Namespace Management")
                yield Vertical(
                    Button("Register Root Namespace", id="register-root-ns-btn"),
                    Button("Register Sub-Namespace", id="register-sub-ns-btn"),
                    Button("Link Address Alias", id="link-addr-alias-btn"),
                    Button("Link Mosaic Alias", id="link-mosaic-alias-btn"),
                    Button("Resolve Namespace", id="resolve-ns-btn"),
                    Button("View My Namespaces", id="view-my-ns-btn"),
                    Button("Close", id="close-ns-menu-btn"),
                )

            def on_button_pressed(self, event):
                from textual.widgets import Button

                if not isinstance(event.button, Button):
                    return
                button_id = event.button.id
                if button_id == "register-root-ns-btn":
                    self.app.pop_screen()
                    self.app.show_register_root_namespace()
                elif button_id == "register-sub-ns-btn":
                    self.app.pop_screen()
                    self.app.show_register_sub_namespace()
                elif button_id == "link-addr-alias-btn":
                    self.app.pop_screen()
                    self.app.show_link_address_alias()
                elif button_id == "link-mosaic-alias-btn":
                    self.app.pop_screen()
                    self.app.show_link_mosaic_alias()
                elif button_id == "resolve-ns-btn":
                    self.app.pop_screen()
                    self.app.show_resolve_namespace()
                elif button_id == "view-my-ns-btn":
                    self.app.pop_screen()
                    self.app.show_my_namespaces()
                elif button_id == "close-ns-menu-btn":
                    self.app.pop_screen()

        self.push_screen(NamespaceMenuScreen())

    def _get_namespace_service(self: "WalletApp") -> NamespaceService:
        if self._namespace_service is None:
            tm = TransactionManager(self.wallet, self.wallet.node_url)
            self._namespace_service = NamespaceService(
                self.wallet, self.wallet._network_client, tm
            )
        return self._namespace_service

    def show_register_root_namespace(self: "WalletApp") -> None:
        service = self._get_namespace_service()
        loading_screen = LoadingScreen("Fetching rental fees...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                fees = service.fetch_rental_fees()
                self.call_from_thread(self._on_rental_fees_loaded, fees, None)
            except Exception as e:
                self.call_from_thread(self._on_rental_fees_loaded, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_rental_fees_loaded(
        self: "WalletApp", fees: dict | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to fetch rental fees: {error}", severity="error")
            return

        self.push_screen(RegisterRootNamespaceScreen(fees or {}))

    def on_register_root_namespace_submitted(
        self: "WalletApp", event: RegisterRootNamespaceSubmitted
    ) -> None:
        loading_screen = LoadingScreen("Registering namespace...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_namespace_service()
                result = service.create_root_namespace(event.name, event.duration_days)
                self.call_from_thread(self._on_namespace_registered, result, None)
            except Exception as e:
                self.call_from_thread(self._on_namespace_registered, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_namespace_registered(
        self: "WalletApp", result: dict | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to register namespace: {error}", severity="error")
            return

        if result:
            self.push_screen(
                TransactionResultScreen(result["hash"], self.wallet.network_name)
            )
            self.notify("Namespace registered!", severity="information")

    def show_register_sub_namespace(self: "WalletApp") -> None:
        service = self._get_namespace_service()
        loading_screen = LoadingScreen("Fetching owned namespaces...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                namespaces = service.fetch_owned_namespaces()
                parent_names = [ns.full_name for ns in namespaces if ns.is_root]
                self.call_from_thread(
                    self._on_owned_namespaces_loaded, parent_names, None
                )
            except Exception as e:
                self.call_from_thread(self._on_owned_namespaces_loaded, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_owned_namespaces_loaded(
        self: "WalletApp", parent_names: list | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to fetch namespaces: {error}", severity="error")
            return

        self.push_screen(RegisterSubNamespaceScreen(parent_names or []))

    def on_register_sub_namespace_submitted(
        self: "WalletApp", event: RegisterSubNamespaceSubmitted
    ) -> None:
        loading_screen = LoadingScreen("Registering sub-namespace...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_namespace_service()
                result = service.create_sub_namespace(event.name, event.parent_name)
                self.call_from_thread(self._on_namespace_registered, result, None)
            except Exception as e:
                self.call_from_thread(self._on_namespace_registered, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def show_link_address_alias(self: "WalletApp") -> None:
        self.push_screen(LinkAddressAliasScreen(address=str(self.wallet.address)))

    def on_link_address_alias_submitted(
        self: "WalletApp", event: LinkAddressAliasSubmitted
    ) -> None:
        loading_screen = LoadingScreen("Linking address alias...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_namespace_service()
                result = service.link_address_alias(event.namespace_name, event.address)
                self.call_from_thread(self._on_alias_linked, result, None)
            except Exception as e:
                self.call_from_thread(self._on_alias_linked, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def show_link_mosaic_alias(self: "WalletApp") -> None:
        self.push_screen(LinkMosaicAliasScreen())

    def on_link_mosaic_alias_submitted(
        self: "WalletApp", event: LinkMosaicAliasSubmitted
    ) -> None:
        loading_screen = LoadingScreen("Linking mosaic alias...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_namespace_service()
                result = service.link_mosaic_alias(
                    event.namespace_name, event.mosaic_id
                )
                self.call_from_thread(self._on_alias_linked, result, None)
            except Exception as e:
                self.call_from_thread(self._on_alias_linked, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_alias_linked(
        self: "WalletApp", result: dict | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to link alias: {error}", severity="error")
            return

        if result:
            self.push_screen(
                TransactionResultScreen(result["hash"], self.wallet.network_name)
            )
            self.notify("Alias linked!", severity="information")

    def show_resolve_namespace(self: "WalletApp") -> None:
        self.push_screen(ResolveNamespaceScreen())

    def on_resolve_namespace_submitted(
        self: "WalletApp", event: ResolveNamespaceSubmitted
    ) -> None:
        loading_screen = LoadingScreen("Resolving namespace...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_namespace_service()
                namespace_id = service.get_namespace_id(event.namespace_name)
                info = service.fetch_namespace_info(namespace_id)

                if info is None:
                    self.call_from_thread(
                        self._on_namespace_resolved, None, None, "Namespace not found"
                    )
                    return

                chain_info = self.wallet._network_client.get(
                    "/chain/info", context="Get chain info"
                )
                current_height = int(chain_info.get("height", 0))
                expiration = service.calculate_expiration(
                    info.end_height, current_height
                )

                self.call_from_thread(
                    self._on_namespace_resolved,
                    info.to_dict(),
                    expiration,
                    None,
                )
            except Exception as e:
                self.call_from_thread(self._on_namespace_resolved, None, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_namespace_resolved(
        self: "WalletApp",
        namespace_info: dict | None,
        expiration: dict | None,
        error: str | None,
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to resolve namespace: {error}", severity="error")
            return

        if namespace_info:
            self.push_screen(NamespaceInfoScreen(namespace_info, expiration))

    def show_my_namespaces(self: "WalletApp") -> None:
        loading_screen = LoadingScreen("Fetching your namespaces...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                service = self._get_namespace_service()
                namespaces = service.fetch_owned_namespaces()
                chain_info = self.wallet._network_client.get(
                    "/chain/info", context="Get chain info"
                )
                current_height = int(chain_info.get("height", 0))

                namespace_list = []
                for ns in namespaces:
                    expiration = service.calculate_expiration(
                        ns.end_height, current_height
                    )
                    namespace_list.append(
                        {
                            "info": ns.to_dict(),
                            "expiration": expiration,
                        }
                    )

                self.call_from_thread(
                    self._on_my_namespaces_loaded, namespace_list, None
                )
            except Exception as e:
                self.call_from_thread(self._on_my_namespaces_loaded, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_my_namespaces_loaded(
        self: "WalletApp", namespaces: list | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to fetch namespaces: {error}", severity="error")
            return

        if not namespaces:
            self.notify("No namespaces owned by this account", severity="information")
            return

        if len(namespaces) == 1:
            ns = namespaces[0]
            self.push_screen(NamespaceInfoScreen(ns["info"], ns.get("expiration")))
        else:
            self._show_namespace_list_screen(namespaces)

    def _show_namespace_list_screen(self: "WalletApp", namespaces: list) -> None:
        class NamespaceListScreen(ModalScreen):
            BINDINGS = [("escape", "app.pop_screen", "Close")]

            def __init__(self, ns_list: list):
                super().__init__()
                self.ns_list = ns_list

            def compose(self):
                yield Label("📛 Your Namespaces", id="ns-list-title")
                yield DataTable(id="ns-list-table")
                yield Horizontal(
                    Button("View", id="view-ns-button", variant="primary"),
                    Button("Close", id="close-ns-list-button"),
                )

            def on_mount(self) -> None:
                table = self.query_one(DataTable)
                table.add_column("Name", key="name")
                table.add_column("Type", key="type")
                table.add_column("Expires", key="expires")

                for ns in self.ns_list:
                    info = ns["info"]
                    exp = ns.get("expiration", {})
                    remaining = exp.get("remaining_days", 0)
                    if exp.get("is_expired"):
                        remaining_text = "EXPIRED"
                    else:
                        remaining_text = f"{remaining:.0f}d"

                    table.add_row(
                        info.get("full_name", "N/A"),
                        "Root" if info.get("is_root") else "Sub",
                        remaining_text,
                        key=info.get("full_name"),
                    )

            def on_button_pressed(self, event: Button.Pressed) -> None:
                if event.button.id == "view-ns-button":
                    table = self.query_one(DataTable)
                    if table.cursor_row is not None and 0 <= table.cursor_row < len(
                        self.ns_list
                    ):
                        selected = self.ns_list[table.cursor_row]
                        self.app.push_screen(
                            NamespaceInfoScreen(
                                selected["info"], selected.get("expiration")
                            )
                        )
                elif event.button.id == "close-ns-list-button":
                    self.app.pop_screen()

        self.push_screen(NamespaceListScreen(namespaces))
