"""Modal screens for the Symbol Quick Wallet application.

This module provides base classes and shared screens. Feature-specific screens
are organized in their respective feature modules:

- src.features.transfer.screen: Transfer-related screens
- src.features.address_book.screen: Address book screens
- src.features.mosaic.screen: Mosaic management screens
- src.features.account.screens: Account management screens
"""

from typing import Callable, Protocol, cast

import qrcode
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from src.shared.logging import get_logger

from src.features.transfer.screen import (
    BatchTransactionResultScreen,
    MosaicInputScreen,
    SaveTemplateScreen,
    TemplateListScreen,
    TemplateSelectorScreen,
    TransactionConfirmScreen,
    TransactionQueueScreen,
    TransactionResultScreen,
    TransactionStatusScreen,
)
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
from src.features.mosaic.screen import (
    CreateMosaicDialogSubmitted,
    CreateMosaicScreen,
    HarvestingLinkScreen,
    HarvestingUnlinkScreen,
    MosaicMetadataScreen,
)
from src.features.account.screens import (
    AccountManagerScreen,
    AddAccountScreen,
    DeleteAccountConfirmScreen,
    EditAccountScreen,
    ExportKeyScreen,
    FirstRunImportWalletScreen,
    FirstRunSetupScreen,
    ImportAccountKeyScreen,
    ImportEncryptedKeyScreen,
    ImportWalletScreen,
    NetworkSelectorScreen,
    PasswordScreen,
    QRScannerScreen,
    SetPasswordScreen,
    SetupPasswordScreen,
)

logger = get_logger(__name__)


class WalletLike(Protocol):
    def get_mosaic_name(self, mosaic_id: int) -> str: ...


class AppWithWalletOps(Protocol):
    wallet: WalletLike

    def unlock_wallet(self, password: str, screen: object) -> bool: ...

    def dump_screen_stack(self, context: str = "") -> None: ...


class BaseModalScreen(ModalScreen):
    """Base modal screen with common key bindings."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("tab", "action_focus_next", "Next"),
        ("shift+tab", "action_focus_previous", "Previous"),
    ]


class CommandSelectorScreen(BaseModalScreen):
    """Screen for selecting commands via keyboard shortcuts."""

    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "confirm", "Confirm")]

    def __init__(self, on_select: Callable[[str], None]):
        super().__init__()
        self.on_select = on_select
        self._commands: list[tuple[str, str]] = []
        self._visible_command_keys: list[str] = []

    def compose(self) -> ComposeResult:
        yield Label("🔍 Select Command")
        yield Input(placeholder="Type to filter commands...", id="command-filter-input")
        yield DataTable(id="command-table")
        yield Button("❌ Cancel", id="cancel-button")

    def on_mount(self) -> None:
        table = cast(DataTable, self.query_one("#command-table"))
        table.add_column("Command", key="command")
        table.add_column("Description", key="description")

        self._commands = [
            ("/dashboard", "📊 Dashboard"),
            ("/d", "📊 Dashboard"),
            ("/transfer", "📤 Transfer"),
            ("/t", "📤 Transfer"),
            ("/address_book", "📒 Address Book"),
            ("/a", "📒 Address Book"),
            ("/history", "📜 History"),
            ("/h", "📜 History"),
            ("/accounts", "👤 Account Manager"),
            ("/templates", "📋 Transaction Templates"),
            ("/show_config", "⚙️ Show Config"),
            ("/network_testnet", "🌐 Network: Testnet"),
            ("/network_mainnet", "🌐 Network: Mainnet"),
            ("/node_default", "🔄 Reset Default Node"),
            ("/test_connection", "🔌 Test Node Connection"),
            ("/create_wallet", "🔑 Create Wallet"),
            ("/import_wallet", "📥 Import Wallet"),
            ("/export_key", "🔐 Export Key"),
            ("/import_encrypted_key", "🔑 Import Encrypted Key"),
            ("/show_qr", "📱 Show QR"),
            ("/create_mosaic", "🎨 Create Mosaic"),
            ("/link_harvesting", "🔗 Link Harvesting"),
            ("/unlink_harvesting", "🔓 Unlink Harvesting"),
        ]
        self._refresh_command_table("")
        cast(Input, self.query_one("#command-filter-input")).focus()

    def _refresh_command_table(self, filter_text: str) -> None:
        table = cast(DataTable, self.query_one("#command-table"))
        table.clear()
        self._visible_command_keys = []

        needle = filter_text.strip().lower()
        for cmd, desc in self._commands:
            if not needle or needle in cmd.lower() or needle in desc.lower():
                table.add_row(cmd, desc, key=cmd)
                self._visible_command_keys.append(cmd)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "command-filter-input":
            self._refresh_command_table(event.value)

    def on_data_table_row_selected(self, event):
        row = event.row_key
        if row:
            self.on_select(row.value if hasattr(row, "value") else str(row))
            self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "command-filter-input":
            self.action_confirm()

    def action_confirm(self) -> None:
        table = cast(DataTable, self.query_one("#command-table"))
        cursor_row = table.cursor_row
        selected_command: str | None = None

        if cursor_row is not None and 0 <= cursor_row < len(self._visible_command_keys):
            selected_command = self._visible_command_keys[cursor_row]
        elif self._visible_command_keys:
            selected_command = self._visible_command_keys[0]

        if selected_command:
            self.on_select(selected_command)
            self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-button":
            self.app.pop_screen()

    def action_focus_next(self) -> None:
        focusable_widgets = self.query("Button, Input, Select, DataTable")
        if not focusable_widgets:
            return

        current_focus = self.focused
        if current_focus is None:
            if focusable_widgets:
                focusable_widgets[0].focus()
            return

        try:
            current_index = list(focusable_widgets).index(current_focus)
            next_index = (current_index + 1) % len(focusable_widgets)
            focusable_widgets[next_index].focus()
        except (ValueError, IndexError):
            if focusable_widgets:
                focusable_widgets[0].focus()

    def action_focus_previous(self) -> None:
        focusable_widgets = self.query("Button, Input, Select, DataTable")
        if not focusable_widgets:
            return

        current_focus = self.focused
        if current_focus is None:
            if focusable_widgets:
                focusable_widgets[-1].focus()
            return

        try:
            current_index = list(focusable_widgets).index(current_focus)
            prev_index = (current_index - 1) % len(focusable_widgets)
            focusable_widgets[prev_index].focus()
        except (ValueError, IndexError):
            if focusable_widgets:
                focusable_widgets[-1].focus()


class QRCodeScreen(BaseModalScreen):
    def __init__(self, address):
        super().__init__()
        self.address = address

    def compose(self) -> ComposeResult:
        yield Label("📱 Wallet Address QR Code")
        yield Label(self.address, id="qr-address")
        yield Static(id="qr-display")
        yield Button("❌ Close", id="close-button")

    def on_mount(self) -> None:
        self.generate_qr_code()

    def generate_qr_code(self):
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        qr.add_data(self.address)
        qr.make(fit=True)

        qr_str = ""
        for row in qr.modules:
            qr_str += "".join(["██" if cell else "  " for cell in row]) + "\n"

        qr_display_widget = cast(Static, self.query_one("#qr-display"))
        qr_display_widget.update(qr_str)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-button":
            self.app.pop_screen()


class LoadingScreen(BaseModalScreen):
    BINDINGS = []

    def __init__(self, message: str = "Loading...", show_progress: bool = False):
        super().__init__()
        self._message = message
        self._show_progress = show_progress
        self._progress_text = ""
        self._retry_count = 0
        self._max_retries = 0
        self._loading_step = 0
        self._loading_timer = None
        self._loading_active = False

    def compose(self) -> ComposeResult:
        yield Label(self._message, id="loading-message")
        yield Static("", id="loading-progress")
        yield Static("", id="loading-spinner")

    def on_mount(self) -> None:
        self._start_loading_animation()

    def on_unmount(self) -> None:
        self._stop_loading_animation()

    def _start_loading_animation(self) -> None:
        self._loading_active = True
        self._loading_step = 0
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        def tick() -> None:
            if not self._loading_active:
                return
            self._loading_step = (self._loading_step + 1) % len(frames)
            spinner = frames[self._loading_step]
            try:
                spinner_widget = cast(Static, self.query_one("#loading-spinner"))
                spinner_widget.update(f"[cyan]{spinner}[/cyan]")
            except Exception:
                pass

        self._loading_timer = self.set_interval(0.08, tick)

    def _stop_loading_animation(self) -> None:
        self._loading_active = False
        if self._loading_timer:
            try:
                self._loading_timer.stop()
            except Exception:
                pass
            self._loading_timer = None

    def update_message(self, message: str) -> None:
        self._message = message
        try:
            label = cast(Label, self.query_one("#loading-message"))
            label.update(message)
        except Exception:
            pass

    def update_progress(self, text: str) -> None:
        self._progress_text = text
        try:
            progress = cast(Static, self.query_one("#loading-progress"))
            progress.update(f"[dim]{text}[/dim]")
        except Exception:
            pass

    def set_retry_status(self, attempt: int, max_retries: int, delay: float) -> None:
        self._retry_count = attempt
        self._max_retries = max_retries
        self.update_progress(f"Retry {attempt}/{max_retries} in {delay:.1f}s...")

    def show_error(self, error_message: str) -> None:
        self._stop_loading_animation()
        try:
            spinner = cast(Static, self.query_one("#loading-spinner"))
            spinner.update("[red]✗[/red]")
            label = cast(Label, self.query_one("#loading-message"))
            label.update(f"[red]{error_message}[/red]")
        except Exception:
            pass


__all__ = [
    "BaseModalScreen",
    "WalletLike",
    "AppWithWalletOps",
    "CommandSelectorScreen",
    "QRCodeScreen",
    "LoadingScreen",
    "BatchTransactionResultScreen",
    "MosaicInputScreen",
    "SaveTemplateScreen",
    "TemplateListScreen",
    "TemplateSelectorScreen",
    "TransactionConfirmScreen",
    "TransactionQueueScreen",
    "TransactionResultScreen",
    "TransactionStatusScreen",
    "AddAddressScreen",
    "AddressBookScreen",
    "AddressBookSelectorScreen",
    "ContactGroupsScreen",
    "CreateGroupScreen",
    "DeleteGroupConfirmScreen",
    "EditAddressScreen",
    "EditGroupScreen",
    "CreateMosaicDialogSubmitted",
    "CreateMosaicScreen",
    "HarvestingLinkScreen",
    "HarvestingUnlinkScreen",
    "MosaicMetadataScreen",
    "AccountManagerScreen",
    "AddAccountScreen",
    "DeleteAccountConfirmScreen",
    "EditAccountScreen",
    "ExportKeyScreen",
    "FirstRunImportWalletScreen",
    "FirstRunSetupScreen",
    "ImportAccountKeyScreen",
    "ImportEncryptedKeyScreen",
    "ImportWalletScreen",
    "NetworkSelectorScreen",
    "PasswordScreen",
    "QRScannerScreen",
    "SetPasswordScreen",
    "SetupPasswordScreen",
]
