"""Multisig account TUI screens for Symbol Quick Wallet."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static, TextArea

if TYPE_CHECKING:
    from src.shared.protocols import WalletProtocol


class MultisigManagerScreen(ModalScreen):
    """Screen for managing multisig accounts - view info and access actions."""

    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def __init__(
        self,
        wallet: "WalletProtocol",
        multisig_service: Any,
    ):
        super().__init__()
        self.wallet = wallet
        self.multisig_service = multisig_service

    def compose(self) -> ComposeResult:
        yield Container(
            Label("🔐 Multisig Account Manager", classes="modal-title"),
            Static("", id="multisig-info"),
            Horizontal(
                Button("🔄 Refresh Info", id="refresh-multisig-info"),
                Button("➕ Convert to Multisig", id="convert-multisig-btn"),
                Button("✏️ Modify Multisig", id="modify-multisig-btn"),
                Button("📤 Multisig Transfer", id="multisig-transfer-btn"),
                Button("📝 Pending Transactions", id="pending-multisig-btn"),
                classes="button-row",
            ),
            Horizontal(
                Button("Close", id="close-multisig-manager"),
                classes="button-row",
            ),
            id="multisig-manager-dialog",
            classes="modal-dialog",
        )

    def on_mount(self) -> None:
        self._refresh_multisig_info()

    def _refresh_multisig_info(self) -> None:
        info_widget = self.query_one("#multisig-info", Static)
        if not self.wallet.address:
            info_widget.update("No wallet loaded")
            return

        info = self.multisig_service.get_multisig_account_info(str(self.wallet.address))

        if info is None:
            info_widget.update(
                "[dim]Account is not a multisig account and is not a cosigner of any multisig account.[/dim]\n\n"
                "Use 'Convert to Multisig' to convert this account to a multisig account."
            )
            return

        lines = []
        if info.is_multisig:
            lines.append("[bold green]This account IS a multisig account:[/bold green]")
            lines.append(f"  Address: {info.account_address}")
            lines.append(f"  Min Approval: {info.min_approval}")
            lines.append(f"  Min Removal: {info.min_removal}")
            lines.append(f"  Cosigners ({len(info.cosignatory_addresses)}):")
            for addr in info.cosignatory_addresses:
                lines.append(f"    • {addr}")
            lines.append("")

        if info.is_cosigner_of:
            lines.append("[bold cyan]This account IS a cosigner of:[/bold cyan]")
            for addr in info.multisig_addresses:
                lines.append(f"    • {addr}")

        info_widget.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "close-multisig-manager":
            self.app.pop_screen()
        elif button_id == "refresh-multisig-info":
            self._refresh_multisig_info()
        elif button_id == "convert-multisig-btn":
            self.app.pop_screen()
            self.app.push_screen(
                ConvertToMultisigScreen(self.wallet, self.multisig_service)
            )
        elif button_id == "modify-multisig-btn":
            self.app.pop_screen()
            self.app.push_screen(
                ModifyMultisigScreen(self.wallet, self.multisig_service)
            )
        elif button_id == "multisig-transfer-btn":
            self.app.pop_screen()
            self.app.push_screen(
                MultisigTransactionScreen(self.wallet, self.multisig_service)
            )
        elif button_id == "pending-multisig-btn":
            self.app.pop_screen()
            self.app.push_screen(
                PendingMultisigScreen(self.wallet, self.multisig_service)
            )


class ConvertToMultisigScreen(ModalScreen):
    """Screen for converting an account to multisig."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    class ConvertRequested(Message):
        """Message sent when conversion is requested."""

        def __init__(
            self,
            cosigners: list[str],
            min_approval: int,
            min_removal: int,
        ) -> None:
            super().__init__()
            self.cosigners = cosigners
            self.min_approval = min_approval
            self.min_removal = min_removal

    def __init__(
        self,
        wallet: "WalletProtocol",
        multisig_service: Any,
    ):
        super().__init__()
        self.wallet = wallet
        self.multisig_service = multisig_service

    def compose(self) -> ComposeResult:
        yield Container(
            Label("➕ Convert to Multisig Account", classes="modal-title"),
            Static(
                "Convert this account to a multisig account by adding cosigners.\n"
                "All cosigners must opt-in by signing the transaction.",
                classes="helper-text",
            ),
            Label("Cosigner Addresses (one per line):"),
            TextArea(id="cosigner-addresses-input", classes="input-field"),
            Label("Minimum Approval Threshold:"),
            Input(placeholder="1", id="min-approval-input", value="1"),
            Label("Minimum Removal Threshold:"),
            Input(placeholder="1", id="min-removal-input", value="1"),
            Static("", id="conversion-error"),
            Horizontal(
                Button("Convert", id="submit-conversion", variant="primary"),
                Button("Cancel", id="cancel-conversion"),
                classes="button-row",
            ),
            id="convert-multisig-dialog",
            classes="modal-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-conversion":
            self.app.pop_screen()
        elif event.button.id == "submit-conversion":
            self._submit_conversion()

    def _submit_conversion(self) -> None:
        error_widget = self.query_one("#conversion-error", Static)
        error_widget.update("")

        cosigners_text = self.query_one("#cosigner-addresses-input", TextArea).text
        min_approval_str = self.query_one("#min-approval-input", Input).value
        min_removal_str = self.query_one("#min-removal-input", Input).value

        cosigners = [
            line.strip() for line in cosigners_text.strip().split("\n") if line.strip()
        ]

        try:
            min_approval = int(min_approval_str)
            min_removal = int(min_removal_str)
        except ValueError:
            error_widget.update("[red]Error: Thresholds must be integers[/red]")
            return

        is_valid, error_msg = self.multisig_service.validate_multisig_conversion(
            cosigners, min_approval, min_removal
        )

        if not is_valid:
            error_widget.update(f"[red]Error: {error_msg}[/red]")
            return

        self.post_message(self.ConvertRequested(cosigners, min_approval, min_removal))
        self.app.pop_screen()


class ModifyMultisigScreen(ModalScreen):
    """Screen for modifying an existing multisig account."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    class ModificationRequested(Message):
        """Message sent when modification is requested."""

        def __init__(
            self,
            min_approval_delta: int,
            min_removal_delta: int,
            address_additions: list[str],
            address_deletions: list[str],
        ) -> None:
            super().__init__()
            self.min_approval_delta = min_approval_delta
            self.min_removal_delta = min_removal_delta
            self.address_additions = address_additions
            self.address_deletions = address_deletions

    def __init__(
        self,
        wallet: "WalletProtocol",
        multisig_service: Any,
    ):
        super().__init__()
        self.wallet = wallet
        self.multisig_service = multisig_service

    def compose(self) -> ComposeResult:
        yield Container(
            Label("✏️ Modify Multisig Account", classes="modal-title"),
            Static(
                "Modify the multisig configuration.\n"
                "Changes require cosigner approvals according to current thresholds.",
                classes="helper-text",
            ),
            Static("", id="current-multisig-info"),
            Label("Min Approval Delta (-25 to +25):"),
            Input(placeholder="0", id="approval-delta-input", value="0"),
            Label("Min Removal Delta (-25 to +25):"),
            Input(placeholder="0", id="removal-delta-input", value="0"),
            Label("Add Cosigners (one address per line):"),
            TextArea(id="add-cosigners-input", classes="input-field"),
            Label("Remove Cosigners (one address per line):"),
            TextArea(id="remove-cosigners-input", classes="input-field"),
            Static("", id="modification-error"),
            Horizontal(
                Button("Modify", id="submit-modification", variant="primary"),
                Button("Cancel", id="cancel-modification"),
                classes="button-row",
            ),
            id="modify-multisig-dialog",
            classes="modal-dialog",
        )

    def on_mount(self) -> None:
        self._refresh_current_info()

    def _refresh_current_info(self) -> None:
        info_widget = self.query_one("#current-multisig-info", Static)
        if not self.wallet.address:
            info_widget.update("[dim]No wallet loaded[/dim]")
            return

        info = self.multisig_service.get_multisig_account_info(str(self.wallet.address))
        if info is None or not info.is_multisig:
            info_widget.update(
                "[yellow]This account is not a multisig account.[/yellow]\n"
                "Use 'Convert to Multisig' first."
            )
            return

        info_widget.update(
            f"[bold]Current Configuration:[/bold]\n"
            f"  Min Approval: {info.min_approval}\n"
            f"  Min Removal: {info.min_removal}\n"
            f"  Cosigners: {len(info.cosignatory_addresses)}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-modification":
            self.app.pop_screen()
        elif event.button.id == "submit-modification":
            self._submit_modification()

    def _submit_modification(self) -> None:
        error_widget = self.query_one("#modification-error", Static)
        error_widget.update("")

        approval_delta_str = self.query_one("#approval-delta-input", Input).value
        removal_delta_str = self.query_one("#removal-delta-input", Input).value
        add_text = self.query_one("#add-cosigners-input", TextArea).text
        remove_text = self.query_one("#remove-cosigners-input", TextArea).text

        try:
            approval_delta = int(approval_delta_str) if approval_delta_str else 0
            removal_delta = int(removal_delta_str) if removal_delta_str else 0
        except ValueError:
            error_widget.update("[red]Error: Deltas must be integers[/red]")
            return

        additions = [
            line.strip() for line in add_text.strip().split("\n") if line.strip()
        ]
        deletions = [
            line.strip() for line in remove_text.strip().split("\n") if line.strip()
        ]

        if (
            approval_delta == 0
            and removal_delta == 0
            and not additions
            and not deletions
        ):
            error_widget.update("[red]Error: No changes specified[/red]")
            return

        self.post_message(
            self.ModificationRequested(
                approval_delta, removal_delta, additions, deletions
            )
        )
        self.app.pop_screen()


class MultisigTransactionScreen(ModalScreen):
    """Screen for initiating transactions from a multisig account."""

    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    class TransactionRequested(Message):
        """Message sent when multisig transaction is requested."""

        def __init__(
            self,
            multisig_address: str,
            recipient_address: str,
            mosaics: list[dict[str, int]],
            message: str,
        ) -> None:
            super().__init__()
            self.multisig_address = multisig_address
            self.recipient_address = recipient_address
            self.mosaics = mosaics
            self.message = message

    def __init__(
        self,
        wallet: "WalletProtocol",
        multisig_service: Any,
    ):
        super().__init__()
        self.wallet = wallet
        self.multisig_service = multisig_service
        self._multisig_info: Any = None

    def compose(self) -> ComposeResult:
        yield Container(
            Label("📤 Multisig Transfer", classes="modal-title"),
            Static(
                "Initiate a transfer from a multisig account.\n"
                "Requires cosigner signatures according to min_approval threshold.",
                classes="helper-text",
            ),
            Static("", id="multisig-accounts-info"),
            Label("Multisig Account Address:"),
            Input(
                placeholder="Multisig address (or leave blank for owned)",
                id="multisig-address-input",
            ),
            Label("Recipient Address:"),
            Input(placeholder="T... recipient address", id="recipient-input"),
            Label("Mosaic ID (hex):"),
            Input(placeholder="e.g., 6BED913FA20223F8", id="mosaic-id-input"),
            Label("Amount (micro units):"),
            Input(placeholder="e.g., 1000000 for 1 XYM", id="amount-input"),
            Label("Message (optional):"),
            Input(placeholder="Optional message", id="message-input"),
            Static("", id="multisig-tx-error"),
            Horizontal(
                Button("Send", id="submit-multisig-tx", variant="primary"),
                Button("Cancel", id="cancel-multisig-tx"),
                classes="button-row",
            ),
            id="multisig-tx-dialog",
            classes="modal-dialog",
        )

    def on_mount(self) -> None:
        self._refresh_multisig_accounts()

    def _refresh_multisig_accounts(self) -> None:
        info_widget = self.query_one("#multisig-accounts-info", Static)
        if not self.wallet.address:
            info_widget.update("[dim]No wallet loaded[/dim]")
            return

        info = self.multisig_service.get_multisig_account_info(str(self.wallet.address))
        if info is None:
            info_widget.update("[dim]No multisig information available[/dim]")
            return

        self._multisig_info = info

        lines = []
        if info.is_multisig:
            lines.append(
                f"[bold]This account is multisig:[/bold] {info.account_address}"
            )
            lines.append(f"  Min Approval: {info.min_approval}")

        if info.is_cosigner_of:
            lines.append("[bold]You are cosigner of:[/bold]")
            for addr in info.multisig_addresses:
                lines.append(f"  • {addr}")

        info_widget.update(
            "\n".join(lines) if lines else "[dim]No multisig relationships[/dim]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-multisig-tx":
            self.app.pop_screen()
        elif event.button.id == "submit-multisig-tx":
            self._submit_transaction()

    def _submit_transaction(self) -> None:
        error_widget = self.query_one("#multisig-tx-error", Static)
        error_widget.update("")

        multisig_addr = self.query_one("#multisig-address-input", Input).value.strip()
        recipient = self.query_one("#recipient-input", Input).value.strip()
        mosaic_id_str = self.query_one("#mosaic-id-input", Input).value.strip()
        amount_str = self.query_one("#amount-input", Input).value.strip()
        message = self.query_one("#message-input", Input).value.strip()

        if not recipient:
            error_widget.update("[red]Error: Recipient address required[/red]")
            return

        if (
            not multisig_addr
            and self._multisig_info
            and self._multisig_info.is_multisig
        ):
            multisig_addr = self._multisig_info.account_address

        if not multisig_addr:
            error_widget.update("[red]Error: Multisig address required[/red]")
            return

        try:
            if mosaic_id_str.startswith("0x"):
                mosaic_id = int(mosaic_id_str, 16)
            else:
                mosaic_id = int(mosaic_id_str, 16)
        except ValueError:
            error_widget.update("[red]Error: Invalid mosaic ID format[/red]")
            return

        try:
            amount = int(amount_str)
        except ValueError:
            error_widget.update("[red]Error: Amount must be an integer[/red]")
            return

        mosaics = [{"mosaic_id": mosaic_id, "amount": amount}]

        self.post_message(
            self.TransactionRequested(multisig_addr, recipient, mosaics, message)
        )
        self.app.pop_screen()


class PendingMultisigScreen(ModalScreen):
    """Screen for viewing and signing pending multisig transactions."""

    BINDINGS = [("escape", "app.pop_screen", "Close")]

    class CosignRequested(Message):
        """Message sent when cosigning is requested."""

        def __init__(self, tx_hash: str) -> None:
            super().__init__()
            self.tx_hash = tx_hash

    def __init__(
        self,
        wallet: "WalletProtocol",
        multisig_service: Any,
    ):
        super().__init__()
        self.wallet = wallet
        self.multisig_service = multisig_service
        self._pending_transactions: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Container(
            Label("📝 Pending Multisig Transactions", classes="modal-title"),
            Static(
                "Transactions requiring your cosignature will appear here.",
                classes="helper-text",
            ),
            DataTable(id="pending-tx-table"),
            Horizontal(
                Button("🔄 Refresh", id="refresh-pending"),
                Button("✍️ Sign Selected", id="cosign-pending", variant="primary"),
                Button("Close", id="close-pending"),
                classes="button-row",
            ),
            Static("", id="pending-error"),
            id="pending-multisig-dialog",
            classes="modal-dialog",
        )

    def on_mount(self) -> None:
        table = self.query_one("#pending-tx-table", DataTable)
        table.add_columns("Hash", "Signer", "Type", "Status")
        self._refresh_pending()

    def _refresh_pending(self) -> None:
        table = self.query_one("#pending-tx-table", DataTable)
        table.clear()

        pending = self.multisig_service.fetch_partial_transactions()
        self._pending_transactions = pending

        if not pending:
            return

        for tx in pending:
            meta = tx.get("meta", {})
            tx_body = tx.get("transaction", {})
            tx_hash = meta.get("hash", "")[:16] + "..."
            signer = tx_body.get("signerPublicKey", "")[:16] + "..."

            inner_txs = tx_body.get("transactions", [])
            tx_type = "Multisig" if inner_txs else "Other"

            cosigs = tx_body.get("cosignatures", [])
            status = f"{len(cosigs)} signed"

            table.add_row(tx_hash, signer, tx_type, status)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-pending":
            self.app.pop_screen()
        elif event.button.id == "refresh-pending":
            self._refresh_pending()
        elif event.button.id == "cosign-pending":
            self._cosign_selected()

    def _cosign_selected(self) -> None:
        error_widget = self.query_one("#pending-error", Static)
        error_widget.update("")

        table = self.query_one("#pending-tx-table", DataTable)
        cursor = table.cursor_coordinate
        if cursor.row is None or cursor.row < 0:
            error_widget.update("[red]Error: No transaction selected[/red]")
            return

        if cursor.row >= len(self._pending_transactions):
            error_widget.update("[red]Error: Invalid selection[/red]")
            return

        tx = self._pending_transactions[cursor.row]
        meta = tx.get("meta", {})
        tx_hash = meta.get("hash", "")

        if not tx_hash:
            error_widget.update("[red]Error: Could not get transaction hash[/red]")
            return

        self.post_message(self.CosignRequested(tx_hash))
        self.app.pop_screen()
