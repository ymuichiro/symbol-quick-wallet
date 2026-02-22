"""Lock transaction event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from src.shared.logging import get_logger
from src.features.lock.screen import (
    LockResultScreen,
    LocksOverviewScreen,
    SecretLockCreateScreen,
    SecretProofCreateScreen,
)
from src.features.lock.service import (
    LockService,
)
from src.screens import LoadingScreen
from src.shared.protocols import WalletProtocol

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = get_logger(__name__)


class LockHandlersMixin:
    """Mixin class providing lock-related event handlers for WalletApp."""

    wallet: WalletProtocol
    is_authenticated: bool
    _lock_service: LockService | None = None

    def _get_lock_service(self: "WalletApp") -> LockService:
        if self._lock_service is None:
            self._lock_service = LockService(self.wallet, self.wallet.node_url)
        return self._lock_service

    def show_lock_menu(self: "WalletApp") -> None:
        class LockMenuScreen(ModalScreen):
            BINDINGS = [("escape", "app.pop_screen", "Close")]

            def compose(self):
                yield Label("🔐 Lock Transactions")
                yield Vertical(
                    Button("Create Secret Lock", id="create-secret-lock-btn"),
                    Button("Claim Secret Lock", id="claim-secret-lock-btn"),
                    Button("View Locks", id="view-locks-btn"),
                    Button("Close", id="close-lock-menu-btn"),
                )

            def on_button_pressed(self, event):
                if not isinstance(event.button, Button):
                    return
                button_id = event.button.id
                if button_id == "create-secret-lock-btn":
                    self.app.pop_screen()
                    self.app.show_create_secret_lock()
                elif button_id == "claim-secret-lock-btn":
                    self.app.pop_screen()
                    self.app.show_claim_secret_lock()
                elif button_id == "view-locks-btn":
                    self.app.pop_screen()
                    self.app.show_locks_overview()
                elif button_id == "close-lock-menu-btn":
                    self.app.pop_screen()

        self.push_screen(LockMenuScreen())

    def show_create_secret_lock(self: "WalletApp") -> None:
        self._get_lock_service()
        loading_screen = LoadingScreen("Fetching mosaics...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                mosaics = self._fetch_owned_mosaics()
                self.call_from_thread(self._on_mosaics_loaded, mosaics, None)
            except Exception as e:
                self.call_from_thread(self._on_mosaics_loaded, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_owned_mosaics(self: "WalletApp") -> list[dict[str, Any]]:
        mosaics = []
        if not self.wallet.address:
            return mosaics

        try:
            result = self.wallet._network_client.get(
                f"/accounts/{self.wallet.address}",
                context="Fetch account mosaics",
            )
            account_mosaics = result.get("account", {}).get("mosaics", [])
            for m in account_mosaics:
                mosaic_id = m.get("id", m.get("mosaicId", "0"))
                if isinstance(mosaic_id, str):
                    mosaic_id = int(mosaic_id, 16)
                amount = int(m.get("amount", "0"))
                mosaics.append(
                    {
                        "id": mosaic_id,
                        "amount": amount,
                        "name": self.wallet.get_mosaic_name(mosaic_id),
                    }
                )
        except Exception as e:
            logger.error("Failed to fetch mosaics: %s", e)

        return mosaics

    def _on_mosaics_loaded(
        self: "WalletApp", mosaics: list | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to fetch mosaics: {error}", severity="error")
            return

        service = self._get_lock_service()
        self.push_screen(SecretLockCreateScreen(service, mosaics or []))

    def on_create_secret_lock_requested(
        self: "WalletApp", event: SecretLockCreateScreen.CreateSecretLockRequested
    ) -> None:
        loading_screen = LoadingScreen("Creating secret lock...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                result = event.lock_service.create_and_announce_secret_lock(
                    recipient_address=event.recipient_address,
                    mosaic_id=event.mosaic_id,
                    amount=event.amount,
                    duration=event.duration,
                    algorithm=event.algorithm,
                )
                self.call_from_thread(
                    self._on_secret_lock_created,
                    result,
                    event.secret,
                    event.proof,
                    None,
                )
            except Exception as e:
                self.call_from_thread(
                    self._on_secret_lock_created, None, None, None, str(e)
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_secret_lock_created(
        self: "WalletApp",
        result: dict | None,
        secret: str | None,
        proof: str | None,
        error: str | None,
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to create secret lock: {error}", severity="error")
            return

        if result:
            self.push_screen(
                LockResultScreen(
                    tx_hash=result.get("hash"),
                    secret=secret,
                    proof=proof,
                    lock_type="secret_lock",
                    network=self.wallet.network_name,
                )
            )
            self.notify("Secret lock created!", severity="information")

    def show_claim_secret_lock(self: "WalletApp") -> None:
        service = self._get_lock_service()
        self.push_screen(SecretProofCreateScreen(service))

    def on_create_secret_proof_requested(
        self: "WalletApp", event: SecretProofCreateScreen.CreateSecretProofRequested
    ) -> None:
        loading_screen = LoadingScreen("Claiming secret lock...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                result = event.lock_service.create_and_announce_secret_proof(
                    recipient_address=event.recipient_address,
                    secret=event.secret,
                    proof=event.proof,
                    algorithm=event.algorithm,
                )
                self.call_from_thread(self._on_secret_proof_created, result, None)
            except Exception as e:
                self.call_from_thread(self._on_secret_proof_created, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_secret_proof_created(
        self: "WalletApp", result: dict | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to claim secret lock: {error}", severity="error")
            return

        if result:
            self.push_screen(
                LockResultScreen(
                    tx_hash=result.get("hash"),
                    lock_type="secret_proof",
                    network=self.wallet.network_name,
                )
            )
            self.notify("Secret lock claimed successfully!", severity="information")

    def show_locks_overview(self: "WalletApp") -> None:
        service = self._get_lock_service()
        self.push_screen(LocksOverviewScreen(service))

    def on_claim_secret_lock_requested(
        self: "WalletApp", event: LocksOverviewScreen.ClaimSecretLockRequested
    ) -> None:
        if event.lock_service is None:
            self.notify("Lock service not available", severity="error")
            return

        self.pop_screen()
        service = event.lock_service
        self.push_screen(
            SecretProofCreateScreen(service, prefill_secret=event.lock.secret)
        )
