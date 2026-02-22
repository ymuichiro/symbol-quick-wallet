"""Multisig account event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from src.features.multisig.service import MultisigService
from src.features.multisig.screen import (
    MultisigManagerScreen,
)
from src.shared.logging import get_logger
from src.shared.protocols import WalletProtocol

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = get_logger(__name__)


class MultisigHandlersMixin:
    """Mixin class providing multisig-related event handlers for WalletApp."""

    wallet: WalletProtocol
    _multisig_service: MultisigService | None = None

    def _get_multisig_service(self: "WalletApp") -> MultisigService:
        """Get or create the multisig service."""
        if self._multisig_service is None:
            self._multisig_service = MultisigService(self.wallet)
        return self._multisig_service

    def show_multisig_manager(self: "WalletApp") -> None:
        """Show the multisig account manager screen."""
        service = self._get_multisig_service()
        self.push_screen(MultisigManagerScreen(self.wallet, service))

    def on_convert_to_multisig_screen_convert_requested(
        self: "WalletApp", event: Any
    ) -> None:
        """Handle convert to multisig request."""
        logger.info("Convert to multisig requested")
        logger.info(f"Cosigners: {event.cosigners}")
        logger.info(f"Min approval: {event.min_approval}")
        logger.info(f"Min removal: {event.min_removal}")

        self.notify(
            "Multisig conversion requires cosigner opt-in signatures.\n"
            "This is a multi-step process - see documentation.",
            severity="information",
            timeout=8,
        )

        service = self._get_multisig_service()

        def worker() -> None:
            try:
                result = service.convert_to_multisig(
                    account_to_convert_public_key=str(self.wallet.public_key),
                    cosigners=event.cosigners,
                    min_approval=event.min_approval,
                    min_removal=event.min_removal,
                )
                self.call_from_thread(
                    self._on_multisig_conversion_complete, result, None
                )
            except Exception as e:
                self.call_from_thread(
                    self._on_multisig_conversion_complete, None, str(e)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_multisig_conversion_complete(
        self: "WalletApp",
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Handle multisig conversion completion."""
        if error:
            self.notify(f"Multisig conversion failed: {error}", severity="error")
            return

        if result:
            tx_hash = result.get("hash", "unknown")
            self.notify(
                f"Multisig conversion announced: {tx_hash[:16]}...\n"
                "Note: Requires cosigner signatures to complete.",
                severity="information",
                timeout=10,
            )

    def on_modify_multisig_screen_modification_requested(
        self: "WalletApp", event: Any
    ) -> None:
        """Handle multisig modification request."""
        logger.info("Modify multisig requested")
        logger.info(f"Approval delta: {event.min_approval_delta}")
        logger.info(f"Removal delta: {event.min_removal_delta}")
        logger.info(f"Additions: {event.address_additions}")
        logger.info(f"Deletions: {event.address_deletions}")

        service = self._get_multisig_service()
        multisig_info = service.get_multisig_account_info(str(self.wallet.address))

        if multisig_info is None or not multisig_info.is_multisig:
            self.notify(
                "This account is not a multisig account",
                severity="error",
            )
            return

        self.notify(
            "Multisig modification requires cosigner approvals.\n"
            f"Current min_approval: {multisig_info.min_approval}",
            severity="information",
            timeout=6,
        )

    def on_multisig_transaction_screen_transaction_requested(
        self: "WalletApp", event: Any
    ) -> None:
        """Handle multisig transaction request."""
        logger.info("Multisig transaction requested")
        logger.info(f"Multisig address: {event.multisig_address}")
        logger.info(f"Recipient: {event.recipient_address}")
        logger.info(f"Mosaics: {event.mosaics}")

        service = self._get_multisig_service()

        def worker() -> None:
            try:
                result = service.initiate_multisig_transaction(
                    multisig_public_key=event.multisig_address,
                    recipient_address=event.recipient_address,
                    mosaics=event.mosaics,
                    message=event.message,
                )
                self.call_from_thread(
                    self._on_multisig_transaction_complete, result, None
                )
            except Exception as e:
                self.call_from_thread(
                    self._on_multisig_transaction_complete, None, str(e)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_multisig_transaction_complete(
        self: "WalletApp",
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Handle multisig transaction completion."""
        if error:
            self.notify(f"Multisig transaction failed: {error}", severity="error")
            return

        if result:
            tx_hash = result.get("hash", "unknown")
            api_msg = result.get("api_message", "")
            self.notify(
                f"Multisig transaction announced: {tx_hash[:16]}...\nStatus: {api_msg}",
                severity="information",
                timeout=10,
            )

    def on_pending_multisig_screen_cosign_requested(
        self: "WalletApp", event: Any
    ) -> None:
        """Handle cosign request for pending transaction."""
        logger.info(f"Cosign requested for: {event.tx_hash}")

        service = self._get_multisig_service()

        def worker() -> None:
            try:
                result = service.cosign_partial_transaction(event.tx_hash)
                self.call_from_thread(self._on_cosign_complete, result, None)
            except Exception as e:
                self.call_from_thread(self._on_cosign_complete, None, str(e))

        threading.Thread(target=worker, daemon=True).start()
        self.notify("Processing cosignature...", severity="information")

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
