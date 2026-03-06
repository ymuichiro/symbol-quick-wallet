import os
import time

import pytest

from src.transaction import TransactionManager


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
    def test_live_transfer_to_self(self, loaded_testnet_wallet, ensure_live_min_balance):
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live transfer tests")

        wallet = loaded_testnet_wallet
        transfer_micro = int(os.getenv("SYMBOL_TEST_TRANSFER_MICRO", "100000"))
        confirm_timeout = int(os.getenv("SYMBOL_TEST_CONFIRM_TIMEOUT", "300"))

        ensure_live_min_balance(wallet, transfer_micro + 1)

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
            timeout_seconds=confirm_timeout,
            poll_interval_seconds=5,
        )
        assert confirmed["group"] == "confirmed"

    def test_live_transfer_with_message(
        self, loaded_testnet_wallet, ensure_live_min_balance
    ):
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live transfer tests")

        wallet = loaded_testnet_wallet
        transfer_micro = int(os.getenv("SYMBOL_TEST_TRANSFER_MICRO", "100000"))
        confirm_timeout = int(os.getenv("SYMBOL_TEST_CONFIRM_TIMEOUT", "300"))

        ensure_live_min_balance(wallet, transfer_micro + 1)

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
            tx_hash, timeout_seconds=confirm_timeout
        )
        assert confirmed["group"] == "confirmed"


@pytest.mark.integration
class TestWalletHarvesting:
    def test_get_harvesting_status(self, loaded_testnet_wallet):
        status = loaded_testnet_wallet.get_harvesting_status()
        assert "is_harvesting" in status
        assert "is_remote" in status
        assert "linked_public_key" in status
