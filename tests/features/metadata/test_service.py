"""Unit tests for MetadataService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.features.metadata.service import (
    MAX_VALUE_SIZE,
    MetadataInfo,
    MetadataService,
    MetadataTargetType,
)


class TestGenerateMetadataKey:
    def test_generate_key_produces_consistent_results(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        mock_wallet.address = "TEST_ADDRESS"
        service = MetadataService(mock_wallet)

        key1 = service.generate_metadata_key("test_key")
        key2 = service.generate_metadata_key("test_key")

        assert key1 == key2
        assert isinstance(key1, int)

    def test_generate_key_different_keys_produce_different_results(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        mock_wallet.address = "TEST_ADDRESS"
        service = MetadataService(mock_wallet)

        key1 = service.generate_metadata_key("key1")
        key2 = service.generate_metadata_key("key2")

        assert key1 != key2

    def test_generate_key_is_64_bit(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        mock_wallet.address = "TEST_ADDRESS"
        service = MetadataService(mock_wallet)

        key = service.generate_metadata_key("any_key")
        assert 0 <= key <= 0xFFFFFFFFFFFFFFFF


class TestValidateKey:
    def test_validate_key_empty_fails(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        is_valid, error = service.validate_key("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_key_valid(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        is_valid, error = service.validate_key("my_key")
        assert is_valid is True
        assert error is None

    def test_validate_key_too_long_fails(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        long_key = "x" * 300
        is_valid, error = service.validate_key(long_key)
        assert is_valid is False
        assert "long" in error.lower()


class TestValidateValue:
    def test_validate_value_empty_fails(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        is_valid, error = service.validate_value("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_value_valid(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        is_valid, error = service.validate_value("test value")
        assert is_valid is True
        assert error is None

    def test_validate_value_exceeds_max_size_fails(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        large_value = "x" * (MAX_VALUE_SIZE + 100)
        is_valid, error = service.validate_value(large_value)
        assert is_valid is False
        assert "max" in error.lower() or "exceeds" in error.lower()


class TestXorBytes:
    def test_xor_equal_length(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        a = b"\x00\x00\x00\x00"
        b = b"\xff\xff\xff\xff"
        result = service._xor_bytes(a, b)
        assert result == b"\xff\xff\xff\xff"

    def test_xor_different_length(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        a = b"\x01\x02"
        b = b"\xff"
        result = service._xor_bytes(a, b)
        assert len(result) == 2
        assert result[0] == 0x01 ^ 0xFF
        assert result[1] == 0x02 ^ 0x00

    def test_xor_empty(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        result = service._xor_bytes(b"", b"test")
        assert result == b"test"


class TestMetadataInfo:
    def test_target_type_name_account(self):
        info = MetadataInfo(
            key=123,
            key_hex="0x7b",
            value="test",
            value_size=4,
            target_type=MetadataTargetType.ACCOUNT,
            target_address="TEST_ADDR",
            source_address="SRC_ADDR",
        )
        assert info.target_type_name == "Account"

    def test_target_type_name_mosaic(self):
        info = MetadataInfo(
            key=123,
            key_hex="0x7b",
            value="test",
            value_size=4,
            target_type=MetadataTargetType.MOSAIC,
            target_address="TEST_ADDR",
            source_address="SRC_ADDR",
        )
        assert info.target_type_name == "Mosaic"

    def test_target_type_name_namespace(self):
        info = MetadataInfo(
            key=123,
            key_hex="0x7b",
            value="test",
            value_size=4,
            target_type=MetadataTargetType.NAMESPACE,
            target_address="TEST_ADDR",
            source_address="SRC_ADDR",
        )
        assert info.target_type_name == "Namespace"

    def test_target_id_hex_with_id(self):
        info = MetadataInfo(
            key=123,
            key_hex="0x7b",
            value="test",
            value_size=4,
            target_type=MetadataTargetType.MOSAIC,
            target_address="TEST_ADDR",
            source_address="SRC_ADDR",
            target_id=0x12345678,
        )
        assert info.target_id_hex == "0x12345678"

    def test_target_id_hex_without_id(self):
        info = MetadataInfo(
            key=123,
            key_hex="0x7b",
            value="test",
            value_size=4,
            target_type=MetadataTargetType.ACCOUNT,
            target_address="TEST_ADDR",
            source_address="SRC_ADDR",
        )
        assert info.target_id_hex is None

    def test_to_dict(self):
        info = MetadataInfo(
            key=123,
            key_hex="0x7b",
            value="test value",
            value_size=10,
            target_type=MetadataTargetType.MOSAIC,
            target_address="TEST_ADDR",
            source_address="SRC_ADDR",
            target_id=0xABCD,
            composite_hash="hash123",
        )
        d = info.to_dict()

        assert d["key"] == 123
        assert d["key_hex"] == "0x7b"
        assert d["value"] == "test value"
        assert d["value_size"] == 10
        assert d["target_type"] == MetadataTargetType.MOSAIC
        assert d["target_type_name"] == "Mosaic"
        assert d["target_address"] == "TEST_ADDR"
        assert d["source_address"] == "SRC_ADDR"
        assert d["target_id"] == 0xABCD
        assert d["target_id_hex"] == "0xabcd"
        assert d["composite_hash"] == "hash123"


@pytest.mark.unit
class TestCalculateValueDelta:
    def test_calculate_delta_new_value(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        delta, size_delta = service.calculate_value_delta("new", "")
        assert delta == b"new"
        assert size_delta == 3

    def test_calculate_delta_same_value(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        delta, size_delta = service.calculate_value_delta("same", "same")
        assert delta == b"\x00\x00\x00\x00"
        assert size_delta == 0

    def test_calculate_delta_different_value(self):
        mock_wallet = MagicMock()
        mock_wallet.node_url = "http://test"
        service = MetadataService(mock_wallet)

        delta, size_delta = service.calculate_value_delta("newer", "old")
        assert len(delta) == 5
        assert size_delta == 2
