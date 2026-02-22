"""Mosaic event handlers for Symbol Quick Wallet TUI."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, cast

from textual.widgets import DataTable

from src.screens import (
    CreateMosaicScreen,
    LoadingScreen,
    MosaicMetadataScreen,
    TransactionResultScreen,
)
from src.shared.protocols import WalletProtocol
from src.transaction import TransactionManager

if TYPE_CHECKING:
    from src.__main__ import WalletApp

logger = logging.getLogger(__name__)


class MosaicHandlersMixin:
    """Mixin class providing mosaic-related event handlers for WalletApp."""

    wallet: WalletProtocol
    mosaics: list[dict[str, int]]
    is_authenticated: bool

    def show_create_mosaic_dialog(self: "WalletApp") -> None:
        self.push_screen(CreateMosaicScreen())

    def on_create_mosaic_dialog_submitted(self: "WalletApp", event: Any) -> None:
        try:
            tm = TransactionManager(self.wallet, self.wallet.node_url)
            result = tm.create_sign_and_announce_mosaic(
                event.supply,
                event.divisibility,
                event.transferable,
                event.supply_mutable,
                event.revokable,
            )
            self.push_screen(
                TransactionResultScreen(result["hash"], self.wallet.network_name)
            )
            self.notify(
                "Mosaic created successfully!",
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
            self.notify(f"Error creating mosaic: {error_msg}", severity="error")

    def update_mosaics_table(self: "WalletApp") -> None:
        logger.info("")
        logger.info(
            "[update_mosaics_table] ========== UPDATE MOSAICS TABLE STARTED =========="
        )
        logger.info(f"[update_mosaics_table] is_authenticated: {self.is_authenticated}")
        logger.info(f"[update_mosaics_table] Number of mosaics: {len(self.mosaics)}")

        logger.info("[update_mosaics_table] Step 1: Querying mosaics-table widget")
        try:
            table = cast(DataTable, self.query_one("#mosaics-table"))
            logger.info("[update_mosaics_table] Step 1: mosaics-table widget found")
        except Exception as e:
            logger.error(
                f"[update_mosaics_table] Step 1: ERROR finding mosaics-table: {e}",
                exc_info=True,
            )
            return

        logger.info("[update_mosaics_table] Step 2: Clearing table columns")
        try:
            table.clear(columns=True)
            logger.info("[update_mosaics_table] Step 2: Table columns cleared")
        except Exception as e:
            logger.error(
                f"[update_mosaics_table] Step 2: ERROR clearing columns: {e}",
                exc_info=True,
            )
            return

        logger.info("[update_mosaics_table] Step 3: Adding table columns")
        try:
            table.add_column("Mosaic", key="mosaic")
            table.add_column("Amount", key="amount")
            table.add_column("Mosaic ID", key="mosaic_id")
            logger.info("[update_mosaics_table] Step 3: Table columns added")
        except Exception as e:
            logger.error(
                f"[update_mosaics_table] Step 3: ERROR adding columns: {e}",
                exc_info=True,
            )
            return

        logger.info(
            f"[update_mosaics_table] Step 4: Adding {len(self.mosaics)} mosaic rows"
        )
        for idx, mosaic in enumerate(self.mosaics):
            try:
                amount_units = f"{mosaic['amount'] / 1_000_000:,.6f} units"
                mosaic_name = self.wallet.get_mosaic_name(mosaic["mosaic_id"])
                logger.info(
                    f"[update_mosaics_table] Adding row {idx + 1}: {mosaic_name} = {amount_units}"
                )
                table.add_row(
                    mosaic_name,
                    amount_units,
                    hex(mosaic["mosaic_id"]),
                    key=str(mosaic["mosaic_id"]),
                )
            except Exception as e:
                logger.error(
                    f"[update_mosaics_table] ERROR adding row {idx + 1}: {e}",
                    exc_info=True,
                )

        logger.info(
            "[update_mosaics_table] ========== UPDATE MOSAICS TABLE COMPLETED =========="
        )
        logger.info("")

    def on_data_table_row_selected(
        self: "WalletApp", event: DataTable.RowSelected
    ) -> None:
        if event.data_table.id == "balance-table":
            self._show_mosaic_metadata_from_table(event)

    def _show_mosaic_metadata_from_table(self: "WalletApp", event: Any) -> None:
        try:
            balance_table = cast(DataTable, self.query_one("#balance-table"))
            cursor_row = balance_table.cursor_row
            if cursor_row is None:
                return

            mosaics = self.wallet.get_balance()
            if cursor_row >= len(mosaics):
                return

            selected_mosaic = mosaics[cursor_row]
            mosaic_id = selected_mosaic.get("id")
            if mosaic_id is None:
                return

            self._show_mosaic_metadata(mosaic_id)
        except Exception as e:
            logger.error(f"Error showing mosaic metadata: {e}")
            self.notify(f"Failed to load mosaic info: {e}", severity="error")

    def _show_mosaic_metadata(self: "WalletApp", mosaic_id: int) -> None:
        loading_screen = LoadingScreen("Loading mosaic info...")
        self.push_screen(loading_screen)

        def worker() -> None:
            try:
                mosaic_info = self.wallet.get_mosaic_full_info(mosaic_id)
                self.call_from_thread(
                    self._on_mosaic_metadata_loaded, mosaic_info, None
                )
            except Exception as e:
                self.call_from_thread(self._on_mosaic_metadata_loaded, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_mosaic_metadata_loaded(
        self: "WalletApp", mosaic_info: dict | None, error: str | None
    ) -> None:
        try:
            self.pop_screen()
        except Exception:
            pass

        if error:
            self.notify(f"Failed to load mosaic info: {error}", severity="error")
            return

        if mosaic_info:
            self.push_screen(MosaicMetadataScreen(mosaic_info))
