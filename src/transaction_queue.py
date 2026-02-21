"""Transaction queue management for batch transaction submission."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QueuedTransaction:
    recipient: str
    mosaics: list[dict[str, int]]
    message: str
    estimated_fee: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = ""

    def __post_init__(self):
        if not self.id:
            timestamp = int(self.created_at.timestamp() * 1000)
            self.id = f"tx-{timestamp}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "recipient": self.recipient,
            "mosaics": self.mosaics,
            "message": self.message,
            "estimated_fee": self.estimated_fee,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueuedTransaction":
        return cls(
            id=data.get("id", ""),
            recipient=data["recipient"],
            mosaics=data["mosaics"],
            message=data.get("message", ""),
            estimated_fee=data.get("estimated_fee", 0.0),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(timezone.utc),
        )


class TransactionQueue:
    QUEUE_VERSION = 1

    def __init__(self, storage_dir: Path | None = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".config" / "symbol-quick-wallet"
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.storage_dir / "transaction_queue.json"
        self._transactions: list[QueuedTransaction] = []
        self._load()

    def _load(self) -> None:
        if not self.queue_file.exists():
            self._transactions = []
            return

        try:
            with open(self.queue_file, "r") as f:
                data = json.load(f)

            version = data.get("version", 0)
            if version >= self.QUEUE_VERSION:
                self._transactions = [
                    QueuedTransaction.from_dict(tx)
                    for tx in data.get("transactions", [])
                ]
            else:
                logger.warning("Transaction queue version mismatch, starting fresh")
                self._transactions = []
        except Exception as e:
            logger.warning("Failed to load transaction queue: %s", e)
            self._transactions = []

    def _save(self) -> None:
        data = {
            "version": self.QUEUE_VERSION,
            "transactions": [tx.to_dict() for tx in self._transactions],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(self.queue_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save transaction queue: %s", e)

    def add(self, transaction: QueuedTransaction) -> str:
        self._transactions.append(transaction)
        self._save()
        logger.info("Added transaction %s to queue", transaction.id)
        return transaction.id

    def remove(self, transaction_id: str) -> bool:
        for i, tx in enumerate(self._transactions):
            if tx.id == transaction_id:
                self._transactions.pop(i)
                self._save()
                logger.info("Removed transaction %s from queue", transaction_id)
                return True
        return False

    def clear(self) -> int:
        count = len(self._transactions)
        self._transactions = []
        self._save()
        logger.info("Cleared transaction queue (%d items)", count)
        return count

    def get_all(self) -> list[QueuedTransaction]:
        return self._transactions.copy()

    def get(self, transaction_id: str) -> QueuedTransaction | None:
        for tx in self._transactions:
            if tx.id == transaction_id:
                return tx
        return None

    def count(self) -> int:
        return len(self._transactions)

    def is_empty(self) -> bool:
        return len(self._transactions) == 0

    def get_total_estimated_fee(self) -> float:
        return sum(tx.estimated_fee for tx in self._transactions)

    def pop_all(self) -> list[QueuedTransaction]:
        transactions = self._transactions.copy()
        self._transactions = []
        self._save()
        return transactions

    def reorder(self, transaction_ids: list[str]) -> bool:
        new_order = []
        seen = set()

        for tx_id in transaction_ids:
            tx = self.get(tx_id)
            if tx and tx_id not in seen:
                new_order.append(tx)
                seen.add(tx_id)

        if len(new_order) != len(self._transactions):
            return False

        self._transactions = new_order
        self._save()
        return True
