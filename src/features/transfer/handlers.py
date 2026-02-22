"""Transfer event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, cast

from textual.widgets import Button, DataTable, Input, Static

from src.features.transfer.validators import TransferAmountValidator
from src.features.transfer.screen import (
    BatchTransactionResultScreen,
    MosaicInputScreen,
    SaveTemplateScreen,
    TemplateListScreen,
    TransactionConfirmScreen,
    TransactionQueueScreen,
    TransactionResultScreen,
    TransactionStatusScreen,
)
from src.features.account.screens import QRScannerScreen
from src.shared.network import NetworkError
from src.shared.protocols import WalletProtocol
from src.shared.transaction_queue import QueuedTransaction, TransactionQueue
from src.shared.transaction_template import TemplateStorage, TransactionTemplate
from src.transaction import TransactionManager

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = logging.getLogger(__name__)


class TransferHandlersMixin:
    """Mixin class providing transfer-related event handlers for WalletApp."""

    mosaics: list[dict[str, int]]
    _tx_queue: TransactionQueue | None
    _template_storage: TemplateStorage | None
    _status_screen: TransactionStatusScreen | None
    _transfer_loading_active: bool
    _transfer_loading_step: int
    _transfer_loading_timer: Any
    wallet: WalletProtocol

    def _get_transfer_validator(self) -> TransferAmountValidator:
        return TransferAmountValidator()

    def _set_transfer_actions_enabled(self: "WalletApp", enabled: bool) -> None:
        button_ids = [
            "#send-button",
            "#add-mosaic-button",
            "#remove-mosaic-button",
            "#select-address-button",
        ]
        for button_id in button_ids:
            try:
                cast(Button, self.query_one(button_id)).disabled = not enabled
            except Exception:
                continue

    def _start_transfer_loading(self: "WalletApp", base_text: str) -> None:
        self._transfer_loading_active = True
        self._transfer_loading_step = 0
        frames = ["|", "/", "-", "\\"]
        result_widget = cast(Static, self.query_one("#transfer-result"))
        result_widget.update(f"[yellow]{base_text} {frames[0]}[/yellow]")

        def tick() -> None:
            if not self._transfer_loading_active:
                return
            self._transfer_loading_step = (self._transfer_loading_step + 1) % len(
                frames
            )
            frame = frames[self._transfer_loading_step]
            result_widget.update(f"[yellow]{base_text} {frame}[/yellow]")

        if self._transfer_loading_timer:
            try:
                self._transfer_loading_timer.stop()
            except Exception:
                pass
        self._transfer_loading_timer = self.set_interval(0.15, tick)

    def _stop_transfer_loading(self: "WalletApp") -> None:
        self._transfer_loading_active = False
        if self._transfer_loading_timer:
            try:
                self._transfer_loading_timer.stop()
            except Exception:
                pass
            self._transfer_loading_timer = None

    def send_transaction(self: "WalletApp") -> None:
        recipient = cast(Input, self.query_one("#recipient-input")).value
        message = cast(Input, self.query_one("#message-input")).value
        result = cast(Static, self.query_one("#transfer-result"))

        if not recipient:
            result.update("[red]Error: Please fill recipient address[/red]")
            return

        if not self.mosaics:
            result.update(
                "[red]Error: Please add at least one mosaic using the + button[/red]"
            )
            return

        try:
            tm = TransactionManager(self.wallet, self.wallet.node_url)
            fee = tm.estimate_fee(recipient, self.mosaics, message)
            self.push_screen(
                TransactionConfirmScreen(recipient, self.mosaics, message, fee),
                self._on_transaction_confirmed,
            )
        except ValueError:
            result.update(
                "[red]Error: Invalid mosaic ID or amount. Use hex for mosaic ID.[/red]"
            )
        except Exception as e:
            result.update(f"[red]Error: {str(e)}[/red]")

    def _on_transaction_confirmed(self: "WalletApp", result: Any) -> None:
        if not result:
            return
        recipient = result.get("recipient")
        mosaics = result.get("mosaics")
        message = result.get("message", "")
        if not recipient or not mosaics:
            self.notify("Invalid transaction payload", severity="error")
            return
        self._submit_transaction_async(recipient, mosaics, message)

    def _submit_transaction_async(
        self: "WalletApp", recipient: str, mosaics: list, message: str
    ) -> None:
        self._set_transfer_actions_enabled(False)

        status_screen = TransactionStatusScreen("", self.wallet.network_name)
        self._status_screen = status_screen
        self.push_screen(status_screen)

        def on_status_update(status: str, detail: str) -> None:
            try:
                self.call_from_thread(status_screen.update_status, status, detail)
            except Exception:
                pass

        def worker() -> None:
            try:
                tm = TransactionManager(self.wallet, self.wallet.node_url)
                signed = tm.create_sign_and_announce(recipient, mosaics, message)
                tx_hash = signed["hash"]

                self.call_from_thread(
                    status_screen.update_status,
                    "announced",
                    f"Transaction announced, hash: {tx_hash[:16]}...",
                )

                status = tm.poll_for_transaction_status(
                    tx_hash,
                    on_status_update=on_status_update,
                    timeout_seconds=180,
                    poll_interval_seconds=3,
                )
                self.call_from_thread(
                    self._on_transaction_send_finished, signed, status, None
                )
            except Exception as e:
                self.call_from_thread(
                    self._on_transaction_send_finished, None, None, str(e)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_transaction_send_finished(
        self: "WalletApp",
        signed: dict | None,
        status: dict | None,
        error: str | None,
    ) -> None:
        self._set_transfer_actions_enabled(True)
        result = cast(Static, self.query_one("#transfer-result"))

        if hasattr(self, "_status_screen") and self._status_screen:
            try:
                self.pop_screen()
            except Exception:
                pass
            self._status_screen = None

        if error:
            result.update(f"[red]Error: {error}[/red]")
            return

        if not signed:
            result.update("[red]Error: transaction result is empty[/red]")
            return

        status_group = (status or {}).get("group", "")
        status_code = (status or {}).get("code", "")
        if status_group == "failed" or (status_code and status_code != "Success"):
            code_text = status_code or "Unknown error"
            result.update(f"[red]Transaction failed: {code_text}[/red]")
            return

        self.push_screen(
            TransactionResultScreen(signed["hash"], self.wallet.network_name)
        )
        self.mosaics = []
        self.update_mosaics_table()
        result.update("[green]Transaction confirmed and sent successfully![/green]")

    def remove_selected_mosaic(self: "WalletApp") -> None:
        table = cast(DataTable, self.query_one("#mosaics-table"))
        cursor_row = table.cursor_row
        if cursor_row is None:
            self.notify("Select a mosaic row to remove", severity="warning")
            return
        if 0 <= cursor_row < len(self.mosaics):
            self.mosaics.pop(cursor_row)
            self.update_mosaics_table()
            cast(Static, self.query_one("#transfer-result")).update(
                "[yellow]Mosaic removed from transaction[/yellow]"
            )
        else:
            self.notify("Invalid selected row", severity="warning")

    def add_to_queue(self: "WalletApp") -> None:
        recipient = cast(Input, self.query_one("#recipient-input")).value
        message = cast(Input, self.query_one("#message-input")).value
        result = cast(Static, self.query_one("#transfer-result"))

        if not recipient:
            result.update("[red]Error: Please fill recipient address[/red]")
            return

        if not self.mosaics:
            result.update(
                "[red]Error: Please add at least one mosaic using the + button[/red]"
            )
            return

        try:
            tm = TransactionManager(self.wallet, self.wallet.node_url)
            fee = tm.estimate_fee(recipient, self.mosaics, message)

            queued_tx = QueuedTransaction(
                recipient=recipient,
                mosaics=self.mosaics.copy(),
                message=message,
                estimated_fee=fee,
            )

            if self._tx_queue is None:
                self._tx_queue = TransactionQueue(self.wallet.wallet_dir)

            self._tx_queue.add(queued_tx)

            self.mosaics = []
            cast(Input, self.query_one("#recipient-input")).value = ""
            cast(Input, self.query_one("#message-input")).value = ""
            self.update_mosaics_table()

            result.update(
                f"[green]Transaction added to queue ({self._tx_queue.count()} pending)[/green]"
            )
            self.notify(
                f"Added to queue ({self._tx_queue.count()} transactions pending)",
                severity="information",
            )
        except ValueError as e:
            result.update(f"[red]Error: {str(e)}[/red]")
        except Exception as e:
            result.update(f"[red]Error: {str(e)}[/red]")

    def view_queue(self: "WalletApp") -> None:
        if self._tx_queue is None:
            self._tx_queue = TransactionQueue(self.wallet.wallet_dir)

        if self._tx_queue.is_empty():
            self.notify("Transaction queue is empty", severity="information")
            return

        transactions = self._tx_queue.get_all()
        total_fee = self._tx_queue.get_total_estimated_fee()
        self.push_screen(
            TransactionQueueScreen(transactions, total_fee),
            self._on_queue_screen_dismissed,
        )

    def _on_queue_screen_dismissed(self: "WalletApp", result: Any) -> None:
        pass

    def scan_qr_for_address(self: "WalletApp") -> None:
        self.push_screen(QRScannerScreen())

    def save_template(self: "WalletApp") -> None:
        recipient = cast(Input, self.query_one("#recipient-input")).value
        message = cast(Input, self.query_one("#message-input")).value
        result = cast(Static, self.query_one("#transfer-result"))

        if not recipient:
            result.update("[red]Error: Please fill recipient address first[/red]")
            return

        if not self.mosaics:
            result.update(
                "[red]Error: Please add at least one mosaic to save as template[/red]"
            )
            return

        self.push_screen(SaveTemplateScreen(recipient, self.mosaics.copy(), message))

    def view_templates(self: "WalletApp") -> None:
        if self._template_storage is None:
            self._template_storage = TemplateStorage(self.wallet.wallet_dir)

        templates = self._template_storage.get_all()
        if not templates:
            self.notify("No templates saved yet", severity="information")
            return

        self.push_screen(TemplateListScreen(templates))

    def on_save_template_screen_save_template_requested(
        self: "WalletApp", event: Any
    ) -> None:
        if self._template_storage is None:
            self._template_storage = TemplateStorage(self.wallet.wallet_dir)

        mosaics_copy = []
        for m in event.mosaics:
            mosaics_copy.append(
                {
                    "mosaic_id": m.get("mosaic_id") or m.get("id"),
                    "amount": m.get("amount"),
                }
            )

        template = TransactionTemplate(
            name=event.name,
            recipient=event.recipient,
            mosaics=mosaics_copy,
            message=event.message,
        )
        self._template_storage.add(template)
        self.notify(f"Template '{event.name}' saved!", severity="information")

    def on_template_list_screen_use_template_requested(
        self: "WalletApp", event: Any
    ) -> None:
        template = event.template
        cast(Input, self.query_one("#recipient-input")).value = template.recipient
        cast(Input, self.query_one("#message-input")).value = template.message

        self.mosaics = []
        for m in template.mosaics:
            mosaic_id = m.get("mosaic_id") or m.get("id")
            amount = m.get("amount", 0)
            self.mosaics.append({"mosaic_id": mosaic_id, "amount": amount})

        self.update_mosaics_table()
        cast(Static, self.query_one("#transfer-result")).update(
            f"[green]Template '{template.name}' loaded[/green]"
        )
        self.notify(f"Template '{template.name}' applied", severity="information")

    def on_template_list_screen_delete_template_requested(
        self: "WalletApp", event: Any
    ) -> None:
        if self._template_storage is None:
            self._template_storage = TemplateStorage(self.wallet.wallet_dir)

        if self._template_storage.remove(event.template_id):
            self.notify("Template deleted", severity="information")
            self.view_templates()
        else:
            self.notify("Failed to delete template", severity="error")

    def on_transaction_queue_screen_submit_all_requested(
        self: "WalletApp", event: Any
    ) -> None:
        self._submit_queue_all()

    def on_transaction_queue_screen_remove_requested(
        self: "WalletApp", event: Any
    ) -> None:
        if self._tx_queue and self._tx_queue.remove(event.transaction_id):
            self.notify("Transaction removed from queue", severity="information")
            self.view_queue()
        else:
            self.notify("Failed to remove transaction", severity="error")

    def on_transaction_queue_screen_clear_requested(
        self: "WalletApp", event: Any
    ) -> None:
        if self._tx_queue:
            count = self._tx_queue.clear()
            self.notify(
                f"Cleared {count} transactions from queue", severity="information"
            )

    def _submit_queue_all(self: "WalletApp") -> None:
        if self._tx_queue is None or self._tx_queue.is_empty():
            self.notify("Queue is empty", severity="warning")
            return

        transactions = self._tx_queue.pop_all()
        self._submit_batch_async(transactions)

    def _submit_batch_async(self: "WalletApp", transactions: list) -> None:
        self._set_transfer_actions_enabled(False)
        result = cast(Static, self.query_one("#transfer-result"))
        result.update("[yellow]Submitting batch transactions...[/yellow]")

        def worker() -> None:
            results = []
            tm = TransactionManager(self.wallet, self.wallet.node_url)

            for tx in transactions:
                try:
                    signed = tm.create_sign_and_announce(
                        tx.recipient, tx.mosaics, tx.message
                    )
                    status = tm.poll_for_transaction_status(
                        signed["hash"],
                        timeout_seconds=180,
                        poll_interval_seconds=3,
                    )
                    status_group = (status or {}).get("group", "")
                    status_code = (status or {}).get("code", "")
                    success = status_group == "confirmed" or (
                        status_group != "failed" and status_code == "Success"
                    )
                    results.append(
                        {
                            "recipient": tx.recipient,
                            "success": success,
                            "hash": signed["hash"] if success else "N/A",
                            "error": None,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "recipient": tx.recipient,
                            "success": False,
                            "hash": "N/A",
                            "error": str(e),
                        }
                    )

            self.call_from_thread(self._on_batch_finished, results)

        threading.Thread(target=worker, daemon=True).start()

    def on_mosaic_added(self: "WalletApp", event: Any) -> None:
        mosaic_id = event.mosaic_id
        amount = event.amount
        self._apply_added_mosaic(mosaic_id, amount)

    def _apply_added_mosaic(self: "WalletApp", mosaic_id: int, amount: int) -> None:
        if amount <= 0:
            self.notify("Amount must be greater than zero", severity="warning")
            return

        existing_mosaic = None
        for m in self.mosaics:
            if m["mosaic_id"] == mosaic_id:
                existing_mosaic = m
                break

        if existing_mosaic:
            existing_mosaic["amount"] += amount
        else:
            self.mosaics.append({"mosaic_id": mosaic_id, "amount": amount})

        self.update_mosaics_table()
        cast(Static, self.query_one("#transfer-result")).update(
            "[green]Mosaic added to transaction[/green]"
        )

    def add_mosaic(self: "WalletApp") -> None:
        result_widget = cast(Static, self.query_one("#transfer-result"))
        result_widget.update("[yellow]Fetching mosaics...[/yellow]")

        def worker() -> None:
            try:
                owned_mosaics = self.wallet.get_balance()
                mosaic_list = []
                for m in owned_mosaics:
                    mosaic_id = m.get("id")
                    mosaic_name = self.wallet.get_mosaic_name(mosaic_id)
                    amount = m.get("amount", 0)
                    try:
                        amount = int(amount)
                    except (ValueError, TypeError):
                        amount = 0
                    divisibility = self._get_mosaic_divisibility(mosaic_id)
                    mosaic_list.append(
                        {
                            "id": mosaic_id,
                            "name": mosaic_name,
                            "amount": amount,
                            "divisibility": divisibility,
                            "human_amount": amount / (10**divisibility)
                            if divisibility >= 0
                            else amount,
                        }
                    )

                self.call_from_thread(self._on_mosaic_list_fetched, mosaic_list, None)
            except Exception as e:
                self.call_from_thread(self._on_mosaic_list_fetched, None, e)

        threading.Thread(target=worker, daemon=True).start()

    def _on_mosaic_list_fetched(
        self: "WalletApp", mosaic_list: list | None, error: Exception | None
    ) -> None:
        result_widget = cast(Static, self.query_one("#transfer-result"))

        if error:
            error_msg = (
                self._format_network_error(error)
                if isinstance(error, NetworkError)
                else str(error)
            )
            result_widget.update(f"[red]{error_msg}[/red]")
            return

        if not mosaic_list:
            result_widget.update("[yellow]No owned mosaics found[/yellow]")
            return

        result_widget.update("")
        self.push_screen(MosaicInputScreen(mosaic_list), self._on_mosaic_selected)

    def _get_mosaic_divisibility(self: "WalletApp", mosaic_id: int | None) -> int:
        if mosaic_id is None:
            return 0

        try:
            currency_id = self.wallet.get_currency_mosaic_id()
            if currency_id is not None and mosaic_id == currency_id:
                return self.wallet.XYM_DIVISIBILITY
        except Exception:
            pass

        try:
            info = self.wallet.get_mosaic_info(f"{mosaic_id:016X}")
            if not info:
                return 0
            mosaic_data = info.get("mosaic", info)
            divisibility = mosaic_data.get("divisibility", 0)
            return int(divisibility)
        except Exception:
            return 0

    def _on_mosaic_selected(self: "WalletApp", result: Any) -> None:
        if not result:
            return
        try:
            mosaic_id = int(result["mosaic_id"])
            amount = int(result["amount"])
        except (KeyError, TypeError, ValueError):
            self.notify("Invalid mosaic selection result", severity="error")
            return
        self._apply_added_mosaic(mosaic_id, amount)

    def on_qr_scanner_screen_qr_code_scanned(self: "WalletApp", event: Any) -> None:
        if not event.data:
            self.notify("No data in QR code", severity="warning")
            return

        address = event.data.get("address", "")
        if not address:
            self.notify("No address found in QR code", severity="warning")
            return

        cast(Input, self.query_one("#recipient-input")).value = address
        self.action_switch_tab("transfer")

        mosaics = event.data.get("mosaics")
        if mosaics and isinstance(mosaics, list):
            for m in mosaics:
                mosaic_id = m.get("mosaic_id") or m.get("id")
                amount = m.get("amount", 0)
                if mosaic_id is not None:
                    self.mosaics.append(
                        {"mosaic_id": int(mosaic_id), "amount": int(amount)}
                    )
            self.update_mosaics_table()
            self.notify(
                f"Address and {len(mosaics)} mosaic(s) scanned from QR code",
                severity="information",
            )
        else:
            self.notify("Address scanned from QR code", severity="information")

        message = event.data.get("message")
        if message:
            cast(Input, self.query_one("#message-input")).value = message

    def _on_batch_finished(self: "WalletApp", results: list[dict]) -> None:
        self._set_transfer_actions_enabled(True)
        result = cast(Static, self.query_one("#transfer-result"))

        success_count = sum(1 for r in results if r.get("success"))
        total_count = len(results)

        if success_count == total_count:
            result.update(
                f"[green]All {total_count} transactions completed successfully![/green]"
            )
        else:
            result.update(
                f"[yellow]Batch completed: {success_count}/{total_count} successful[/yellow]"
            )

        self.push_screen(
            BatchTransactionResultScreen(results, self.wallet.network_name)
        )
