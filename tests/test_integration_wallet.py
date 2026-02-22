"""Integration tests for Wallet against real Symbol blockchain nodes.

These tests verify wallet operations by connecting to actual Symbol nodes.
"""

import os
import time

import pytest
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.transaction import TransactionManager
from src.wallet import Wallet
from tests.live_test_key import HARDCODED_TEST_PRIVATE_KEY

TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"


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


@pytest.mark.integration
class TestWalletNodeConnection:
    def test_test_node_connection_success(self, testnet_wallet):
        result = testnet_wallet.test_node_connection()
        assert result["healthy"] is True
        assert "networkHeight" in result

    def test_get_currency_mosaic_id(self, testnet_wallet):
        mosaic_id = testnet_wallet.get_currency_mosaic_id()
        assert mosaic_id is not None
        assert mosaic_id > 0
        assert mosaic_id == testnet_wallet.TESTNET_XYM_MOSAIC_ID


@pytest.mark.integration
class TestWalletBalanceOperations:
    def test_get_balance_for_address(self, testnet_wallet):
        faucet_address = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        mosaics = testnet_wallet.get_balance(address=faucet_address)
        assert isinstance(mosaics, list)

    def test_get_account_balances(self, testnet_wallet):
        faucet_address = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        result = testnet_wallet.get_account_balances(address=faucet_address)
        assert result["address"] == faucet_address
        assert "xym_micro" in result
        assert "xym" in result
        assert "mosaics" in result
        assert isinstance(result["mosaics"], list)

    def test_get_xym_balance(self, testnet_wallet):
        faucet_address = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        result = testnet_wallet.get_xym_balance(address=faucet_address)
        assert result["address"] == faucet_address
        assert "xym_micro" in result
        assert "xym" in result


@pytest.mark.integration
class TestWalletTransactionOperations:
    def test_get_transaction_history(self, loaded_testnet_wallet):
        history = loaded_testnet_wallet.get_transaction_history(limit=5)
        assert isinstance(history, list)

    def test_get_transaction_status_for_nonexistent(self, testnet_wallet):
        fake_hash = "A" * 64
        status = testnet_wallet.get_transaction_status(fake_hash)
        assert status["hash"] == fake_hash
        assert status["group"] == "not_found"


@pytest.mark.integration
class TestWalletMosaicOperations:
    def test_get_mosaic_name_for_xym(self, testnet_wallet):
        testnet_xym_id = 0x72C0212E67A08BCE
        name = testnet_wallet.get_mosaic_name(testnet_xym_id)
        assert name == "XYM"

    def test_get_mosaic_info_for_xym(self, testnet_wallet):
        testnet_xym_id = "72C0212E67A08BCE"
        info = testnet_wallet.get_mosaic_info(testnet_xym_id)
        if info is not None:
            assert "mosaic" in info or "id" in info


@pytest.mark.integration
@pytest.mark.slow
class TestWalletLiveTransaction:
    def test_live_transfer_to_self(self, loaded_testnet_wallet):
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live transfer tests")

        wallet = loaded_testnet_wallet
        before = wallet.get_xym_balance()
        transfer_micro = int(os.getenv("SYMBOL_TEST_TRANSFER_MICRO", "100000"))

        assert before["xym_micro"] > transfer_micro, (
            f"Insufficient balance: {before['xym_micro']} micro XYM available"
        )

        manager = TransactionManager(wallet, wallet.node_url)
        currency_mosaic_id = manager.get_currency_mosaic_id()
        message = f"integration-test-{int(time.time())}"

        result = manager.create_sign_and_announce(
            str(wallet.address),
            [{"mosaic_id": currency_mosaic_id, "amount": transfer_micro}],
            message,
        )

        tx_hash = result["hash"]
        assert len(tx_hash) == 64

        confirmed = wallet.wait_for_transaction_confirmation(
            tx_hash,
            timeout_seconds=180,
            poll_interval_seconds=5,
        )
        assert confirmed["group"] == "confirmed"

    def test_live_transfer_with_message(self, loaded_testnet_wallet):
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live transfer tests")

        wallet = loaded_testnet_wallet
        before = wallet.get_xym_balance()
        transfer_micro = int(os.getenv("SYMBOL_TEST_TRANSFER_MICRO", "100000"))

        if before["xym_micro"] <= transfer_micro:
            pytest.skip(f"Insufficient balance: {before['xym_micro']} micro XYM")

        manager = TransactionManager(wallet, wallet.node_url)
        currency_mosaic_id = manager.get_currency_mosaic_id()
        message = f"msg-test-{int(time.time())}"

        result = manager.create_sign_and_announce(
            str(wallet.address),
            [{"mosaic_id": currency_mosaic_id, "amount": transfer_micro}],
            message,
        )

        tx_hash = result["hash"]
        confirmed = wallet.wait_for_transaction_confirmation(
            tx_hash, timeout_seconds=180
        )
        assert confirmed["group"] == "confirmed"


@pytest.mark.integration
class TestWalletHarvesting:
    def test_get_harvesting_status(self, loaded_testnet_wallet):
        status = loaded_testnet_wallet.get_harvesting_status()
        assert "is_harvesting" in status
        assert "is_remote" in status
        assert "linked_public_key" in status


@pytest.mark.integration
class TestWalletAddressBook:
    def test_address_book_operations(self, testnet_wallet):
        test_address = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        testnet_wallet.add_address(test_address, "Test Contact", "Test note")

        addresses = testnet_wallet.get_addresses()
        assert test_address in addresses
        assert addresses[test_address]["name"] == "Test Contact"

        info = testnet_wallet.get_address_info(test_address)
        assert info["name"] == "Test Contact"
        assert info["note"] == "Test note"

        testnet_wallet.update_address(test_address, "Updated Name", "Updated note")
        updated_info = testnet_wallet.get_address_info(test_address)
        assert updated_info["name"] == "Updated Name"

        testnet_wallet.remove_address(test_address)
        assert test_address not in testnet_wallet.get_addresses()

    def test_contact_groups(self, testnet_wallet):
        group_id = testnet_wallet.create_contact_group("Test Group", "#FF0000")
        assert group_id in testnet_wallet.get_contact_groups()

        group = testnet_wallet.get_contact_group(group_id)
        assert group["name"] == "Test Group"

        testnet_wallet.update_contact_group(group_id, "Renamed Group", "#00FF00")
        updated_group = testnet_wallet.get_contact_group(group_id)
        assert updated_group["name"] == "Renamed Group"

        testnet_wallet.delete_contact_group(group_id)
        assert group_id not in testnet_wallet.get_contact_groups()
