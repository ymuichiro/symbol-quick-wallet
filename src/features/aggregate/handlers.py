"""Aggregate transaction event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from symbolchain import sc

from src.features.aggregate.service import (
    AggregateService,
    PartialTransactionInfo,
)
from src.features.aggregate.screen import (
    AggregateBuilderScreen,
    AggregateResultScreen,
    AggregateStatusScreen,
    CosignConfirmScreen,
    InnerTransactionInputScreen,
    PartialTransactionsScreen,
)
from src.shared.logging import get_logger
from src.shared.protocols import WalletProtocol

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = get_logger(__name__)


class AggregateHandlersMixin:
    """Mixin class providing aggregate-related event handlers for WalletApp."""

    wallet: WalletProtocol
    _aggregate_service: AggregateService | None = None

    def _get_aggregate_service(self: "WalletApp") -> AggregateService:
        """Get or create the aggregate service."""
        if self._aggregate_service is None:
            self._aggregate_service = AggregateService(self.wallet)
        return self._aggregate_service

    def show_aggregate_menu(self: "WalletApp") -> None:
        """Show the aggregate transaction menu."""
        service = self._get_aggregate_service()
        mosaics = getattr(self, "mosaics", [])
        self.push_screen(AggregateBuilderScreen(service, mosaics))

    def show_partial_transactions(self: "WalletApp") -> None:
        """Show pending partial transactions requiring cosignatures."""
        service = self._get_aggregate_service()
        self.push_screen(PartialTransactionsScreen(service))

    def on_aggregate_builder_screen_add_inner_transaction_requested(
        self: "WalletApp", event: Any
    ) -> None:
        """Handle request to add an inner transaction."""
        logger.info("Add inner transaction requested")
        mosaics = getattr(self, "mosaics", [])
        self.push_screen(InnerTransactionInputScreen(mosaics))

    def on_inner_transaction_input_screen_dismiss(
        self: "WalletApp", result: dict[str, Any] | None
    ) -> None:
        """Handle inner transaction input completion."""
        if result is None:
            return

        logger.info(f"Inner transaction added: recipient={result.get('recipient', '')}")

        for screen in reversed(self.screen_stack):
            if isinstance(screen, AggregateBuilderScreen):
                screen.add_inner_transaction(result)
                break

    def on_aggregate_builder_screen_create_aggregate_requested(
        self: "WalletApp", event: Any
    ) -> None:
        """Handle request to create an aggregate transaction."""
        logger.info(f"Create aggregate requested: type={event.agg_type}")
        logger.info(f"Inner transactions: {len(event.inner_txs)}")

        service = event.aggregate_service
        inner_txs = event.inner_txs
        agg_type = event.agg_type

        if agg_type == "complete":
            self._create_aggregate_complete(service, inner_txs)
        else:
            self._create_aggregate_bonded(service, inner_txs)

    def _create_aggregate_complete(
        self: "WalletApp", service: AggregateService, inner_txs: list[dict[str, Any]]
    ) -> None:
        """Create and announce an aggregate complete transaction."""

        def worker() -> None:
            try:
                embedded_txs = []
                for tx_data in inner_txs:
                    embedded = service.create_embedded_transfer(
                        signer_public_key=str(self.wallet.public_key),
                        recipient_address=tx_data["recipient"],
                        mosaics=tx_data.get("mosaics", []),
                        message=tx_data.get("message", ""),
                    )
                    embedded_txs.append(embedded)

                result = service.create_and_announce_aggregate_complete(
                    embedded_txs, fee_multiplier=100
                )
                self.call_from_thread(
                    self._on_aggregate_complete_announced, result, None
                )
            except Exception as e:
                logger.error(f"Failed to create aggregate complete: {e}")
                self.call_from_thread(
                    self._on_aggregate_complete_announced, None, str(e)
                )

        self.notify(
            "Creating aggregate complete transaction...", severity="information"
        )
        threading.Thread(target=worker, daemon=True).start()

    def _on_aggregate_complete_announced(
        self: "WalletApp",
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Handle aggregate complete announcement completion."""
        if error:
            self.notify(f"Aggregate complete failed: {error}", severity="error")
            return

        if result:
            tx_hash = result.get("hash", "unknown")
            self.notify(
                f"Aggregate complete announced: {tx_hash[:16]}...",
                severity="information",
            )
            self.push_screen(
                AggregateResultScreen(
                    tx_hash=tx_hash,
                    network=self.wallet.network_name,
                    is_bonded=False,
                )
            )

    def _create_aggregate_bonded(
        self: "WalletApp", service: AggregateService, inner_txs: list[dict[str, Any]]
    ) -> None:
        """Create and announce an aggregate bonded transaction with hash lock."""

        def on_status_update(stage: str, message: str) -> None:
            self.call_from_thread(
                self.notify,
                f"[{stage}] {message}",
                severity="information",
                timeout=3,
            )

        def worker() -> None:
            try:
                embedded_txs = []
                for tx_data in inner_txs:
                    embedded = service.create_embedded_transfer(
                        signer_public_key=str(self.wallet.public_key),
                        recipient_address=tx_data["recipient"],
                        mosaics=tx_data.get("mosaics", []),
                        message=tx_data.get("message", ""),
                    )
                    embedded_txs.append(embedded)

                result = service.create_and_announce_aggregate_bonded(
                    embedded_txs,
                    fee_multiplier=100,
                    wait_for_hash_lock=True,
                    timeout_seconds=120,
                    on_status_update=on_status_update,
                )
                self.call_from_thread(self._on_aggregate_bonded_announced, result, None)
            except Exception as e:
                logger.error(f"Failed to create aggregate bonded: {e}")
                self.call_from_thread(self._on_aggregate_bonded_announced, None, str(e))

        self.notify("Creating aggregate bonded transaction...", severity="information")
        threading.Thread(target=worker, daemon=True).start()

    def _on_aggregate_bonded_announced(
        self: "WalletApp",
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Handle aggregate bonded announcement completion."""
        if error:
            self.notify(f"Aggregate bonded failed: {error}", severity="error")
            return

        if result:
            hash_lock_hash = result.get("hash_lock_hash", "unknown")
            aggregate_hash = result.get("aggregate_hash", "unknown")
            self.notify(
                f"Aggregate bonded announced!\nHash lock: {hash_lock_hash[:16]}...\nAggregate: {aggregate_hash[:16]}...",
                severity="information",
                timeout=10,
            )
            self.push_screen(
                AggregateResultScreen(
                    hash_lock_hash=hash_lock_hash,
                    aggregate_hash=aggregate_hash,
                    network=self.wallet.network_name,
                    is_bonded=True,
                )
            )

    def on_partial_transactions_screen_cosign_requested(
        self: "WalletApp", event: Any
    ) -> None:
        """Handle cosign request for a partial transaction."""
        partial = event.partial
        service = event.aggregate_service

        logger.info(f"Cosign requested for partial: {partial.hash}")

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self._cosign_partial_transaction(service, partial)

        self.push_screen(CosignConfirmScreen(partial), on_confirm)

    def _cosign_partial_transaction(
        self: "WalletApp", service: AggregateService, partial: PartialTransactionInfo
    ) -> None:
        """Cosign a partial transaction."""

        def worker() -> None:
            try:
                result = service.cosign_partial(partial)
                self.call_from_thread(self._on_cosign_complete, result, None)
            except Exception as e:
                logger.error(f"Failed to cosign partial transaction: {e}")
                self.call_from_thread(self._on_cosign_complete, None, str(e))

        self.notify("Processing cosignature...", severity="information")
        threading.Thread(target=worker, daemon=True).start()

    def _on_cosign_complete(
        self: "WalletApp",
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Handle cosign completion."""
        if error:
            self.notify(f"Cosignature failed: {error}", severity="error")
            return

        if result:
            self.notify(
                "Cosignature announced successfully!",
                severity="information",
            )
