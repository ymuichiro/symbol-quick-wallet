import tempfile
from pathlib import Path

import pytest
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.wallet import Wallet


@pytest.mark.unit
def test_load_wallet_with_correct_password():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        wallet = Wallet(network_name="testnet")
        wallet.wallet_dir = temp_dir_path
        wallet.wallet_file = temp_dir_path / "wallet.json"
        wallet.config_file = temp_dir_path / "config.json"
        wallet.address_book_file = temp_dir_path / "address_book.json"

        password = "correct_password"
        private_key = PrivateKey.random()
        facade = SymbolFacade("testnet")
        account = facade.create_account(private_key)

        wallet.private_key = private_key
        wallet.public_key = account.public_key
        wallet.address = account.address
        wallet.password = password

        wallet._save_wallet()

        new_wallet = Wallet(network_name="testnet")
        new_wallet.wallet_dir = temp_dir_path
        new_wallet.wallet_file = temp_dir_path / "wallet.json"
        new_wallet.config_file = temp_dir_path / "config.json"
        new_wallet.address_book_file = temp_dir_path / "address_book.json"
        try:
            new_wallet.load_wallet_from_storage(password)
            assert new_wallet.address == account.address
        except Exception as e:
            pytest.fail(f"Should not raise exception with correct password: {e}")


@pytest.mark.unit
def test_load_wallet_with_incorrect_password():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        wallet = Wallet(network_name="testnet")
        wallet.wallet_dir = temp_dir_path
        wallet.wallet_file = temp_dir_path / "wallet.json"
        wallet.config_file = temp_dir_path / "config.json"
        wallet.address_book_file = temp_dir_path / "address_book.json"

        correct_password = "correct_password"
        private_key = PrivateKey.random()
        facade = SymbolFacade("testnet")
        account = facade.create_account(private_key)

        wallet.private_key = private_key
        wallet.public_key = account.public_key
        wallet.address = account.address
        wallet.password = correct_password

        wallet._save_wallet()

        new_wallet = Wallet(network_name="testnet")
        new_wallet.wallet_dir = temp_dir_path
        new_wallet.wallet_file = temp_dir_path / "wallet.json"
        new_wallet.config_file = temp_dir_path / "config.json"
        new_wallet.address_book_file = temp_dir_path / "address_book.json"
        with pytest.raises(Exception) as exc_info:
            new_wallet.load_wallet_from_storage("incorrect_password")

        assert "Invalid password" in str(exc_info.value) or "Decryption failed" in str(
            exc_info.value
        )


@pytest.mark.unit
def test_load_wallet_with_empty_password():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        wallet = Wallet(network_name="testnet")
        wallet.wallet_dir = temp_dir_path
        wallet.wallet_file = temp_dir_path / "wallet.json"
        wallet.config_file = temp_dir_path / "config.json"
        wallet.address_book_file = temp_dir_path / "address_book.json"

        private_key = PrivateKey.random()
        facade = SymbolFacade("testnet")
        account = facade.create_account(private_key)

        wallet.private_key = private_key
        wallet.public_key = account.public_key
        wallet.address = account.address
        wallet.password = "some_password"

        wallet._save_wallet()

        new_wallet = Wallet(network_name="testnet")
        new_wallet.wallet_dir = temp_dir_path
        new_wallet.wallet_file = temp_dir_path / "wallet.json"
        new_wallet.config_file = temp_dir_path / "config.json"
        new_wallet.address_book_file = temp_dir_path / "address_book.json"
        with pytest.raises(Exception) as exc_info:
            new_wallet.load_wallet_from_storage("")

        assert "Password is required" in str(exc_info.value)


@pytest.mark.unit
def test_load_wallet_without_password():
    with tempfile.TemporaryDirectory() as temp_dir:
        wallet = Wallet(network_name="testnet")
        private_key = PrivateKey.random()
        facade = SymbolFacade("testnet")
        account = facade.create_account(private_key)

        wallet.private_key = private_key
        wallet.public_key = account.public_key
        wallet.address = account.address
        wallet.password = "some_password"

        wallet._save_wallet()

        new_wallet = Wallet(network_name="testnet")
        with pytest.raises(Exception) as exc_info:
            new_wallet.load_wallet_from_storage(None)

        assert "Password is required" in str(exc_info.value)
