"""Aggregate transaction service for Symbol Quick Wallet.

Supports aggregate complete and bonded transactions for multi-party workflows.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol, cast

from symbolchain import sc
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.shared.network import NetworkClient, NetworkError

logger = logging.getLogger(__name__)

HASH_LOCK_DURATION = 480
HASH_LOCK_AMOUNT = 10_000_000
MAX_INNER_TRANSACTIONS = 100
MAX_COSIGNERS = 25


@dataclass
class InnerTransaction:
    """Represents an inner transaction for aggregate transactions."""

    type: str
    signer_public_key: str
    recipient_address: str | None = None
    mosaics: list[dict[str, int]] = field(default_factory=list)
    message: str = ""
    message_hex: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CosignerInfo:
    """Information about a cosigner for aggregate transactions."""

    public_key: str
    address: str
    has_signed: bool = False


@dataclass
class AggregateTransactionInfo:
    """Information about an aggregate transaction."""

    hash: str
    type: str
    signer_public_key: str
    deadline: int
    max_fee: int
    inner_transactions: list[InnerTransaction] = field(default_factory=list)
    cosignatures: list[dict[str, str]] = field(default_factory=list)
    required_cosigners: list[CosignerInfo] = field(default_factory=list)
    status: str = "pending"
    height: int | None = None


@dataclass
class PartialTransactionInfo:
    """Information about a partial (pending cosignature) transaction."""

    hash: str
    signer_public_key: str
    deadline: int
    inner_transactions: list[InnerTransaction] = field(default_factory=list)
    cosignatures: list[dict[str, str]] = field(default_factory=list)
    missing_cosigners: list[str] = field(default_factory=list)
    expires_in: int = 0


class WalletProtocol(Protocol):
    """Protocol defining wallet interface needed for aggregate transactions."""

    address: str | None
    public_key: Any
    private_key: Any
    network_name: str
    node_url: str
    facade: SymbolFacade

    def get_currency_mosaic_id(self) -> int | None: ...


class AggregateService:
    """Service for handling aggregate transaction operations."""

    DEFAULT_FEE_MULTIPLIER = 100
    SIZE_PER_COSIGNATURE = 104

    def __init__(self, wallet: WalletProtocol, node_url: str | None = None):
        self.wallet = wallet
        self.facade = wallet.facade
        self.node_url = node_url or wallet.node_url
        self._network_client = NetworkClient(node_url=self.node_url)

    def _normalize_address(self, address: str) -> str:
        return address.replace("-", "").strip().upper()

    def _get_deadline_timestamp(self, hours: int = 2) -> int:
        return self.facade.network.from_datetime(
            datetime.now(timezone.utc) + timedelta(hours=hours)
        ).timestamp

    def create_embedded_transfer(
        self,
        signer_public_key: str,
        recipient_address: str,
        mosaics: list[dict[str, int]],
        message: str = "",
    ) -> sc.EmbeddedTransaction:
        """Create an embedded transfer transaction for use in aggregate."""
        mosaic_descriptors = []
        for mosaic in mosaics:
            mosaic_id = mosaic.get("mosaic_id", mosaic.get("id", 0))
            amount = mosaic.get("amount", 0)
            mosaic_descriptors.append(
                sc.UnresolvedMosaicDescriptor(
                    mosaic_id=sc.UnresolvedMosaicId(mosaic_id),
                    amount=sc.Amount(amount),
                )
            )

        message_bytes = message.encode("utf-8") if message else b""
        if message_bytes:
            message_bytes = b"\x00" + message_bytes

        descriptor = sc.TransferTransactionV1Descriptor(
            recipient_address=sc.UnresolvedAddress(
                self._normalize_address(recipient_address)
            ),
            mosaics=mosaic_descriptors,
            message=message_bytes,
        )

        return self.facade.create_embedded_transaction_from_descriptor(
            descriptor, sc.PublicKey(signer_public_key)
        )

    def create_aggregate_complete(
        self,
        inner_transactions: list[sc.EmbeddedTransaction],
        fee_multiplier: int = 100,
        required_cosigners: int = 0,
    ) -> sc.Transaction:
        """Create an aggregate complete transaction.

        All required signatures must be collected before announcement.
        """
        transactions_hash = self.facade.hash_embedded_transactions(inner_transactions)

        descriptor = sc.AggregateCompleteTransactionV2Descriptor(
            transactions_hash=transactions_hash,
            transactions=inner_transactions,
        )

        tx = self.facade.create_transaction_from_descriptor(
            descriptor,
            sc.PublicKey(str(self.wallet.public_key)),
            sc.Amount(fee_multiplier),
            60 * 60 * 2,
            required_cosigners,
        )

        return tx

    def create_aggregate_bonded(
        self,
        inner_transactions: list[sc.EmbeddedTransaction],
        fee_multiplier: int = 100,
    ) -> sc.Transaction:
        """Create an aggregate bonded transaction.

        This requires a hash lock before announcement and collects cosignatures after.
        """
        transactions_hash = self.facade.hash_embedded_transactions(inner_transactions)

        descriptor = sc.AggregateBondedTransactionV2Descriptor(
            transactions_hash=transactions_hash,
            transactions=inner_transactions,
        )

        tx = self.facade.create_transaction_from_descriptor(
            descriptor,
            sc.PublicKey(str(self.wallet.public_key)),
            sc.Amount(fee_multiplier),
            60 * 60 * 2,
            0,
        )

        return tx

    def create_hash_lock(
        self,
        aggregate_tx: sc.Transaction,
        lock_amount: int = HASH_LOCK_AMOUNT,
        duration: int = HASH_LOCK_DURATION,
        fee_multiplier: int = 100,
    ) -> sc.Transaction:
        """Create a hash lock transaction for aggregate bonded.

        The hash lock locks funds to allow announcing the aggregate bonded transaction.
        """
        aggregate_hash = self.facade.hash_transaction(aggregate_tx)

        currency_mosaic_id = self.wallet.get_currency_mosaic_id() or 0x6BED913FA20223F8

        mosaic_descriptor = sc.UnresolvedMosaicDescriptor(
            mosaic_id=sc.UnresolvedMosaicId(currency_mosaic_id),
            amount=sc.Amount(lock_amount),
        )

        descriptor = sc.HashLockTransactionV1Descriptor(
            mosaic=mosaic_descriptor,
            duration=sc.BlockDuration(duration),
            hash=sc.Hash256(aggregate_hash.bytes),
        )

        tx = self.facade.create_transaction_from_descriptor(
            descriptor,
            sc.PublicKey(str(self.wallet.public_key)),
            sc.Amount(fee_multiplier),
            60 * 60 * 2,
            0,
        )

        return tx

    def sign_transaction(self, transaction: sc.Transaction) -> sc.Signature:
        """Sign a transaction with the wallet's private key."""
        account = self.facade.create_account(self.wallet.private_key)
        return account.sign_transaction(transaction)

    def cosign_transaction(
        self, transaction: sc.Transaction, signature: sc.Signature | None = None
    ) -> sc.Cosignature:
        """Create a cosignature for an aggregate transaction."""
        account = self.facade.create_account(self.wallet.private_key)
        if signature is None:
            signature = account.sign_transaction(transaction)
        return sc.Cosignature(
            signer_public_key=self.wallet.public_key,
            signature=signature,
        )

    def attach_signature(
        self, transaction: sc.Transaction, signature: sc.Signature
    ) -> str:
        """Attach signature to transaction and return JSON payload."""
        return self.facade.transaction_factory.attach_signature(transaction, signature)

    def attach_cosignature(
        self, transaction: sc.Transaction, cosignature: sc.Cosignature
    ) -> sc.Transaction:
        """Attach a cosignature to an aggregate transaction."""
        if hasattr(transaction, "cosignatures"):
            transaction.cosignatures.append(cosignature)
        return transaction

    def calculate_transaction_hash(self, transaction: sc.Transaction) -> str:
        """Calculate the hash of a transaction."""
        return str(self.facade.hash_transaction(transaction))

    def calculate_fee(
        self,
        transaction: sc.Transaction,
        num_cosignatures: int = 0,
        fee_multiplier: int = 100,
    ) -> int:
        """Calculate the fee for a transaction including cosignatures."""
        base_size = transaction.size
        cosignature_size = num_cosignatures * self.SIZE_PER_COSIGNATURE
        return (base_size + cosignature_size) * fee_multiplier

    def announce_transaction(self, signed_payload: str) -> dict[str, Any]:
        """Announce a signed transaction to the network."""
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
            return cast(dict[str, Any], result)
        except NetworkError as e:
            logger.error("Failed to announce transaction: %s", e.message)
            raise Exception(e.message) from e

    def announce_partial(self, signed_payload: str) -> dict[str, Any]:
        """Announce a partial transaction (aggregate bonded) to the network."""
        try:
            result = self._network_client.put(
                "/transactions/partial",
                context="Announce partial transaction",
                data=signed_payload,
                headers={"Content-Type": "application/json"},
            )
            logger.info(
                "Partial transaction announced successfully: %s",
                result.get("message", "unknown"),
            )
            return cast(dict[str, Any], result)
        except NetworkError as e:
            logger.error("Failed to announce partial transaction: %s", e.message)
            raise Exception(e.message) from e

    def fetch_partial_transactions(
        self, address: str | None = None
    ) -> list[PartialTransactionInfo]:
        """Fetch partial transactions requiring cosignatures.

        If address is provided, filters for transactions requiring that address's signature.
        """
        target_address = address or str(self.wallet.address)
        if not target_address:
            return []

        try:
            params = f"?address={self._normalize_address(target_address)}"
            result = self._network_client.get(
                f"/transactions/partial{params}",
                context="Fetch partial transactions",
            )

            partials: list[PartialTransactionInfo] = []
            data = result.get("data", []) if isinstance(result, dict) else result

            for tx_data in cast(list[dict[str, Any]], data):
                partial = self._parse_partial_transaction(tx_data)
                if partial:
                    partials.append(partial)

            return partials
        except NetworkError as e:
            logger.error("Failed to fetch partial transactions: %s", e.message)
            return []

    def _parse_partial_transaction(
        self, tx_data: dict[str, Any]
    ) -> PartialTransactionInfo | None:
        """Parse API response into PartialTransactionInfo."""
        try:
            meta = tx_data.get("meta", {})
            tx_body = tx_data.get("transaction", {})

            inner_txs = self._parse_inner_transactions(tx_body)

            cosignatures = []
            for cosig in tx_body.get("cosignatures", []):
                cosignatures.append(
                    {
                        "signer_public_key": cosig.get("signerPublicKey", ""),
                        "signature": cosig.get("signature", ""),
                    }
                )

            missing_cosigners = meta.get("cosignatureKeys", [])
            deadline = int(tx_body.get("deadline", 0))
            current_timestamp = self._get_deadline_timestamp(0)
            expires_in = max(0, deadline - current_timestamp)

            return PartialTransactionInfo(
                hash=meta.get("hash", tx_data.get("id", "")),
                signer_public_key=tx_body.get("signerPublicKey", ""),
                deadline=deadline,
                inner_transactions=inner_txs,
                cosignatures=cosignatures,
                missing_cosigners=missing_cosigners,
                expires_in=expires_in,
            )
        except Exception as e:
            logger.warning("Failed to parse partial transaction: %s", e)
            return None

    def _parse_inner_transactions(
        self, tx_body: dict[str, Any]
    ) -> list[InnerTransaction]:
        """Parse inner transactions from aggregate transaction body."""
        inner_txs = []
        transactions = tx_body.get("transactions", [])

        for inner in cast(list[dict[str, Any]], transactions):
            tx_type = inner.get("type", 0)
            signer_pk = inner.get("signerPublicKey", "")

            inner_tx = InnerTransaction(
                type=self._tx_type_to_name(tx_type),
                signer_public_key=signer_pk,
                recipient_address=inner.get("recipientAddress"),
                mosaics=self._parse_mosaics(inner.get("mosaics", [])),
                message=self._parse_message(inner.get("message", "")),
                message_hex=inner.get("message", ""),
                raw_data=inner,
            )
            inner_txs.append(inner_tx)

        return inner_txs

    def _parse_mosaics(self, mosaics: list[dict[str, Any]]) -> list[dict[str, int]]:
        """Parse mosaics from transaction data."""
        result = []
        for mosaic in mosaics:
            mosaic_id = mosaic.get("id", mosaic.get("mosaicId", 0))
            if isinstance(mosaic_id, str):
                mosaic_id = (
                    int(mosaic_id, 16) if mosaic_id.startswith("0x") else int(mosaic_id)
                )
            amount = mosaic.get("amount", 0)
            if isinstance(amount, str):
                amount = int(amount)
            result.append({"mosaic_id": mosaic_id, "amount": amount})
        return result

    def _parse_message(self, message_hex: str) -> str:
        """Parse message from hex string."""
        if not message_hex:
            return ""
        try:
            message_bytes = bytes.fromhex(message_hex)
            if message_bytes and message_bytes[0] == 0x00:
                message_bytes = message_bytes[1:]
            return message_bytes.decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return message_hex

    def _tx_type_to_name(self, tx_type: int | str) -> str:
        """Convert transaction type number to name."""
        if isinstance(tx_type, str):
            return tx_type

        type_names = {
            16724: "transfer",
            16717: "mosaic_definition",
            16973: "mosaic_supply_change",
            16718: "namespace_registration",
            16961: "aggregate_bonded",
            16705: "aggregate_complete",
            16712: "hash_lock",
            16716: "account_key_link",
            16725: "multisig_account_modification",
        }
        return type_names.get(tx_type, f"type_{tx_type}")

    def fetch_partial_by_hash(self, tx_hash: str) -> PartialTransactionInfo | None:
        """Fetch a specific partial transaction by hash."""
        try:
            result = self._network_client.get(
                f"/transactions/partial/{tx_hash.strip().upper()}",
                context="Fetch partial transaction by hash",
            )
            return self._parse_partial_transaction(
                cast(dict[str, Any], result) if isinstance(result, dict) else {}
            )
        except NetworkError as e:
            logger.error("Failed to fetch partial transaction: %s", e.message)
            return None

    def cosign_partial(
        self,
        partial_tx: PartialTransactionInfo,
    ) -> dict[str, Any]:
        """Cosign a partial transaction.

        Returns the cosigned transaction payload ready to announce.
        """
        try:
            result = self._network_client.get(
                f"/transactions/partial/{partial_tx.hash}",
                context="Fetch partial for cosigning",
            )

            if not result:
                raise Exception("Partial transaction not found")

            tx_payload = result.get("transaction", {})
            payload_hex = self._build_cosignature_payload(partial_tx.hash)

            announce_result = self._network_client.put(
                "/transactions/cosignature",
                context="Announce cosignature",
                data=payload_hex,
                headers={"Content-Type": "application/json"},
            )

            logger.info("Cosignature announced for %s", partial_tx.hash)
            return cast(dict[str, Any], announce_result)
        except NetworkError as e:
            logger.error("Failed to cosign partial transaction: %s", e.message)
            raise Exception(e.message) from e

    def _build_cosignature_payload(self, tx_hash: str) -> str:
        """Build cosignature payload for announcing."""
        account = self.facade.create_account(self.wallet.private_key)
        cosig = sc.DetachedCosignature(
            signer_public_key=self.wallet.public_key,
            signature=account.sign(sc.Hash256(bytes.fromhex(tx_hash))),
        )

        payload = {"payload": cosig.serialize().hex()}
        return json.dumps(payload)

    def create_and_announce_aggregate_complete(
        self,
        inner_txs: list[sc.EmbeddedTransaction],
        cosignatures: list[sc.Cosignature] | None = None,
        fee_multiplier: int = 100,
    ) -> dict[str, Any]:
        """Create, sign, and announce an aggregate complete transaction."""
        num_cosignatures = len(cosignatures) if cosignatures else 0
        tx = self.create_aggregate_complete(inner_txs, fee_multiplier, num_cosignatures)

        if cosignatures:
            for cosig in cosignatures:
                tx = self.attach_cosignature(tx, cosig)

        signature = self.sign_transaction(tx)
        signed_payload = self.attach_signature(tx, signature)
        tx_hash = self.calculate_transaction_hash(tx)

        result = self.announce_transaction(signed_payload)
        return {
            "hash": tx_hash,
            "api_message": result.get("message", ""),
            "response": result,
        }

    def create_and_announce_aggregate_bonded(
        self,
        inner_txs: list[sc.EmbeddedTransaction],
        lock_amount: int = HASH_LOCK_AMOUNT,
        fee_multiplier: int = 100,
        wait_for_hash_lock: bool = True,
        timeout_seconds: int = 120,
        on_status_update: Callable[[str, str], None] | None = None,
    ) -> dict[str, Any]:
        """Create, sign, and announce an aggregate bonded transaction with hash lock.

        This is a two-step process:
        1. Announce hash lock transaction
        2. Wait for hash lock confirmation
        3. Announce aggregate bonded transaction
        """
        aggregate_tx = self.create_aggregate_bonded(inner_txs, fee_multiplier)
        aggregate_hash = self.calculate_transaction_hash(aggregate_tx)

        hash_lock_tx = self.create_hash_lock(
            aggregate_tx, lock_amount, HASH_LOCK_DURATION, fee_multiplier
        )

        hash_lock_sig = self.sign_transaction(hash_lock_tx)
        hash_lock_payload = self.attach_signature(hash_lock_tx, hash_lock_sig)
        hash_lock_hash = self.calculate_transaction_hash(hash_lock_tx)

        if on_status_update:
            on_status_update("hash_lock", "Announcing hash lock transaction...")

        hash_lock_result = self.announce_transaction(hash_lock_payload)

        if not hash_lock_result.get("message"):
            raise Exception("Failed to announce hash lock transaction")

        if wait_for_hash_lock:
            if on_status_update:
                on_status_update("hash_lock", "Waiting for hash lock confirmation...")

            self._wait_for_confirmation(hash_lock_hash, timeout_seconds)

        aggregate_sig = self.sign_transaction(aggregate_tx)
        aggregate_payload = self.attach_signature(aggregate_tx, aggregate_sig)

        if on_status_update:
            on_status_update("aggregate", "Announcing aggregate bonded transaction...")

        aggregate_result = self.announce_partial(aggregate_payload)

        return {
            "hash_lock_hash": hash_lock_hash,
            "aggregate_hash": aggregate_hash,
            "hash_lock_response": hash_lock_result,
            "aggregate_response": aggregate_result,
        }

    def _wait_for_confirmation(
        self,
        tx_hash: str,
        timeout_seconds: int = 120,
        poll_interval: int = 5,
    ) -> dict[str, Any]:
        """Wait for a transaction to be confirmed."""
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            try:
                response = self._network_client.post(
                    "/transactionStatus",
                    context="Check transaction status",
                    json={"hashes": [tx_hash.strip().upper()]},
                )
                statuses = cast(
                    list[dict[str, Any]], response if isinstance(response, list) else []
                )
                if statuses:
                    status = statuses[0]
                    group = status.get("group", "")
                    if group == "confirmed":
                        return status
                    if group == "failed":
                        raise Exception(
                            f"Transaction failed: {status.get('code', 'unknown')}"
                        )
            except NetworkError:
                pass

            time.sleep(poll_interval)

        raise TimeoutError(
            f"Transaction not confirmed within {timeout_seconds} seconds"
        )

    def poll_for_transaction_status(
        self,
        tx_hash: str,
        on_status_update: Callable[[str, str], None] | None = None,
        timeout_seconds: int = 180,
        poll_interval_seconds: int = 3,
    ) -> dict[str, Any]:
        """Poll for transaction status until confirmed or failed."""
        deadline = time.time() + timeout_seconds
        last_status = ""

        while time.time() < deadline:
            try:
                response = self._network_client.post(
                    "/transactionStatus",
                    context="Check transaction status",
                    json={"hashes": [tx_hash.strip().upper()]},
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
            f"Transaction status not found within {timeout_seconds} seconds: {tx_hash}"
        )
