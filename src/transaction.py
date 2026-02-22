from __future__ import annotations

import logging
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, cast

from symbolchain import sc
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.shared.network import NetworkClient, NetworkError
from src.shared.validation import AmountValidator, MosaicIdValidator

logger = logging.getLogger(__name__)


class TransactionManager:
    XYM_MOSAIC_ID = 0x6BED913FA20223F8
    MESSAGE_MAX_BYTES = 1023
    DEFAULT_FEE_MULTIPLIER = 100

    def __init__(self, wallet, node_url="http://sym-test-01.opening-line.jp:3000"):
        self.wallet = wallet
        self.facade = SymbolFacade(wallet.network_name)
        self.node_url = node_url
        self._network_client = NetworkClient(
            node_url=node_url,
            timeout_config=wallet.config.timeout_config
            if hasattr(wallet, "config")
            else None,
            retry_config=wallet.config.retry_config
            if hasattr(wallet, "config")
            else None,
        )

    def _require_wallet_loaded(self) -> None:
        if not self.wallet.private_key or not self.wallet.public_key:
            raise ValueError("Wallet is not loaded")

    @staticmethod
    def _normalize_address(address: str) -> str:
        return address.replace("-", "").strip().upper()

    @staticmethod
    def _normalize_mosaic_id(value: Any) -> int:
        result = MosaicIdValidator.validate(value)
        if not result.is_valid:
            raise ValueError(result.error_message or "Invalid mosaic ID")
        if result.normalized_value is None:
            raise ValueError("Invalid mosaic ID")
        return result.normalized_value

    @staticmethod
    def _normalize_amount(value: Any) -> int:
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("Mosaic amount must be a positive integer")
            return value

        if isinstance(value, str):
            value = value.strip()

        result = AmountValidator.parse_human_amount(str(value))
        if not result.is_valid:
            raise ValueError(result.error_message or "Invalid amount")

        if result.normalized_value is None:
            raise ValueError("Invalid amount")

        return int(result.normalized_value)

    def normalize_mosaics(self, mosaics: list[dict[str, Any]]) -> list[dict[str, int]]:
        aggregated: dict[int, int] = {}
        for mosaic in mosaics:
            if "mosaic_id" not in mosaic:
                raise ValueError("Missing mosaic_id in mosaics")

            mosaic_id = self._normalize_mosaic_id(mosaic["mosaic_id"])
            amount = self._normalize_amount(mosaic.get("amount"))
            aggregated[mosaic_id] = aggregated.get(mosaic_id, 0) + amount

        return [
            {"mosaic_id": mosaic_id, "amount": amount}
            for mosaic_id, amount in sorted(
                aggregated.items(), key=lambda item: item[0]
            )
        ]

    def _normalize_message(self, message: str | None) -> str:
        message_value = (message or "").strip()
        if len(message_value.encode("utf-8")) > self.MESSAGE_MAX_BYTES:
            raise ValueError(
                f"Message is too long. Maximum is {self.MESSAGE_MAX_BYTES} bytes."
            )
        return message_value

    def create_transfer_transaction(self, recipient_address, mosaics, message=""):
        self._require_wallet_loaded()
        deadline_timestamp = self.facade.network.from_datetime(
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).timestamp

        transfer_dict = {
            "type": "transfer_transaction_v1",
            "signer_public_key": str(self.wallet.public_key),
            "deadline": deadline_timestamp,
            "recipient_address": self._normalize_address(recipient_address),
            "mosaics": self.normalize_mosaics(mosaics),
            "message": self._normalize_message(message),
        }

        transfer = self.facade.transaction_factory.create(transfer_dict)
        transfer.fee = sc.Amount(transfer.size * self.DEFAULT_FEE_MULTIPLIER)
        return transfer

    def get_currency_mosaic_id(self) -> int:
        currency_id = self.wallet.get_currency_mosaic_id()
        if currency_id is None:
            return self.XYM_MOSAIC_ID
        return currency_id

    def sign_transaction(self, transaction):
        self._require_wallet_loaded()
        account = self.facade.create_account(self.wallet.private_key)
        return account.sign_transaction(transaction)

    def attach_signature(self, transaction, signature):
        return self.facade.transaction_factory.attach_signature(transaction, signature)

    def calculate_transaction_hash_from_signed_payload(
        self, signed_payload: str
    ) -> str:
        payload_obj = json.loads(signed_payload)
        payload_hex = payload_obj["payload"]
        signed_tx = sc.TransactionFactory.deserialize(bytes.fromhex(payload_hex))
        return str(self.facade.hash_transaction(signed_tx))

    def calculate_fee(self, transaction):
        return transaction.size

    def estimate_fee(self, recipient_address, mosaics, message=""):
        transfer = self.create_transfer_transaction(recipient_address, mosaics, message)
        fee = self.calculate_fee(transfer)
        return fee / 1_000_000

    def announce_transaction(self, signed_payload):
        try:
            result = self._network_client.put(
                "/transactions",
                context="Announce transaction",
                data=signed_payload,
                headers={"Content-Type": "application/json"},
            )
            logger.info(
                "Transaction announced successfully: %s",
                result.get("message", "unknown"),
            )
            return result
        except NetworkError as e:
            logger.error("Failed to announce transaction: %s", e.message)
            raise Exception(e.message) from e

    def _sign_attach_and_announce(self, transaction) -> dict[str, Any]:
        signature = self.sign_transaction(transaction)
        signed_payload = self.attach_signature(transaction, signature)
        tx_hash = self.calculate_transaction_hash_from_signed_payload(signed_payload)
        result = self.announce_transaction(signed_payload)
        return {
            "hash": tx_hash,
            "api_message": result.get("message", ""),
            "response": result,
        }

    def create_sign_and_announce(self, recipient_address, mosaics, message=""):
        transfer = self.create_transfer_transaction(recipient_address, mosaics, message)
        result = self._sign_attach_and_announce(transfer)
        logger.info("Transfer transaction sent to %s", recipient_address)
        return result

    def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout_seconds: int = 120,
        poll_interval_seconds: int = 5,
    ) -> dict[str, Any]:
        return self.wallet.wait_for_transaction_confirmation(
            tx_hash,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    def poll_for_transaction_status(
        self,
        tx_hash: str,
        on_status_update: Callable[[str, str], None] | None = None,
        timeout_seconds: int = 180,
        poll_interval_seconds: int = 3,
    ) -> dict[str, Any]:
        normalized_hash = tx_hash.strip().upper()
        deadline = time.time() + timeout_seconds
        last_status = ""

        while time.time() < deadline:
            try:
                response = self._network_client.post(
                    "/transactionStatus",
                    context="Check transaction status",
                    json={"hashes": [normalized_hash]},
                )
                statuses = cast(
                    list[dict[str, Any]], response if isinstance(response, list) else []
                )
                if statuses:
                    status = statuses[0]
                    group = status.get("group", "")
                    code = status.get("code", "")

                    if group in {"confirmed", "failed"}:
                        if on_status_update:
                            on_status_update(group, code or f"Transaction {group}")
                        return status

                    current_status = f"{group}:{code}" if code else group
                    if current_status != last_status:
                        if on_status_update:
                            on_status_update(group, code or f"Status: {group}")
                        last_status = current_status
            except NetworkError:
                pass

            time.sleep(poll_interval_seconds)

        raise TimeoutError(
            f"Transaction status not found within {timeout_seconds} seconds: {normalized_hash}"
        )

    def create_sign_and_announce_link_harvesting(self, remote_public_key):
        link_tx = self.wallet.link_harvesting_account(remote_public_key)
        result = self._sign_attach_and_announce(link_tx)
        logger.info("Harvesting link transaction sent")
        return result

    def create_sign_and_announce_unlink_harvesting(self):
        link_tx = self.wallet.unlink_harvesting_account()
        result = self._sign_attach_and_announce(link_tx)
        logger.info("Harvesting unlink transaction sent")
        return result

    def create_sign_and_announce_mosaic(
        self,
        supply,
        divisibility=0,
        transferable=True,
        supply_mutable=False,
        revokable=False,
    ):
        mosaic_tx = self.wallet.create_mosaic_transaction(
            supply,
            divisibility,
            transferable,
            supply_mutable,
            revokable,
        )
        result = self._sign_attach_and_announce(mosaic_tx)
        logger.info("Mosaic creation transaction sent: supply=%s", supply)
        return result

    def create_sign_and_announce_root_namespace(
        self,
        name: str,
        duration_blocks: int,
    ) -> dict[str, Any]:
        ns_tx = self.wallet.create_root_namespace_transaction(name, duration_blocks)
        result = self._sign_attach_and_announce(ns_tx)
        logger.info("Root namespace transaction sent: %s", name)
        return result

    def create_sign_and_announce_sub_namespace(
        self,
        name: str,
        parent_name: str,
    ) -> dict[str, Any]:
        ns_tx = self.wallet.create_sub_namespace_transaction(name, parent_name)
        result = self._sign_attach_and_announce(ns_tx)
        logger.info("Sub-namespace transaction sent: %s.%s", parent_name, name)
        return result

    def create_sign_and_announce_address_alias(
        self,
        namespace_name: str,
        address: str,
        link_action: str = "link",
    ) -> dict[str, Any]:
        alias_tx = self.wallet.create_address_alias_transaction(
            namespace_name, address, link_action
        )
        result = self._sign_attach_and_announce(alias_tx)
        logger.info(
            "Address alias transaction sent: %s -> %s, action=%s",
            namespace_name,
            address,
            link_action,
        )
        return result

    def create_sign_and_announce_mosaic_alias(
        self,
        namespace_name: str,
        mosaic_id: int,
        link_action: str = "link",
    ) -> dict[str, Any]:
        alias_tx = self.wallet.create_mosaic_alias_transaction(
            namespace_name, mosaic_id, link_action
        )
        result = self._sign_attach_and_announce(alias_tx)
        logger.info(
            "Mosaic alias transaction sent: %s -> %s, action=%s",
            namespace_name,
            hex(mosaic_id),
            link_action,
        )
        return result
