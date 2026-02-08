import pytest
import requests
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade
from datetime import timedelta, datetime, timezone

TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"


@pytest.mark.integration
def test_node_health():
    """Test if testnet node is accessible"""
    response = requests.get(f"{TESTNET_NODE}/node/health", timeout=10)
    assert response.status_code == 200
    data = response.json()
    assert data.get("status", {}).get("apiNode") == "up"


@pytest.mark.integration
def test_account_info_endpoint():
    """Test account info endpoint"""
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    url = f"{TESTNET_NODE}/accounts/{str(account.address)}"
    response = requests.get(url, timeout=10)

    # New account returns 404, which is expected
    assert response.status_code in [200, 404]


@pytest.mark.integration
def test_network_info():
    """Test network info endpoint"""
    response = requests.get(f"{TESTNET_NODE}/network/properties", timeout=10)
    # May return 404 on some nodes
    assert response.status_code in [200, 404]


@pytest.mark.slow
@pytest.mark.integration
def test_transaction_announce_to_testnet():
    """Test announcing a transaction to testnet"""
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    deadline_timestamp = int(
        (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp() * 1000
    )

    # Create a self-transfer transaction (no mosaics)
    transfer_dict = {
        "type": "transfer_transaction_v1",
        "signer_public_key": str(account.public_key),
        "deadline": deadline_timestamp,
        "recipient_address": str(account.address),
        "mosaics": [],  # Empty mosaics for testing
        "message": "",
    }

    transfer = facade.transaction_factory.create(transfer_dict)
    signature = account.sign_transaction(transfer)
    signed_payload = facade.transaction_factory.attach_signature(transfer, signature)

    # Try to announce (will likely fail due to no funds, but tests endpoint)
    try:
        url = f"{TESTNET_NODE}/transactions"
        headers = {"Content-Type": "application/json"}
        response = requests.put(url, data=signed_payload, headers=headers, timeout=10)
        # We expect failure (200 with error message) or success (202)
        assert response.status_code in [200, 202, 400, 409]
    except requests.exceptions.Timeout:
        pytest.skip("Node timeout - skipping announcement test")
    except requests.exceptions.ConnectionError:
        pytest.skip("Connection error - skipping announcement test")


@pytest.mark.integration
def test_chain_info():
    """Test chain info endpoint"""
    response = requests.get(f"{TESTNET_NODE}/chain/info", timeout=10)
    assert response.status_code == 200
    data = response.json()
    assert "height" in data
    # Height may be returned as string or int
    height = data["height"]
    assert int(height) >= 0


@pytest.mark.integration
def test_mosaic_info_endpoint():
    """Test mosaic info endpoint for XYM"""
    xym_mosaic_id = "7777031834025731064"  # Decimal ID for XYM
    response = requests.get(f"{TESTNET_NODE}/mosaics/{xym_mosaic_id}", timeout=10)
    # May return 404 or 409 depending on node
    assert response.status_code in [200, 404, 409]
