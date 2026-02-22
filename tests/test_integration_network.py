"""Integration tests for NetworkClient against real Symbol blockchain nodes.

These tests connect to actual Symbol nodes and verify network functionality.
No mocks are used - all operations hit real endpoints.
"""

import pytest

from src.shared.network import (
    NetworkClient,
    NetworkError,
    NetworkErrorType,
    RetryConfig,
    TimeoutConfig,
)

TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"


@pytest.fixture
def network_client():
    return NetworkClient(
        node_url=TESTNET_NODE,
        timeout_config=TimeoutConfig(connect_timeout=10.0, read_timeout=30.0),
        retry_config=RetryConfig(max_retries=2, base_delay=1.0),
    )


@pytest.mark.integration
class TestNetworkClientConnection:
    def test_node_health_check(self, network_client):
        result = network_client.test_connection()
        assert result["healthy"] is True
        assert result["url"] == TESTNET_NODE
        assert "networkHeight" in result
        assert result["networkHeight"] >= 0

    def test_get_node_info(self, network_client):
        result = network_client.get("/node/info", context="Get node info")
        assert "networkIdentifier" in result
        assert "version" in result

    def test_get_chain_info(self, network_client):
        result = network_client.get("/chain/info", context="Get chain info")
        assert "height" in result
        height = result["height"]
        assert int(height) >= 0

    def test_get_network_properties(self, network_client):
        result = network_client.get(
            "/network/properties", context="Get network properties"
        )
        assert "chain" in result
        assert "currencyMosaicId" in result["chain"]


@pytest.mark.integration
class TestNetworkClientAccountEndpoints:
    def test_get_account_info_for_known_address(self, network_client):
        faucet_address = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        result = network_client.get_optional(
            f"/accounts/{faucet_address}", context="Get faucet account info"
        )
        if result is not None:
            assert "account" in result or "mosaics" in result

    def test_get_account_info_returns_none_for_nonexistent(self, network_client):
        nonexistent_address = "TAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        result = network_client.get_optional(
            f"/accounts/{nonexistent_address}", context="Get nonexistent account"
        )
        assert result is None


@pytest.mark.integration
class TestNetworkClientMosaicEndpoints:
    def test_get_mosaic_info_for_testnet_xym(self, network_client):
        testnet_xym_id = "72C0212E67A08BCE"
        result = network_client.get_optional(
            f"/mosaics/{testnet_xym_id}", context="Get testnet XYM mosaic info"
        )
        if result is not None:
            assert "mosaic" in result or "id" in result

    def test_get_mosaic_info_returns_none_for_nonexistent(self, network_client):
        nonexistent_mosaic_id = "0000000000000000"
        result = network_client.get_optional(
            f"/mosaics/{nonexistent_mosaic_id}",
            context="Get nonexistent mosaic info",
        )
        assert result is None


@pytest.mark.integration
class TestNetworkClientTransactionEndpoints:
    def test_get_confirmed_transactions(self, network_client):
        result = network_client.get(
            "/transactions/confirmed?limit=5",
            context="Get recent confirmed transactions",
        )
        assert "data" in result
        assert isinstance(result["data"], list)

    def test_post_transaction_status(self, network_client):
        fake_hash = "A" * 64
        result = network_client.post(
            "/transactionStatus",
            context="Check transaction status",
            json={"hashes": [fake_hash]},
        )
        assert isinstance(result, list) or "status" in result


@pytest.mark.integration
class TestNetworkClientErrorHandling:
    def test_get_raises_on_invalid_endpoint(self, network_client):
        with pytest.raises(NetworkError) as exc_info:
            network_client.get("/nonexistent/endpoint", context="Invalid endpoint")
        assert exc_info.value.error_type in (NetworkErrorType.HTTP_ERROR,)
