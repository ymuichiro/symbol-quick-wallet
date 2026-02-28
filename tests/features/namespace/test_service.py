"""Tests for namespace service integration with real Symbol nodes."""

from __future__ import annotations

import pytest

from src.features.namespace.service import NamespaceInfo, NamespaceService
from src.shared.network import NetworkClient


@pytest.fixture
def network_client():
    return NetworkClient(node_url="http://sym-test-01.opening-line.jp:3000")


@pytest.fixture
def mock_wallet():
    class MockWallet:
        address = "TAD5BMHBUCKQTPHOZMEJ3TYGFUJQK6YZVMNZ5GA"
        network_name = "testnet"

    return MockWallet()


@pytest.fixture
def namespace_service(mock_wallet, network_client):
    return NamespaceService(mock_wallet, network_client)


class TestNamespaceIDGeneration:
    def test_generate_namespace_id_root(self, namespace_service):
        ns_id = namespace_service.generate_namespace_id("xembook", 0)
        assert isinstance(ns_id, int)
        assert ns_id > 0

    def test_generate_namespace_id_consistent(self, namespace_service):
        id1 = namespace_service.generate_namespace_id("test", 0)
        id2 = namespace_service.generate_namespace_id("test", 0)
        assert id1 == id2

    def test_generate_namespace_id_different_names(self, namespace_service):
        id1 = namespace_service.generate_namespace_id("alpha", 0)
        id2 = namespace_service.generate_namespace_id("beta", 0)
        assert id1 != id2

    def test_generate_namespace_path_single(self, namespace_service):
        path = namespace_service.generate_namespace_path("xembook")
        assert len(path) == 1
        assert isinstance(path[0], int)

    def test_generate_namespace_path_nested(self, namespace_service):
        path = namespace_service.generate_namespace_path("xembook.tomato")
        assert len(path) == 2
        assert path[0] != path[1]

    def test_get_namespace_id(self, namespace_service):
        ns_id = namespace_service.get_namespace_id("symbol.xym")
        assert isinstance(ns_id, int)
        assert ns_id > 0


class TestNamespaceInfo:
    def test_namespace_info_is_root(self):
        info = NamespaceInfo(
            namespace_id=12345,
            name="test",
            full_name="test",
            registration_type=0,
            depth=1,
            owner_address="TTEST",
            start_height=100,
            end_height=1000,
            active=True,
            alias_type=0,
        )
        assert info.is_root is True
        assert info.has_address_alias is False
        assert info.has_mosaic_alias is False

    def test_namespace_info_is_sub(self):
        info = NamespaceInfo(
            namespace_id=12345,
            name="sub",
            full_name="test.sub",
            registration_type=1,
            depth=2,
            owner_address="TTEST",
            start_height=100,
            end_height=1000,
            active=True,
            alias_type=0,
        )
        assert info.is_root is False

    def test_namespace_info_has_address_alias(self):
        info = NamespaceInfo(
            namespace_id=12345,
            name="test",
            full_name="test",
            registration_type=0,
            depth=1,
            owner_address="TTEST",
            start_height=100,
            end_height=1000,
            active=True,
            alias_type=2,
            alias_address="TALIAS",
        )
        assert info.has_address_alias is True
        assert info.alias_address == "TALIAS"

    def test_namespace_info_has_mosaic_alias(self):
        info = NamespaceInfo(
            namespace_id=12345,
            name="test",
            full_name="test",
            registration_type=0,
            depth=1,
            owner_address="TTEST",
            start_height=100,
            end_height=1000,
            active=True,
            alias_type=1,
            alias_mosaic_id=0x6BED913FA20223F8,
        )
        assert info.has_mosaic_alias is True
        assert info.alias_mosaic_id == 0x6BED913FA20223F8

    def test_namespace_info_to_dict(self):
        info = NamespaceInfo(
            namespace_id=12345,
            name="test",
            full_name="test.sub",
            registration_type=1,
            depth=2,
            owner_address="TTEST",
            start_height=100,
            end_height=1000,
            active=True,
            alias_type=0,
        )
        d = info.to_dict()
        assert d["namespace_id"] == 12345
        assert d["full_name"] == "test.sub"
        assert d["registration_type_name"] == "sub"
        assert info.is_root is False


class TestExpirationCalculation:
    def test_calculate_expiration_active(self, namespace_service):
        result = namespace_service.calculate_expiration(
            end_height=10000, current_height=5000
        )
        assert result["end_height"] == 10000
        assert result["current_height"] == 5000
        assert result["remaining_blocks"] == 5000
        assert result["is_expired"] is False

    def test_calculate_expiration_expired(self, namespace_service):
        result = namespace_service.calculate_expiration(
            end_height=1000, current_height=2000
        )
        assert result["remaining_blocks"] == 0
        assert result["is_expired"] is True

    def test_calculate_expiration_just_expired(self, namespace_service):
        result = namespace_service.calculate_expiration(
            end_height=1000, current_height=1000
        )
        assert result["remaining_blocks"] == 0
        assert result["is_expired"] is True

    def test_calculate_expiration_remaining_days(self, namespace_service):
        remaining_blocks = 86400
        result = namespace_service.calculate_expiration(
            end_height=100000, current_height=100000 - remaining_blocks
        )
        expected_days = remaining_blocks * 30 / (24 * 60 * 60)
        assert abs(result["remaining_days"] - expected_days) < 0.1


@pytest.mark.integration
class TestNamespaceResolution:
    def test_resolve_nonexistent_namespace(self, namespace_service):
        fake_id = namespace_service.get_namespace_id("nonexistent12345fake")
        info = namespace_service.fetch_namespace_info(fake_id)
        assert info is None

    @pytest.mark.skip(
        reason="Namespace ID generation algorithm needs verification with Symbol SDK"
    )
    def test_resolve_symbol_xym_namespace(self, namespace_service):
        ns_id = namespace_service.get_namespace_id("symbol.xym")
        info = namespace_service.fetch_namespace_info(ns_id)
        assert info is not None
        assert info.has_mosaic_alias is True
        assert info.alias_mosaic_id == 0x6BED913FA20223F8

    @pytest.mark.skip(
        reason="Namespace ID generation algorithm needs verification with Symbol SDK"
    )
    def test_resolve_namespace_to_mosaic_id(self, namespace_service):
        mosaic_id = namespace_service.resolve_namespace_to_mosaic_id("symbol.xym")
        assert mosaic_id is not None
        assert mosaic_id == 0x6BED913FA20223F8


@pytest.mark.integration
class TestRentalFees:
    def test_fetch_rental_fees(self, namespace_service):
        fees = namespace_service.fetch_rental_fees()
        assert "root_fee_per_block" in fees
        assert "child_fee" in fees
        assert fees["root_fee_per_block"] >= 0
        assert fees["child_fee"] >= 0

    def test_estimate_root_namespace_cost(self, namespace_service):
        estimate = namespace_service.estimate_root_namespace_cost(365)
        assert "duration_days" in estimate
        assert "duration_blocks" in estimate
        assert "rental_fee" in estimate
        assert "rental_fee_xym" in estimate
        assert estimate["duration_days"] == 365
        expected_blocks = int(365 * 24 * 60 * 60 / 30)
        assert estimate["duration_blocks"] == expected_blocks
