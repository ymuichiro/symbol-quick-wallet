from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from symbolchain import sc
from symbolchain.facade.SymbolFacade import SymbolFacade

logger = logging.getLogger(__name__)


class TransactionManager:
    XYM_MOSAIC_ID = 0x6BED913FA20223F8
    MESSAGE_MAX_BYTES = 1023
    DEFAULT_FEE_MULTIPLIER = 100

    def __init__(self, wallet, node_url="http://sym-test-01.opening-line.jp:3000"):
        self.wallet = wallet
        self.facade = SymbolFacade(wallet.network_name)
        self.node_url = node_url

    def _require_wallet_loaded(self) -> None:
        if not self.wallet.private_key or not self.wallet.public_key:
            raise ValueError("Wallet is not loaded")

    @staticmethod
    def _normalize_address(address: str) -> str:
        return address.replace("-", "").strip().upper()

    @staticmethod
    def _normalize_mosaic_id(value: Any) -> int:
        if isinstance(value, int):
            return value

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized.startswith("0x"):
                return int(normalized, 16)
            try:
                return int(normalized, 16)
            except ValueError:
                return int(normalized)

        raise ValueError(f"Unsupported mosaic ID type: {type(value).__name__}")

    @staticmethod
    def _normalize_amount(value: Any) -> int:
        try:
            amount = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid amount: {value}") from exc

        if amount <= 0:
            raise ValueError("Mosaic amount must be positive")

        return amount

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
            for mosaic_id, amount in sorted(aggregated.items(), key=lambda item: item[0])
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

    def calculate_transaction_hash_from_signed_payload(self, signed_payload: str) -> str:
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
            url = f"{self.node_url}/transactions"
            response = requests.put(
                url,
                data=signed_payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            if response.content:
                try:
                    result = response.json()
                except ValueError:
                    result = {"message": response.text}
            else:
                result = {"message": ""}
            logger.info(
                "Transaction announced successfully: %s",
                result.get("message", "unknown"),
            )
            return result
        except requests.exceptions.Timeout as exc:
            logger.error("Connection timeout announcing transaction: %s", self.node_url)
            raise Exception(
                f"Connection timeout. Node may be unavailable: {self.node_url}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Cannot connect to node: %s", self.node_url)
            raise Exception(
                f"Cannot connect to node: {self.node_url}. Check your network connection."
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "?"
            error_detail = (
                exc.response.text
                if exc.response is not None and exc.response.text
                else "Unknown error"
            )
            logger.error("HTTP error announcing transaction: %s", status_code)
            raise Exception(f"HTTP error {status_code}: {error_detail}") from exc
        except Exception as exc:
            logger.error("Failed to announce transaction: %s", str(exc))
            raise Exception(f"Failed to announce transaction: {str(exc)}") from exc

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

    def wait_for_transaction_status(
        self,
        tx_hash: str,
        timeout_seconds: int = 180,
        poll_interval_seconds: int = 5,
    ) -> dict[str, Any]:
        import time

        normalized_hash = tx_hash.strip().upper()
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            response = requests.post(
                f"{self.node_url}/transactionStatus",
                json={"hashes": [normalized_hash]},
                timeout=10,
            )
            response.raise_for_status()
            statuses = response.json()
            if statuses:
                status = statuses[0]
                if status.get("group") in {"confirmed", "failed"}:
                    return status
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
