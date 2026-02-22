"""Lock transaction screens for Symbol Quick Wallet."""

from __future__ import annotations

import logging
from typing import Any, Protocol, cast

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from src.features.lock.service import (
    HashLockInfo,
    LockHashAlgorithm,
    LockService,
    SecretLockInfo,
    SecretProofPair,
)

logger = logging.getLogger(__name__)


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


class LocksOverviewScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("r", "refresh", "Refresh")]

    def __init__(self, lock_service: LockService | None = None):
        super().__init__()
        self.lock_service = lock_service
        self._secret_locks: list[SecretLockInfo] = []
        self._hash_locks: list[HashLockInfo] = []
        self._selected_type = "secret"
        self._selected_hash: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("Lock Transactions Overview", id="locks-title")
        yield Label("Lock Type:")
        yield Select(
            [
                ("Secret Locks", "secret"),
                ("Hash Locks", "hash"),
            ],
            id="lock-type-select",
            value="secret",
        )
        yield Static("Loading locks...", id="locks-status")
        yield DataTable(id="locks-table")
        yield VerticalScroll(Static("", id="lock-details"), id="details-container")
        yield Horizontal(
            Button("Claim Secret Lock", id="claim-button", variant="primary"),
            Button("Refresh", id="refresh-button"),
            Button("Close", id="close-button"),
        )

    def on_mount(self) -> None:
        self._load_locks()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "lock-type-select":
            self._selected_type = str(event.value) if event.value else "secret"
            self._load_locks()

    def _load_locks(self) -> None:
        status_widget = cast(Static, self.query_one("#locks-status"))
        table = cast(DataTable, self.query_one("#locks-table"))

        table.clear()
        table.add_column("Hash", key="hash")
        table.add_column("Amount", key="amount")
        table.add_column("Status", key="status")
        table.add_column("End Height", key="end_height")

        if self.lock_service is None:
            status_widget.update("[red]Lock service not available[/red]")
            return

        try:
            if self._selected_type == "secret":
                self._secret_locks = self.lock_service.fetch_secret_locks()
                self._hash_locks = []

                if not self._secret_locks:
                    status_widget.update("[dim]No secret locks found[/dim]")
                    return

                status_widget.update(
                    f"[green]Found {len(self._secret_locks)} secret lock(s)[/green]"
                )

                for lock in self._secret_locks:
                    hash_short = lock.composite_hash[:16] + "..."
                    amount_xym = lock.amount / 1_000_000
                    status_str = "Active" if lock.status == 0 else "Used"
                    table.add_row(
                        hash_short,
                        f"{amount_xym:.6f}",
                        status_str,
                        str(lock.end_height),
                        key=lock.composite_hash,
                    )
            else:
                self._hash_locks = self.lock_service.fetch_hash_locks()
                self._secret_locks = []

                if not self._hash_locks:
                    status_widget.update("[dim]No hash locks found[/dim]")
                    return

                status_widget.update(
                    f"[green]Found {len(self._hash_locks)} hash lock(s)[/green]"
                )

                for lock in self._hash_locks:
                    hash_short = lock.composite_hash[:16] + "..."
                    amount_xym = lock.amount / 1_000_000
                    status_str = "Active" if lock.status == 0 else "Used"
                    table.add_row(
                        hash_short,
                        f"{amount_xym:.6f}",
                        status_str,
                        str(lock.end_height),
                        key=lock.composite_hash,
                    )

        except Exception as e:
            logger.error("Failed to load locks: %s", e)
            status_widget.update(f"[red]Failed to load: {e}[/red]")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key:
            self._selected_hash = (
                str(event.row_key.value)
                if hasattr(event.row_key, "value")
                else str(event.row_key)
            )
            self._update_details()

    def _update_details(self) -> None:
        details_widget = cast(Static, self.query_one("#lock-details"))

        if not self._selected_hash:
            details_widget.update("")
            return

        if self._selected_type == "secret":
            lock = None
            for sl in self._secret_locks:
                if sl.composite_hash == self._selected_hash:
                    lock = sl
                    break

            if not lock:
                details_widget.update("[dim]Lock not found[/dim]")
                return

            lines = [
                f"[bold]Composite Hash:[/bold] {lock.composite_hash}",
                f"[bold]Owner Address:[/bold] {lock.owner_address}",
                f"[bold]Recipient:[/bold] {lock.recipient_address}",
                f"[bold]Mosaic ID:[/bold] {hex(lock.mosaic_id)}",
                f"[bold]Amount:[/bold] {lock.amount / 1_000_000:.6f}",
                f"[bold]End Height:[/bold] {lock.end_height}",
                f"[bold]Hash Algorithm:[/bold] {LockHashAlgorithm(lock.hash_algorithm).name}",
                f"[bold]Secret:[/bold] {lock.secret}",
                f"[bold]Status:[/bold] {'Active' if lock.status == 0 else 'Used'}",
            ]
        else:
            lock = None
            for hl in self._hash_locks:
                if hl.composite_hash == self._selected_hash:
                    lock = hl
                    break

            if not lock:
                details_widget.update("[dim]Lock not found[/dim]")
                return

            lines = [
                f"[bold]Composite Hash:[/bold] {lock.composite_hash}",
                f"[bold]Owner Address:[/bold] {lock.owner_address}",
                f"[bold]Mosaic ID:[/bold] {hex(lock.mosaic_id)}",
                f"[bold]Amount:[/bold] {lock.amount / 1_000_000:.6f} XYM",
                f"[bold]End Height:[/bold] {lock.end_height}",
                f"[bold]Transaction Hash:[/bold] {lock.hash}",
                f"[bold]Status:[/bold] {'Active' if lock.status == 0 else 'Used'}",
            ]

        details_widget.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "claim-button":
            self._claim_selected()
        elif event.button.id == "refresh-button":
            self._load_locks()
        elif event.button.id == "close-button":
            self.app.pop_screen()

    def action_refresh(self) -> None:
        self._load_locks()

    def _claim_selected(self) -> None:
        if not self._selected_hash:
            self.notify("Please select a lock first", severity="warning")
            return

        if self._selected_type != "secret":
            self.notify("Only secret locks can be claimed", severity="warning")
            return

        lock = None
        for sl in self._secret_locks:
            if sl.composite_hash == self._selected_hash:
                lock = sl
                break

        if not lock:
            self.notify("Selected lock not found", severity="error")
            return

        self.post_message(
            self.ClaimSecretLockRequested(lock=lock, lock_service=self.lock_service)
        )

    class ClaimSecretLockRequested(Message):
        def __init__(self, lock: SecretLockInfo, lock_service: LockService | None):
            super().__init__()
            self.lock = lock
            self.lock_service = lock_service


class SecretLockCreateScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "submit", "Create")]

    def __init__(
        self,
        lock_service: LockService | None = None,
        owned_mosaics: list[dict[str, Any]] | None = None,
    ):
        super().__init__()
        self.lock_service = lock_service
        self.owned_mosaics = owned_mosaics or []
        self._generated_secret: SecretProofPair | None = None

    def compose(self) -> ComposeResult:
        yield Label("Create Secret Lock", id="secret-lock-title")
        yield Label("Recipient Address:")
        yield Input(placeholder="N/A...", id="recipient-input")
        yield Label("Mosaic:")
        mosaic_options = []
        for m in self.owned_mosaics:
            name = m.get("name", hex(m.get("id", 0)))
            balance = m.get("amount", 0) / 1_000_000
            mosaic_options.append((f"{name} ({balance:.6f})", hex(m.get("id", 0))))
        yield Select(
            mosaic_options if mosaic_options else [("(No mosaics)", None)],
            id="mosaic-select",
        )
        yield Label("Amount:")
        yield Input(placeholder="e.g. 1.5", id="amount-input")
        yield Label("Duration (blocks, max 525600):")
        yield Input(placeholder="480 (default ~8h)", id="duration-input", value="480")
        yield Label("Hash Algorithm:")
        yield Select(
            [
                ("SHA3-256 (recommended)", "0"),
                ("HASH-160 (Bitcoin compatible)", "1"),
                ("HASH-256", "2"),
            ],
            id="algorithm-select",
            value="0",
        )
        yield Label("", id="secret-display")
        yield Label("", id="proof-display")
        yield Horizontal(
            Button("Generate Secret/Proof", id="generate-button"),
            Button("Create Lock", id="create-button", variant="primary"),
            Button("Cancel", id="cancel-button"),
        )
        yield Label("", id="validation-error")

    def on_mount(self) -> None:
        self._generate_secret()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "generate-button":
            self._generate_secret()
        elif event.button.id == "create-button":
            self._submit()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    def action_submit(self) -> None:
        self._submit()

    def _generate_secret(self) -> None:
        algo_select = cast(Select, self.query_one("#algorithm-select"))
        algo_value = int(str(algo_select.value) if algo_select.value else "0")
        algorithm = LockHashAlgorithm(algo_value)
        self._generated_secret = SecretProofPair.generate(algorithm)

        secret_display = cast(Label, self.query_one("#secret-display"))
        proof_display = cast(Label, self.query_one("#proof-display"))

        secret_display.update(
            f"[green]Secret:[/green] {self._generated_secret.secret_hex}"
        )
        proof_display.update(
            f"[yellow]Proof (save this!):[/yellow] {self._generated_secret.proof_hex}"
        )

    def _submit(self) -> None:
        if self.lock_service is None:
            self.notify("Lock service not available", severity="error")
            return

        recipient_input = cast(Input, self.query_one("#recipient-input"))
        mosaic_select = cast(Select, self.query_one("#mosaic-select"))
        amount_input = cast(Input, self.query_one("#amount-input"))
        duration_input = cast(Input, self.query_one("#duration-input"))
        algo_select = cast(Select, self.query_one("#algorithm-select"))
        error_label = cast(Label, self.query_one("#validation-error"))

        recipient = recipient_input.value.strip()
        if not recipient:
            error_label.update("Recipient address is required")
            return

        if not mosaic_select.value:
            error_label.update("Please select a mosaic")
            return

        try:
            mosaic_id = int(str(mosaic_select.value), 16)
        except ValueError:
            error_label.update("Invalid mosaic ID")
            return

        try:
            amount = float(amount_input.value.strip())
            amount_micro = int(amount * 1_000_000)
        except ValueError:
            error_label.update("Invalid amount format")
            return

        try:
            duration = int(duration_input.value.strip() or "480")
            if duration > 525600:
                error_label.update("Duration exceeds maximum (525600 blocks)")
                return
        except ValueError:
            error_label.update("Invalid duration format")
            return

        algo_value = int(str(algo_select.value) if algo_select.value else "0")
        algorithm = LockHashAlgorithm(algo_value)

        if (
            self._generated_secret is None
            or self._generated_secret.algorithm != algorithm
        ):
            self._generate_secret()
            error_label.update("Please re-submit after secret generation")
            return

        self.post_message(
            self.CreateSecretLockRequested(
                recipient_address=recipient,
                mosaic_id=mosaic_id,
                amount=amount_micro,
                duration=duration,
                secret=self._generated_secret.secret_hex,
                proof=self._generated_secret.proof_hex,
                algorithm=algorithm,
                lock_service=self.lock_service,
            )
        )

    class CreateSecretLockRequested(Message):
        def __init__(
            self,
            recipient_address: str,
            mosaic_id: int,
            amount: int,
            duration: int,
            secret: str,
            proof: str,
            algorithm: LockHashAlgorithm,
            lock_service: LockService,
        ):
            super().__init__()
            self.recipient_address = recipient_address
            self.mosaic_id = mosaic_id
            self.amount = amount
            self.duration = duration
            self.secret = secret
            self.proof = proof
            self.algorithm = algorithm
            self.lock_service = lock_service


class SecretProofCreateScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("enter", "submit", "Claim")]

    def __init__(
        self,
        lock_service: LockService | None = None,
        prefill_secret: str | None = None,
    ):
        super().__init__()
        self.lock_service = lock_service
        self.prefill_secret = prefill_secret

    def compose(self) -> ComposeResult:
        yield Label("Claim Secret Lock", id="secret-proof-title")
        yield Label("Recipient Address (your address to receive):")
        yield Input(placeholder="Your address...", id="recipient-input")
        yield Label("Secret (from the lock):")
        yield Input(
            placeholder="Hex secret...",
            id="secret-input",
            value=self.prefill_secret or "",
        )
        yield Label("Proof (the preimage):")
        yield Input(placeholder="Hex proof...", id="proof-input")
        yield Label("Hash Algorithm:")
        yield Select(
            [
                ("SHA3-256", "0"),
                ("HASH-160", "1"),
                ("HASH-256", "2"),
            ],
            id="algorithm-select",
            value="0",
        )
        yield Label("", id="validation-error")
        yield Horizontal(
            Button("Claim Lock", id="claim-button", variant="primary"),
            Button("Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "claim-button":
            self._submit()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    def action_submit(self) -> None:
        self._submit()

    def _submit(self) -> None:
        if self.lock_service is None:
            self.notify("Lock service not available", severity="error")
            return

        recipient_input = cast(Input, self.query_one("#recipient-input"))
        secret_input = cast(Input, self.query_one("#secret-input"))
        proof_input = cast(Input, self.query_one("#proof-input"))
        algo_select = cast(Select, self.query_one("#algorithm-select"))
        error_label = cast(Label, self.query_one("#validation-error"))

        recipient = recipient_input.value.strip()
        if not recipient:
            error_label.update("Recipient address is required")
            return

        secret = secret_input.value.strip()
        if not secret:
            error_label.update("Secret is required")
            return

        proof = proof_input.value.strip()
        if not proof:
            error_label.update("Proof is required")
            return

        algo_value = int(str(algo_select.value) if algo_select.value else "0")
        algorithm = LockHashAlgorithm(algo_value)

        self.post_message(
            self.CreateSecretProofRequested(
                recipient_address=recipient,
                secret=secret,
                proof=proof,
                algorithm=algorithm,
                lock_service=self.lock_service,
            )
        )

    class CreateSecretProofRequested(Message):
        def __init__(
            self,
            recipient_address: str,
            secret: str,
            proof: str,
            algorithm: LockHashAlgorithm,
            lock_service: LockService,
        ):
            super().__init__()
            self.recipient_address = recipient_address
            self.secret = secret
            self.proof = proof
            self.algorithm = algorithm
            self.lock_service = lock_service


class LockResultScreen(BaseModalScreen):
    def __init__(
        self,
        tx_hash: str | None = None,
        secret: str | None = None,
        proof: str | None = None,
        lock_type: str = "secret_lock",
        network: str = "testnet",
    ):
        super().__init__()
        self.tx_hash = tx_hash
        self.secret = secret
        self.proof = proof
        self.lock_type = lock_type
        self.network = network

    def compose(self) -> ComposeResult:
        if self.lock_type == "secret_lock":
            yield Label("Secret Lock Created!", id="lock-result-title")
            yield Label("Transaction Hash:")
            if self.tx_hash:
                yield Static(self.tx_hash, id="tx-hash")
            if self.secret:
                yield Label("")
                yield Label("[yellow]Secret (publicly visible):[/yellow]")
                yield Static(self.secret, id="secret-value")
            if self.proof:
                yield Label("")
                yield Label("[red]Proof (SAVE THIS - needed to claim!):[/red]")
                yield Static(self.proof, id="proof-value")
        elif self.lock_type == "secret_proof":
            yield Label("Secret Lock Claimed!", id="lock-result-title")
            yield Label("Transaction Hash:")
            if self.tx_hash:
                yield Static(self.tx_hash, id="tx-hash")
        else:
            yield Label("Hash Lock Created!", id="lock-result-title")
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
            Button("Copy Hash", id="copy-button", variant="primary"),
            Button("Close", id="close-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-button":
            import pyperclip

            if self.tx_hash:
                pyperclip.copy(self.tx_hash)
                self.notify("Transaction hash copied!", severity="information")
            elif self.proof:
                pyperclip.copy(self.proof)
                self.notify("Proof copied!", severity="information")
        elif event.button.id == "close-button":
            self.app.pop_screen()
