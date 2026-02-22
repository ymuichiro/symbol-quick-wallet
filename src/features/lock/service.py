"""Lock transaction service for Symbol Quick Wallet.

Supports hash lock and secret lock transactions for cross-chain swaps and conditional payments.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any, Callable, Protocol, cast

from symbolchain import sc
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.shared.logging import get_logger
from src.shared.network import NetworkClient, NetworkError

logger = get_logger(__name__)

HASH_LOCK_DURATION = 480
HASH_LOCK_AMOUNT = 10_000_000
MAX_SECRET_LOCK_DURATION = 365 * 24 * 60
SECRET_SIZE = 20
PROOF_SIZE = 20


class LockHashAlgorithm(IntEnum):
    SHA3_256 = 0
    HASH_160 = 1
    HASH_256 = 2


@dataclass
class SecretProofPair:
    secret: bytes
    proof: bytes
    algorithm: LockHashAlgorithm = LockHashAlgorithm.SHA3_256

    @classmethod
    def generate(
        cls, algorithm: LockHashAlgorithm = LockHashAlgorithm.SHA3_256
    ) -> "SecretProofPair":
        proof = secrets.token_bytes(PROOF_SIZE)
        if algorithm == LockHashAlgorithm.SHA3_256:
            secret = hashlib.sha3_256(proof).digest()
        elif algorithm == LockHashAlgorithm.HASH_256:
            secret = hashlib.sha256(proof).digest()
        elif algorithm == LockHashAlgorithm.HASH_160:
            secret = hashlib.new("ripemd160", hashlib.sha256(proof).digest()).digest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        return cls(secret=secret, proof=proof, algorithm=algorithm)

    @classmethod
    def from_proof(
        cls, proof: bytes, algorithm: LockHashAlgorithm = LockHashAlgorithm.SHA3_256
    ) -> "SecretProofPair":
        if algorithm == LockHashAlgorithm.SHA3_256:
            secret = hashlib.sha3_256(proof).digest()
        elif algorithm == LockHashAlgorithm.HASH_256:
            secret = hashlib.sha256(proof).digest()
        elif algorithm == LockHashAlgorithm.HASH_160:
            secret = hashlib.new("ripemd160", hashlib.sha256(proof).digest()).digest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        return cls(secret=secret, proof=proof, algorithm=algorithm)

    @property
    def secret_hex(self) -> str:
        return self.secret.hex().upper()

    @property
    def proof_hex(self) -> str:
        return self.proof.hex().upper()


@dataclass
class SecretLockInfo:
    composite_hash: str
    owner_address: str
    recipient_address: str
    mosaic_id: int
    amount: int
    end_height: int
    hash_algorithm: int
    secret: str
    status: int

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "SecretLockInfo":
        lock_data = data.get("lock", data)
        return cls(
            composite_hash=lock_data.get("compositeHash", ""),
            owner_address=lock_data.get("ownerAddress", ""),
            recipient_address=lock_data.get("recipientAddress", ""),
            mosaic_id=int(lock_data.get("mosaicId", "0"), 16)
            if isinstance(lock_data.get("mosaicId"), str)
            else lock_data.get("mosaicId", 0),
            amount=int(lock_data.get("amount", "0")),
            end_height=int(lock_data.get("endHeight", "0")),
            hash_algorithm=lock_data.get("hashAlgorithm", 0),
            secret=lock_data.get("secret", ""),
            status=lock_data.get("status", 0),
        )


@dataclass
class HashLockInfo:
    composite_hash: str
    owner_address: str
    mosaic_id: int
    amount: int
    end_height: int
    hash: str
    status: int

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "HashLockInfo":
        lock_data = data.get("lock", data)
        return cls(
            composite_hash=lock_data.get("compositeHash", ""),
            owner_address=lock_data.get("ownerAddress", ""),
            mosaic_id=int(lock_data.get("mosaicId", "0"), 16)
            if isinstance(lock_data.get("mosaicId"), str)
            else lock_data.get("mosaicId", 0),
            amount=int(lock_data.get("amount", "0")),
            end_height=int(lock_data.get("endHeight", "0")),
            hash=lock_data.get("hash", ""),
            status=lock_data.get("status", 0),
        )


class WalletProtocol(Protocol):
    address: str | None
    public_key: Any
    private_key: Any
    network_name: str
    node_url: str
    facade: SymbolFacade

    def get_currency_mosaic_id(self) -> int | None: ...


class LockService:
    DEFAULT_FEE_MULTIPLIER = 100

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

    def generate_secret_proof(
        self, algorithm: LockHashAlgorithm = LockHashAlgorithm.SHA3_256
    ) -> SecretProofPair:
        return SecretProofPair.generate(algorithm)

    def create_secret_lock(
        self,
        recipient_address: str,
        mosaic_id: int,
        amount: int,
        secret: bytes,
        duration: int,
        algorithm: LockHashAlgorithm = LockHashAlgorithm.SHA3_256,
        fee_multiplier: int = 100,
    ) -> sc.Transaction:
        deadline_timestamp = self._get_deadline_timestamp()

        lock_dict = {
            "type": "secret_lock_transaction_v1",
            "signer_public_key": str(self.wallet.public_key),
            "deadline": deadline_timestamp,
            "recipient_address": self._normalize_address(recipient_address),
            "secret": secret.hex(),
            "mosaic": {"mosaic_id": mosaic_id, "amount": amount},
            "duration": duration,
            "hash_algorithm": algorithm.value,
        }

        tx = self.facade.transaction_factory.create(lock_dict)
        tx.fee = sc.Amount(tx.size * fee_multiplier)

        return tx

    def create_secret_proof(
        self,
        recipient_address: str,
        secret: bytes,
        proof: bytes,
        algorithm: LockHashAlgorithm = LockHashAlgorithm.SHA3_256,
        fee_multiplier: int = 100,
    ) -> sc.Transaction:
        deadline_timestamp = self._get_deadline_timestamp()

        proof_dict = {
            "type": "secret_proof_transaction_v1",
            "signer_public_key": str(self.wallet.public_key),
            "deadline": deadline_timestamp,
            "recipient_address": self._normalize_address(recipient_address),
            "secret": secret.hex(),
            "hash_algorithm": algorithm.value,
            "proof": proof.hex(),
        }

        tx = self.facade.transaction_factory.create(proof_dict)
        tx.fee = sc.Amount(tx.size * fee_multiplier)

        return tx

    def create_hash_lock(
        self,
        aggregate_tx: sc.Transaction,
        lock_amount: int = HASH_LOCK_AMOUNT,
        duration: int = HASH_LOCK_DURATION,
        fee_multiplier: int = 100,
    ) -> sc.Transaction:
        aggregate_hash = self.facade.hash_transaction(aggregate_tx)
        currency_mosaic_id = self.wallet.get_currency_mosaic_id() or 0x6BED913FA20223F8
        deadline_timestamp = self._get_deadline_timestamp()

        lock_dict = {
            "type": "hash_lock_transaction_v1",
            "signer_public_key": str(self.wallet.public_key),
            "deadline": deadline_timestamp,
            "mosaic": {"mosaic_id": currency_mosaic_id, "amount": lock_amount},
            "duration": duration,
            "hash": str(aggregate_hash),
        }

        tx = self.facade.transaction_factory.create(lock_dict)
        tx.fee = sc.Amount(tx.size * fee_multiplier)

        return tx

    def sign_transaction(self, transaction: sc.Transaction) -> sc.Signature:
        account = self.facade.create_account(self.wallet.private_key)
        return account.sign_transaction(transaction)

    def attach_signature(
        self, transaction: sc.Transaction, signature: sc.Signature
    ) -> str:
        return self.facade.transaction_factory.attach_signature(transaction, signature)

    def calculate_transaction_hash(self, transaction: sc.Transaction) -> str:
        return str(self.facade.hash_transaction(transaction))

    def calculate_fee(
        self, transaction: sc.Transaction, fee_multiplier: int = 100
    ) -> int:
        return transaction.size * fee_multiplier

    def announce_transaction(self, signed_payload: str) -> dict[str, Any]:
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

    def create_and_announce_secret_lock(
        self,
        recipient_address: str,
        mosaic_id: int,
        amount: int,
        duration: int,
        algorithm: LockHashAlgorithm = LockHashAlgorithm.SHA3_256,
        fee_multiplier: int = 100,
    ) -> dict[str, Any]:
        secret_proof = self.generate_secret_proof(algorithm)

        lock_tx = self.create_secret_lock(
            recipient_address=recipient_address,
            mosaic_id=mosaic_id,
            amount=amount,
            secret=secret_proof.secret,
            duration=duration,
            algorithm=algorithm,
            fee_multiplier=fee_multiplier,
        )

        signature = self.sign_transaction(lock_tx)
        signed_payload = self.attach_signature(lock_tx, signature)
        tx_hash = self.calculate_transaction_hash(lock_tx)

        result = self.announce_transaction(signed_payload)

        return {
            "hash": tx_hash,
            "secret": secret_proof.secret_hex,
            "proof": secret_proof.proof_hex,
            "algorithm": algorithm.value,
            "api_message": result.get("message", ""),
            "response": result,
        }

    def create_and_announce_secret_proof(
        self,
        recipient_address: str,
        secret: str | bytes,
        proof: str | bytes,
        algorithm: LockHashAlgorithm = LockHashAlgorithm.SHA3_256,
        fee_multiplier: int = 100,
    ) -> dict[str, Any]:
        if isinstance(secret, str):
            secret = bytes.fromhex(secret)
        if isinstance(proof, str):
            proof = bytes.fromhex(proof)

        proof_tx = self.create_secret_proof(
            recipient_address=recipient_address,
            secret=secret,
            proof=proof,
            algorithm=algorithm,
            fee_multiplier=fee_multiplier,
        )

        signature = self.sign_transaction(proof_tx)
        signed_payload = self.attach_signature(proof_tx, signature)
        tx_hash = self.calculate_transaction_hash(proof_tx)

        result = self.announce_transaction(signed_payload)

        return {
            "hash": tx_hash,
            "secret": secret.hex().upper(),
            "proof": proof.hex().upper(),
            "api_message": result.get("message", ""),
            "response": result,
        }

    def create_and_announce_hash_lock(
        self,
        aggregate_tx: sc.Transaction,
        lock_amount: int = HASH_LOCK_AMOUNT,
        duration: int = HASH_LOCK_DURATION,
        fee_multiplier: int = 100,
    ) -> dict[str, Any]:
        hash_lock_tx = self.create_hash_lock(
            aggregate_tx=aggregate_tx,
            lock_amount=lock_amount,
            duration=duration,
            fee_multiplier=fee_multiplier,
        )

        signature = self.sign_transaction(hash_lock_tx)
        signed_payload = self.attach_signature(hash_lock_tx, signature)
        tx_hash = self.calculate_transaction_hash(hash_lock_tx)

        result = self.announce_transaction(signed_payload)

        return {
            "hash": tx_hash,
            "aggregate_hash": self.calculate_transaction_hash(aggregate_tx),
            "lock_amount": lock_amount,
            "duration": duration,
            "api_message": result.get("message", ""),
            "response": result,
        }

    def fetch_secret_locks(self, address: str | None = None) -> list[SecretLockInfo]:
        target_address = address or str(self.wallet.address)
        if not target_address:
            return []

        try:
            params = f"?address={self._normalize_address(target_address)}"
            result = self._network_client.get(
                f"/lock/secret{params}",
                context="Fetch secret locks",
            )

            locks: list[SecretLockInfo] = []
            data = result.get("data", []) if isinstance(result, dict) else result

            for lock_data in cast(list[dict[str, Any]], data):
                try:
                    lock_info = SecretLockInfo.from_api_response(lock_data)
                    locks.append(lock_info)
                except Exception as e:
                    logger.warning("Failed to parse secret lock: %s", e)

            return locks
        except NetworkError as e:
            logger.error("Failed to fetch secret locks: %s", e.message)
            return []

    def fetch_secret_lock_by_secret(self, secret: str) -> SecretLockInfo | None:
        try:
            result = self._network_client.get(
                f"/lock/secret/{secret.strip().upper()}",
                context="Fetch secret lock by secret",
            )

            if result:
                return SecretLockInfo.from_api_response(
                    cast(dict[str, Any], result) if isinstance(result, dict) else {}
                )
            return None
        except NetworkError as e:
            logger.error("Failed to fetch secret lock: %s", e.message)
            return None

    def fetch_hash_locks(self, address: str | None = None) -> list[HashLockInfo]:
        target_address = address or str(self.wallet.address)
        if not target_address:
            return []

        try:
            params = f"?address={self._normalize_address(target_address)}"
            result = self._network_client.get(
                f"/lock/hash{params}",
                context="Fetch hash locks",
            )

            locks: list[HashLockInfo] = []
            data = result.get("data", []) if isinstance(result, dict) else result

            for lock_data in cast(list[dict[str, Any]], data):
                try:
                    lock_info = HashLockInfo.from_api_response(lock_data)
                    locks.append(lock_info)
                except Exception as e:
                    logger.warning("Failed to parse hash lock: %s", e)

            return locks
        except NetworkError as e:
            logger.error("Failed to fetch hash locks: %s", e.message)
            return []

    def fetch_hash_lock_by_hash(self, tx_hash: str) -> HashLockInfo | None:
        try:
            result = self._network_client.get(
                f"/lock/hash/{tx_hash.strip().upper()}",
                context="Fetch hash lock by hash",
            )

            if result:
                return HashLockInfo.from_api_response(
                    cast(dict[str, Any], result) if isinstance(result, dict) else {}
                )
            return None
        except NetworkError as e:
            logger.error("Failed to fetch hash lock: %s", e.message)
            return None

    def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout_seconds: int = 120,
        poll_interval: int = 5,
    ) -> dict[str, Any]:
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
