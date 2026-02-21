"""Transaction template management for saved transfer configurations."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

logger = logging.getLogger(__name__)


@dataclass
class TransactionTemplate:
    name: str
    recipient: str
    mosaics: list[dict[str, int]]
    message: str = ""
    id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id:
            self.id = f"tpl-{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "recipient": self.recipient,
            "mosaics": self.mosaics,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransactionTemplate":
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            recipient=data["recipient"],
            mosaics=data.get("mosaics", []),
            message=data.get("message", ""),
            created_at=datetime.fromisoformat(created_at)
            if created_at
            else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(updated_at)
            if updated_at
            else datetime.now(timezone.utc),
        )


class TemplateStorage:
    TEMPLATE_VERSION = 1

    def __init__(self, storage_dir: Path | None = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".config" / "symbol-quick-wallet"
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.templates_file = self.storage_dir / "transaction_templates.json"
        self._templates: list[TransactionTemplate] = []
        self._load()

    def _load(self) -> None:
        if not self.templates_file.exists():
            self._templates = []
            return

        try:
            with open(self.templates_file, "r") as f:
                data = json.load(f)

            version = data.get("version", 0)
            if version >= self.TEMPLATE_VERSION:
                self._templates = [
                    TransactionTemplate.from_dict(tpl)
                    for tpl in data.get("templates", [])
                ]
            else:
                logger.warning("Template storage version mismatch, starting fresh")
                self._templates = []
        except Exception as e:
            logger.warning("Failed to load templates: %s", e)
            self._templates = []

    def _save(self) -> None:
        data = {
            "version": self.TEMPLATE_VERSION,
            "templates": [tpl.to_dict() for tpl in self._templates],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(self.templates_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save templates: %s", e)

    def add(self, template: TransactionTemplate) -> str:
        self._templates.append(template)
        self._save()
        logger.info("Added template %s (%s)", template.id, template.name)
        return template.id

    def update(self, template_id: str, updates: dict[str, Any]) -> bool:
        for i, tpl in enumerate(self._templates):
            if tpl.id == template_id:
                updated = TransactionTemplate(
                    id=tpl.id,
                    name=updates.get("name", tpl.name),
                    recipient=updates.get("recipient", tpl.recipient),
                    mosaics=updates.get("mosaics", tpl.mosaics),
                    message=updates.get("message", tpl.message),
                    created_at=tpl.created_at,
                    updated_at=datetime.now(timezone.utc),
                )
                self._templates[i] = updated
                self._save()
                logger.info("Updated template %s", template_id)
                return True
        return False

    def remove(self, template_id: str) -> bool:
        for i, tpl in enumerate(self._templates):
            if tpl.id == template_id:
                self._templates.pop(i)
                self._save()
                logger.info("Removed template %s", template_id)
                return True
        return False

    def get(self, template_id: str) -> TransactionTemplate | None:
        for tpl in self._templates:
            if tpl.id == template_id:
                return tpl
        return None

    def get_all(self) -> list[TransactionTemplate]:
        return self._templates.copy()

    def count(self) -> int:
        return len(self._templates)

    def is_empty(self) -> bool:
        return len(self._templates) == 0
