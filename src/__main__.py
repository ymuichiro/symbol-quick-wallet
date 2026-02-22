"""Main application entry point for Symbol Quick Wallet."""

import logging
import threading
import traceback
from pathlib import Path
from typing import cast

# Create log directory if it doesn't exist
log_dir = Path.home() / ".symbol-quick-wallet"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "wallet.log"

# Configure logging - only write to file, not to stdout
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode="w"),
    ],
    force=True,
)

logger = logging.getLogger(__name__)

# Log startup
logger.info("Logging system initialized")
logger.info(f"Log file: {log_file}")

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    Tab,
    Tabs,
)

from src.screens import (
    CommandSelectorScreen,
    FirstRunImportWalletScreen,
    FirstRunSetupScreen,
    HarvestingLinkScreen,
    HarvestingUnlinkScreen,
    ImportWalletScreen,
    LoadingScreen,
    NetworkSelectorScreen,
    PasswordScreen,
    QRCodeScreen,
    SetupPasswordScreen,
    TransactionResultScreen,
    TransactionStatusScreen,
)
from src.features.transfer.handlers import TransferHandlersMixin
from src.features.address_book.handlers import AddressBookHandlersMixin
from src.features.account.handlers import AccountHandlersMixin
from src.features.mosaic.handlers import MosaicHandlersMixin
from src.shared.transaction_template import TemplateStorage
from src.shared.transaction_queue import TransactionQueue
from src.shared.connection_state import (
    ConnectionMonitor,
    ConnectionMonitorConfig,
    ConnectionState,
    get_connection_state_message,
)
from src.shared.network import NetworkError, NetworkErrorType
from src.shared.protocols import WalletProtocol
from src.shared.styles import CSS
from src.transaction import TransactionManager
from src.wallet import Wallet
from src.shared.clipboard import copy_text


class WalletApp(
    TransferHandlersMixin,
    AddressBookHandlersMixin,
    AccountHandlersMixin,
    MosaicHandlersMixin,
    App,
):
    CSS = CSS
    TITLE = "Symbol Quick Wallet"

    BINDINGS = [
        ("/", "show_command_selector", "Command"),
        ("q", "quit", "Quit"),
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_previous", "Previous"),
    ]

    password_retry_count = 0
    is_authenticated = False
    _transfer_loading_active = False
    _transfer_loading_step = 0
    _transfer_loading_timer = None
    _network_loading_active = False
    _network_loading_step = 0
    _network_loading_timer = None
    _network_loading_widget = None
    _loading_screen: LoadingScreen | None = None
    _connection_monitor: ConnectionMonitor | None = None
    _previous_connection_state: ConnectionState = ConnectionState.UNKNOWN
    _tx_queue: TransactionQueue | None = None
    _template_storage: TemplateStorage | None = None
    _status_screen: TransactionStatusScreen | None = None
    wallet: WalletProtocol

    def _format_network_error(self, error: Exception) -> str:
        """Format a network error with meaningful user-friendly message."""
        if isinstance(error, NetworkError):
            if error.error_type == NetworkErrorType.TIMEOUT:
                return f"Connection timeout. The node at {self.wallet.node_url} is not responding. Please try again or switch to a different node."
            elif error.error_type == NetworkErrorType.CONNECTION_ERROR:
                return f"Cannot connect to node. Please check your internet connection and verify the node URL: {self.wallet.node_url}"
            elif error.error_type == NetworkErrorType.HTTP_ERROR:
                status_info = (
                    f" (HTTP {error.status_code})" if error.status_code else ""
                )
                return f"Server error{status_info}: {error.message}"
            else:
                return f"Network error: {error.message}"
        return f"Error: {str(error)}"

    def _start_network_loading(self, widget: Static, base_text: str) -> None:
        """Start a loading animation on a widget."""
        self._network_loading_active = True
        self._network_loading_step = 0
        self._network_loading_widget = widget
        frames = ["|", "/", "-", "\\"]
        widget.update(f"[yellow]{base_text} {frames[0]}[/yellow]")

        def tick() -> None:
            if not self._network_loading_active:
                return
            self._network_loading_step = (self._network_loading_step + 1) % len(frames)
            frame = frames[self._network_loading_step]
            if self._network_loading_widget:
                self._network_loading_widget.update(
                    f"[yellow]{base_text} {frame}[/yellow]"
                )

        if self._network_loading_timer:
            try:
                self._network_loading_timer.stop()
            except Exception:
                pass
        self._network_loading_timer = self.set_interval(0.15, tick)

    def _stop_network_loading(self) -> None:
        """Stop the loading animation."""
        self._network_loading_active = False
        if self._network_loading_timer:
            try:
                self._network_loading_timer.stop()
            except Exception:
                pass
            self._network_loading_timer = None
        self._network_loading_widget = None

    def action_show_command_selector(self) -> None:
        self.show_command_selector()

    def show_command_selector(self) -> None:
        def on_select(command: str):
            self.execute_command(command)

        self.push_screen(CommandSelectorScreen(on_select))

    def on_key(self, event) -> None:
        if event.key == "/":
            self.show_command_selector()

    def on_mount(self) -> None:
        """Handle application mount."""
        logger.info("=" * 80)
        logger.info("[on_mount] ========== APPLICATION MOUNTING STARTED ==========")
        logger.info("=" * 80)
        logger.info(f"[on_mount] is_authenticated={self.is_authenticated}")
        logger.info(f"[on_mount] password_retry_count={self.password_retry_count}")

        logger.info("[on_mount] Creating Wallet instance")
        self.wallet = Wallet()
        logger.info(f"[on_mount] Wallet created, wallet_dir={self.wallet.wallet_dir}")
        logger.info(f"[on_mount] Wallet file path: {self.wallet.wallet_file}")
        logger.info(
            f"[on_mount] Wallet file exists: {self.wallet.wallet_file.exists()}"
        )

        self.mosaics = []
        logger.info(f"[on_mount] Initialized mosaics list: {len(self.mosaics)} items")

        self._tx_queue = TransactionQueue(self.wallet.wallet_dir)
        logger.info(
            f"[on_mount] Transaction queue initialized with {self._tx_queue.count()} items"
        )

        self._template_storage = TemplateStorage(self.wallet.wallet_dir)
        logger.info(
            f"[on_mount] Template storage initialized with {self._template_storage.count()} templates"
        )

        logger.info("[on_mount] Checking if first run")
        is_first_run = self.wallet.is_first_run()
        logger.info(f"[on_mount] is_first_run={is_first_run}")

        logger.info("[on_mount] Checking wallet validity")
        has_valid_wallet = self.wallet.has_wallet()
        logger.info(f"[on_mount] has_valid_wallet={has_valid_wallet}")

        if not is_first_run:
            logger.info("=" * 80)
            logger.info("[on_mount] WALLET EXISTS - PASSWORD AUTHENTICATION REQUIRED")
            logger.info("=" * 80)
            logger.info(f"[on_mount] Wallet file path: {self.wallet.wallet_file}")
            logger.info("[on_mount] Pushing PasswordScreen")
            logger.info(
                f"[on_mount] is_authenticated before password: {self.is_authenticated}"
            )
            self.push_screen(
                PasswordScreen(title="🔐 Unlock Wallet", confirm_button_text="Unlock")
            )
            logger.info("[on_mount] PasswordScreen pushed successfully")
            logger.info(f"[on_mount] Screen stack size: {len(self.screen_stack)}")
        else:
            logger.info("=" * 80)
            logger.info("[on_mount] FIRST RUN - SHOWING NETWORK SELECTOR")
            logger.info("=" * 80)
            logger.info("[on_mount] Pushing NetworkSelectorScreen")
            self.push_screen(NetworkSelectorScreen())
            logger.info("[on_mount] NetworkSelectorScreen pushed successfully")

        logger.info("[on_mount] Hiding all tabs")
        self.hide_all_tabs()
        logger.info("[on_mount] All tabs hidden")

        logger.info("[on_mount] Hiding tabs control")
        self.tabs.display = "none"
        logger.info(f"[on_mount] Tabs control display set to: {self.tabs.display}")

        logger.info("[on_mount] ========== APPLICATION MOUNTING COMPLETED ==========")
        logger.info("=" * 80)
        self.set_focus(None)

    def on_unmount(self) -> None:
        self._stop_connection_monitoring()

    def unlock_wallet(self, password: str, screen) -> bool:
        """Unlock wallet directly from password screen.

        Returns:
            bool: True if unlock succeeded, False if it failed
        """
        logger.info("")
        logger.info("=" * 80)
        logger.info("[unlock_wallet] ========== DIRECT UNLOCK WALLET CALLED ==========")
        logger.info("=" * 80)
        logger.info(f"[unlock_wallet] Password length: {len(password)}")
        logger.info(
            f"[unlock_wallet] Current is_authenticated: {self.is_authenticated}"
        )

        try:
            logger.info("[unlock_wallet] Setting password and loading accounts")
            self.wallet.password = password
            accounts = self.wallet.get_accounts()
            if accounts:
                logger.info(
                    f"[unlock_wallet] Found {len(accounts)} accounts, loading current"
                )
                self.wallet.load_current_account()
            else:
                logger.info(
                    "[unlock_wallet] No accounts in registry, loading from legacy wallet"
                )
                self.wallet.load_wallet_from_storage(password)
            logger.info("[unlock_wallet] Wallet loaded successfully")
            self.is_authenticated = True

            logger.info("[unlock_wallet] Hiding all tabs and showing loading screen")
            self.hide_all_tabs()
            self._loading_screen = LoadingScreen(
                "Loading wallet data...", show_progress=True
            )
            self.push_screen(self._loading_screen)

            def worker() -> None:
                try:
                    self._async_update_wallet_data()
                    self.call_from_thread(self._on_unlock_data_loaded, None)
                except Exception as e:
                    self.call_from_thread(self._on_unlock_data_loaded, e)

            threading.Thread(target=worker, daemon=True).start()

            logger.info("[unlock_wallet] ========== UNLOCK WALLET SUCCESS ==========")
            logger.info("")

            return True

        except Exception as e:
            logger.error(f"[unlock_wallet] Exception: {str(e)}", exc_info=True)
            error_msg = str(e)
            if "Invalid password" in error_msg:
                self.notify(f"Invalid password: {error_msg}", severity="error")
            else:
                self.notify(f"Failed to unlock wallet: {error_msg}", severity="error")
            logger.info("[unlock_wallet] Password screen remains open for retry")
            logger.info("")

            return False

    def _async_update_wallet_data(self) -> None:
        """Update wallet data in background thread."""
        self.update_dashboard()
        self.update_address_book()
        self.update_settings()
        self.update_mosaics_table()

    def _on_unlock_data_loaded(self, error: Exception | None) -> None:
        """Handle completion of async wallet data loading."""
        if self._loading_screen:
            try:
                self.app.pop_screen()
            except Exception:
                pass
            self._loading_screen = None

        if error:
            error_msg = self._format_network_error(error)
            self.notify(f"Error loading wallet data: {error_msg}", severity="warning")

        self.query_one("#dashboard-tab").display = "block"
        self.tabs.display = "block"
        self.action_focus_next()
        self.password_retry_count = 0

        current_account = self.wallet.get_current_account()
        label = current_account.label if current_account else "Wallet"
        self.notify(f"{label} unlocked successfully!", severity="information")

        self._start_connection_monitoring()

    def _start_connection_monitoring(self) -> None:
        if self._connection_monitor:
            return

        def on_state_change(
            old_state: ConnectionState,
            new_state: ConnectionState,
            status,
        ) -> None:
            self._handle_connection_state_change(old_state, new_state, status)

        config = ConnectionMonitorConfig(
            check_interval_seconds=30.0,
            failure_threshold=2,
            recovery_threshold=1,
        )
        self._connection_monitor = ConnectionMonitor(
            node_url=self.wallet.node_url,
            config=config,
            on_state_change=on_state_change,
        )
        self._connection_monitor.start()
        logger.info("Connection monitoring started for node: %s", self.wallet.node_url)

    def _handle_connection_state_change(
        self,
        old_state: ConnectionState,
        new_state: ConnectionState,
        status,
    ) -> None:
        if old_state == new_state:
            return

        self._previous_connection_state = new_state
        title, message = get_connection_state_message(new_state)

        logger.info(
            "Connection state changed: %s -> %s",
            old_state.value,
            new_state.value,
        )

        try:
            if new_state == ConnectionState.ONLINE:
                self.call_from_thread(
                    self.notify,
                    f"{title}: {message}",
                    severity="information",
                    timeout=5,
                )
                self.call_from_thread(self._update_connection_status_display)
            elif new_state == ConnectionState.OFFLINE:
                self.call_from_thread(
                    self.notify,
                    f"{title}: {message}",
                    severity="error",
                    timeout=10,
                )
                self.call_from_thread(self._update_connection_status_display)
            elif new_state == ConnectionState.NODE_UNREACHABLE:
                self.call_from_thread(
                    self.notify,
                    f"{title}: {message}",
                    severity="warning",
                    timeout=8,
                )
                self.call_from_thread(self._update_connection_status_display)
        except Exception as e:
            logger.error("Error handling connection state change: %s", e)

    def _update_connection_status_display(self) -> None:
        try:
            status_widget = cast(Static, self.query_one("#connection-status"))
            if self._connection_monitor is None:
                return

            status = self._connection_monitor.status
            if status.state == ConnectionState.ONLINE:
                status_widget.update("[green]● Online[/green]")
            elif status.state == ConnectionState.OFFLINE:
                status_widget.update("[red]● Offline[/red]")
            elif status.state == ConnectionState.NODE_UNREACHABLE:
                status_widget.update("[yellow]● Node Unreachable[/yellow]")
            else:
                status_widget.update("[dim]● Unknown[/dim]")
        except Exception as e:
            logger.debug("Could not update connection status display: %s", e)

    def _stop_connection_monitoring(self) -> None:
        if self._connection_monitor:
            self._connection_monitor.stop()
            self._connection_monitor = None
            logger.info("Connection monitoring stopped")

    def on_password_dialog_submitted(self, event):
        """Handle password dialog submission."""
        self.dump_screen_stack("on_password_dialog_submitted START")

        logger.info(
            f"[on_password_dialog_submitted] Event has screen: {hasattr(event, 'screen')}"
        )
        if hasattr(event, "screen") and event.screen:
            logger.info(
                f"[on_password_dialog_submitted] Event screen: {type(event.screen)}"
            )

        logger.info("")
        logger.info("=" * 80)
        logger.info(
            "[on_password_dialog_submitted] ========== PASSWORD DIALOG SUBMITTED =========="
        )
        logger.info("=" * 80)
        logger.info(f"[on_password_dialog_submitted] Event type: {type(event)}")
        logger.info(
            f"[on_password_dialog_submitted] Event password length: {len(event.password) if event.password else 0}"
        )
        logger.info(
            f"[on_password_dialog_submitted] Event screen_type: {getattr(event, 'screen_type', 'N/A')}"
        )
        logger.info(
            f"[on_password_dialog_submitted] Current is_authenticated: {self.is_authenticated}"
        )
        logger.info(
            f"[on_password_dialog_submitted] Current password_retry_count: {self.password_retry_count}"
        )
        logger.info(
            f"[on_password_dialog_submitted] Screen stack size: {len(self.screen_stack)}"
        )
        logger.info(
            f"[on_password_dialog_submitted] Active screen: {type(self.screen)}"
        )

        if not event.password:
            logger.warning(
                "[on_password_dialog_submitted] ERROR: Empty password provided"
            )
            logger.info("[on_password_dialog_submitted] Showing error notification")
            self.notify("Password cannot be empty", severity="error")
            logger.info("[on_password_dialog_submitted] Pushing PasswordScreen again")
            self.push_screen(
                PasswordScreen(title="🔐 Unlock Wallet", confirm_button_text="Unlock")
            )
            logger.info(
                "[on_password_dialog_submitted] PasswordScreen pushed, returning"
            )
            logger.info("")
            return

        logger.info("")
        logger.info(
            "[on_password_dialog_submitted] ========== ATTEMPTING TO LOAD WALLET =========="
        )
        logger.info("")

        try:
            logger.info(
                "[on_password_dialog_submitted] Step 1: Calling wallet.load_wallet_from_storage()"
            )
            logger.info(
                f"[on_password_dialog_submitted] Password length for loading: {len(event.password)}"
            )
            self.wallet.load_wallet_from_storage(event.password)
            logger.info(
                "[on_password_dialog_submitted] Step 1: Wallet loaded successfully"
            )

            logger.info(
                "[on_password_dialog_submitted] Step 2: Setting is_authenticated = True"
            )
            self.is_authenticated = True
            logger.info(
                f"[on_password_dialog_submitted] is_authenticated now: {self.is_authenticated}"
            )

            logger.info(
                "[on_password_dialog_submitted] Step 3: Calling update_dashboard()"
            )
            try:
                self.update_dashboard()
                logger.info(
                    "[on_password_dialog_submitted] Step 3: Dashboard updated successfully"
                )
            except Exception as e:
                logger.error(
                    f"[on_password_dialog_submitted] Step 3: Dashboard update FAILED: {str(e)}",
                    exc_info=True,
                )

            logger.info(
                "[on_password_dialog_submitted] Step 4: Calling update_address_book()"
            )
            try:
                self.update_address_book()
                logger.info(
                    "[on_password_dialog_submitted] Step 4: Address book updated successfully"
                )
            except Exception as e:
                logger.error(
                    f"[on_password_dialog_submitted] Step 4: Address book update FAILED: {str(e)}",
                    exc_info=True,
                )

            logger.info(
                "[on_password_dialog_submitted] Step 5: Calling update_settings()"
            )
            try:
                self.update_settings()
                logger.info(
                    "[on_password_dialog_submitted] Step 5: Settings updated successfully"
                )
            except Exception as e:
                logger.error(
                    f"[on_password_dialog_submitted] Step 5: Settings update FAILED: {str(e)}",
                    exc_info=True,
                )

            logger.info(
                "[on_password_dialog_submitted] Step 6: Calling update_mosaics_table()"
            )
            try:
                self.update_mosaics_table()
                logger.info(
                    "[on_password_dialog_submitted] Step 6: Mosaics table updated successfully"
                )
            except Exception as e:
                logger.error(
                    f"[on_password_dialog_submitted] Step 6: Mosaics table update FAILED: {str(e)}",
                    exc_info=True,
                )

            logger.info("")
            logger.info("[on_password_dialog_submitted] Step 7: Managing UI display")
            logger.info(
                "[on_password_dialog_submitted] Step 7.1: Calling hide_all_tabs()"
            )
            self.hide_all_tabs()
            logger.info("[on_password_dialog_submitted] Step 7.1: All tabs hidden")

            logger.info(
                "[on_password_dialog_submitted] Step 7.2: Showing dashboard-tab"
            )
            dashboard_tab = self.query_one("#dashboard-tab")
            dashboard_tab.display = "block"
            logger.info(
                f"[on_password_dialog_submitted] Step 7.2: dashboard-tab display set to: {dashboard_tab.display}"
            )

            logger.info("[on_password_dialog_submitted] Step 7.3: Showing tabs control")
            self.tabs.display = "block"
            logger.info(
                f"[on_password_dialog_submitted] Step 7.3: Tabs display set to: {self.tabs.display}"
            )

            logger.info(
                "[on_password_dialog_submitted] Step 7.4: Setting focus to next widget"
            )
            self.action_focus_next()
            logger.info("[on_password_dialog_submitted] Step 7.4: Focus set")

            logger.info(
                "[on_password_dialog_submitted] Step 8: Resetting password_retry_count to 0"
            )
            self.password_retry_count = 0
            logger.info(
                f"[on_password_dialog_submitted] password_retry_count now: {self.password_retry_count}"
            )

            logger.info("")
            logger.info(
                "[on_password_dialog_submitted] Step 9: Showing success notification"
            )
            self.notify("Wallet unlocked successfully!", severity="information")
            logger.info("[on_password_dialog_submitted] Success notification shown")

            logger.info("")
            logger.info(
                "[on_password_dialog_submitted] ========== PASSWORD AUTHENTICATION SUCCESS =========="
            )
            logger.info("=" * 80)
            logger.info("")
            logger.info("[on_password_dialog_submitted] Popping password screen")
            if hasattr(event, "screen") and event.screen:
                self.pop_screen()
                logger.info(
                    "[on_password_dialog_submitted] Password screen popped successfully"
                )
            else:
                logger.warning("[on_password_dialog_submitted] No screen to pop")
            logger.info("")

        except Exception as e:
            logger.info("")
            logger.error("=" * 80)
            logger.error(
                "[on_password_dialog_submitted] ========== EXCEPTION CAUGHT =========="
            )
            logger.error("=" * 80)

            self.password_retry_count += 1
            logger.error(
                f"[on_password_dialog_submitted] Exception type: {type(e).__name__}"
            )
            logger.error(f"[on_password_dialog_submitted] Exception message: {str(e)}")
            logger.error(
                f"[on_password_dialog_submitted] password_retry_count incremented to: {self.password_retry_count}"
            )
            logger.error("[on_password_dialog_submitted] Full traceback:")
            logger.error(traceback.format_exc())
            logger.error("=" * 80)

            error_msg = str(e)
            logger.info("[on_password_dialog_submitted] Showing error notification")
            if "Invalid password" in error_msg:
                logger.info(
                    f"[on_password_dialog_submitted] Error is invalid password: {error_msg}"
                )
                self.notify(f"Invalid password: {error_msg}", severity="error")
            else:
                logger.info(f"[on_password_dialog_submitted] Error is: {error_msg}")
                self.notify(f"Failed to unlock wallet: {error_msg}", severity="error")

            logger.info("")
            logger.error(
                "[on_password_dialog_submitted] ========== CALLING app.exit() =========="
            )
            self.dump_screen_stack("on_password_dialog_submitted BEFORE app.exit()")
            logger.error("[on_password_dialog_submitted] About to call self.app.exit()")
            logger.error("=" * 80)

            self.app.exit()

            self.dump_screen_stack("on_password_dialog_submitted AFTER app.exit()")
            logger.error(
                "[on_password_dialog_submitted] app.exit() called successfully"
            )
            logger.error(
                "[on_password_dialog_submitted] ========== app.exit() COMPLETED =========="
            )
            logger.error("")

    def on_setup_password_submitted(self, event):
        """Handle setup password submission."""
        logger.info(
            f"[on_setup_password_submitted] Setup password submitted, password={event.password}"
        )
        self.wallet.password = event.password
        logger.info(
            "[on_setup_password_submitted] Wallet password set, pushing FirstRunSetupScreen"
        )
        self.push_screen(FirstRunSetupScreen(self.wallet.network_name))
        logger.info("[on_setup_password_submitted] FirstRunSetupScreen pushed")

    def on_tabs_tab_activated(self, event) -> None:
        """Handle tab activation."""
        logger.info(
            f"[on_tabs_tab_activated] Tab activated: {event.tab.id if event.tab else 'None'}, is_authenticated={self.is_authenticated}"
        )
        if not self.is_authenticated:
            logger.info(
                "[on_tabs_tab_activated] Not authenticated, ignoring tab activation"
            )
            return
        if not event.tab:
            return
        tab_id = event.tab.id
        tab_name = tab_id.replace("-tab-btn", "").replace("-", "_")
        logger.info(f"[on_tabs_tab_activated] Switching to tab: {tab_name}")
        self.action_switch_tab(tab_name)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("[dim]● Checking...[/dim]", id="connection-status")
        self.tabs = Tabs(
            Tab("Dashboard", id="dashboard-tab-btn"),
            Tab("Transfer", id="transfer-tab-btn"),
            Tab("Address Book", id="address-book-tab-btn"),
            Tab("History", id="history-tab-btn"),
        )
        yield self.tabs

        with Container(id="dashboard-tab"):
            yield Label("📊 Dashboard", id="dashboard-title")
            yield Button("Loading...", id="wallet-info-button", variant="default")
            yield Static(id="harvesting-status")
            yield Label("Balance:")
            yield DataTable(id="balance-table")
            yield Button("🔄 Refresh", id="refresh-dashboard-button")

        with Container(id="transfer-tab"):
            yield Label("📤 Transfer", id="transfer-title")
            yield Static(
                "Send XYM / mosaics to a recipient address. Add at least one mosaic amount in micro-units.",
                id="transfer-helper",
            )
            yield Label("Recipient Address")
            yield Input(
                placeholder="T... (Symbol address)",
                id="recipient-input",
            )
            yield Label("Message (optional)")
            yield Input(placeholder="Plain text message", id="message-input")
            yield Label("Selected Mosaics", id="selected-mosaics-title")
            yield DataTable(id="mosaics-table")
            yield Horizontal(
                Button("Add [+]", id="add-mosaic-button"),
                Button("Remove [-]", id="remove-mosaic-button"),
                id="mosaic-actions-row",
            )
            yield Horizontal(
                Button("📒 Select Address", id="select-address-button"),
                Button("📷 Scan QR", id="scan-qr-button"),
                Button("📤 Send Now", id="send-button", variant="primary"),
                id="transfer-actions-row",
            )
            yield Horizontal(
                Button("➕ Add to Queue", id="add-to-queue-button"),
                Button("📋 View Queue", id="view-queue-button"),
                id="queue-actions-row",
            )
            yield Horizontal(
                Button("💾 Save Template", id="save-template-button"),
                Button("📋 Templates", id="view-templates-button"),
                id="template-actions-row",
            )
            yield Static(id="transfer-result")

        with Container(id="address-book-tab"):
            yield Label("📒 Address Book", id="address-book-title")
            yield DataTable(id="address-book-table")
            yield Horizontal(
                Button("➕ Add", id="add-address-button"),
                Button("🗑️ Remove", id="remove-address-button"),
                Button("📋 View All", id="view-address-book-button"),
            )

        with Container(id="history-tab"):
            yield Label("📜 Transaction History", id="history-title")
            yield DataTable(id="history-table")
            yield Button("🔄 Refresh", id="refresh-history-button")

        yield Container(
            Static(id="command-suggestions"),
            id="command-suggestions-container",
            classes="hidden",
        )

        yield Input(
            placeholder="Type / to search commands (e.g., /dashboard, /d)",
            id="command-input",
            classes="hidden",
        )

        yield Footer()

    def on_input_changed(self, event) -> None:
        if event.input.id == "command-input":
            self.update_command_suggestions(event.value)

    def update_command_suggestions(self, text: str) -> None:
        text_lower = text.lower()

        if text == "/":
            suggestions_text = "\n".join(
                [
                    "  /dashboard - 📊 Dashboard",
                    "  /transfer - 📤 Transfer",
                    "  /address_book - 📒 Address Book",
                    "  /history - 📜 History",
                    "  /accounts - 👤 Account Manager",
                    "  /templates - 📋 Transaction Templates",
                    "  /show_config - ⚙️ Show Config",
                    "  /network_testnet - 🌐 Network Testnet",
                    "  /network_mainnet - 🌐 Network Mainnet",
                    "  /node_default - 🔄 Reset Default Node",
                ]
            )
        elif text_lower.startswith("/"):
            command_part = text_lower[1:]

            commands = [
                ("📊 Dashboard", "dashboard"),
                ("📤 Transfer", "transfer"),
                ("📒 Address Book", "address_book"),
                ("📜 History", "history"),
                ("👤 Account Manager", "accounts"),
                ("📋 Transaction Templates", "templates"),
                ("⚙️ Show Config", "show_config"),
                ("🌐 Network Testnet", "network_testnet"),
                ("🌐 Network Mainnet", "network_mainnet"),
                ("🔄 Reset Default Node", "node_default"),
                ("🔌 Test Node Connection", "test_connection"),
                ("🔑 Create Wallet", "create_wallet"),
                ("📥 Import Wallet", "import_wallet"),
                ("🔐 Export Key", "export_key"),
                ("🔑 Import Encrypted Key", "import_encrypted_key"),
                ("📱 Show QR", "show_qr"),
                ("🎨 Create Mosaic", "create_mosaic"),
                ("🔗 Link Harvesting", "link_harvesting"),
                ("🔓 Unlink Harvesting", "unlink_harvesting"),
            ]

            matching_commands = []
            for label, cmd in commands:
                if cmd.startswith(command_part) or label.lower().startswith(
                    command_part
                ):
                    full_cmd = f"/{cmd}"
                    if full_cmd == text_lower:
                        matching_commands.insert(0, (label, cmd, True))
                    else:
                        matching_commands.append((label, cmd, False))

            if not matching_commands:
                suggestions_text = ""
            else:
                suggestions_text = "\n".join(
                    [
                        f"  /{cmd} - {label}" if is_exact else f"  /{cmd} - {label}"
                        for label, cmd, is_exact in matching_commands[:8]
                    ]
                )
        else:
            suggestions_text = ""

        suggestions = cast(Static, self.query_one("#command-suggestions"))
        suggestions.update(suggestions_text)

        suggestions_container = self.query_one("#command-suggestions-container")
        if text.startswith("/"):
            suggestions_container.remove_class("hidden")
        else:
            suggestions_container.add_class("hidden")

    def execute_command(self, command: str) -> None:
        normalized = command.strip().lower()
        if not normalized:
            return

        if normalized.startswith("/"):
            normalized = normalized[1:]

        tab_commands = {
            "d": "dashboard",
            "dashboard": "dashboard",
            "t": "transfer",
            "transfer": "transfer",
            "a": "address_book",
            "address_book": "address_book",
            "h": "history",
            "history": "history",
        }
        if normalized in tab_commands:
            self.action_switch_tab(tab_commands[normalized])
            return

        if normalized == "show_config":
            self.notify(
                f"Network={self.wallet.network_name}, Node={self.wallet.node_url}",
                severity="information",
            )
        elif normalized == "network_testnet":
            self.wallet.network_name = "testnet"
            self.reset_node_url()
            self.wallet._save_config()
            from symbolchain.facade.SymbolFacade import SymbolFacade

            self.wallet.facade = SymbolFacade("testnet")
            self.notify("Network set to testnet", severity="information")
        elif normalized == "network_mainnet":
            self.wallet.network_name = "mainnet"
            self.reset_node_url()
            self.wallet._save_config()
            from symbolchain.facade.SymbolFacade import SymbolFacade

            self.wallet.facade = SymbolFacade("mainnet")
            self.notify("Network set to mainnet", severity="information")
        elif normalized == "node_default":
            self.reset_node_url()
            self.wallet._save_config()
            self.notify(f"Node reset to {self.wallet.node_url}", severity="information")
        elif normalized == "test_connection":
            self.test_node_connection()
        elif normalized == "create_wallet":
            self.create_new_wallet()
        elif normalized == "import_wallet":
            self.show_import_wallet_dialog()
        elif normalized == "export_key":
            self.show_export_key_dialog()
        elif normalized == "import_encrypted_key":
            self.show_import_encrypted_key_dialog()
        elif normalized == "show_qr":
            self.show_qr_code()
        elif normalized == "create_mosaic":
            self.show_create_mosaic_dialog()
        elif normalized == "link_harvesting":
            self.show_link_harvesting_dialog()
        elif normalized == "unlink_harvesting":
            self.show_unlink_harvesting_dialog()
        elif normalized == "accounts":
            self.show_account_manager()
        elif normalized == "templates":
            self.view_templates()
        else:
            self.notify(f"Unknown command: /{normalized}", severity="warning")

    def action_switch_tab(self, tab_name: str) -> None:
        logger.info(f"[action_switch_tab] Switching to tab: {tab_name}")
        if tab_name.startswith("/"):
            tab_name = tab_name[1:]
        shorthand = {
            "d": "dashboard",
            "t": "transfer",
            "a": "address_book",
            "h": "history",
        }
        tab_name = shorthand.get(tab_name, tab_name)
        tab_map = {
            "dashboard": "dashboard-tab",
            "transfer": "transfer-tab",
            "address_book": "address-book-tab",
            "history": "history-tab",
        }
        target_tab = tab_map.get(tab_name)
        if not target_tab:
            logger.warning(f"[action_switch_tab] Unknown tab name: {tab_name}")
            return
        for tab in [
            "dashboard-tab",
            "transfer-tab",
            "address-book-tab",
            "history-tab",
        ]:
            tab_widget = self.query_one(f"#{tab}")
            if tab_widget:
                if tab == target_tab:
                    tab_widget.display = "block"
                    logger.info(f"[action_switch_tab] Showing tab: {tab}")
                else:
                    tab_widget.display = "none"
        if tab_name == "address_book":
            self.update_address_book()
        elif tab_name == "dashboard":
            self.update_dashboard()
        elif tab_name == "history":
            self.update_history()
        logger.info("[action_switch_tab] Tab switch completed")
        self.action_focus_next()

    def action_next_tab(self) -> None:
        tab_btns = [
            "dashboard-tab-btn",
            "transfer-tab-btn",
            "address-book-tab-btn",
            "history-tab-btn",
        ]
        tabs = ["dashboard", "transfer", "address_book", "history"]
        current_tab = self.tabs.active_tab
        if current_tab and hasattr(current_tab, "id"):
            current_id = current_tab.id
            if current_id in tab_btns:
                current_index = tab_btns.index(current_id)
                next_index = (current_index + 1) % len(tab_btns)
                self.action_switch_tab(tabs[next_index])

    def action_previous_tab(self) -> None:
        tab_btns = [
            "dashboard-tab-btn",
            "transfer-tab-btn",
            "address-book-tab-btn",
            "history-tab-btn",
        ]
        tabs = ["dashboard", "transfer", "address_book", "history"]
        current_tab = self.tabs.active_tab
        if current_tab and hasattr(current_tab, "id"):
            current_id = current_tab.id
            if current_id in tab_btns:
                current_index = tab_btns.index(current_id)
                prev_index = (current_index - 1) % len(tab_btns)
                self.action_switch_tab(tabs[prev_index])

    def action_focus_next(self) -> None:
        focusable_widgets = self._get_focusable_widgets()
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
        focusable_widgets = self._get_focusable_widgets()
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

    def _is_widget_visible(self, widget: Widget) -> bool:
        current: object | None = widget
        while current is not None:
            if str(getattr(current, "display", "")) == "none":
                return False
            current = getattr(current, "parent", None)
        return True

    def _get_focusable_widgets(self) -> list[Widget]:
        widgets = list(self.query("Tabs, Button, Input, Select, DataTable"))
        result: list[Widget] = []
        for widget in widgets:
            if not getattr(widget, "can_focus", False):
                continue
            if getattr(widget, "disabled", False):
                continue
            if not self._is_widget_visible(widget):
                continue
            result.append(widget)
        return result

    def hide_all_tabs(self):
        logger.info("")
        logger.info("[hide_all_tabs] ========== HIDING ALL TABS STARTED ==========")
        logger.info(f"[hide_all_tabs] Current tabs display: {self.tabs.display}")

        tab_ids = [
            "#dashboard-tab",
            "#transfer-tab",
            "#address-book-tab",
            "#history-tab",
        ]

        for tab_id in tab_ids:
            logger.info(f"[hide_all_tabs] Processing tab: {tab_id}")
            try:
                tab = self.query_one(tab_id)
                current_display = tab.display
                tab.display = "none"
                logger.info(
                    f"[hide_all_tabs] {tab_id}: {current_display} -> {tab.display}"
                )
            except Exception as e:
                logger.error(
                    f"[hide_all_tabs] ERROR hiding {tab_id}: {e}", exc_info=True
                )

        logger.info(
            f"[hide_all_tabs] All tabs hidden, tabs display: {self.tabs.display}"
        )
        logger.info("[hide_all_tabs] ========== HIDING ALL TABS COMPLETED ==========")
        logger.info("")

    def update_dashboard(self):
        logger.info("")
        logger.info("[update_dashboard] ========== UPDATE DASHBOARD STARTED ==========")
        logger.info(f"[update_dashboard] is_authenticated: {self.is_authenticated}")
        logger.info(f"[update_dashboard] Wallet address: {self.wallet.address}")
        logger.info(
            f"[update_dashboard] Wallet loaded: {self.wallet.address is not None}"
        )

        logger.info("[update_dashboard] Querying dashboard widgets")
        try:
            wallet_info = cast(Button, self.query_one("#wallet-info-button"))
            logger.info("[update_dashboard] wallet-info-button widget found")
        except Exception as e:
            logger.error(
                f"[update_dashboard] ERROR finding wallet-info-button: {e}",
                exc_info=True,
            )
            return

        try:
            harvesting_status = cast(Static, self.query_one("#harvesting-status"))
            logger.info("[update_dashboard] harvesting-status widget found")
        except Exception as e:
            logger.error(
                f"[update_dashboard] ERROR finding harvesting-status: {e}",
                exc_info=True,
            )
            return

        try:
            balance_table = cast(DataTable, self.query_one("#balance-table"))
            logger.info("[update_dashboard] balance-table widget found")
        except Exception as e:
            logger.error(
                f"[update_dashboard] ERROR finding balance-table: {e}", exc_info=True
            )
            return

        logger.info(f"[update_dashboard] Wallet address: {self.wallet.address}")

        if self.wallet.address:
            logger.info("[update_dashboard] Wallet address exists, updating UI")

            logger.info("[update_dashboard] Step 1: Updating wallet-info")
            try:
                current_account = self.wallet.get_current_account()
                label = (
                    current_account.label
                    if current_account and current_account.label
                    else "Account"
                )
                wallet_info.label = f"{label}: {self.wallet.get_address()}"
                logger.info(
                    "[update_dashboard] Step 1: wallet-info updated successfully"
                )
            except Exception as e:
                logger.error(
                    f"[update_dashboard] Step 1: ERROR updating wallet-info: {e}",
                    exc_info=True,
                )

            logger.info("[update_dashboard] Step 2: Updating harvesting-status")
            try:
                harvesting_status_data = self.wallet.get_harvesting_status()
                logger.info(
                    f"[update_dashboard] Harvesting status data: {harvesting_status_data}"
                )

                if harvesting_status_data["is_harvesting"]:
                    logger.info("[update_dashboard] Wallet is harvesting")
                    if harvesting_status_data["is_remote"]:
                        logger.info(
                            "[update_dashboard] Harvesting mode: Remote (Delegated)"
                        )
                        harvesting_status.update(
                            "[green]🔗 Harvesting: Remote (Delegated)[/green]"
                        )
                    else:
                        logger.info(
                            "[update_dashboard] Harvesting mode: Local (Not Delegated)"
                        )
                        harvesting_status.update(
                            "[yellow]🔒 Harvesting: Local (Not Delegated)[/yellow]"
                        )
                else:
                    logger.info("[update_dashboard] Wallet is not harvesting")
                    harvesting_status.update("[red]❌ Harvesting: Not Active[/red]")
                logger.info(
                    "[update_dashboard] Step 2: harvesting-status updated successfully"
                )
            except Exception as e:
                logger.error(
                    f"[update_dashboard] Step 2: ERROR updating harvesting-status: {e}",
                    exc_info=True,
                )
                error_msg = (
                    self._format_network_error(e)
                    if isinstance(e, NetworkError)
                    else str(e)
                )
                harvesting_status.update(
                    f"[red]Harvesting Status: Error - {error_msg}[/red]"
                )

            logger.info("[update_dashboard] Step 3: Updating balance-table")
            try:
                logger.info("[update_dashboard] Getting wallet balance")
                mosaics = self.wallet.get_balance()
                logger.info(f"[update_dashboard] Got {len(mosaics)} mosaics")

                logger.info("[update_dashboard] Clearing balance-table columns")
                balance_table.clear(columns=True)

                logger.info("[update_dashboard] Adding balance-table columns")
                balance_table.add_column("Mosaic", key="mosaic")
                balance_table.add_column("Amount", key="amount")
                balance_table.add_column("Mosaic ID", key="mosaic_id")

                logger.info("[update_dashboard] Adding mosaic rows")
                for m in mosaics:
                    mosaic_id = m.get("id")
                    amount = m.get("amount", 0)
                    mosaic_name = self.wallet.get_mosaic_name(mosaic_id)
                    amount_units = f"{amount / 1_000_000:,.6f}"
                    logger.info(
                        f"[update_dashboard] Adding row: {mosaic_name} = {amount_units}"
                    )
                    mosaic_id_hex = hex(mosaic_id) if mosaic_id is not None else "N/A"
                    balance_table.add_row(mosaic_name, amount_units, mosaic_id_hex)

                logger.info(
                    "[update_dashboard] Step 3: balance-table updated successfully"
                )
            except NetworkError as e:
                logger.error(
                    f"[update_dashboard] Step 3: Network error: {e.message}",
                    exc_info=True,
                )
                balance_table.clear(columns=True)
                balance_table.add_column("Error", key="error")
                balance_table.add_row(self._format_network_error(e))
            except Exception as e:
                logger.error(
                    f"[update_dashboard] Step 3: ERROR updating balance-table: {e}",
                    exc_info=True,
                )
                error_msg = str(e)

                balance_table.clear(columns=True)
                balance_table.add_column("Error", key="error")
                balance_table.add_row(f"Unable to fetch balance: {error_msg}")
        else:
            logger.info(
                "[update_dashboard] No wallet address, showing no wallet loaded message"
            )

            logger.info(
                "[update_dashboard] Step A: Updating wallet-info to show no wallet"
            )
            wallet_info.label = "No wallet loaded. Use slash commands to create/import."

            logger.info("[update_dashboard] Step B: Clearing harvesting-status")
            harvesting_status.update("")

            logger.info(
                "[update_dashboard] Step C: Clearing balance-table and showing message"
            )
            balance_table.clear(columns=True)
            balance_table.add_column("Message", key="message")
            balance_table.add_row("No wallet loaded")

        logger.info(
            "[update_dashboard] ========== UPDATE DASHBOARD COMPLETED =========="
        )
        logger.info("")

    def update_history(self):
        table = cast(DataTable, self.query_one("#history-table"))
        table.clear(columns=True)
        table.add_column("Hash", key="hash")
        table.add_column("Date", key="date")
        table.add_column("Amount", key="amount")
        table.add_column("Direction", key="direction")

        try:
            transactions = self.wallet.get_transaction_history()
            for tx in transactions:
                tx_hash = tx.get("hash") or tx.get("meta", {}).get("hash")
                tx_hash = tx_hash or "unknown"
                tx_date = tx.get("date") or tx.get("transaction", {}).get("deadline")
                tx_date = str(tx_date) if tx_date is not None else "-"
                amount = tx.get("amount")
                if amount is None:
                    mosaics = tx.get("transaction", {}).get("mosaics", [])
                    amount = mosaics[0].get("amount") if mosaics else 0
                if amount is None:
                    amount = 0
                try:
                    amount_value = int(amount)
                except (ValueError, TypeError):
                    amount_value = 0
                direction = tx.get("direction")
                if not direction:
                    recipient = tx.get("transaction", {}).get("recipientAddress")
                    direction = (
                        "incoming"
                        if recipient and str(recipient) == str(self.wallet.address)
                        else "outgoing"
                    )

                table.add_row(
                    f"{tx_hash[:16]}...",
                    tx_date,
                    f"{amount_value / 1_000_000:,.6f} XYM",
                    "Received" if direction == "incoming" else "Sent",
                )
        except NetworkError as e:
            table.add_row("[red]Error[/red]", self._format_network_error(e), "", "")
        except Exception as e:
            table.add_row("[red]Error[/red]", str(e), "", "")

    def update_settings(self):
        # Settings tab has been removed; keep this method as a compatibility no-op.
        logger.info(
            "[update_settings] Settings tab is removed; current config network=%s node=%s",
            self.wallet.network_name,
            self.wallet.node_url,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        logger.info("")
        logger.info("=" * 80)
        logger.info("[on_button_pressed] ========== BUTTON PRESSED ==========")
        logger.info(f"[on_button_pressed] Button ID: {button_id}")
        logger.info(
            f"[on_button_pressed] Button label: {event.button.label if hasattr(event.button, 'label') else 'N/A'}"
        )
        logger.info("=" * 80)

        if button_id == "send-button":
            logger.info("[on_button_pressed] Action: send_transaction")
            self.send_transaction()
        elif button_id == "add-mosaic-button":
            logger.info("[on_button_pressed] Action: add_mosaic")
            self.add_mosaic()
        elif button_id == "remove-mosaic-button":
            logger.info("[on_button_pressed] Action: remove_selected_mosaic")
            self.remove_selected_mosaic()
        elif button_id == "select-address-button":
            logger.info("[on_button_pressed] Action: show_address_book_selector")
            self.show_address_book_selector()
        elif button_id == "add-address-button":
            logger.info("[on_button_pressed] Action: show_add_address_dialog")
            self.show_add_address_dialog()
        elif button_id == "remove-address-button":
            logger.info("[on_button_pressed] Action: remove_selected_address")
            self.remove_selected_address()
        elif button_id == "refresh-history-button":
            logger.info("[on_button_pressed] Action: refresh_history_async")
            self.refresh_history_async()
        elif button_id == "refresh-dashboard-button":
            logger.info("[on_button_pressed] Action: refresh_dashboard_async")
            self.refresh_dashboard_async()
        elif button_id == "view-address-book-button":
            logger.info("[on_button_pressed] Action: show_address_book")
            self.show_address_book()
        elif button_id == "wallet-info-button":
            logger.info("[on_button_pressed] Action: copy_address")
            self.copy_address()
        elif button_id == "add-to-queue-button":
            logger.info("[on_button_pressed] Action: add_to_queue")
            self.add_to_queue()
        elif button_id == "view-queue-button":
            logger.info("[on_button_pressed] Action: view_queue")
            self.view_queue()
        elif button_id == "scan-qr-button":
            logger.info("[on_button_pressed] Action: scan_qr_for_address")
            self.scan_qr_for_address()
        elif button_id == "save-template-button":
            logger.info("[on_button_pressed] Action: save_template")
            self.save_template()
        elif button_id == "view-templates-button":
            logger.info("[on_button_pressed] Action: view_templates")
            self.view_templates()
        else:
            logger.warning(f"[on_button_pressed] Unknown button ID: {button_id}")
        logger.info(
            "[on_button_pressed] ========== BUTTON HANDLER COMPLETED =========="
        )
        logger.info("")

    def copy_to_clipboard_osc52(self, text: str) -> bool:
        result = copy_text(text, prefer_osc52=True)
        return bool(result["success"])

    def copy_address(self):
        """Copy wallet address to clipboard."""
        logger.info("")
        logger.info("=" * 80)
        logger.info("[copy_address] ========== COPY ADDRESS STARTED ==========")
        logger.info("=" * 80)
        logger.info(
            f"[copy_address] Wallet address exists: {self.wallet.address is not None}"
        )
        logger.info(f"[copy_address] Wallet address value: {self.wallet.address}")

        if self.wallet.address:
            logger.info("[copy_address] Wallet address found, attempting to copy")
            copy_result = copy_text(self.wallet.address, prefer_osc52=True)
            if copy_result["success"]:
                method = copy_result["method"]
                logger.info("[copy_address] Address copied using %s", method)
                self.notify("Address copied to clipboard!", severity="information")
            else:
                logger.warning("[copy_address] Clipboard copy failed, showing fallback")
                self.notify(
                    "Clipboard unavailable. Address is shown on screen.",
                    severity="warning",
                )
                self._show_temp_address_display()

            logger.info("[copy_address] ========== COPY ADDRESS COMPLETED ==========")
            logger.info("=" * 80)
            logger.info("")
        else:
            logger.warning("[copy_address] No wallet address available")
            self.notify("No wallet address to copy", severity="warning")

    def _show_temp_address_display(self):
        """Show temporary address display for 10 seconds that won't disappear on click."""
        import threading
        import time

        logger.info("[_show_temp_address_display] Creating temporary address display")

        # Use unique ID to avoid DuplicateIds error when clicking multiple times
        widget_id = f"temp-address-display-{int(time.time() * 1000)}"
        logger.info(f"[_show_temp_address_display] Using widget ID: {widget_id}")

        # Remove any existing temporary displays
        temp_displays = self.query(".temp-address")
        if temp_displays:
            logger.info(
                f"[_show_temp_address_display] Removing {len(temp_displays)} existing temporary displays"
            )
            for display in temp_displays:
                try:
                    display.remove()
                    logger.info(
                        f"[_show_temp_address_display] Removed display: {display.id}"
                    )
                except Exception as e:
                    logger.error(
                        f"[_show_temp_address_display] Error removing display: {e}",
                        exc_info=True,
                    )

        # Create a new Static widget to display the address
        address_display = Static(
            f"[cyan]Address: {self.wallet.address}[/cyan]",
            id=widget_id,
            classes="temp-address",
        )

        # Add it to screen (not as a modal, as part of current screen)
        self.screen.mount(address_display)
        logger.info(
            f"[_show_temp_address_display] Temporary address display mounted with ID: {widget_id}"
        )

        # Remove it after 10 seconds in a separate thread
        def remove_after_delay():
            logger.info(
                f"[_show_temp_address_display] Starting 10-second timer for {widget_id}"
            )
            time.sleep(10)
            logger.info(
                f"[_show_temp_address_display] Timer expired, removing display {widget_id}"
            )

            def remove_in_main_thread():
                try:
                    temp_display = self.query_one(f"#{widget_id}")
                    if temp_display:
                        temp_display.remove()
                        logger.info(
                            f"[_show_temp_address_display] Temporary display {widget_id} removed"
                        )
                except Exception as e:
                    logger.error(
                        f"[_show_temp_address_display] Error removing display {widget_id}: {e}",
                        exc_info=True,
                    )

            # Schedule removal in the main thread
            self.call_from_thread(remove_in_main_thread)

        thread = threading.Thread(target=remove_after_delay, daemon=True)
        thread.start()
        logger.info(
            f"[_show_temp_address_display] Timer thread started for {widget_id}"
        )

    def save_settings(self):
        self.wallet._save_config()
        self.notify("Settings saved", severity="information")

    def reset_node_url(self):
        if self.wallet.network_name == "testnet":
            self.wallet.node_url = "http://sym-test-01.opening-line.jp:3000"
        elif self.wallet.network_name == "mainnet":
            self.wallet.node_url = "http://sym-main-01.opening-line.jp:3000"
        if self._connection_monitor:
            self._connection_monitor.update_node_url(self.wallet.node_url)
        self.notify("Node URL reset to default", severity="information")

    def test_node_connection(self):
        """Test node connection using current configured node URL."""
        node_url = self.wallet.node_url
        if not node_url:
            self.notify("Node URL is empty", severity="error")
            return

        self.notify("Testing connection...", severity="information")

        def worker() -> None:
            try:
                logger.info("Testing node connection: %s", node_url)
                connection_result = self.wallet.test_node_connection(node_url)
                self.call_from_thread(
                    self._on_node_connection_test_finished, connection_result, None
                )
            except Exception as e:
                self.call_from_thread(self._on_node_connection_test_finished, None, e)

        threading.Thread(target=worker, daemon=True).start()

    def _on_node_connection_test_finished(
        self, result: dict | None, error: Exception | None
    ) -> None:
        if error:
            error_msg = (
                self._format_network_error(error)
                if isinstance(error, NetworkError)
                else str(error)
            )
            logger.error("Node connection test failed: %s", error_msg)
            self.notify(f"Connection test failed: {error_msg}", severity="error")
            return

        if result and result.get("healthy"):
            self.notify(
                f"Connection successful: api={result['apiNode']} height={result['networkHeight']}",
                severity="information",
            )
        else:
            api_status = result.get("apiNode", "unknown") if result else "unknown"
            self.notify(
                f"Connection failed: api={api_status}",
                severity="warning",
            )

    def create_new_wallet(self):
        self.wallet.create_wallet()
        self.update_dashboard()

    def show_import_wallet_dialog(self):
        self.push_screen(ImportWalletScreen())

    def show_link_harvesting_dialog(self):
        self.push_screen(HarvestingLinkScreen())

    def show_unlink_harvesting_dialog(self):
        self.push_screen(HarvestingUnlinkScreen())

    def on_transaction_confirm_dialog_submitted(self, event):
        self._submit_transaction_async(event.recipient, event.mosaics, event.message)

    def on_import_wallet_dialog_submitted(self, event):
        try:
            self.wallet.import_wallet(event.private_key)
            self.update_dashboard()
            self.notify("Wallet imported successfully", severity="information")
        except Exception as e:
            self.notify(f"Error: {str(e)}", severity="error")

    def on_harvesting_link_dialog_submitted(self, event):
        try:
            tm = TransactionManager(self.wallet, self.wallet.node_url)
            result = tm.create_sign_and_announce_link_harvesting(
                event.remote_public_key
            )
            self.push_screen(
                TransactionResultScreen(result["hash"], self.wallet.network_name)
            )
            self.notify(
                "Harvesting linked successfully!",
                severity="information",
            )
            self.update_dashboard()
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                error_msg = f"Connection timeout. Node at {self.wallet.node_url} may be unavailable."
            elif "cannot connect" in error_msg.lower():
                error_msg = f"Cannot connect to node. Check your network and node URL: {self.wallet.node_url}"
            elif "http error" in error_msg.lower():
                error_msg = f"Node returned error: {error_msg}"
            self.notify(f"Error linking harvesting: {error_msg}", severity="error")

    def on_harvesting_unlink_dialog_submitted(self, event):
        try:
            tm = TransactionManager(self.wallet, self.wallet.node_url)
            result = tm.create_sign_and_announce_unlink_harvesting()
            self.push_screen(
                TransactionResultScreen(result["hash"], self.wallet.network_name)
            )
            self.notify(
                "Harvesting unlinked successfully!",
                severity="information",
            )
            self.update_dashboard()
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                error_msg = f"Connection timeout. Node at {self.wallet.node_url} may be unavailable."
            elif "cannot connect" in error_msg.lower():
                error_msg = f"Cannot connect to node. Check your network and node URL: {self.wallet.node_url}"
            elif "http error" in error_msg.lower():
                error_msg = f"Node returned error: {error_msg}"
            self.notify(f"Error unlinking harvesting: {error_msg}", severity="error")

    def refresh_dashboard_async(self) -> None:
        """Refresh dashboard with loading indicator."""
        try:
            balance_table = cast(DataTable, self.query_one("#balance-table"))
            self._start_network_loading(
                cast(Static, self.query_one("#harvesting-status")), "Refreshing"
            )
            balance_table.clear(columns=True)
            balance_table.add_column("Status", key="status")
            balance_table.add_row("[yellow]Loading...[/yellow]")
        except Exception:
            pass

        def worker() -> None:
            try:
                self.call_from_thread(self._on_dashboard_refresh_finished, None)
            except Exception as e:
                self.call_from_thread(self._on_dashboard_refresh_finished, e)

        threading.Thread(target=worker, daemon=True).start()

    def _on_dashboard_refresh_finished(self, error: Exception | None) -> None:
        self._stop_network_loading()
        if error:
            self.notify(self._format_network_error(error), severity="error")
        else:
            self.update_dashboard()
            self.notify("Dashboard refreshed", severity="information")

    def refresh_history_async(self) -> None:
        """Refresh history with loading indicator."""
        try:
            table = cast(DataTable, self.query_one("#history-table"))
            table.clear(columns=True)
            table.add_column("Status", key="status")
            table.add_row("[yellow]Loading...[/yellow]")
        except Exception:
            pass

        def worker() -> None:
            try:
                self.call_from_thread(self._on_history_refresh_finished, None)
            except Exception as e:
                self.call_from_thread(self._on_history_refresh_finished, e)

        threading.Thread(target=worker, daemon=True).start()

    def _on_history_refresh_finished(self, error: Exception | None) -> None:
        if error:
            table = cast(DataTable, self.query_one("#history-table"))
            table.clear(columns=True)
            table.add_column("Error", key="error")
            error_msg = (
                self._format_network_error(error)
                if isinstance(error, NetworkError)
                else str(error)
            )
            table.add_row(f"[red]{error_msg}[/red]")
        else:
            self.update_history()

    def show_qr_code(self):
        """Show QR code of wallet address."""
        if self.wallet.address:
            self.push_screen(QRCodeScreen(self.wallet.get_address()))

    def on_network_selector_screen_network_selected(self, event):
        """Handle network selection."""
        logger.info(
            f"[on_network_selector_screen_network_selected] Network selected: {event.network}"
        )
        self.wallet.network_name = event.network
        if event.network == "testnet":
            self.wallet.node_url = "http://sym-test-01.opening-line.jp:3000"
        else:
            self.wallet.node_url = "http://sym-main-01.opening-line.jp:3000"
        self.wallet._save_config()
        logger.info(
            "[on_network_selector_screen_network_selected] Network config saved, popping network selector"
        )
        self.app.pop_screen()
        logger.info(
            "[on_network_selector_screen_network_selected] Network selector popped, pushing SetupPasswordScreen"
        )
        self.push_screen(SetupPasswordScreen())
        logger.info(
            "[on_network_selector_screen_network_selected] SetupPasswordScreen pushed"
        )

    def on_first_run_setup_screen_setup_action(self, event):
        """Handle first run setup action."""
        logger.info(
            f"[on_first_run_setup_screen_setup_action] Setup action received: {event.action}"
        )
        action = event.action
        network = self.wallet.network_name
        from symbolchain.facade.SymbolFacade import SymbolFacade

        self.wallet.facade = SymbolFacade(network)

        if action == "create":
            try:
                logger.info(
                    "[on_first_run_setup_screen_setup_action] Creating new wallet"
                )
                self.wallet.create_wallet()
                logger.info(
                    "[on_first_run_setup_screen_setup_action] Wallet created, calling finish_setup()"
                )
                self.finish_setup()
                logger.info(
                    "[on_first_run_setup_screen_setup_action] finish_setup() completed"
                )
                logger.info(
                    "[on_first_run_setup_screen_setup_action] Popping FirstRunSetupScreen"
                )
                self.app.pop_screen()
                logger.info("New wallet created and encrypted")
            except Exception as e:
                logger.error(f"Failed to create wallet: {str(e)}", exc_info=True)
                self.notify(f"Failed to create wallet: {str(e)}", severity="error")
        elif action == "import":
            logger.info(
                "[on_first_run_setup_screen_setup_action] Importing wallet, pushing FirstRunImportWalletScreen"
            )
            self.app.pop_screen()
            self.push_screen(FirstRunImportWalletScreen(network))

    def on_set_password_dialog_submitted(self, event):
        """Handle set password dialog submission."""
        network = (
            event.screen.network
            if hasattr(event.screen, "network")
            else self.wallet.network_name
        )
        self.wallet.network_name = network
        if network == "testnet":
            self.wallet.node_url = "http://sym-test-01.opening-line.jp:3000"
        else:
            self.wallet.node_url = "http://sym-main-01.opening-line.jp:3000"
        self.wallet._save_config()
        from symbolchain.facade.SymbolFacade import SymbolFacade

        self.wallet.facade = SymbolFacade(network)
        self.wallet.password = event.password

        if event.action == "create":
            try:
                self.wallet.create_wallet()
                self.finish_setup()
                logger.info("New wallet created and encrypted")
            except Exception as e:
                logger.error(f"Failed to create wallet: {str(e)}")
                self.notify(f"Failed to create wallet: {str(e)}", severity="error")
        elif event.action == "import":
            self.push_screen(FirstRunImportWalletScreen(network))

    def on_first_run_import_wallet_dialog_submitted(self, event):
        """Handle first run import wallet."""
        try:
            network = (
                event.screen.network
                if hasattr(event.screen, "network")
                else self.wallet.network_name
            )
            self.wallet.network_name = network
            if network == "testnet":
                self.wallet.node_url = "http://sym-test-01.opening-line.jp:3000"
            else:
                self.wallet.node_url = "http://sym-main-01.opening-line.jp:3000"
            self.wallet._save_config()
            from symbolchain.facade.SymbolFacade import SymbolFacade

            self.wallet.facade = SymbolFacade(network)

            self.wallet.import_wallet(event.private_key)
            self.finish_setup()
        except Exception as e:
            self.notify(f"Error importing wallet: {str(e)}", severity="error")

    def finish_setup(self):
        """Complete setup and update UI."""
        logger.info("")
        logger.info("=" * 80)
        logger.info("[finish_setup] ========== FINISH SETUP STARTED ==========")
        logger.info("=" * 80)
        logger.info(f"[finish_setup] is_authenticated before: {self.is_authenticated}")
        logger.info(
            f"[finish_setup] Wallet password set: {self.wallet.password is not None and len(self.wallet.password) > 0}"
        )

        try:
            logger.info("[finish_setup] Step 1: Loading wallet from storage")
            password = self.wallet.password
            logger.info(
                f"[finish_setup] Password length: {len(password) if password else 0}"
            )
            self.wallet.load_wallet_from_storage(password)
            logger.info("[finish_setup] Step 1: Wallet loaded successfully")
            if not self.wallet.get_accounts():
                logger.info(
                    "[finish_setup] Migrating legacy wallet to accounts registry"
                )
                self.wallet._migrate_legacy_wallet_to_accounts()
            if self.wallet.get_accounts():
                self.wallet.load_current_account()
            self.is_authenticated = True
            logger.info(f"[finish_setup] is_authenticated now: {self.is_authenticated}")
        except Exception as e:
            logger.error(
                f"[finish_setup] Step 1: ERROR loading wallet: {str(e)}", exc_info=True
            )
            raise

        logger.info("[finish_setup] Step 2: Hiding all tabs and showing loading screen")
        self.hide_all_tabs()
        self._loading_screen = LoadingScreen("Setting up wallet...", show_progress=True)
        self.push_screen(self._loading_screen)

        def worker() -> None:
            try:
                self._async_update_wallet_data()
                self.call_from_thread(self._on_finish_setup_data_loaded, None)
            except Exception as e:
                self.call_from_thread(self._on_finish_setup_data_loaded, e)

        threading.Thread(target=worker, daemon=True).start()

        logger.info("[finish_setup] ========== FINISH SETUP LOADING ASYNC ==========")
        logger.info("")

    def _on_finish_setup_data_loaded(self, error: Exception | None) -> None:
        """Handle completion of async setup data loading."""
        if self._loading_screen:
            try:
                self.app.pop_screen()
            except Exception:
                pass
            self._loading_screen = None

        if error:
            error_msg = self._format_network_error(error)
            self.notify(f"Error loading wallet data: {error_msg}", severity="warning")

        self.query_one("#dashboard-tab").display = "block"
        self.tabs.display = "block"
        self.notify("Setup completed successfully!", severity="information")
        self.action_focus_next()

        logger.info("[finish_setup] ========== FINISH SETUP COMPLETED ==========")
        logger.info("=" * 80)
        logger.info("")

    def dump_screen_stack(self, context: str = ""):
        """Dump current screen stack state for debugging."""
        logger.info("")
        logger.info("=" * 80)
        logger.info(
            f"[dump_screen_stack] ========== SCREEN STACK DUMP: {context} =========="
        )
        logger.info("=" * 80)
        logger.info(f"[dump_screen_stack] Screen stack size: {len(self.screen_stack)}")
        logger.info(f"[dump_screen_stack] Current screen: {type(self.screen)}")
        logger.info(f"[dump_screen_stack] Current screen id: {id(self.screen)}")

        for idx, screen in enumerate(self.screen_stack):
            logger.info(
                f"[dump_screen_stack] Stack[{idx}]: {type(screen)} (id={id(screen)})"
            )

        logger.info(f"[dump_screen_stack] Tabs display: {self.tabs.display}")
        logger.info(f"[dump_screen_stack] is_authenticated: {self.is_authenticated}")
        logger.info(
            f"[dump_screen_stack] password_retry_count: {self.password_retry_count}"
        )
        logger.info(
            "[dump_screen_stack] ========== SCREEN STACK DUMP COMPLETED =========="
        )
        logger.info("=" * 80)
        logger.info("")


def main():
    """Entry point for the application."""
    app = WalletApp()
    app.run()


if __name__ == "__main__":
    main()
