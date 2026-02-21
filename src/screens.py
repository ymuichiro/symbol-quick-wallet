"""Modal screens for the Symbol Quick Wallet application."""

import logging
from typing import Callable, Protocol, cast

import qrcode
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from src.validation import AmountValidator

logger = logging.getLogger(__name__)


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


class AddressBookSelectorScreen(BaseModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def __init__(self, addresses):
        super().__init__()
        self.addresses = addresses

    def compose(self) -> ComposeResult:
        yield Label("📒 Select Address")
        yield DataTable(id="selector-table")
        yield Button("❌ Cancel", id="cancel-button")

    def on_mount(self) -> None:
        table = cast(DataTable, self.query_one("#selector-table"))
        table.add_column("Name")
        table.add_column("Address")
        for addr, info in self.addresses.items():
            table.add_row(info["name"], addr, key=addr)

    def on_data_table_row_selected(self, event):
        row = event.row_key
        address = row.value if hasattr(row, "value") else str(row)
        self.post_message(self.AddressBookSelected(address=address))
        self.app.pop_screen()

    class AddressBookSelected(Message):
        def __init__(self, address):
            super().__init__()
            self.address = address


class AddressBookScreen(BaseModalScreen):
    def __init__(self, addresses):
        super().__init__()
        self.addresses = addresses
        self._address_keys = []

    def compose(self) -> ComposeResult:
        yield Label("📒 Address Book")
        yield DataTable(id="address-book-table")
        yield Horizontal(
            Button("📤 Send to Selected", id="send-button", variant="primary"),
            Button("✏️ Edit", id="edit-button"),
            Button("🗑️ Delete", id="delete-button"),
            Button("❌ Close", id="cancel-button"),
        )

    def on_mount(self) -> None:
        table = cast(DataTable, self.query_one("#address-book-table"))
        table.add_column("Name", key="name")
        table.add_column("Address", key="address")
        table.add_column("Note", key="note")
        self._address_keys = list(self.addresses.keys())
        for addr in self._address_keys:
            info = self.addresses[addr]
            table.add_row(info["name"], addr, info["note"], key=addr)

    def _get_selected_address(self) -> str | None:
        table = cast(DataTable, self.query_one("#address-book-table"))
        cursor_row = table.cursor_row
        if cursor_row is None:
            return None

        try:
            get_row_at = getattr(table, "get_row_at", None)
            if callable(get_row_at):
                selected = get_row_at(cursor_row)
            else:
                if 0 <= cursor_row < len(self._address_keys):
                    selected = table.get_row(self._address_keys[cursor_row])
                else:
                    selected = None
        except Exception:
            selected = None

        if selected and len(selected) >= 2:
            return selected[1]

        if 0 <= cursor_row < len(self._address_keys):
            return self._address_keys[cursor_row]
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-button":
            address = self._get_selected_address()
            if address:
                self.post_message(self.SendToAddress(address=address))
                self.app.pop_screen()
        elif event.button.id == "edit-button":
            address = self._get_selected_address()
            if address:
                info = self.addresses[address]
                self.post_message(
                    self.EditAddress(
                        address=address, name=info["name"], note=info["note"]
                    )
                )
        elif event.button.id == "delete-button":
            address = self._get_selected_address()
            if address:
                self.post_message(self.DeleteAddress(address=address))
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class SendToAddress(Message):
        def __init__(self, address):
            super().__init__()
            self.address = address

    class EditAddress(Message):
        def __init__(self, address, name, note):
            super().__init__()
            self.address = address
            self.name = name
            self.note = note

    class DeleteAddress(Message):
        def __init__(self, address):
            super().__init__()
            self.address = address


class EditAddressScreen(BaseModalScreen):
    def __init__(self, address, name, note):
        super().__init__()
        self.address_value = address
        self.name_value = name
        self.note_value = note

    def compose(self) -> ComposeResult:
        yield Label("✏️ Edit Address")
        yield Label(f"Address: {self.address_value}")
        yield Input(placeholder="Name", id="name-input", value=self.name_value)
        yield Input(
            placeholder="Note (optional)", id="note-input", value=self.note_value
        )
        yield Horizontal(
            Button("✓ Save", id="save-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            name_input = cast(Input, self.query_one("#name-input"))
            note_input = cast(Input, self.query_one("#note-input"))
            name = name_input.value
            note = note_input.value
            self.post_message(
                self.EditAddressDialogSubmitted(
                    address=self.address_value, name=name, note=note
                )
            )
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class EditAddressDialogSubmitted(Message):
        def __init__(self, address, name, note):
            super().__init__()
            self.address = address
            self.name = name
            self.note = note


class AddAddressScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("➕ Add to Address Book")
        yield Input(placeholder="Name (Label)", id="name-input")
        yield Input(placeholder="Address", id="address-input")
        yield Input(placeholder="Note (optional)", id="note-input")
        yield Horizontal(
            Button("✓ Save", id="save-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            name_input = cast(Input, self.query_one("#name-input"))
            address_input = cast(Input, self.query_one("#address-input"))
            note_input = cast(Input, self.query_one("#note-input"))
            name = name_input.value
            address = address_input.value
            note = note_input.value
            self.post_message(
                self.AddAddressDialogSubmitted(name=name, address=address, note=note)
            )
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class AddAddressDialogSubmitted(Message):
        def __init__(self, name, address, note=""):
            super().__init__()
            self.name = name
            self.address = address
            self.note = note


class ImportWalletScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("📥 Import Wallet")
        yield Input(
            placeholder="Private Key (hex)", id="private-key-input", password=True
        )
        yield Label("⚠️ Never share your private key with anyone!")
        yield Horizontal(
            Button("✓ Import", id="import-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-button":
            private_key_input = cast(Input, self.query_one("#private-key-input"))
            private_key = private_key_input.value
            if private_key:
                self.post_message(
                    self.ImportWalletDialogSubmitted(private_key=private_key)
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class ImportWalletDialogSubmitted(Message):
        def __init__(self, private_key):
            super().__init__()
            self.private_key = private_key


class FirstRunImportWalletScreen(ImportWalletScreen):
    def __init__(self, network):
        super().__init__()
        self.network = network

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-button":
            private_key_input = cast(Input, self.query_one("#private-key-input"))
            private_key = private_key_input.value
            if private_key:
                self.post_message(
                    self.FirstRunImportWalletDialogSubmitted(private_key=private_key)
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class FirstRunImportWalletDialogSubmitted(Message):
        def __init__(self, private_key):
            super().__init__()
            self.private_key = private_key


class ExportKeyScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("🔐 Export Encrypted Private Key")
        yield Input(placeholder="Password", id="password-input", password=True)
        yield Label(
            "⚠️ The encrypted key will be saved to ~/.symbol-quick-wallet/encrypted_private_key.json"
        )
        yield Label(
            "ℹ️ Make sure to remember your password - there is no recovery option!"
        )
        yield Horizontal(
            Button("✓ Export", id="export-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-button":
            password_input = cast(Input, self.query_one("#password-input"))
            password = password_input.value
            if password:
                self.post_message(self.ExportKeyDialogSubmitted(password=password))
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class ExportKeyDialogSubmitted(Message):
        def __init__(self, password):
            super().__init__()
            self.password = password


class ImportEncryptedKeyScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("📥 Import Encrypted Private Key")
        yield Input(placeholder="File path", id="file-path-input")
        yield Input(placeholder="Password", id="password-input", password=True)
        yield Label("ℹ️ Default path: ~/.symbol-quick-wallet/encrypted_private_key.json")
        yield Horizontal(
            Button("✓ Import", id="import-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-button":
            file_path_input = cast(Input, self.query_one("#file-path-input"))
            password_input = cast(Input, self.query_one("#password-input"))
            file_path = file_path_input.value
            password = password_input.value
            if file_path and password:
                self.post_message(
                    self.ImportEncryptedKeyDialogSubmitted(
                        file_path=file_path, password=password
                    )
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class ImportEncryptedKeyDialogSubmitted(Message):
        def __init__(self, file_path, password):
            super().__init__()
            self.file_path = file_path
            self.password = password


class TransactionConfirmScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "confirm", "Confirm")]

    def __init__(self, recipient, mosaics, message, fee):
        super().__init__()
        self.recipient = recipient
        self.mosaics = mosaics
        self.message = message
        self.fee = fee
        self.wallet: WalletLike | None = None

    def compose(self) -> ComposeResult:
        yield Label("✅ Confirm Transaction", id="confirm-title")
        yield Static(f"📤 Recipient: {self.recipient}")
        yield Label("💰 Mosaics:")
        yield Static(id="mosaics-list")
        yield Static(f"⚡ Fee: {self.fee:,.6f} XYM")
        yield Static(f"💬 Message: {self.message if self.message else '(none)'}")
        yield Horizontal(
            Button("✓ Confirm", id="confirm-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_mount(self) -> None:
        self.wallet = cast(AppWithWalletOps, self.app).wallet
        self.update_mosaics_list()

    def update_mosaics_list(self):
        if self.wallet is None:
            return
        mosaics_text = ""
        for mosaic in self.mosaics:
            amount_units = f"{mosaic['amount'] / 1_000_000:,.6f} units"
            mosaic_name = self.wallet.get_mosaic_name(mosaic["mosaic_id"])
            mosaics_text += f"  - {amount_units} ({mosaic_name})\n"
        mosaics_list_widget = cast(Static, self.query_one("#mosaics-list"))
        mosaics_list_widget.update(mosaics_text.strip())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-button":
            self.dismiss(
                {
                    "recipient": self.recipient,
                    "mosaics": self.mosaics,
                    "message": self.message,
                }
            )
        elif event.button.id == "cancel-button":
            self.dismiss(None)

    def action_confirm(self) -> None:
        self.dismiss(
            {
                "recipient": self.recipient,
                "mosaics": self.mosaics,
                "message": self.message,
            }
        )

    class TransactionConfirmDialogSubmitted(Message):
        def __init__(self, recipient, mosaics, message):
            super().__init__()
            self.recipient = recipient
            self.mosaics = mosaics
            self.message = message


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


class CreateMosaicScreen(BaseModalScreen):
    def __init__(self):
        super().__init__()
        self.transferable = True
        self.supply_mutable = False
        self.revokable = False

    def compose(self) -> ComposeResult:
        yield Label("🎨 Create Mosaic")
        yield Label("Supply (in micro-units):")
        yield Input(
            placeholder="1000000 (1 XYM)",
            id="supply-input",
            type="number",
        )
        yield Label("Divisibility (0-6):")
        yield Input(
            placeholder="0-6",
            id="divisibility-input",
            type="number",
            value="0",
        )
        yield Label(f"Transferable: {self.transferable}", id="transferable-label")
        yield Label(f"Supply Mutable: {self.supply_mutable}", id="mutable-label")
        yield Label(f"Revokable: {self.revokable}", id="revokable-label")
        yield Horizontal(
            Button("Toggle Transferable", id="toggle-transferable"),
            Button("Toggle Mutable", id="toggle-mutable"),
            Button("Toggle Revokable", id="toggle-revokable"),
        )
        yield Label(
            "💡 Transferable: Can be sent to others\n"
            "Supply Mutable: Can change supply later\n"
            "Revokable: Issuer can revoke mosaics"
        )
        yield Horizontal(
            Button("✓ Create", id="create-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "toggle-transferable":
            self.transferable = not self.transferable
            cast(Label, self.query_one("#transferable-label")).update(
                f"Transferable: {self.transferable}"
            )
        elif event.button.id == "toggle-mutable":
            self.supply_mutable = not self.supply_mutable
            cast(Label, self.query_one("#mutable-label")).update(
                f"Supply Mutable: {self.supply_mutable}"
            )
        elif event.button.id == "toggle-revokable":
            self.revokable = not self.revokable
            cast(Label, self.query_one("#revokable-label")).update(
                f"Revokable: {self.revokable}"
            )
        elif event.button.id == "create-button":
            supply_input = cast(Input, self.query_one("#supply-input"))
            divisibility_input = cast(Input, self.query_one("#divisibility-input"))
            supply = supply_input.value
            divisibility = divisibility_input.value
            if supply and divisibility:
                self.post_message(
                    CreateMosaicDialogSubmitted(
                        supply=int(supply),
                        divisibility=int(divisibility),
                        transferable=self.transferable,
                        supply_mutable=self.supply_mutable,
                        revokable=self.revokable,
                    )
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()


class CreateMosaicDialogSubmitted(Message):
    def __init__(self, supply, divisibility, transferable, supply_mutable, revokable):
        super().__init__()
        self.supply = supply
        self.divisibility = divisibility
        self.transferable = transferable
        self.supply_mutable = supply_mutable
        self.revokable = revokable


class SetupPasswordSubmitted(Message):
    def __init__(self, password):
        super().__init__()
        self.password = password


class SetupPasswordScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("🔐 Set Password")
        yield Label("Enter a password for your new wallet:")
        yield Input(placeholder="Password", id="password-input", password=True)
        yield Label(
            "⚠️ Make sure to remember your password. There is no recovery option!",
            classes="warning",
        )
        yield Horizontal(
            Button("✓ Next", id="next-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next-button":
            password_input = cast(Input, self.query_one("#password-input"))
            password = password_input.value
            logger.info("[SetupPasswordScreen] Next button pressed")
            self.post_message(SetupPasswordSubmitted(password=password))
            logger.info("[SetupPasswordScreen] SetupPasswordSubmitted message sent")
            self.app.pop_screen()
            logger.info("[SetupPasswordScreen] Screen popped")
        elif event.button.id == "cancel-button":
            logger.info("[SetupPasswordScreen] Cancel button pressed")
            self.app.pop_screen()


class PasswordScreen(BaseModalScreen):
    def __init__(
        self,
        title: str = "Password",
        confirm_button_text: str = "Confirm",
        screen_type: str = "unlock",
    ):
        super().__init__()
        self.dialog_title = title
        self.confirm_button_text = confirm_button_text
        self.screen_type = screen_type

    BINDINGS = [
        ("escape", "action_escape", "Escape"),
        ("tab", "action_focus_next", "Next"),
        ("shift+tab", "action_focus_previous", "Previous"),
        ("enter", "action_confirm", "Confirm"),
    ]

    def action_escape(self) -> None:
        import logging

        logger = logging.getLogger("src.screens")
        logger.info(
            f"[PasswordScreen.action_escape] Escape pressed, screen_type={self.screen_type}"
        )
        if self.screen_type == "unlock":
            self.notify(
                "Password required to access wallet. Exiting application.",
                severity="warning",
            )
            logger.info("[PasswordScreen.action_escape] Exiting application")
            self.app.exit()
        else:
            logger.info("[PasswordScreen.action_escape] Popping screen")
            self.app.pop_screen()

    def action_confirm(self) -> None:
        import logging

        logger = logging.getLogger("src.screens")
        logger.info(
            "[PasswordScreen.action_confirm] Enter pressed, confirming password"
        )

        password_input = cast(Input, self.query_one("#password-input"))
        password = password_input.value
        if not password:
            logger.warning("[PasswordScreen.action_confirm] Empty password, ignoring")
            return

        if self.screen_type == "unlock":
            logger.info("[PasswordScreen.action_confirm] Calling app to unlock wallet")
            try:
                success = cast(AppWithWalletOps, self.app).unlock_wallet(password, self)
                logger.info(
                    f"[PasswordScreen.action_confirm] app.unlock_wallet() returned: {success}"
                )
                if success:
                    logger.info(
                        "[PasswordScreen.action_confirm] Unlock successful, popping screen"
                    )
                    self.app.pop_screen()
                else:
                    logger.info(
                        "[PasswordScreen.action_confirm] Unlock failed, clearing password input"
                    )
                    password_input = cast(Input, self.query_one("#password-input"))
                    password_input.value = ""
            except Exception as e:
                logger.error(
                    f"[PasswordScreen.action_confirm] ERROR: {e}", exc_info=True
                )
                self.notify(f"Error: {str(e)}", severity="error")
        else:
            logger.info(
                "[PasswordScreen.action_confirm] Posting message for other screen types"
            )
            try:
                self.app.post_message(
                    self.PasswordDialogSubmitted(
                        password=password, screen_type=self.screen_type, screen=self
                    )
                )
                logger.info(
                    "[PasswordScreen.action_confirm] Message posted successfully"
                )
                self.app.pop_screen()
                logger.info("[PasswordScreen.action_confirm] Screen popped")
            except Exception as e:
                logger.error(
                    f"[PasswordScreen.action_confirm] ERROR: {e}", exc_info=True
                )
                self.notify(f"Error: {str(e)}", severity="error")

    def compose(self) -> ComposeResult:
        import logging

        logger = logging.getLogger("src.screens")
        logger.info("")
        logger.info("=" * 80)
        logger.info(
            "[PasswordScreen.compose] ========== PASSWORD SCREEN COMPOSING =========="
        )
        logger.info("=" * 80)
        logger.info(f"[PasswordScreen.compose] Screen type: {self.screen_type}")
        logger.info(f"[PasswordScreen.compose] Title: {self.dialog_title}")
        logger.info(
            f"[PasswordScreen.compose] Confirm button text: {self.confirm_button_text}"
        )
        logger.info(f"[PasswordScreen.compose] App type: {type(self.app)}")
        logger.info(
            f"[PasswordScreen.compose] Screen stack size: {len(self.app.screen_stack)}"
        )

        logger.info("[PasswordScreen.compose] Creating UI components")
        yield Label(self.dialog_title, id="password-title")
        logger.info("[PasswordScreen.compose] Password title label created")

        yield Input(
            placeholder="Password",
            id="password-input",
            password=True,
        )
        logger.info("[PasswordScreen.compose] Password input created")
        if self.confirm_button_text != "Confirm":
            logger.info("[PasswordScreen.compose] Creating hint label")
            yield Label("(Leave empty for no password)", classes="hint")
            logger.info("[PasswordScreen.compose] Hint label created")

        logger.info("[PasswordScreen.compose] Creating buttons")
        yield Horizontal(
            Button(
                f"✓ {self.confirm_button_text}", id="confirm-button", variant="primary"
            ),
            Button("✗ Cancel", id="cancel-button"),
        )
        logger.info("[PasswordScreen.compose] Buttons created")

        logger.info(
            "[PasswordScreen.compose] ========== PASSWORD SCREEN COMPOSED =========="
        )
        logger.info("=" * 80)
        logger.info("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key press in password input."""
        if event.input.id == "password-input":
            import logging

            logger = logging.getLogger("src.screens")
            logger.info("")
            logger.info("=" * 80)
            logger.info(
                "[PasswordScreen.on_input_submitted] ========== INPUT SUBMITTED (ENTER KEY) =========="
            )
            logger.info("=" * 80)
            logger.info(
                f"[PasswordScreen.on_input_submitted] Input ID: {event.input.id}"
            )
            logger.info(
                f"[PasswordScreen.on_input_submitted] Screen type: {self.screen_type}"
            )
            logger.info(
                f"[PasswordScreen.on_input_submitted] Password length: {len(event.value) if event.value else 0}"
            )
            logger.info(
                "[PasswordScreen.on_input_submitted] Simulating confirm button press"
            )

            password = event.value
            if not password:
                logger.warning(
                    "[PasswordScreen.on_input_submitted] Empty password, ignoring"
                )
                return

            if self.screen_type == "unlock":
                logger.info(
                    "[PasswordScreen.on_input_submitted] Calling app to unlock wallet"
                )
                try:
                    success = cast(AppWithWalletOps, self.app).unlock_wallet(
                        password, self
                    )
                    logger.info(
                        f"[PasswordScreen.on_input_submitted] app.unlock_wallet() returned: {success}"
                    )
                    if success:
                        logger.info(
                            "[PasswordScreen.on_input_submitted] Unlock successful, popping screen"
                        )
                        self.app.pop_screen()
                        logger.info(
                            "[PasswordScreen.on_input_submitted] Screen popped successfully"
                        )
                    else:
                        logger.info(
                            "[PasswordScreen.on_input_submitted] Unlock failed, screen remains open"
                        )
                        # Clear password input for retry
                        event.input.value = ""
                except Exception as e:
                    logger.error(
                        f"[PasswordScreen.on_input_submitted] ERROR: {e}", exc_info=True
                    )
                    self.notify(f"Error: {str(e)}", severity="error")
            else:
                logger.info(
                    "[PasswordScreen.on_input_submitted] Posting message for other screen types"
                )
                try:
                    self.app.post_message(
                        self.PasswordDialogSubmitted(
                            password=password, screen_type=self.screen_type, screen=self
                        )
                    )
                    logger.info(
                        "[PasswordScreen.on_input_submitted] Message posted successfully"
                    )
                    self.app.pop_screen()
                    logger.info("[PasswordScreen.on_input_submitted] Screen popped")
                except Exception as e:
                    logger.error(
                        f"[PasswordScreen.on_input_submitted] ERROR: {e}", exc_info=True
                    )
                    self.notify(f"Error: {str(e)}", severity="error")

            logger.info("")
            logger.info(
                "[PasswordScreen.on_input_submitted] ========== INPUT SUBMITTED COMPLETED =========="
            )
            logger.info("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        import logging

        logger = logging.getLogger("src.screens")
        logger.info("")
        logger.info("=" * 80)
        logger.info(
            "[PasswordScreen.on_button_pressed] ========== BUTTON PRESSED =========="
        )
        logger.info("=" * 80)
        logger.info(f"[PasswordScreen.on_button_pressed] Button ID: {event.button.id}")
        logger.info(
            f"[PasswordScreen.on_button_pressed] Screen type: {self.screen_type}"
        )
        logger.info(f"[PasswordScreen.on_button_pressed] App type: {type(self.app)}")
        logger.info(
            f"[PasswordScreen.on_button_pressed] Screen stack size: {len(self.app.screen_stack)}"
        )
        logger.info(
            f"[PasswordScreen.on_button_pressed] Current screen: {type(self.app.screen)}"
        )

        if event.button.id == "confirm-button":
            logger.info(
                "[PasswordScreen.on_button_pressed] ========== CONFIRM BUTTON =========="
            )
            logger.info(
                "[PasswordScreen.on_button_pressed] Getting password from input"
            )
            password_input = cast(Input, self.query_one("#password-input"))
            password = password_input.value
            if not password:
                logger.warning(
                    "[PasswordScreen.on_button_pressed] Empty password, ignoring"
                )
                return
            logger.info(
                f"[PasswordScreen.on_button_pressed] Password length: {len(password) if password else 0}"
            )
            logger.info(
                f"[PasswordScreen.on_button_pressed] Password provided: {password is not None and len(password) > 0}"
            )

            logger.info("")
            logger.info(
                "[PasswordScreen.on_button_pressed] ========== CREATING MESSAGE =========="
            )
            logger.info(
                "[PasswordScreen.on_button_pressed] Creating PasswordDialogSubmitted"
            )
            logger.info(
                f"[PasswordScreen.on_button_pressed] Message password length: {len(password) if password else 0}"
            )
            logger.info(
                f"[PasswordScreen.on_button_pressed] Message screen_type: {self.screen_type}"
            )

            logger.info("")
            logger.info(
                "[PasswordScreen.on_button_pressed] ========== POSTING MESSAGE TO APP =========="
            )
            logger.info(
                "[PasswordScreen.on_button_pressed] About to call app.post_message()"
            )
            logger.info(
                f"[PasswordScreen.on_button_pressed] App has on_password_dialog_submitted: {hasattr(self.app, 'on_password_dialog_submitted')}"
            )

            try:
                logger.info("")
                logger.info(
                    "[PasswordScreen.on_button_pressed] ========== DIRECT PASSWORD VERIFICATION =========="
                )
                logger.info("")

                if self.screen_type == "unlock":
                    logger.info(
                        "[PasswordScreen.on_button_pressed] Calling app to unlock wallet"
                    )
                    success = cast(AppWithWalletOps, self.app).unlock_wallet(
                        password, self
                    )
                    logger.info(
                        f"[PasswordScreen.on_button_pressed] app.unlock_wallet() returned: {success}"
                    )
                    if success:
                        logger.info(
                            "[PasswordScreen.on_button_pressed] Unlock successful, popping screen"
                        )
                        self.app.pop_screen()
                        logger.info("[PasswordScreen.on_button_pressed] Screen popped")
                    else:
                        logger.info(
                            "[PasswordScreen.on_button_pressed] Unlock failed, screen remains open"
                        )
                else:
                    logger.info(
                        "[PasswordScreen.on_button_pressed] Posting message for other screen types"
                    )
                    self.app.post_message(
                        self.PasswordDialogSubmitted(
                            password=password, screen_type=self.screen_type, screen=self
                        )
                    )
                    logger.info(
                        "[PasswordScreen.on_button_pressed] Message posted successfully"
                    )
                    self.app.pop_screen()
                    logger.info("[PasswordScreen.on_button_pressed] Screen popped")

                logger.info("")
                logger.info(
                    "[PasswordScreen.on_button_pressed] ========== DIRECT PASSWORD VERIFICATION COMPLETED =========="
                )
                logger.info("")
            except Exception as e:
                logger.error(
                    f"[PasswordScreen.on_button_pressed] ERROR: {e}",
                    exc_info=True,
                )
                logger.error("")
                self.notify(f"Error: {str(e)}", severity="error")

            logger.info("")
            logger.info(
                "[PasswordScreen.on_button_pressed] ========== CONFIRM BUTTON HANDLING COMPLETED =========="
            )
            logger.info("")

        elif event.button.id == "cancel-button":
            logger.info(
                "[PasswordScreen.on_button_pressed] ========== CANCEL BUTTON =========="
            )
            logger.info("[PasswordScreen.on_button_pressed] Cancel button pressed")

            if self.screen_type == "unlock":
                logger.info(
                    "[PasswordScreen.on_button_pressed] Screen type is unlock, showing notification and exiting"
                )
                self.notify(
                    "Password required to access wallet. Exiting application.",
                    severity="warning",
                )
                logger.info(
                    "[PasswordScreen.on_button_pressed] About to call app.exit()"
                )
                dump_screen_stack = getattr(self.app, "dump_screen_stack", None)
                if callable(dump_screen_stack):
                    dump_screen_stack(
                        "PasswordScreen.on_button_pressed CANCEL BEFORE app.exit()"
                    )
                self.app.exit()
                logger.info("[PasswordScreen.on_button_pressed] app.exit() called")
            else:
                logger.info(
                    "[PasswordScreen.on_button_pressed] Screen type is not unlock, just popping screen"
                )
                logger.info(
                    "[PasswordScreen.on_button_pressed] About to call app.pop_screen()"
                )
                self.app.pop_screen()
                logger.info(
                    "[PasswordScreen.on_button_pressed] app.pop_screen() called"
                )

            logger.info(
                "[PasswordScreen.on_button_pressed] ========== BUTTON HANDLING COMPLETED =========="
            )
            logger.info("=" * 80)
            logger.info("")

    class PasswordDialogSubmitted(Message):
        def __init__(self, password, screen_type="unlock", screen=None):
            super().__init__()
            self.password = password
            self.screen_type = screen_type
            self.screen = screen


class NetworkSelectorScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("🌐 Select Network")
        yield Horizontal(
            Button("Testnet", id="testnet-button", variant="primary"),
            Button("Mainnet", id="mainnet-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "testnet-button":
            self.post_message(self.NetworkSelected(network="testnet"))
        elif event.button.id == "mainnet-button":
            self.post_message(self.NetworkSelected(network="mainnet"))

    class NetworkSelected(Message):
        def __init__(self, network):
            super().__init__()
            self.network = network


class FirstRunSetupScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("🚀 Wallet Setup")
        yield Static("Choose an option:")
        yield Horizontal(
            Button("✨ Create New Wallet", id="create-button", variant="primary"),
            Button("🔑 Import Existing Wallet", id="import-button"),
            Button("❌ Cancel", id="cancel-button"),
        )
        yield Static(
            "💡 New wallet will be created with the password you just entered.",
            classes="hint",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-button":
            self.post_message(self.SetupAction(action="create"))
        elif event.button.id == "import-button":
            self.post_message(self.SetupAction(action="import"))
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class SetupAction(Message):
        def __init__(self, action):
            super().__init__()
            self.action = action


class SetPasswordScreen(BaseModalScreen):
    def __init__(self, network, action):
        super().__init__()
        self.network = network
        self.action = action  # "create" or "import"

    def compose(self) -> ComposeResult:
        yield Label(f"🔐 Set Password - {self.network.upper()}")
        yield Label(f"Action: {self.action.capitalize()} Wallet")
        yield Label("Password (required):")
        yield Input(placeholder="Enter password", id="password-input", password=True)
        yield Label("Confirm Password:")
        yield Input(
            placeholder="Confirm password", id="confirm-password-input", password=True
        )
        yield Horizontal(
            Button("✓ Set Password", id="set-password-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )
        yield Static(
            "⚠️ Make sure to remember your password. There is no recovery option!",
            classes="warning",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "set-password-button":
            password_input = cast(Input, self.query_one("#password-input"))
            confirm_password_input = cast(
                Input, self.query_one("#confirm-password-input")
            )
            password = password_input.value
            confirm_password = confirm_password_input.value
            if not password:
                self.notify("Password cannot be empty", severity="error")
            elif password != confirm_password:
                self.notify("Passwords do not match", severity="error")
            else:
                self.post_message(
                    self.SetPasswordDialogSubmitted(
                        password=password, action=self.action
                    )
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class SetPasswordDialogSubmitted(Message):
        def __init__(self, password, action):
            super().__init__()
            self.password = password
            self.action = action  # "create" or "import"


class MosaicInputScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "confirm", "Confirm")]

    def __init__(self, owned_mosaics):
        super().__init__()
        self.owned_mosaics = owned_mosaics
        self._selected_mosaic_id: int | None = None
        self._validation_error: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("➕ Add Mosaic to Transaction")

        mosaic_options = [(m["name"], hex(m["id"])) for m in self.owned_mosaics]
        yield Label("Select Mosaic:")
        yield Select(
            mosaic_options,
            id="mosaic-select",
            prompt="Select a mosaic...",
            allow_blank=False,
        )

        yield Label("Amount (human units):")
        yield Input(
            placeholder="e.g. 1.25",
            id="amount-input",
            type="text",
        )

        yield Label("", id="validation-error-label")

        yield Label("💡 Your owned mosaics:")
        for mosaic in self.owned_mosaics:
            divisibility = int(mosaic.get("divisibility", 0))
            owned_human = mosaic.get("human_amount")
            if owned_human is None:
                owned_human = mosaic["amount"] / (10**divisibility)
            yield Static(
                f"  - {mosaic['name']}: {owned_human:,.{divisibility}f} units "
                f"(divisibility: {divisibility})"
            )

        yield Horizontal(
            Button("✓ Add", id="add-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def action_confirm(self) -> None:
        self._submit_selected_mosaic()

    def on_mount(self) -> None:
        self._clear_validation_error()

    def _clear_validation_error(self) -> None:
        try:
            error_label = cast(Label, self.query_one("#validation-error-label"))
            error_label.update("")
        except Exception:
            pass

    def _show_validation_error(self, message: str) -> None:
        try:
            error_label = cast(Label, self.query_one("#validation-error-label"))
            error_label.update(f"⚠️ {message}")
            self._validation_error = message
        except Exception:
            self.notify(message, severity="error")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "amount-input":
            self._validate_amount_input(event.value)

    def _validate_amount_input(self, value: str) -> bool:
        if not value or not value.strip():
            self._clear_validation_error()
            return False

        mosaic_select = cast(Select, self.query_one("#mosaic-select"))
        if not mosaic_select.value or not isinstance(mosaic_select.value, str):
            return False

        try:
            mosaic_id = int(mosaic_select.value, 16)
        except (TypeError, ValueError):
            return False

        selected_mosaic = None
        for mosaic in self.owned_mosaics:
            if mosaic["id"] == mosaic_id:
                selected_mosaic = mosaic
                break

        if not selected_mosaic:
            return False

        divisibility = int(selected_mosaic.get("divisibility", 0))
        owned_amount = selected_mosaic.get("amount", 0)

        result = AmountValidator.validate_full(value, divisibility, owned_amount)

        if not result.is_valid:
            self._show_validation_error(result.error_message or "Invalid amount")
            return False

        self._clear_validation_error()
        return True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "amount-input":
            self._submit_selected_mosaic()

    def _submit_selected_mosaic(self) -> None:
        mosaic_select = cast(Select, self.query_one("#mosaic-select"))
        amount_input = cast(Input, self.query_one("#amount-input"))

        if not mosaic_select.value:
            self._show_validation_error("Please select a mosaic")
            return

        if not amount_input.value:
            self._show_validation_error("Please enter an amount")
            return

        if not isinstance(mosaic_select.value, str):
            self._show_validation_error("Please select a valid mosaic")
            return

        try:
            mosaic_id = int(mosaic_select.value, 16)
        except (TypeError, ValueError):
            self._show_validation_error("Please select a valid mosaic")
            return

        selected_mosaic = None
        for mosaic in self.owned_mosaics:
            if mosaic["id"] == mosaic_id:
                selected_mosaic = mosaic
                break

        if not selected_mosaic:
            self._show_validation_error("Selected mosaic was not found")
            return

        divisibility = int(selected_mosaic.get("divisibility", 0))
        owned_amount = selected_mosaic.get("amount", 0)

        validation_result = AmountValidator.validate_full(
            amount_input.value, divisibility, owned_amount
        )

        if not validation_result.is_valid:
            self._show_validation_error(
                validation_result.error_message or "Invalid amount"
            )
            return

        self.dismiss(
            {"mosaic_id": mosaic_id, "amount": validation_result.normalized_value}
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-button":
            self._submit_selected_mosaic()
        elif event.button.id == "cancel-button":
            self.dismiss(None)

    class MosaicAdded(Message):
        def __init__(self, mosaic_id, amount):
            super().__init__()
            self.mosaic_id = mosaic_id
            self.amount = amount


class HarvestingLinkScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("🔗 Link Harvesting Account")
        yield Label(
            "Enter the public key of the node you want to delegate harvesting to:"
        )
        yield Input(
            placeholder="Remote Public Key",
            id="remote-public-key-input",
        )
        yield Label(
            "⚠️ Make sure you trust this node. Once linked, the node can harvest on your behalf."
        )
        yield Horizontal(
            Button("✓ Link", id="link-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "link-button":
            remote_public_key_input = cast(
                Input, self.query_one("#remote-public-key-input")
            )
            remote_public_key = remote_public_key_input.value
            if remote_public_key:
                self.post_message(
                    self.HarvestingLinkDialogSubmitted(
                        remote_public_key=remote_public_key
                    )
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class HarvestingLinkDialogSubmitted(Message):
        def __init__(self, remote_public_key):
            super().__init__()
            self.remote_public_key = remote_public_key


class HarvestingUnlinkScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("🔗 Unlink Harvesting Account")
        yield Label("Are you sure you want to unlink your harvesting account?")
        yield Label("⚠️ You will stop harvesting and may lose rewards.")
        yield Horizontal(
            Button("✓ Unlink", id="unlink-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "unlink-button":
            self.post_message(self.HarvestingUnlinkDialogSubmitted())
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class HarvestingUnlinkDialogSubmitted(Message):
        pass


class TransactionResultScreen(BaseModalScreen):
    def __init__(self, tx_hash, network="testnet"):
        super().__init__()
        self.tx_hash = tx_hash
        self.network = network

    def compose(self) -> ComposeResult:
        yield Label("✅ Transaction Sent!", id="result-title")
        yield Label("Transaction Hash:")
        yield Static(self.tx_hash, id="tx-hash-display")
        if self.network == "testnet":
            explorer_url = f"https://testnet.symbol.fyi/transactions/{self.tx_hash}"
        else:
            explorer_url = f"https://symbol.fyi/transactions/{self.tx_hash}"
        yield Label(f"Explorer: {explorer_url}")
        yield Button("📋 Copy Hash", id="copy-hash-button", variant="primary")
        yield Button("❌ Close", id="close-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-hash-button":
            import pyperclip

            pyperclip.copy(self.tx_hash)
            self.notify("Transaction hash copied to clipboard!", severity="information")
        elif event.button.id == "close-button":
            self.app.pop_screen()


class AccountManagerScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "select", "Select")]

    def __init__(self, accounts, current_index):
        super().__init__()
        self.accounts = accounts
        self.current_index = current_index
        self._account_keys = []

    def compose(self) -> ComposeResult:
        yield Label("👤 Account Manager")
        yield DataTable(id="accounts-table")
        yield Horizontal(
            Button("🔄 Switch", id="switch-button", variant="primary"),
            Button("➕ Add New", id="add-button"),
            Button("✏️ Edit", id="edit-button"),
            Button("🗑️ Delete", id="delete-button"),
            Button("❌ Close", id="close-button"),
        )

    def on_mount(self) -> None:
        table = cast(DataTable, self.query_one("#accounts-table"))
        table.add_column("Label", key="label")
        table.add_column("Address", key="address")
        table.add_column("Address Book", key="address_book")
        table.add_column("Active", key="active")
        self._account_keys = list(range(len(self.accounts)))
        for idx, acc in enumerate(self.accounts):
            active = "✓" if idx == self.current_index else ""
            book_type = "Shared" if acc.address_book_shared else "Private"
            table.add_row(acc.label, acc.address, book_type, active, key=str(idx))
        table.cursor_row = self.current_index

    def _get_selected_index(self) -> int | None:
        table = cast(DataTable, self.query_one("#accounts-table"))
        cursor_row = table.cursor_row
        if cursor_row is not None and 0 <= cursor_row < len(self.accounts):
            return cursor_row
        return None

    def on_data_table_row_selected(self, event):
        self._switch_to_selected()

    def action_select(self) -> None:
        self._switch_to_selected()

    def _switch_to_selected(self):
        idx = self._get_selected_index()
        if idx is not None:
            self.post_message(self.AccountSelected(index=idx))
            self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        idx = self._get_selected_index()
        if event.button.id == "switch-button":
            if idx is not None:
                self.post_message(self.AccountSelected(index=idx))
                self.app.pop_screen()
        elif event.button.id == "add-button":
            self.post_message(self.AddAccountRequested())
        elif event.button.id == "edit-button":
            if idx is not None:
                acc = self.accounts[idx]
                self.post_message(
                    self.EditAccountRequested(
                        index=idx,
                        label=acc.label,
                        address_book_shared=acc.address_book_shared,
                    )
                )
        elif event.button.id == "delete-button":
            if idx is not None:
                self.post_message(self.DeleteAccountRequested(index=idx))
        elif event.button.id == "close-button":
            self.app.pop_screen()

    class AccountSelected(Message):
        def __init__(self, index: int):
            super().__init__()
            self.index = index

    class AddAccountRequested(Message):
        pass

    class EditAccountRequested(Message):
        def __init__(self, index: int, label: str, address_book_shared: bool):
            super().__init__()
            self.index = index
            self.label = label
            self.address_book_shared = address_book_shared

    class DeleteAccountRequested(Message):
        def __init__(self, index: int):
            super().__init__()
            self.index = index


class AddAccountScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("➕ Add New Account")
        yield Label("Account Label:")
        yield Input(placeholder="e.g., Savings Account", id="label-input")
        yield Label("Address Book:")
        yield Horizontal(
            Button("Shared (Recommended)", id="shared-button", variant="primary"),
            Button("Private", id="private-button"),
            id="address-book-buttons",
        )
        yield Label(id="address-book-hint")
        yield Horizontal(
            Button("✨ Create New", id="create-button"),
            Button("🔑 Import Private Key", id="import-button"),
        )
        yield Horizontal(
            Button("❌ Cancel", id="cancel-button"),
        )

    def on_mount(self) -> None:
        self._address_book_shared = True
        self._update_address_book_hint()

    def _update_address_book_hint(self):
        hint = cast(Label, self.query_one("#address-book-hint"))
        if self._address_book_shared:
            hint.update("Using shared address book across all accounts")
        else:
            hint.update("This account will have its own private address book")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "shared-button":
            self._address_book_shared = True
            self._update_address_book_hint()
        elif event.button.id == "private-button":
            self._address_book_shared = False
            self._update_address_book_hint()
        elif event.button.id == "create-button":
            label_input = cast(Input, self.query_one("#label-input"))
            label = label_input.value.strip()
            self.post_message(
                self.CreateAccountRequested(
                    label=label, address_book_shared=self._address_book_shared
                )
            )
            self.app.pop_screen()
        elif event.button.id == "import-button":
            label_input = cast(Input, self.query_one("#label-input"))
            label = label_input.value.strip()
            self.post_message(
                self.ImportAccountRequested(
                    label=label, address_book_shared=self._address_book_shared
                )
            )
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class CreateAccountRequested(Message):
        def __init__(self, label: str, address_book_shared: bool):
            super().__init__()
            self.label = label
            self.address_book_shared = address_book_shared

    class ImportAccountRequested(Message):
        def __init__(self, label: str, address_book_shared: bool):
            super().__init__()
            self.label = label
            self.address_book_shared = address_book_shared


class ImportAccountKeyScreen(BaseModalScreen):
    def __init__(self, label: str, address_book_shared: bool):
        super().__init__()
        self.label = label
        self.address_book_shared = address_book_shared

    def compose(self) -> ComposeResult:
        yield Label("🔑 Import Account")
        yield Label(f"Label: {self.label or '(default)'}")
        yield Label("Private Key (hex):")
        yield Input(
            placeholder="64-character hex private key",
            id="private-key-input",
            password=True,
        )
        yield Label("⚠️ Never share your private key!")
        yield Horizontal(
            Button("✓ Import", id="import-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-button":
            key_input = cast(Input, self.query_one("#private-key-input"))
            private_key = key_input.value.strip()
            if private_key:
                self.post_message(
                    self.ImportKeySubmitted(
                        private_key=private_key,
                        label=self.label,
                        address_book_shared=self.address_book_shared,
                    )
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class ImportKeySubmitted(Message):
        def __init__(self, private_key: str, label: str, address_book_shared: bool):
            super().__init__()
            self.private_key = private_key
            self.label = label
            self.address_book_shared = address_book_shared


class EditAccountScreen(BaseModalScreen):
    def __init__(self, index: int, label: str, address_book_shared: bool):
        super().__init__()
        self.index = index
        self.label_value = label
        self.address_book_shared_value = address_book_shared

    def compose(self) -> ComposeResult:
        yield Label("✏️ Edit Account")
        yield Label("Account Label:")
        yield Input(
            placeholder="Account label", id="label-input", value=self.label_value
        )
        yield Label("Address Book:")
        yield Horizontal(
            Button("Shared", id="shared-button"),
            Button("Private", id="private-button"),
        )
        yield Label(id="address-book-status")
        yield Horizontal(
            Button("✓ Save", id="save-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_mount(self) -> None:
        self._update_address_book_status()

    def _update_address_book_status(self):
        status = cast(Label, self.query_one("#address-book-status"))
        if self.address_book_shared_value:
            status.update("Current: Shared address book")
        else:
            status.update("Current: Private address book")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "shared-button":
            self.address_book_shared_value = True
            self._update_address_book_status()
        elif event.button.id == "private-button":
            self.address_book_shared_value = False
            self._update_address_book_status()
        elif event.button.id == "save-button":
            label_input = cast(Input, self.query_one("#label-input"))
            label = label_input.value.strip()
            self.post_message(
                self.EditAccountSubmitted(
                    index=self.index,
                    label=label,
                    address_book_shared=self.address_book_shared_value,
                )
            )
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class EditAccountSubmitted(Message):
        def __init__(self, index: int, label: str, address_book_shared: bool):
            super().__init__()
            self.index = index
            self.label = label
            self.address_book_shared = address_book_shared


class DeleteAccountConfirmScreen(BaseModalScreen):
    def __init__(self, index: int, label: str, address: str):
        super().__init__()
        self.index = index
        self.label = label
        self.address = address

    def compose(self) -> ComposeResult:
        yield Label("🗑️ Delete Account")
        yield Label(f"Account: {self.label}")
        yield Label(f"Address: {self.address}")
        yield Label("⚠️ This action cannot be undone!")
        yield Label("The account will be removed from this wallet.")
        yield Horizontal(
            Button("🗑️ Delete", id="delete-button", variant="error"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "delete-button":
            self.post_message(self.DeleteConfirmed(index=self.index))
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class DeleteConfirmed(Message):
        def __init__(self, index: int):
            super().__init__()
            self.index = index


class QRScannerScreen(BaseModalScreen):
    def __init__(self):
        super().__init__()
        self._scanner = None
        self._scanned = False

    def compose(self) -> ComposeResult:
        yield Label("📷 Scan QR Code")
        yield Label("Point your camera at a Symbol address or transaction QR code")
        yield Static("", id="scanner-status")
        yield Static("", id="scanner-preview")
        yield Horizontal(
            Button("📷 Start Scanner", id="start-scanner-button", variant="primary"),
            Button("📋 Paste from Clipboard", id="paste-button"),
            Button("❌ Cancel", id="cancel-button"),
        )

    def on_mount(self) -> None:
        self._update_status("Ready to scan. Click 'Start Scanner' to begin.")

    def _update_status(self, text: str) -> None:
        try:
            status = cast(Static, self.query_one("#scanner-status"))
            status.update(text)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-scanner-button":
            self._start_scanning()
        elif event.button.id == "paste-button":
            self._paste_from_clipboard()
        elif event.button.id == "cancel-button":
            self._stop_scanning()
            self.app.pop_screen()

    def _start_scanning(self) -> None:
        try:
            from src.qr_scanner import QRScanner, scan_qr_from_camera

            scanner = QRScanner()
            if not scanner.is_camera_available():
                self._update_status(
                    "[red]No camera available. Try pasting from clipboard.[/red]"
                )
                return

            self._update_status("[yellow]Scanning... Point camera at QR code[/yellow]")
            self._scanner = scan_qr_from_camera(
                on_scan=self._on_qr_scanned, on_error=self._on_scan_error
            )
        except ImportError as e:
            self._update_status(f"[red]Scanner libraries not installed: {e}[/red]")
        except Exception as e:
            self._update_status(f"[red]Failed to start scanner: {e}[/red]")

    def _stop_scanning(self) -> None:
        if self._scanner is not None:
            try:
                self._scanner.stop_scanning()
            except Exception:
                pass
            self._scanner = None

    def _on_qr_scanned(self, data) -> None:
        if self._scanned:
            return
        self._scanned = True
        self._stop_scanning()

        def post_result():
            self.post_message(self.QRCodeScanned(data=data))
            self.app.pop_screen()

        self.app.call_from_thread(post_result)

    def _on_scan_error(self, error: str) -> None:
        def update():
            self._update_status(f"[red]Error: {error}[/red]")

        self.app.call_from_thread(update)

    def _paste_from_clipboard(self) -> None:
        try:
            import pyperclip

            text = pyperclip.paste()
            if text:
                self._process_qr_text(text)
            else:
                self._update_status("[yellow]Clipboard is empty[/yellow]")
        except Exception as e:
            self._update_status(f"[red]Failed to read clipboard: {e}[/red]")

    def _process_qr_text(self, text: str) -> None:
        from src.qr_scanner import QRScanner

        data = QRScanner.parse_symbol_qr(text)
        self.post_message(self.QRCodeScanned(data=data))
        self.app.pop_screen()

    def on_unmount(self) -> None:
        self._stop_scanning()

    class QRCodeScanned(Message):
        def __init__(self, data):
            super().__init__()
            self.data = data
