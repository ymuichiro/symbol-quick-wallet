"""Aggregate transaction screens for Symbol Quick Wallet."""

from __future__ import annotations

from typing import Any, Protocol, cast

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from src.shared.logging import get_logger
from src.features.aggregate.service import (
    AggregateService,
    PartialTransactionInfo,
)

logger = get_logger(__name__)


class AppProtocol(Protocol):
    wallet: Any
    network_name: str
    node_url: str

    def notify(self, message: str, severity: str = "information") -> None: ...


class BaseModalScreen(ModalScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("tab", "action_focus_next", "Next"),
        ("shift+tab", "action_focus_previous", "Previous"),
    ]


class PartialTransactionsScreen(BaseModalScreen):
    """Screen to display pending partial transactions requiring cosignatures."""

    BINDINGS = BaseModalScreen.BINDINGS + [("r", "refresh", "Refresh")]

    def __init__(self, aggregate_service: AggregateService | None = None):
        super().__init__()
        self.aggregate_service = aggregate_service
        self._partials: list[PartialTransactionInfo] = []
        self._selected_hash: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("📋 Pending Cosignature Requests", id="partial-title")
        yield Static("Loading partial transactions...", id="partial-status")
        yield DataTable(id="partial-table")
        yield VerticalScroll(Static("", id="partial-details"), id="details-container")
        yield Horizontal(
            Button("✍️ Cosign Selected", id="cosign-button", variant="primary"),
            Button("🔄 Refresh", id="refresh-button"),
            Button("❌ Close", id="close-button"),
        )

    def on_mount(self) -> None:
        self._load_partials()

    def _load_partials(self) -> None:
        status_widget = cast(Static, self.query_one("#partial-status"))
        table = cast(DataTable, self.query_one("#partial-table"))

        table.clear()
        table.add_column("Hash", key="hash")
        table.add_column("Expires In", key="expires")
        table.add_column("Inner Tx Count", key="count")
        table.add_column("Cosignatures", key="cosigs")

        if self.aggregate_service is None:
            status_widget.update("[red]Aggregate service not available[/red]")
            return

        try:
            self._partials = self.aggregate_service.fetch_partial_transactions()

            if not self._partials:
                status_widget.update(
                    "[dim]No pending transactions requiring your signature[/dim]"
                )
                return

            status_widget.update(
                f"[green]Found {len(self._partials)} pending transaction(s)[/green]"
            )

            for partial in self._partials:
                hash_short = (
                    partial.hash[:16] + "..."
                    if len(partial.hash) > 16
                    else partial.hash
                )
                expires_str = self._format_expires_in(partial.expires_in)
                count_str = str(len(partial.inner_transactions))
                cosigs_str = str(len(partial.cosignatures))
                table.add_row(
                    hash_short, expires_str, count_str, cosigs_str, key=partial.hash
                )

        except Exception as e:
            logger.error("Failed to load partial transactions: %s", e)
            status_widget.update(f"[red]Failed to load: {e}[/red]")

    def _format_expires_in(self, seconds: int) -> str:
        if seconds <= 0:
            return "[red]Expired[/red]"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 24:
            days = hours // 24
            return f"{days}d {hours % 24}h"
        return f"{hours}h {minutes}m"

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key:
            self._selected_hash = (
                str(event.row_key.value)
                if hasattr(event.row_key, "value")
                else str(event.row_key)
            )
            self._update_details()

    def _update_details(self) -> None:
        details_widget = cast(Static, self.query_one("#partial-details"))

        if not self._selected_hash:
            details_widget.update("")
            return

        partial = None
        for p in self._partials:
            if p.hash == self._selected_hash:
                partial = p
                break

        if not partial:
            details_widget.update("[dim]Select a transaction to view details[/dim]")
            return

        lines = [
            f"[bold]Transaction Hash:[/bold] {partial.hash}",
            f"[bold]Signer:[/bold] {partial.signer_public_key[:32]}...",
            f"[bold]Deadline:[/bold] {partial.deadline}",
            "",
            "[bold]Inner Transactions:[/bold]",
        ]

        for idx, inner in enumerate(partial.inner_transactions):
            lines.append(f"  {idx + 1}. Type: {inner.type}")
            if inner.recipient_address:
                lines.append(f"     To: {inner.recipient_address[:32]}...")
            if inner.mosaics:
                for mosaic in inner.mosaics:
                    lines.append(
                        f"     Mosaic: {hex(mosaic.get('mosaic_id', 0))}, Amount: {mosaic.get('amount', 0)}"
                    )
            if inner.message:
                lines.append(f"     Message: {inner.message[:50]}...")

        if partial.cosignatures:
            lines.append("")
            lines.append("[bold]Existing Cosignatures:[/bold]")
            for cosig in partial.cosignatures:
                signer = cosig.get("signer_public_key", "")[:20]
                lines.append(f"  - {signer}...")

        details_widget.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cosign-button":
            self._cosign_selected()
        elif event.button.id == "refresh-button":
            self._load_partials()
        elif event.button.id == "close-button":
            self.app.pop_screen()

    def action_refresh(self) -> None:
        self._load_partials()

    def _cosign_selected(self) -> None:
        if not self._selected_hash:
            self.notify("Please select a transaction first", severity="warning")
            return

        if self.aggregate_service is None:
            self.notify("Aggregate service not available", severity="error")
            return

        partial = None
        for p in self._partials:
            if p.hash == self._selected_hash:
                partial = p
                break

        if not partial:
            self.notify("Selected transaction not found", severity="error")
            return

        self.post_message(
            self.CosignRequested(
                partial=partial, aggregate_service=self.aggregate_service
            )
        )

    class CosignRequested(Message):
        def __init__(
            self, partial: PartialTransactionInfo, aggregate_service: AggregateService
        ):
            super().__init__()
            self.partial = partial
            self.aggregate_service = aggregate_service


class CosignConfirmScreen(BaseModalScreen):
    """Screen to confirm cosigning a partial transaction."""

    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "confirm", "Confirm")]

    def __init__(self, partial: PartialTransactionInfo):
        super().__init__()
        self.partial = partial

    def compose(self) -> ComposeResult:
        yield Label("✍️ Confirm Cosignature", id="cosign-title")
        yield Static(f"Transaction Hash: {self.partial.hash}", id="cosign-hash")
        yield Label("")
        yield Label("This will add your signature to the following transaction:")
        yield VerticalScroll(Static(self._format_details(), id="cosign-details"))
        yield Horizontal(
            Button("✓ Cosign", id="confirm-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def _format_details(self) -> str:
        lines = []
        for idx, inner in enumerate(self.partial.inner_transactions):
            lines.append(f"Transaction {idx + 1}:")
            lines.append(f"  Type: {inner.type}")
            if inner.recipient_address:
                lines.append(f"  Recipient: {inner.recipient_address}")
            if inner.mosaics:
                for mosaic in inner.mosaics:
                    mosaic_id = hex(mosaic.get("mosaic_id", 0))
                    amount = mosaic.get("amount", 0) / 1_000_000
                    lines.append(f"  Mosaic: {mosaic_id} - {amount:.6f} XYM")
            if inner.message:
                lines.append(f"  Message: {inner.message}")
            lines.append("")

        existing_cosigs = len(self.partial.cosignatures)
        lines.append(f"Existing cosignatures: {existing_cosigs}")

        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-button":
            self.dismiss(True)
        elif event.button.id == "cancel-button":
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


class AggregateBuilderScreen(BaseModalScreen):
    """Screen to build aggregate transactions."""

    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "submit", "Submit")]

    def __init__(
        self,
        aggregate_service: AggregateService | None = None,
        owned_mosaics: list[dict[str, Any]] | None = None,
    ):
        super().__init__()
        self.aggregate_service = aggregate_service
        self.owned_mosaics = owned_mosaics or []
        self._inner_txs: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("🔧 Build Aggregate Transaction", id="agg-builder-title")
        yield Label("Aggregate Type:")
        yield Select(
            [
                ("Complete (all signatures now)", "complete"),
                ("Bonded (collect signatures later)", "bonded"),
            ],
            id="agg-type-select",
            value="complete",
        )
        yield Label("")
        yield Label("Inner Transactions:")
        yield DataTable(id="inner-tx-table")
        yield Static("No inner transactions added yet", id="inner-tx-count")
        yield Horizontal(
            Button("➕ Add Transfer", id="add-tx-button"),
            Button("🗑️ Clear All", id="clear-button"),
        )
        yield Label("")
        yield Static("", id="fee-estimate")
        yield Horizontal(
            Button("📤 Create Transaction", id="create-button", variant="primary"),
            Button("❌ Cancel", id="cancel-button"),
        )

    def on_mount(self) -> None:
        table = cast(DataTable, self.query_one("#inner-tx-table"))
        table.add_column("Recipient", key="recipient")
        table.add_column("Mosaics", key="mosaics")
        table.add_column("Message", key="message")

    def _update_display(self) -> None:
        table = cast(DataTable, self.query_one("#inner-tx-table"))
        count_widget = cast(Static, self.query_one("#inner-tx-count"))
        fee_widget = cast(Static, self.query_one("#fee-estimate"))

        table.clear()
        for tx in self._inner_txs:
            recipient = tx.get("recipient", "")[:20]
            if len(tx.get("recipient", "")) > 20:
                recipient += "..."
            mosaics_str = self._format_mosaics(tx.get("mosaics", []))
            message = tx.get("message", "")[:15]
            if len(tx.get("message", "")) > 15:
                message += "..."
            table.add_row(recipient, mosaics_str, message)

        count_widget.update(f"{len(self._inner_txs)} inner transaction(s)")

        if self._inner_txs:
            fee_widget.update("Estimated fee will be calculated on confirmation")
        else:
            fee_widget.update("")

    def _format_mosaics(self, mosaics: list[dict]) -> str:
        if not mosaics:
            return "(none)"
        if len(mosaics) == 1:
            amount = mosaics[0].get("amount", 0) / 1_000_000
            return f"{amount:.2f} XYM"
        return f"{len(mosaics)} mosaics"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-tx-button":
            self.post_message(self.AddInnerTransactionRequested())
        elif event.button.id == "clear-button":
            self._inner_txs = []
            self._update_display()
        elif event.button.id == "create-button":
            self._create_aggregate()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    def action_submit(self) -> None:
        self._create_aggregate()

    def add_inner_transaction(self, tx: dict[str, Any]) -> None:
        self._inner_txs.append(tx)
        self._update_display()

    def _create_aggregate(self) -> None:
        if not self._inner_txs:
            self.notify("Please add at least one inner transaction", severity="warning")
            return

        if self.aggregate_service is None:
            self.notify("Aggregate service not available", severity="error")
            return

        type_select = cast(Select, self.query_one("#agg-type-select"))
        agg_type = str(type_select.value) if type_select.value else "complete"

        self.post_message(
            self.CreateAggregateRequested(
                inner_txs=self._inner_txs.copy(),
                agg_type=agg_type,
                aggregate_service=self.aggregate_service,
            )
        )

    class AddInnerTransactionRequested(Message):
        pass

    class CreateAggregateRequested(Message):
        def __init__(
            self,
            inner_txs: list[dict[str, Any]],
            agg_type: str,
            aggregate_service: AggregateService,
        ):
            super().__init__()
            self.inner_txs = inner_txs
            self.agg_type = agg_type
            self.aggregate_service = aggregate_service


class InnerTransactionInputScreen(BaseModalScreen):
    """Screen to add an inner transaction to an aggregate."""

    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "submit", "Add")]

    def __init__(self, owned_mosaics: list[dict[str, Any]] | None = None):
        super().__init__()
        self.owned_mosaics = owned_mosaics or []

    def compose(self) -> ComposeResult:
        yield Label("➕ Add Inner Transfer Transaction")
        yield Label("Recipient Address:")
        yield Input(placeholder="N/A...", id="recipient-input")
        yield Label("Mosaic (optional):")
        mosaic_options = [("(No mosaic)", None)]
        for m in self.owned_mosaics:
            name = m.get("name", hex(m.get("id", 0)))
            mosaic_options.append((name, hex(m.get("id", 0))))
        yield Select(mosaic_options, id="mosaic-select", value=None)
        yield Label("Amount (if mosaic selected):")
        yield Input(placeholder="e.g. 1.5", id="amount-input", disabled=True)
        yield Label("Message (optional):")
        yield Input(placeholder="Optional message...", id="message-input")
        yield Label("", id="validation-error")
        yield Horizontal(
            Button("✓ Add", id="add-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "mosaic-select":
            amount_input = cast(Input, self.query_one("#amount-input"))
            amount_input.disabled = event.value is None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-button":
            self._submit()
        elif event.button.id == "cancel-button":
            self.dismiss(None)

    def action_submit(self) -> None:
        self._submit()

    def _submit(self) -> None:
        recipient_input = cast(Input, self.query_one("#recipient-input"))
        mosaic_select = cast(Select, self.query_one("#mosaic-select"))
        amount_input = cast(Input, self.query_one("#amount-input"))
        message_input = cast(Input, self.query_one("#message-input"))
        error_label = cast(Label, self.query_one("#validation-error"))

        recipient = recipient_input.value.strip()
        if not recipient:
            error_label.update("⚠️ Recipient address is required")
            return

        mosaics: list[dict[str, int]] = []
        if mosaic_select.value:
            try:
                mosaic_id = int(str(mosaic_select.value), 16)
                amount_str = amount_input.value.strip()
                if not amount_str:
                    error_label.update("⚠️ Amount is required when mosaic is selected")
                    return

                amount = float(amount_str)
                amount_micro = int(amount * 1_000_000)
                mosaics.append({"mosaic_id": mosaic_id, "amount": amount_micro})
            except ValueError:
                error_label.update("⚠️ Invalid amount format")
                return

        message = message_input.value.strip()

        self.dismiss(
            {
                "recipient": recipient,
                "mosaics": mosaics,
                "message": message,
            }
        )


class AggregateResultScreen(BaseModalScreen):
    """Screen to display aggregate transaction results."""

    def __init__(
        self,
        tx_hash: str | None = None,
        hash_lock_hash: str | None = None,
        aggregate_hash: str | None = None,
        network: str = "testnet",
        is_bonded: bool = False,
    ):
        super().__init__()
        self.tx_hash = tx_hash
        self.hash_lock_hash = hash_lock_hash
        self.aggregate_hash = aggregate_hash
        self.network = network
        self.is_bonded = is_bonded

    def compose(self) -> ComposeResult:
        yield Label("✅ Aggregate Transaction Sent!", id="agg-result-title")

        if self.is_bonded:
            yield Label("Hash Lock Transaction:")
            if self.hash_lock_hash:
                yield Static(self.hash_lock_hash, id="hash-lock-hash")
            yield Label("")
            yield Label("Aggregate Bonded Transaction:")
            if self.aggregate_hash:
                yield Static(self.aggregate_hash, id="aggregate-hash")
            yield Label("")
            yield Label(
                "[dim]Note: The aggregate bonded is now pending and awaits cosignatures.[/dim]"
            )
        else:
            yield Label("Transaction Hash:")
            if self.tx_hash:
                yield Static(self.tx_hash, id="tx-hash")

        if self.network == "testnet":
            base_url = "https://testnet.symbol.fyi/transactions/"
        else:
            base_url = "https://symbol.fyi/transactions/"

        if self.tx_hash:
            yield Label(f"Explorer: {base_url}{self.tx_hash}")

        yield Horizontal(
            Button("📋 Copy Hash", id="copy-button", variant="primary"),
            Button("❌ Close", id="close-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-button":
            import pyperclip

            hash_to_copy = self.tx_hash or self.aggregate_hash or ""
            if hash_to_copy:
                pyperclip.copy(hash_to_copy)
                self.notify("Transaction hash copied!", severity="information")
        elif event.button.id == "close-button":
            self.app.pop_screen()


class AggregateStatusScreen(BaseModalScreen):
    """Screen to monitor aggregate transaction status."""

    def __init__(self, tx_hash: str, network: str = "testnet", is_bonded: bool = False):
        super().__init__()
        self.tx_hash = tx_hash
        self.network = network
        self.is_bonded = is_bonded
        self._status = "pending"
        self._detail = "Waiting for status..."
        self._elapsed = 0
        self._timer = None

    def compose(self) -> ComposeResult:
        title = (
            "⏳ Aggregate Bonded Status" if self.is_bonded else "⏳ Transaction Status"
        )
        yield Label(title, id="status-title")
        yield Static(self.tx_hash[:40] + "...", id="status-hash")
        yield Label("Status:")
        yield Static("[yellow]⏳ Pending...[/yellow]", id="status-value")
        yield Static("", id="status-detail")
        yield Static("Elapsed: 0s", id="elapsed")
        yield Button("❌ Close", id="close-button")

    def on_mount(self) -> None:
        self._start_timer()

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def _start_timer(self) -> None:
        def tick() -> None:
            self._elapsed += 1
            try:
                elapsed_widget = cast(Static, self.query_one("#elapsed"))
                elapsed_widget.update(f"Elapsed: {self._elapsed}s")
            except Exception:
                pass

        self._timer = self.set_interval(1.0, tick)

    def update_status(self, status: str, detail: str = "") -> None:
        self._status = status
        self._detail = detail

        try:
            value_widget = cast(Static, self.query_one("#status-value"))
            detail_widget = cast(Static, self.query_one("#status-detail"))

            if status == "confirmed":
                value_widget.update("[green]✓ Confirmed[/green]")
                detail_widget.update(
                    f"[green]{detail or 'Transaction confirmed'}[/green]"
                )
            elif status == "partial":
                value_widget.update("[cyan]⏳ Partial (awaiting cosignatures)[/cyan]")
                detail_widget.update(f"[dim]{detail}[/dim]")
            elif status == "failed":
                value_widget.update("[red]✗ Failed[/red]")
                detail_widget.update(f"[red]{detail or 'Transaction failed'}[/red]")
            else:
                value_widget.update(f"[yellow]⏳ {status.title()}[/yellow]")
                detail_widget.update(f"[dim]{detail}[/dim]")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-button":
            self.app.pop_screen()
