"""Account management modal screens for Symbol Quick Wallet."""

import logging
from typing import Protocol, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.coordinate import Coordinate
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

logger = logging.getLogger(__name__)


class AppWithWalletOps(Protocol):
    wallet: "WalletLike"

    def unlock_wallet(self, password: str, screen: object) -> bool: ...

    def dump_screen_stack(self, context: str = "") -> None: ...


class WalletLike(Protocol):
    def get_mosaic_name(self, mosaic_id: int) -> str: ...


class BaseModalScreen(ModalScreen):
    """Base modal screen with common key bindings."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("tab", "action_focus_next", "Next"),
        ("shift+tab", "action_focus_previous", "Previous"),
    ]


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
        if event.input.id == "password-input":
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
        self.action = action

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
            self.action = action


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
        table.cursor_coordinate = Coordinate(self.current_index, 0)

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
            from src.shared.qr_scanner import QRScanner, scan_qr_from_camera

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
        from src.shared.qr_scanner import QRScanner

        data = QRScanner.parse_symbol_qr(text)
        self.post_message(self.QRCodeScanned(data=data))
        self.app.pop_screen()

    def on_unmount(self) -> None:
        self._stop_scanning()

    class QRCodeScanned(Message):
        def __init__(self, data):
            super().__init__()
            self.data = data
