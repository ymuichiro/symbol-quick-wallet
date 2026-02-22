"""Transfer-related modal screens for Symbol Quick Wallet."""

from typing import Protocol, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from src.shared.logging import get_logger
from src.features.transfer.validators import TransferAmountValidator

logger = get_logger(__name__)


class WalletLike(Protocol):
    def get_mosaic_name(self, mosaic_id: int) -> str: ...


class AppWithWalletOps(Protocol):
    wallet: WalletLike


class BaseModalScreen(ModalScreen):
    """Base modal screen with common key bindings."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("tab", "action_focus_next", "Next"),
        ("shift+tab", "action_focus_previous", "Previous"),
    ]


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


class TransactionStatusScreen(BaseModalScreen):
    BINDINGS = []

    def __init__(self, tx_hash: str, network: str = "testnet"):
        super().__init__()
        self.tx_hash = tx_hash
        self.network = network
        self._status = "pending"
        self._status_detail = "Waiting for status..."
        self._elapsed_seconds = 0
        self._loading_step = 0
        self._loading_timer = None
        self._loading_active = False
        self._elapsed_timer = None

    def compose(self) -> ComposeResult:
        yield Label("⏳ Transaction Status", id="tx-status-title")
        yield Static(self.tx_hash[:32] + "...", id="tx-status-hash")
        yield Label("Status:", id="tx-status-label")
        yield Static("[yellow]⏳ Pending...[/yellow]", id="tx-status-value")
        yield Static("", id="tx-status-detail")
        yield Static("Elapsed: 0s", id="tx-status-elapsed")

    def on_mount(self) -> None:
        self._start_loading_animation()
        self._start_elapsed_timer()

    def on_unmount(self) -> None:
        self._stop_loading_animation()
        self._stop_elapsed_timer()

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
                status_widget = cast(Static, self.query_one("#tx-status-value"))
                current = getattr(status_widget, "renderable", None) or ""
                if "[yellow]" in str(current):
                    status_widget.update(
                        f"[yellow]{spinner} {current.replace('[yellow]', '').replace('[/yellow]', '')}[/yellow]"
                    )
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

    def _start_elapsed_timer(self) -> None:
        def tick() -> None:
            self._elapsed_seconds += 1
            try:
                elapsed_widget = cast(Static, self.query_one("#tx-status-elapsed"))
                elapsed_widget.update(f"Elapsed: {self._elapsed_seconds}s")
            except Exception:
                pass

        self._elapsed_timer = self.set_interval(1.0, tick)

    def _stop_elapsed_timer(self) -> None:
        if self._elapsed_timer:
            try:
                self._elapsed_timer.stop()
            except Exception:
                pass
            self._elapsed_timer = None

    def update_status(self, status: str, detail: str = "") -> None:
        self._status = status
        self._status_detail = detail
        try:
            status_widget = cast(Static, self.query_one("#tx-status-value"))
            detail_widget = cast(Static, self.query_one("#tx-status-detail"))

            if status == "confirmed":
                self._stop_loading_animation()
                status_widget.update("[green]✓ Confirmed[/green]")
                detail_widget.update(
                    f"[green]{detail or 'Transaction confirmed successfully'}[/green]"
                )
            elif status == "failed":
                self._stop_loading_animation()
                status_widget.update("[red]✗ Failed[/red]")
                detail_widget.update(f"[red]{detail or 'Transaction failed'}[/red]")
            elif status == "unconfirmed":
                status_widget.update("[yellow]⏳ Unconfirmed (in mempool)[/yellow]")
                detail_widget.update(f"[dim]{detail}[/dim]")
            elif status == "partial":
                status_widget.update("[cyan]⏳ Partial[/cyan]")
                detail_widget.update(f"[dim]{detail}[/dim]")
            else:
                status_widget.update(f"[yellow]⏳ {status.title()}[/yellow]")
                detail_widget.update(f"[dim]{detail}[/dim]")
        except Exception:
            pass

    def show_success(self, tx_hash: str) -> None:
        self._stop_loading_animation()
        try:
            status_widget = cast(Static, self.query_one("#tx-status-value"))
            detail_widget = cast(Static, self.query_one("#tx-status-detail"))
            status_widget.update("[green]✓ Confirmed[/green]")
            if self.network == "testnet":
                explorer_url = f"https://testnet.symbol.fyi/transactions/{tx_hash}"
            else:
                explorer_url = f"https://symbol.fyi/transactions/{tx_hash}"
            detail_widget.update(
                f"[green]Transaction confirmed![/green]\n[dim]Explorer: {explorer_url}[/dim]"
            )
        except Exception:
            pass

    def show_failure(self, error: str) -> None:
        self._stop_loading_animation()
        try:
            status_widget = cast(Static, self.query_one("#tx-status-value"))
            detail_widget = cast(Static, self.query_one("#tx-status-detail"))
            status_widget.update("[red]✗ Failed[/red]")
            detail_widget.update(f"[red]{error}[/red]")
        except Exception:
            pass


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

        result = TransferAmountValidator.validate_full(
            value, divisibility, owned_amount
        )

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

        validation_result = TransferAmountValidator.validate_full(
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


class TransactionQueueScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "submit_all", "Submit All")]

    def __init__(self, transactions, total_fee: float):
        super().__init__()
        self.transactions = transactions
        self.total_fee = total_fee
        self._transaction_ids = [tx.id for tx in transactions]

    def compose(self) -> ComposeResult:
        yield Label("📋 Transaction Queue", id="queue-title")
        yield Label(
            f"{len(self.transactions)} transaction(s) pending", id="queue-count"
        )
        yield DataTable(id="queue-table")
        yield Static(
            f"💰 Total Estimated Fee: {self.total_fee:,.6f} XYM", id="total-fee"
        )
        yield Horizontal(
            Button("📤 Submit All", id="submit-all-button", variant="primary"),
            Button("🗑️ Remove Selected", id="remove-button"),
            Button("🗑️ Clear All", id="clear-button"),
            Button("❌ Close", id="close-button"),
        )

    def on_mount(self) -> None:
        table = cast(DataTable, self.query_one("#queue-table"))
        table.add_column("#", key="index")
        table.add_column("Recipient", key="recipient")
        table.add_column("Mosaics", key="mosaics")
        table.add_column("Message", key="message")
        table.add_column("Fee", key="fee")

        for idx, tx in enumerate(self.transactions):
            recipient = (
                tx.recipient[:20] + "..." if len(tx.recipient) > 20 else tx.recipient
            )
            mosaics_str = self._format_mosaics(tx.mosaics)
            message_preview = (
                (tx.message[:15] + "...") if len(tx.message) > 15 else tx.message
            )
            fee_str = f"{tx.estimated_fee:,.6f}"
            table.add_row(
                str(idx + 1),
                recipient,
                mosaics_str,
                message_preview,
                fee_str,
                key=tx.id,
            )

    def _format_mosaics(self, mosaics: list[dict]) -> str:
        if not mosaics:
            return "(none)"
        if len(mosaics) == 1:
            amount = mosaics[0].get("amount", 0) / 1_000_000
            return f"{amount:,.2f}"
        return f"{len(mosaics)} mosaics"

    def _get_selected_id(self) -> str | None:
        table = cast(DataTable, self.query_one("#queue-table"))
        cursor_row = table.cursor_row
        if cursor_row is not None and 0 <= cursor_row < len(self._transaction_ids):
            return self._transaction_ids[cursor_row]
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-all-button":
            self.post_message(self.SubmitAllRequested())
            self.app.pop_screen()
        elif event.button.id == "remove-button":
            tx_id = self._get_selected_id()
            if tx_id:
                self.post_message(self.RemoveRequested(transaction_id=tx_id))
        elif event.button.id == "clear-button":
            self.post_message(self.ClearRequested())
            self.app.pop_screen()
        elif event.button.id == "close-button":
            self.app.pop_screen()

    class SubmitAllRequested(Message):
        pass

    class RemoveRequested(Message):
        def __init__(self, transaction_id: str):
            super().__init__()
            self.transaction_id = transaction_id

    class ClearRequested(Message):
        pass


class BatchTransactionResultScreen(BaseModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def __init__(self, results: list[dict], network: str = "testnet"):
        super().__init__()
        self.results = results
        self.network = network

    def compose(self) -> ComposeResult:
        yield Label("📋 Batch Transaction Results", id="batch-result-title")
        yield DataTable(id="batch-results-table")
        yield Static("", id="batch-summary")
        yield Button("❌ Close", id="close-button")

    def on_mount(self) -> None:
        table = cast(DataTable, self.query_one("#batch-results-table"))
        table.add_column("#", key="index")
        table.add_column("Recipient", key="recipient")
        table.add_column("Status", key="status")
        table.add_column("Hash", key="hash")

        success_count = 0
        for idx, result in enumerate(self.results):
            recipient = result.get("recipient", "")[:20]
            if len(result.get("recipient", "")) > 20:
                recipient += "..."
            status = "✅ Success" if result.get("success") else "❌ Failed"
            hash_val = result.get("hash", "N/A")
            if result.get("success") and hash_val != "N/A":
                hash_val = hash_val[:16] + "..."
            table.add_row(str(idx + 1), recipient, status, hash_val, key=str(idx))
            if result.get("success"):
                success_count += 1

        summary = cast(Static, self.query_one("#batch-summary"))
        summary.update(
            f"Summary: {success_count}/{len(self.results)} transactions successful"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-button":
            self.app.pop_screen()


class TemplateSelectorScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "select", "Select")]

    def __init__(self, templates):
        super().__init__()
        self.templates = templates
        self._template_ids = [tpl.id for tpl in templates]

    def compose(self) -> ComposeResult:
        yield Label("📋 Select Template")
        if not self.templates:
            yield Label("No templates saved yet.")
        else:
            yield DataTable(id="template-table")
        yield Horizontal(
            Button("❌ Cancel", id="cancel-button"),
        )

    def on_mount(self) -> None:
        if not self.templates:
            return
        table = cast(DataTable, self.query_one("#template-table"))
        table.add_column("Name", key="name")
        table.add_column("Recipient", key="recipient")
        table.add_column("Message", key="message")
        for tpl in self.templates:
            recipient_short = (
                tpl.recipient[:20] + "..." if len(tpl.recipient) > 20 else tpl.recipient
            )
            message_short = (
                (tpl.message[:15] + "...") if len(tpl.message) > 15 else tpl.message
            )
            table.add_row(tpl.name, recipient_short, message_short, key=tpl.id)

    def on_data_table_row_selected(self, event):
        row = event.row_key
        template_id = row.value if hasattr(row, "value") else str(row)
        self._select_template(template_id)

    def action_select(self) -> None:
        table = cast(DataTable, self.query_one("#template-table"))
        cursor_row = table.cursor_row
        if cursor_row is not None and 0 <= cursor_row < len(self._template_ids):
            self._select_template(self._template_ids[cursor_row])

    def _select_template(self, template_id: str) -> None:
        for tpl in self.templates:
            if tpl.id == template_id:
                self.post_message(self.TemplateSelected(template=tpl))
                self.app.pop_screen()
                return

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-button":
            self.app.pop_screen()

    class TemplateSelected(Message):
        def __init__(self, template):
            super().__init__()
            self.template = template


class SaveTemplateScreen(BaseModalScreen):
    def __init__(self, recipient: str, mosaics: list, message: str):
        super().__init__()
        self.recipient = recipient
        self.mosaics = mosaics
        self.message = message

    def compose(self) -> ComposeResult:
        yield Label("💾 Save as Template")
        yield Label("Template Name:")
        yield Input(placeholder="e.g., Monthly Rent Payment", id="name-input")
        yield Label(
            f"Recipient: {self.recipient[:30]}{'...' if len(self.recipient) > 30 else ''}"
        )
        yield Label(f"Mosaics: {len(self.mosaics)} item(s)")
        yield Label(
            f"Message: {self.message[:30] if self.message else '(none)'}{'...' if len(self.message) > 30 else ''}"
        )
        yield Horizontal(
            Button("✓ Save", id="save-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            name_input = cast(Input, self.query_one("#name-input"))
            name = name_input.value.strip()
            if not name:
                self.notify("Please enter a template name", severity="warning")
                return
            self.post_message(
                self.SaveTemplateRequested(
                    name=name,
                    recipient=self.recipient,
                    mosaics=self.mosaics,
                    message=self.message,
                )
            )
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class SaveTemplateRequested(Message):
        def __init__(self, name: str, recipient: str, mosaics: list, message: str):
            super().__init__()
            self.name = name
            self.recipient = recipient
            self.mosaics = mosaics
            self.message = message


class TemplateListScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "use", "Use")]

    def __init__(self, templates):
        super().__init__()
        self.templates = templates
        self._template_ids = [tpl.id for tpl in templates]

    def compose(self) -> ComposeResult:
        yield Label("📋 Transaction Templates", id="template-list-title")
        if not self.templates:
            yield Label("No templates saved yet.")
            yield Label("Use 'Save as Template' in the Transfer tab to create one.")
        else:
            yield DataTable(id="templates-table")
        yield Horizontal(
            Button("📤 Use Selected", id="use-button", variant="primary"),
            Button("🗑️ Delete", id="delete-button"),
            Button("❌ Close", id="close-button"),
        )

    def on_mount(self) -> None:
        if not self.templates:
            return
        table = cast(DataTable, self.query_one("#templates-table"))
        table.add_column("Name", key="name")
        table.add_column("Recipient", key="recipient")
        table.add_column("Mosaics", key="mosaics")
        table.add_column("Message", key="message")
        for tpl in self.templates:
            recipient_short = (
                tpl.recipient[:20] + "..." if len(tpl.recipient) > 20 else tpl.recipient
            )
            mosaics_str = self._format_mosaics(tpl.mosaics)
            message_short = (
                (tpl.message[:15] + "...") if len(tpl.message) > 15 else tpl.message
            )
            table.add_row(
                tpl.name, recipient_short, mosaics_str, message_short, key=tpl.id
            )

    def _format_mosaics(self, mosaics: list) -> str:
        if not mosaics:
            return "(none)"
        if len(mosaics) == 1:
            amount = mosaics[0].get("amount", 0) / 1_000_000
            return f"{amount:,.2f}"
        return f"{len(mosaics)} mosaics"

    def _get_selected_id(self) -> str | None:
        if not self.templates:
            return None
        table = cast(DataTable, self.query_one("#templates-table"))
        cursor_row = table.cursor_row
        if cursor_row is not None and 0 <= cursor_row < len(self._template_ids):
            return self._template_ids[cursor_row]
        return None

    def on_data_table_row_selected(self, event):
        self._use_selected()

    def action_use(self) -> None:
        self._use_selected()

    def _use_selected(self) -> None:
        template_id = self._get_selected_id()
        if template_id:
            for tpl in self.templates:
                if tpl.id == template_id:
                    self.post_message(self.UseTemplateRequested(template=tpl))
                    self.app.pop_screen()
                    return

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "use-button":
            self._use_selected()
        elif event.button.id == "delete-button":
            template_id = self._get_selected_id()
            if template_id:
                self.post_message(self.DeleteTemplateRequested(template_id=template_id))
        elif event.button.id == "close-button":
            self.app.pop_screen()

    class UseTemplateRequested(Message):
        def __init__(self, template):
            super().__init__()
            self.template = template

    class DeleteTemplateRequested(Message):
        def __init__(self, template_id: str):
            super().__init__()
            self.template_id = template_id
