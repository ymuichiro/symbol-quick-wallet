"""Tests for transaction template functionality."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.shared.transaction_template import TemplateStorage, TransactionTemplate


class TestTransactionTemplate:
    def test_create_template_with_defaults(self):
        template = TransactionTemplate(
            name="Test Template",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[{"mosaic_id": 0x6BED913FA20223F8, "amount": 1_000_000}],
        )

        assert template.name == "Test Template"
        assert template.recipient.startswith("T")
        assert len(template.mosaics) == 1
        assert template.id.startswith("tpl-")
        assert isinstance(template.created_at, datetime)
        assert isinstance(template.updated_at, datetime)

    def test_create_template_with_custom_id(self):
        template = TransactionTemplate(
            id="custom-id",
            name="Custom",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[],
        )

        assert template.id == "custom-id"

    def test_to_dict(self):
        template = TransactionTemplate(
            id="test-123",
            name="Test",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[{"mosaic_id": 123, "amount": 456}],
            message="Test message",
        )

        data = template.to_dict()

        assert data["id"] == "test-123"
        assert data["name"] == "Test"
        assert data["recipient"].startswith("T")
        assert data["mosaics"] == [{"mosaic_id": 123, "amount": 456}]
        assert data["message"] == "Test message"
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_dict(self):
        data = {
            "id": "tpl-abc123",
            "name": "Monthly Payment",
            "recipient": "TTEST123456789012345678901234567890123456789012345",
            "mosaics": [{"mosaic_id": 0x6BED913FA20223F8, "amount": 10_000_000}],
            "message": "Rent",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-02T00:00:00+00:00",
        }

        template = TransactionTemplate.from_dict(data)

        assert template.id == "tpl-abc123"
        assert template.name == "Monthly Payment"
        assert template.mosaics[0]["amount"] == 10_000_000
        assert template.message == "Rent"

    def test_from_dict_without_timestamps(self):
        data = {
            "name": "No Timestamps",
            "recipient": "TTEST123456789012345678901234567890123456789012345",
            "mosaics": [],
        }

        template = TransactionTemplate.from_dict(data)

        assert template.name == "No Timestamps"
        assert isinstance(template.created_at, datetime)
        assert isinstance(template.updated_at, datetime)

    def test_roundtrip_serialization(self):
        original = TransactionTemplate(
            name="Roundtrip Test",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[
                {"mosaic_id": 0x6BED913FA20223F8, "amount": 5_000_000},
                {"mosaic_id": 0x1234567890ABCDEF, "amount": 100},
            ],
            message="Test message",
        )

        data = original.to_dict()
        restored = TransactionTemplate.from_dict(data)

        assert restored.name == original.name
        assert restored.recipient == original.recipient
        assert restored.mosaics == original.mosaics
        assert restored.message == original.message
        assert restored.id == original.id


class TestTemplateStorage:
    @pytest.fixture
    def temp_storage_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def storage(self, temp_storage_dir):
        return TemplateStorage(temp_storage_dir)

    def test_initializes_empty_storage(self, temp_storage_dir):
        storage = TemplateStorage(temp_storage_dir)

        assert storage.is_empty()
        assert storage.count() == 0
        assert storage.get_all() == []

    def test_creates_storage_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "subdir" / "storage"
            TemplateStorage(storage_path)

            assert storage_path.exists()

    def test_add_template(self, storage):
        template = TransactionTemplate(
            name="Test Add",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[{"mosaic_id": 123, "amount": 1000}],
        )

        template_id = storage.add(template)

        assert template_id == template.id
        assert storage.count() == 1
        assert not storage.is_empty()

    def test_get_template(self, storage):
        template = TransactionTemplate(
            name="Test Get",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[],
        )
        storage.add(template)

        retrieved = storage.get(template.id)

        assert retrieved is not None
        assert retrieved.name == "Test Get"
        assert retrieved.id == template.id

    def test_get_nonexistent_template(self, storage):
        result = storage.get("nonexistent-id")

        assert result is None

    def test_get_all_templates(self, storage):
        t1 = TransactionTemplate(
            name="Template 1",
            recipient="TTEST111111111111111111111111111111111111111111",
            mosaics=[],
        )
        t2 = TransactionTemplate(
            name="Template 2",
            recipient="TTEST222222222222222222222222222222222222222222",
            mosaics=[],
        )

        storage.add(t1)
        storage.add(t2)

        all_templates = storage.get_all()

        assert len(all_templates) == 2
        names = [t.name for t in all_templates]
        assert "Template 1" in names
        assert "Template 2" in names

    def test_update_template(self, storage):
        template = TransactionTemplate(
            name="Original",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[{"mosaic_id": 1, "amount": 100}],
            message="Original message",
        )
        storage.add(template)

        success = storage.update(
            template.id,
            {
                "name": "Updated",
                "mosaics": [{"mosaic_id": 2, "amount": 200}],
                "message": "Updated message",
            },
        )

        assert success
        updated = storage.get(template.id)
        assert updated is not None
        assert updated.name == "Updated"
        assert updated.mosaics == [{"mosaic_id": 2, "amount": 200}]
        assert updated.message == "Updated message"
        assert updated.recipient == template.recipient

    def test_update_nonexistent_template(self, storage):
        success = storage.update("nonexistent", {"name": "New Name"})

        assert not success

    def test_remove_template(self, storage):
        template = TransactionTemplate(
            name="To Remove",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[],
        )
        storage.add(template)

        assert storage.count() == 1

        success = storage.remove(template.id)

        assert success
        assert storage.count() == 0
        assert storage.get(template.id) is None

    def test_remove_nonexistent_template(self, storage):
        success = storage.remove("nonexistent-id")

        assert not success

    def test_persists_templates(self, temp_storage_dir):
        storage1 = TemplateStorage(temp_storage_dir)
        template = TransactionTemplate(
            name="Persistent",
            recipient="TTEST123456789012345678901234567890123456789012345",
            mosaics=[{"mosaic_id": 999, "amount": 888}],
            message="Should persist",
        )
        storage1.add(template)

        storage2 = TemplateStorage(temp_storage_dir)

        assert storage2.count() == 1
        retrieved = storage2.get(template.id)
        assert retrieved is not None
        assert retrieved.name == "Persistent"
        assert retrieved.message == "Should persist"

    def test_handles_corrupted_storage_file(self, temp_storage_dir):
        storage_file = temp_storage_dir / "transaction_templates.json"
        storage_file.write_text("not valid json")

        storage = TemplateStorage(temp_storage_dir)

        assert storage.is_empty()

    def test_handles_missing_storage_file(self, temp_storage_dir):
        storage = TemplateStorage(temp_storage_dir)

        assert storage.is_empty()
        assert storage.get_all() == []

    def test_count_returns_correct_number(self, storage):
        for i in range(5):
            storage.add(
                TransactionTemplate(
                    name=f"Template {i}",
                    recipient=f"TTEST{i:045d}",
                    mosaics=[],
                )
            )

        assert storage.count() == 5

    def test_multiple_operations(self, storage):
        t1 = TransactionTemplate(
            name="First",
            recipient="TTESTAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            mosaics=[],
        )
        t2 = TransactionTemplate(
            name="Second",
            recipient="TTESTBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            mosaics=[],
        )

        storage.add(t1)
        storage.add(t2)
        assert storage.count() == 2

        storage.update(t1.id, {"name": "First Updated"})
        assert storage.get(t1.id).name == "First Updated"

        storage.remove(t2.id)
        assert storage.count() == 1
        assert storage.get(t2.id) is None
