"""Tests for MetadataService."""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest
from symbolchain.symbol import IdGenerator

from src.features.metadata.service import (
    MAX_VALUE_SIZE,
    MetadataInfo,
    MetadataService,
    MetadataTargetType,
)
from src.transaction import TransactionManager


def _mock_wallet(address: str = "TEST_ADDRESS") -> MagicMock:
    wallet = MagicMock()
    wallet.node_url = "http://test"
    wallet.address = address
    return wallet


class TestGenerateMetadataKey:
    def test_generate_key_produces_consistent_results(self):
        service = MetadataService(_mock_wallet())

        key1 = service.generate_metadata_key("test_key")
        key2 = service.generate_metadata_key("test_key")

        assert key1 == key2
        assert isinstance(key1, int)

    def test_generate_key_different_keys_produce_different_results(self):
        service = MetadataService(_mock_wallet())

        key1 = service.generate_metadata_key("key1")
        key2 = service.generate_metadata_key("key2")

        assert key1 != key2

    def test_generate_key_is_64_bit(self):
        service = MetadataService(_mock_wallet())

        key = service.generate_metadata_key("any_key")
        assert 0 <= key <= 0xFFFFFFFFFFFFFFFF


class TestValidateKey:
    def test_validate_key_empty_fails(self):
        service = MetadataService(_mock_wallet())

        is_valid, error = service.validate_key("")
        assert is_valid is False
        assert error is not None
        assert "empty" in error.lower()

    def test_validate_key_valid(self):
        service = MetadataService(_mock_wallet())

        is_valid, error = service.validate_key("my_key")
        assert is_valid is True
        assert error is None

    def test_validate_key_too_long_fails(self):
        service = MetadataService(_mock_wallet())

        long_key = "x" * 300
        is_valid, error = service.validate_key(long_key)
        assert is_valid is False
        assert error is not None
        assert "long" in error.lower()


class TestValidateValue:
    def test_validate_value_empty_fails(self):
        service = MetadataService(_mock_wallet())

        is_valid, error = service.validate_value("")
        assert is_valid is False
        assert error is not None
        assert "empty" in error.lower()

    def test_validate_value_valid(self):
        service = MetadataService(_mock_wallet())

        is_valid, error = service.validate_value("test value")
        assert is_valid is True
        assert error is None

    def test_validate_value_exceeds_max_size_fails(self):
        service = MetadataService(_mock_wallet())

        large_value = "x" * (MAX_VALUE_SIZE + 100)
        is_valid, error = service.validate_value(large_value)
        assert is_valid is False
        assert error is not None
        assert "max" in error.lower() or "exceeds" in error.lower()


class TestXorBytes:
    def test_xor_equal_length(self):
        service = MetadataService(_mock_wallet())

        a = b"\x00\x00\x00\x00"
        b = b"\xff\xff\xff\xff"
        result = service._xor_bytes(a, b)
        assert result == b"\xff\xff\xff\xff"

    def test_xor_different_length(self):
        service = MetadataService(_mock_wallet())

        a = b"\x01\x02"
        b = b"\xff"
        result = service._xor_bytes(a, b)
        assert len(result) == 2
        assert result[0] == 0x01 ^ 0xFF
        assert result[1] == 0x02 ^ 0x00

    def test_xor_empty(self):
        service = MetadataService(_mock_wallet())

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
class TestMetadataServiceUnit:
    def test_calculate_delta_new_value(self):
        service = MetadataService(_mock_wallet())

        delta, size_delta = service.calculate_value_delta("new", "")
        assert delta == b"new"
        assert size_delta == 3

    def test_calculate_delta_same_value(self):
        service = MetadataService(_mock_wallet())

        delta, size_delta = service.calculate_value_delta("same", "same")
        assert delta == b"\x00\x00\x00\x00"
        assert size_delta == 0

    def test_calculate_delta_different_value(self):
        service = MetadataService(_mock_wallet())

        delta, size_delta = service.calculate_value_delta("newer", "old")
        assert len(delta) == 5
        assert size_delta == 2

    def test_parse_metadata_response(self):
        service = MetadataService(_mock_wallet())
        response = {
            "data": [
                {
                    "metadataEntry": {
                        "scopedMetadataKey": "0xA",
                        "metadataType": MetadataTargetType.ACCOUNT.value,
                        "targetAddress": "TADDR",
                        "sourceAddress": "TSRC",
                        "targetId": "0000000000000000",
                        "value": "74657374",
                        "valueSize": 4,
                        "compositeHash": "ABC123",
                    }
                }
            ]
        }

        parsed = service._parse_metadata_response(response)

        assert len(parsed) == 1
        assert parsed[0].value == "test"
        assert parsed[0].key == 10
        assert parsed[0].target_id is None

    def test_fetch_account_metadata_calls_network_client(self):
        wallet = _mock_wallet("TADDR")
        network_client = MagicMock()
        network_client.get.return_value = {"data": []}
        service = MetadataService(wallet, network_client=network_client)

        result = service.fetch_account_metadata("TADDR", source_address="TSRC")

        assert result == []
        network_client.get.assert_called_once()

    def test_assign_account_metadata_requires_transaction_manager(self):
        service = MetadataService(_mock_wallet("TADDR"), transaction_manager=None)

        with pytest.raises(ValueError, match="Transaction manager is required"):
            service.assign_account_metadata("key", "value", "TADDR")

    def test_assign_account_metadata_calls_transaction_manager(self):
        wallet = _mock_wallet("TADDR")
        transaction_manager = MagicMock()
        transaction_manager.create_sign_and_announce_account_metadata.return_value = {
            "hash": "A" * 64
        }
        service = MetadataService(wallet, transaction_manager=transaction_manager)

        result = service.assign_account_metadata("test_key", "value", "TADDR")

        assert result["hash"] == "A" * 64
        transaction_manager.create_sign_and_announce_account_metadata.assert_called_once()

    def test_remove_metadata_not_found_raises(self):
        service = MetadataService(_mock_wallet("TADDR"), transaction_manager=MagicMock())

        with pytest.raises(ValueError, match="Metadata entry not found"):
            service.remove_metadata(
                "missing",
                MetadataTargetType.ACCOUNT,
                "TADDR",
            )

    def test_remove_metadata_for_mosaic_requires_target_id(self):
        service = MetadataService(_mock_wallet("TADDR"), transaction_manager=MagicMock())
        key = service.generate_metadata_key("mosaic_key")
        with patch.object(
            service,
            "get_existing_metadata",
            return_value=MetadataInfo(
                key=key,
                key_hex=hex(key),
                value="abc",
                value_size=3,
                target_type=MetadataTargetType.MOSAIC,
                target_address="TADDR",
                source_address="TSRC",
                target_id=0x123,
            ),
        ):
            with pytest.raises(ValueError, match="Mosaic ID is required"):
                service.remove_metadata(
                    "mosaic_key",
                    MetadataTargetType.MOSAIC,
                    "TADDR",
                )


@pytest.mark.integration
class TestMetadataServiceReadIntegration:
    FAUCET_ADDRESS = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
    TESTNET_XYM_MOSAIC_ID = 0x72C0212E67A08BCE

    def test_fetch_all_metadata_for_account_returns_list(self, testnet_wallet):
        service = MetadataService(testnet_wallet)
        result = service.fetch_all_metadata_for_account(self.FAUCET_ADDRESS)

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, MetadataInfo)

    def test_fetch_mosaic_metadata_returns_list(self, testnet_wallet):
        service = MetadataService(testnet_wallet)
        result = service.fetch_mosaic_metadata(
            self.TESTNET_XYM_MOSAIC_ID,
            source_address=self.FAUCET_ADDRESS,
        )

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, MetadataInfo)

    def test_fetch_namespace_metadata_returns_list(self, testnet_wallet):
        service = MetadataService(testnet_wallet)
        namespace_id = int(IdGenerator.generate_namespace_path("symbol.xym")[-1])
        result = service.fetch_namespace_metadata(
            namespace_id,
            source_address=self.FAUCET_ADDRESS,
        )

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, MetadataInfo)

    def test_get_existing_metadata_for_unknown_key_returns_none(self, testnet_wallet):
        testnet_wallet.address = self.FAUCET_ADDRESS
        service = MetadataService(testnet_wallet)

        result = service.get_existing_metadata(
            key=0xFFFFFFFFFFFFFFFF,
            target_type=MetadataTargetType.ACCOUNT,
            target_address=self.FAUCET_ADDRESS,
        )

        assert result is None


@pytest.mark.integration
@pytest.mark.slow
class TestMetadataServiceLiveIntegration:
    def test_live_assign_and_remove_account_metadata(
        self, loaded_testnet_wallet, ensure_live_min_balance
    ):
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live metadata tests")

        wallet = loaded_testnet_wallet
        min_balance = int(os.getenv("SYMBOL_TEST_METADATA_MIN_BALANCE_MICRO", "500000"))
        ensure_live_min_balance(wallet, min_balance)

        confirm_timeout = int(os.getenv("SYMBOL_TEST_CONFIRM_TIMEOUT", "300"))
        manager = TransactionManager(wallet, wallet.node_url)
        service = MetadataService(wallet, transaction_manager=manager)

        key_string = f"meta_live_{int(time.time())}"
        value = f"value_{int(time.time())}"
        target_address = str(wallet.address)

        assign_result = service.assign_account_metadata(
            key_string=key_string,
            value=value,
            target_address=target_address,
        )

        assert "hash" in assign_result
        assert len(assign_result["hash"]) == 64

        assign_status = manager.wait_for_transaction_status(
            assign_result["hash"],
            timeout_seconds=confirm_timeout,
            poll_interval_seconds=5,
        )
        assert assign_status["group"] == "confirmed"

        key = service.generate_metadata_key(key_string)
        existing: MetadataInfo | None = None
        for _ in range(20):
            existing = service.get_existing_metadata(
                key=key,
                target_type=MetadataTargetType.ACCOUNT,
                target_address=target_address,
            )
            if existing and existing.value == value:
                break
            time.sleep(3)

        assert existing is not None
        assert existing.value == value

        remove_result = service.remove_metadata(
            key_string=key_string,
            target_type=MetadataTargetType.ACCOUNT,
            target_address=target_address,
        )
        assert "hash" in remove_result

        remove_status = manager.wait_for_transaction_status(
            remove_result["hash"],
            timeout_seconds=confirm_timeout,
            poll_interval_seconds=5,
        )
        assert remove_status["group"] == "confirmed"

        removed = None
        for _ in range(20):
            removed = service.get_existing_metadata(
                key=key,
                target_type=MetadataTargetType.ACCOUNT,
                target_address=target_address,
            )
            if removed is None:
                break
            time.sleep(3)

        assert removed is None
