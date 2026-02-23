"""Integration tests for account operations against real Symbol testnet."""

from __future__ import annotations

import os

import pytest
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.features.account.service import AccountService
from src.wallet import Wallet
from tests.live_test_key import HARDCODED_TEST_PRIVATE_KEY

TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"
TESTNET_XYM_MOSAIC_ID = 0x72C0212E67A08BCE


@pytest.fixture
def testnet_wallet():
    wallet = Wallet(network_name="testnet")
    wallet.node_url = TESTNET_NODE
    wallet._update_node_url(TESTNET_NODE)
    return wallet


@pytest.fixture
def loaded_testnet_wallet():
    private_key_hex = HARDCODED_TEST_PRIVATE_KEY.strip()
    if not private_key_hex:
        private_key_hex = os.getenv("SYMBOL_TEST_PRIVATE_KEY", "").strip()
    if not private_key_hex:
        pytest.skip("No test private key available")

    wallet = Wallet(network_name="testnet")
    wallet.node_url = TESTNET_NODE
    wallet._update_node_url(TESTNET_NODE)
    wallet.facade = SymbolFacade("testnet")
    wallet.private_key = PrivateKey(private_key_hex)
    account = wallet.facade.create_account(wallet.private_key)
    wallet.public_key = account.public_key
    wallet.address = account.address
    return wallet


@pytest.fixture
def account_service(loaded_testnet_wallet):
    return AccountService(loaded_testnet_wallet)


@pytest.mark.integration
class TestAccountNodeConnection:
    """Integration tests for account node connection on testnet."""

    def test_node_health_check(self, testnet_wallet):
        result = testnet_wallet.test_node_connection()
        assert result["healthy"] is True
        assert "networkHeight" in result
        assert result["networkHeight"] >= 0

    def test_get_network_properties(self, testnet_wallet):
        props = testnet_wallet._network_client.get(
            "/network/properties", context="Get network properties"
        )
        assert props is not None
        assert "chain" in props or "network" in props


@pytest.mark.integration
class TestAccountBalanceOperations:
    """Integration tests for account balance operations on testnet."""

    def test_get_balance_for_faucet_address(self, testnet_wallet):
        faucet_address = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        mosaics = testnet_wallet.get_balance(address=faucet_address)
        assert isinstance(mosaics, list)

    def test_get_account_balances_for_faucet(self, testnet_wallet):
        faucet_address = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        result = testnet_wallet.get_account_balances(address=faucet_address)
        assert result["address"] == faucet_address
        assert "xym_micro" in result
        assert "xym" in result
        assert "mosaics" in result

    def test_get_xym_balance_for_loaded_wallet(self, loaded_testnet_wallet):
        result = loaded_testnet_wallet.get_xym_balance()
        assert "address" in result
        assert "xym_micro" in result
        assert "xym" in result
        assert result["address"] == str(loaded_testnet_wallet.address)


@pytest.mark.integration
class TestAccountInfoOperations:
    """Integration tests for account info operations on testnet."""

    def test_get_account_info(self, loaded_testnet_wallet):
        info = loaded_testnet_wallet._network_client.get_optional(
            f"/accounts/{loaded_testnet_wallet.address}",
            context="Get account info",
        )
        if info is not None:
            assert "account" in info or "address" in info

    def test_address_format(self, loaded_testnet_wallet):
        address = str(loaded_testnet_wallet.address)
        assert address.startswith("T")
        assert len(address) == 39

    def test_public_key_format(self, loaded_testnet_wallet):
        public_key = str(loaded_testnet_wallet.public_key)
        assert len(public_key) == 64
        try:
            int(public_key, 16)
        except ValueError:
            pytest.fail("Public key is not valid hex")


@pytest.mark.integration
class TestAccountServiceIntegration:
    """Integration tests for AccountService with real wallet."""

    def test_get_all_accounts(self, loaded_testnet_wallet):
        service = AccountService(loaded_testnet_wallet)
        accounts = service.get_all_accounts()
        assert isinstance(accounts, list)

    def test_get_current_account_info(self, loaded_testnet_wallet):
        service = AccountService(loaded_testnet_wallet)
        info = service.get_current_account_info()
        if info is not None:
            assert info.index >= 0
            assert info.address.startswith("T")


@pytest.mark.integration
class TestAccountTransactionHistory:
    """Integration tests for account transaction history on testnet."""

    def test_get_transaction_history(self, loaded_testnet_wallet):
        history = loaded_testnet_wallet.get_transaction_history(limit=5)
        assert isinstance(history, list)

    def test_get_transaction_status_nonexistent(self, testnet_wallet):
        fake_hash = "A" * 64
        status = testnet_wallet.get_transaction_status(fake_hash)
        assert status["hash"] == fake_hash
        assert status["group"] == "not_found"


@pytest.mark.integration
class TestAccountHarvestingStatus:
    """Integration tests for account harvesting status on testnet."""

    def test_get_harvesting_status(self, loaded_testnet_wallet):
        status = loaded_testnet_wallet.get_harvesting_status()
        assert "is_harvesting" in status
        assert "is_remote" in status
        assert "linked_public_key" in status


@pytest.mark.integration
class TestAccountMosaicOperations:
    """Integration tests for account mosaic operations on testnet."""

    def test_get_mosaic_name_xym(self, testnet_wallet):
        name = testnet_wallet.get_mosaic_name(TESTNET_XYM_MOSAIC_ID)
        assert name == "XYM"

    def test_get_mosaic_info_xym(self, testnet_wallet):
        info = testnet_wallet.get_mosaic_info(TESTNET_XYM_MOSAIC_ID)
        if info is not None:
            assert "mosaic" in info or "id" in info

    def test_get_mosaic_full_info_xym(self, testnet_wallet):
        info = testnet_wallet.get_mosaic_full_info(TESTNET_XYM_MOSAIC_ID)
        assert info is not None
        assert "mosaic_id" in info
        assert info["mosaic_id"] == TESTNET_XYM_MOSAIC_ID
        if info.get("found"):
            assert "divisibility" in info


@pytest.mark.integration
class TestAccountAddressBookIntegration:
    """Integration tests for account address book on testnet."""

    def test_address_book_operations(self, loaded_testnet_wallet):
        loaded_testnet_wallet.address_book = {}
        loaded_testnet_wallet.address_book[
            "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        ] = {
            "name": "Faucet",
            "note": "Testnet faucet",
            "address": "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ",
        }
        assert (
            "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
            in loaded_testnet_wallet.address_book
        )
        assert (
            loaded_testnet_wallet.address_book[
                "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
            ]["name"]
            == "Faucet"
        )
