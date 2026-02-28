"""Multisig account service for Symbol Quick Wallet.

Supports converting accounts to multisig, adding/removing cosignatories,
setting approval and removal thresholds, and initiating/signing multisig transactions.

Reference: docs/quick_learning_symbol_v3/09_multisig.md
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, cast

from symbolchain import sc

from src.shared.logging import get_logger
from src.shared.network import NetworkClient, NetworkError
from src.shared.protocols import WalletProtocol

logger = get_logger(__name__)

MAX_COSIGNATORIES = 25
MAX_MULTISIG_DEPTH = 3


@dataclass
class CosignerInfo:
    """Information about a cosigner in a multisig account."""

    address: str
    public_key: str = ""
    label: str = ""


@dataclass
class MultisigAccountInfo:
    """Information about a multisig account."""

    account_address: str
    min_approval: int = 0
    min_removal: int = 0
    cosignatory_addresses: list[str] = field(default_factory=list)
    multisig_addresses: list[str] = field(default_factory=list)

    @property
    def is_multisig(self) -> bool:
        return len(self.cosignatory_addresses) > 0

    @property
    def is_cosigner_of(self) -> bool:
        return len(self.multisig_addresses) > 0


class MultisigService:
    """Service for handling multisignature account operations."""

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

    def get_multisig_account_info(self, address: str) -> MultisigAccountInfo | None:
        """Fetch multisig account information from the network."""
        normalized_address = self._normalize_address(address)
        try:
            result = self._network_client.get_optional(
                f"/accounts/{normalized_address}/multisig",
                context="Fetch multisig account info",
            )
            if result is None:
                return None

            multisig_data = result.get("multisig", result)
            if not multisig_data:
                return None

            return MultisigAccountInfo(
                account_address=multisig_data.get("accountAddress", ""),
                min_approval=multisig_data.get("minApproval", 0),
                min_removal=multisig_data.get("minRemoval", 0),
                cosignatory_addresses=multisig_data.get("cosignatoryAddresses", []),
                multisig_addresses=multisig_data.get("multisigAddresses", []),
            )
        except NetworkError as e:
            logger.error("Failed to fetch multisig info: %s", e.message)
            return None

    def create_multisig_modification_embedded(
        self,
        signer_public_key: str,
        min_approval_delta: int,
        min_removal_delta: int,
        address_additions: list[str],
        address_deletions: list[str],
    ) -> sc.EmbeddedTransaction:
        """Create an embedded multisig account modification transaction.

        Args:
            signer_public_key: Public key of the account to convert to/from multisig
            min_approval_delta: Change in minimum approval threshold (-25 to +25)
            min_removal_delta: Change in minimum removal threshold (-25 to +25)
            address_additions: List of cosigner addresses to add
            address_deletions: List of cosigner addresses to remove

        Returns:
            Embedded multisig modification transaction
        """
        multisig_dict = {
            "type": "multisig_account_modification_transaction_v1",
            "signer_public_key": signer_public_key,
            "min_approval_delta": min_approval_delta,
            "min_removal_delta": min_removal_delta,
            "address_additions": [
                self._normalize_address(addr) for addr in address_additions
            ],
            "address_deletions": [
                self._normalize_address(addr) for addr in address_deletions
            ],
        }

        return self.facade.transaction_factory.create_embedded(multisig_dict)

    def create_aggregate_complete_for_multisig(
        self,
        embedded_tx: sc.EmbeddedTransaction,
        fee_multiplier: int = 100,
        required_cosigners: int = 0,
    ) -> sc.Transaction:
        """Create an aggregate complete transaction for multisig modification.

        Args:
            embedded_tx: The embedded multisig modification transaction
            fee_multiplier: Fee multiplier
            required_cosigners: Number of additional cosignatures needed

        Returns:
            Aggregate complete transaction
        """
        deadline_timestamp = self._get_deadline_timestamp()
        transactions_hash = self.facade.hash_embedded_transactions([embedded_tx])

        aggregate_dict = {
            "type": "aggregate_complete_transaction_v2",
            "signer_public_key": str(self.wallet.public_key),
            "deadline": deadline_timestamp,
            "transactions_hash": str(transactions_hash),
            "transactions": [embedded_tx],
        }

        tx = self.facade.transaction_factory.create(aggregate_dict)
        tx.fee = sc.Amount(
            (tx.size + required_cosigners * self.SIZE_PER_COSIGNATURE) * fee_multiplier
        )
        return tx

    def sign_transaction(self, transaction: sc.Transaction) -> sc.Signature:
        """Sign a transaction with the wallet's private key."""
        account = self.facade.create_account(self.wallet.private_key)
        return account.sign_transaction(transaction)

    def cosign_transaction(
        self, transaction: sc.Transaction, detached: bool = False
    ) -> sc.Cosignature:
        """Create a cosignature for an aggregate transaction.

        Args:
            transaction: The transaction to cosign
            detached: If True, create a detached cosignature (for separate announcement)

        Returns:
            Cosignature for the transaction
        """
        account = self.facade.create_account(self.wallet.private_key)
        if detached:
            tx_hash = self.facade.hash_transaction(transaction)
            signature = account.sign(sc.Hash256(tx_hash.bytes))  # pyright: ignore[reportAttributeAccessIssue]
        else:
            signature = account.sign_transaction(transaction)
        cosig = sc.Cosignature()
        cosig._signer_public_key = self.wallet.public_key
        cosig._signature = signature
        return cosig

    def attach_signature(
        self, transaction: sc.Transaction, signature: sc.Signature
    ) -> str:
        """Attach signature to transaction and return JSON payload."""
        return self.facade.transaction_factory.attach_signature(transaction, signature)

    def attach_cosignature(
        self, transaction: sc.Transaction, cosignature: sc.Cosignature
    ) -> sc.Transaction:
        """Attach a cosignature to an aggregate transaction."""
        transaction.cosignatures.append(cosignature)  # type: ignore[union-attr]
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

    def announce_cosignature(self, cosignature_payload: str) -> dict[str, Any]:
        """Announce a cosignature to the network."""
        try:
            result = self._network_client.put(
                "/transactions/cosignature",
                context="Announce cosignature",
                data=cosignature_payload,
                headers={"Content-Type": "application/json"},
            )
            logger.info("Cosignature announced successfully")
            return cast(dict[str, Any], result)
        except NetworkError as e:
            logger.error("Failed to announce cosignature: %s", e.message)
            raise Exception(e.message) from e

    def convert_to_multisig(
        self,
        account_to_convert_public_key: str,
        cosigners: list[str],
        min_approval: int,
        min_removal: int,
        cosigner_accounts: list[Any] | None = None,
        fee_multiplier: int = 100,
    ) -> dict[str, Any]:
        """Convert an account to a multisig account.

        This creates an aggregate complete transaction that:
        1. Adds the specified cosigners
        2. Sets the approval and removal thresholds
        3. Requires all cosigners to sign (opt-in)

        Args:
            account_to_convert_public_key: Public key of account to convert
            cosigners: List of cosigner addresses to add
            min_approval: Minimum approvals required (1-25)
            min_removal: Minimum signatures to remove a cosigner (1-25)
            cosigner_accounts: Optional list of account objects for cosigning
            fee_multiplier: Fee multiplier

        Returns:
            Transaction result with hash and status
        """
        if len(cosigners) > MAX_COSIGNATORIES:
            raise ValueError(f"Maximum {MAX_COSIGNATORIES} cosigners allowed")

        if min_approval < 1 or min_approval > len(cosigners):
            raise ValueError(f"min_approval must be between 1 and {len(cosigners)}")

        if min_removal < 1 or min_removal > len(cosigners):
            raise ValueError(f"min_removal must be between 1 and {len(cosigners)}")

        embedded_multisig = self.create_multisig_modification_embedded(
            signer_public_key=account_to_convert_public_key,
            min_approval_delta=min_approval,
            min_removal_delta=min_removal,
            address_additions=cosigners,
            address_deletions=[],
        )

        num_cosigners = len(cosigners) if cosigner_accounts else 0
        aggregate_tx = self.create_aggregate_complete_for_multisig(
            embedded_multisig, fee_multiplier, num_cosigners
        )

        signature = self.sign_transaction(aggregate_tx)

        if cosigner_accounts:
            for cosigner in cosigner_accounts:
                cosig = sc.Cosignature()
                cosig.signer_public_key = cosigner.public_key
                cosig.signature = cosigner.sign_transaction(aggregate_tx)
                self.attach_cosignature(aggregate_tx, cosig)

        signed_payload = self.attach_signature(aggregate_tx, signature)
        tx_hash = self.calculate_transaction_hash(aggregate_tx)

        result = self.announce_transaction(signed_payload)
        return {
            "hash": tx_hash,
            "api_message": result.get("message", ""),
            "response": result,
        }

    def modify_multisig(
        self,
        multisig_account_public_key: str,
        min_approval_delta: int = 0,
        min_removal_delta: int = 0,
        address_additions: list[str] | None = None,
        address_deletions: list[str] | None = None,
        cosigner_accounts: list[Any] | None = None,
        fee_multiplier: int = 100,
    ) -> dict[str, Any]:
        """Modify an existing multisig account.

        Can add/remove cosigners and adjust thresholds.

        Args:
            multisig_account_public_key: Public key of the multisig account
            min_approval_delta: Change to min approval threshold
            min_removal_delta: Change to min removal threshold
            address_additions: Addresses to add as cosigners
            address_deletions: Addresses to remove from cosigners
            cosigner_accounts: Accounts to sign with (must meet min_approval)
            fee_multiplier: Fee multiplier

        Returns:
            Transaction result
        """
        additions = address_additions or []
        deletions = address_deletions or []

        if (
            not additions
            and not deletions
            and min_approval_delta == 0
            and min_removal_delta == 0
        ):
            raise ValueError("No modifications specified")

        embedded_multisig = self.create_multisig_modification_embedded(
            signer_public_key=multisig_account_public_key,
            min_approval_delta=min_approval_delta,
            min_removal_delta=min_removal_delta,
            address_additions=additions,
            address_deletions=deletions,
        )

        new_cosigners = len([a for a in additions if cosigner_accounts])
        num_cosigners = len(cosigner_accounts) if cosigner_accounts else 0

        aggregate_tx = self.create_aggregate_complete_for_multisig(
            embedded_multisig, fee_multiplier, num_cosigners + new_cosigners
        )

        signature = self.sign_transaction(aggregate_tx)

        if cosigner_accounts:
            for cosigner in cosigner_accounts:
                cosig = sc.Cosignature()
                cosig.signer_public_key = cosigner.public_key
                cosig.signature = cosigner.sign_transaction(aggregate_tx)
                self.attach_cosignature(aggregate_tx, cosig)

        signed_payload = self.attach_signature(aggregate_tx, signature)
        tx_hash = self.calculate_transaction_hash(aggregate_tx)

        result = self.announce_transaction(signed_payload)
        return {
            "hash": tx_hash,
            "api_message": result.get("message", ""),
            "response": result,
        }

    def create_multisig_transfer_embedded(
        self,
        multisig_public_key: str,
        recipient_address: str,
        mosaics: list[dict[str, int]],
        message: str = "",
    ) -> sc.EmbeddedTransaction:
        """Create an embedded transfer transaction from a multisig account.

        Args:
            multisig_public_key: Public key of the multisig account
            recipient_address: Recipient address
            mosaics: List of mosaics to transfer
            message: Optional message

        Returns:
            Embedded transfer transaction
        """
        normalized_mosaics = []
        for mosaic in mosaics:
            mosaic_id = mosaic.get("mosaic_id", mosaic.get("id", 0))
            amount = mosaic.get("amount", 0)
            normalized_mosaics.append({"mosaic_id": mosaic_id, "amount": amount})

        message_bytes = message.encode("utf-8") if message else b""
        if message_bytes:
            message_bytes = b"\x00" + message_bytes

        transfer_dict = {
            "type": "transfer_transaction_v1",
            "signer_public_key": multisig_public_key,
            "recipient_address": self._normalize_address(recipient_address),
            "mosaics": normalized_mosaics,
            "message": message_bytes.hex() if message_bytes else "",
        }

        return self.facade.transaction_factory.create_embedded(transfer_dict)

    def initiate_multisig_transaction(
        self,
        multisig_public_key: str,
        recipient_address: str,
        mosaics: list[dict[str, int]],
        message: str = "",
        cosigner_accounts: list[Any] | None = None,
        min_approval: int = 1,
        fee_multiplier: int = 100,
    ) -> dict[str, Any]:
        """Initiate a transaction from a multisig account.

        Args:
            multisig_public_key: Public key of the multisig account
            recipient_address: Recipient address
            mosaics: Mosaics to transfer
            message: Optional message
            cosigner_accounts: Cosigner accounts (must provide min_approval signatures)
            min_approval: Minimum approvals required
            fee_multiplier: Fee multiplier

        Returns:
            Transaction result
        """
        embedded_transfer = self.create_multisig_transfer_embedded(
            multisig_public_key, recipient_address, mosaics, message
        )

        num_cosigners = len(cosigner_accounts) if cosigner_accounts else 0
        aggregate_tx = self.create_aggregate_complete_for_multisig(
            embedded_transfer, fee_multiplier, num_cosigners
        )

        signature = self.sign_transaction(aggregate_tx)

        if cosigner_accounts:
            for cosigner in cosigner_accounts:
                cosig = sc.Cosignature()
                cosig.signer_public_key = cosigner.public_key
                cosig.signature = cosigner.sign_transaction(aggregate_tx)
                self.attach_cosignature(aggregate_tx, cosig)

        signed_payload = self.attach_signature(aggregate_tx, signature)
        tx_hash = self.calculate_transaction_hash(aggregate_tx)

        result = self.announce_transaction(signed_payload)
        return {
            "hash": tx_hash,
            "api_message": result.get("message", ""),
            "response": result,
        }

    def fetch_partial_transactions(
        self, address: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch partial transactions requiring cosignatures.

        Args:
            address: Optional address to filter by

        Returns:
            List of partial transactions
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

            data = result.get("data", []) if isinstance(result, dict) else result
            return cast(list[dict[str, Any]], data)
        except NetworkError as e:
            logger.error("Failed to fetch partial transactions: %s", e.message)
            return []

    def cosign_partial_transaction(
        self,
        tx_hash: str,
    ) -> dict[str, Any]:
        """Cosign a partial transaction by hash.

        Args:
            tx_hash: Hash of the partial transaction

        Returns:
            Announcement result
        """
        account = self.facade.create_account(self.wallet.private_key)

        cosig = sc.DetachedCosignature()
        cosig._signer_public_key = self.wallet.public_key
        cosig._signature = account.sign(sc.Hash256(bytes.fromhex(tx_hash)))  # pyright: ignore[reportAttributeAccessIssue]

        payload = json.dumps({"payload": cosig.serialize().hex()})

        return self.announce_cosignature(payload)

    def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout_seconds: int = 120,
        poll_interval: int = 5,
        on_status_update: Callable[[str, str], None] | None = None,
    ) -> dict[str, Any]:
        """Wait for a transaction to be confirmed.

        Args:
            tx_hash: Transaction hash
            timeout_seconds: Maximum wait time
            poll_interval: Polling interval
            on_status_update: Optional callback for status updates

        Returns:
            Final transaction status

        Raises:
            TimeoutError: If transaction not confirmed within timeout
        """
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            try:
                response = self._network_client.post(
                    "/transactionStatus",
                    context="Check transaction status",
                    json={"hashes": [tx_hash.strip().upper()]},
                )
                statuses = cast(
                    list[dict[str, Any]],
                    response if isinstance(response, list) else [],
                )
                if statuses:
                    status = statuses[0]
                    group = status.get("group", "")
                    code = status.get("code", "")

                    if group == "confirmed":
                        if on_status_update:
                            on_status_update("confirmed", code)
                        return status

                    if group == "failed":
                        if on_status_update:
                            on_status_update("failed", code)
                        raise Exception(f"Transaction failed: {code}")

                    if on_status_update:
                        on_status_update(group, code or f"Status: {group}")

            except NetworkError:
                pass

            time.sleep(poll_interval)

        raise TimeoutError(
            f"Transaction not confirmed within {timeout_seconds} seconds"
        )

    def validate_multisig_conversion(
        self,
        cosigners: list[str],
        min_approval: int,
        min_removal: int,
    ) -> tuple[bool, str]:
        """Validate multisig conversion parameters.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not cosigners:
            return False, "At least one cosigner is required"

        if len(cosigners) > MAX_COSIGNATORIES:
            return False, f"Maximum {MAX_COSIGNATORIES} cosigners allowed"

        if min_approval < 1:
            return False, "Minimum approval must be at least 1"

        if min_approval > len(cosigners):
            return (
                False,
                f"Minimum approval cannot exceed number of cosigners ({len(cosigners)})",
            )

        if min_removal < 1:
            return False, "Minimum removal must be at least 1"

        if min_removal > len(cosigners):
            return (
                False,
                f"Minimum removal cannot exceed number of cosigners ({len(cosigners)})",
            )

        for addr in cosigners:
            normalized = self._normalize_address(addr)
            if len(normalized) < 39 or len(normalized) > 40:
                return False, f"Invalid address format: {addr}"
            if normalized[0] not in ("T", "N"):
                return False, f"Invalid address network prefix: {addr}"

        return True, ""
