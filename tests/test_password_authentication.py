import pytest
import json
import os
import tempfile
from pathlib import Path
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade
from src.wallet import Wallet


@pytest.mark.unit
def test_load_wallet_with_correct_password():
    """Test loading wallet with correct password"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        # Create a wallet with a known password
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

        # Save wallet
        wallet._save_wallet()

        # Load wallet with correct password
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
    """Test loading wallet with incorrect password"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        # Create a wallet with a known password
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

        # Save wallet
        wallet._save_wallet()

        # Load wallet with an incorrect password
        new_wallet = Wallet(network_name="testnet")
        new_wallet.wallet_dir = temp_dir_path
        new_wallet.wallet_file = temp_dir_path / "wallet.json"
        new_wallet.config_file = temp_dir_path / "config.json"
        new_wallet.address_book_file = temp_dir_path / "address_book.json"
        with pytest.raises(Exception) as exc_info:
            new_wallet.load_wallet_from_storage("incorrect_password")

        # Check that exception message contains "Invalid password"
        assert "Invalid password" in str(exc_info.value) or "Decryption failed" in str(
            exc_info.value
        )


@pytest.mark.unit
def test_load_wallet_with_empty_password():
    """Test loading wallet with empty password"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        # Create a wallet
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

        # Save wallet
        wallet._save_wallet()

        # Load wallet with an empty password
        new_wallet = Wallet(network_name="testnet")
        new_wallet.wallet_dir = temp_dir_path
        new_wallet.wallet_file = temp_dir_path / "wallet.json"
        new_wallet.config_file = temp_dir_path / "config.json"
        new_wallet.address_book_file = temp_dir_path / "address_book.json"
        with pytest.raises(Exception) as exc_info:
            new_wallet.load_wallet_from_storage("")

        # Check that exception message contains "Password is required"
        assert "Password is required" in str(exc_info.value)


@pytest.mark.unit
def test_load_wallet_without_password():
    """Test loading wallet without password"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        # Create a wallet
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

        # Save wallet
        wallet._save_wallet()

        # Load wallet without password
        new_wallet = Wallet(network_name="testnet")
        new_wallet.wallet_dir = temp_dir_path
        new_wallet.wallet_file = temp_dir_path / "wallet.json"
        new_wallet.config_file = temp_dir_path / "config.json"
        new_wallet.address_book_file = temp_dir_path / "address_book.json"
        with pytest.raises(Exception) as exc_info:
            new_wallet.load_wallet_from_storage(None)

        # Check that exception message contains "Password is required"
        assert "Password is required" in str(exc_info.value)


@pytest.mark.unit
def test_load_wallet_without_password():
    """Test loading wallet without password"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a wallet
        wallet = Wallet(network_name="testnet")
        private_key = PrivateKey.random()
        facade = SymbolFacade("testnet")
        account = facade.create_account(private_key)

        wallet.private_key = private_key
        wallet.public_key = account.public_key
        wallet.address = account.address
        wallet.password = "some_password"

        # Save the wallet
        wallet._save_wallet()

        # Load the wallet without password
        new_wallet = Wallet(network_name="testnet")
        with pytest.raises(Exception) as exc_info:
            new_wallet.load_wallet_from_storage(None)

        # Check that the exception message contains "Password is required"
        assert "Password is required" in str(exc_info.value)
