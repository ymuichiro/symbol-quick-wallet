import pytest
import json
import tempfile
import os
from pathlib import Path
from src.wallet import Wallet
from symbolchain.CryptoTypes import PrivateKey


@pytest.mark.unit
def test_wallet_creation():
    """Test wallet creation with new private key"""
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    assert wallet.private_key is not None
    assert wallet.public_key is not None
    assert wallet.address is not None
    assert str(wallet.address).startswith("T")  # Testnet address

    wallet2 = Wallet(password="test_password")
    wallet2.load_wallet_from_storage("test_password")
    assert str(wallet2.address) == str(wallet.address)
    assert str(wallet2.private_key) == str(wallet.private_key)


@pytest.mark.unit
def test_address_book_operations():
    """Test address book add and remove"""
    import tempfile

    # Create temporary file for address book

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmpfile:
        json.dump({}, tmpfile)

    wallet = Wallet()
    wallet.address_book_file = Path(tmpfile.name)
    wallet._load_address_book()

    # Add addresses
    wallet.add_address(
        "TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I", "Test User", "Test note"
    )
    wallet.add_address("TBI7VJYLRJ7VJXZ4D7J6Z5V6X5V6X5V6X5V6", "Faucet")

    addresses = wallet.get_addresses()
    assert len(addresses) == 2
    assert "TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I" in addresses
    assert "TBI7VJYLRJ7VJXZ4D7J6Z5V6X5V6X5V6X5V6" in addresses
    assert addresses["TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I"]["name"] == "Test User"
    assert addresses["TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I"]["note"] == "Test note"
    assert addresses["TBI7VJYLRJ7VJXZ4D7J6Z5V6X5V6X5V6X5V6"]["name"] == "Faucet"

    # Update address
    wallet.update_address(
        "TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I", "Updated User", "Updated note"
    )
    addresses = wallet.get_addresses()
    assert (
        addresses["TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I"]["name"] == "Updated User"
    )
    assert (
        addresses["TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I"]["note"] == "Updated note"
    )

    # Remove address
    wallet.remove_address("TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I")
    addresses = wallet.get_addresses()
    assert len(addresses) == 1
    assert "TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I" not in addresses
    assert "TBI7VJYLRJ7VJXZ4D7J6Z5V6X5V6X5V6X5V6" in addresses

    # Cleanup
    os.unlink(wallet.address_book_file)


@pytest.mark.unit
def test_private_key_encryption():
    """Test private key encryption and decryption"""
    wallet = Wallet()
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    assert encrypted_data is not None
    assert len(encrypted_data) > 0
    assert (
        str(wallet.private_key) not in encrypted_data
    )  # Plain key not in encrypted data


@pytest.mark.unit
def test_private_key_decryption():
    """Test private key decryption"""
    wallet = Wallet()
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    # Decrypt
    decrypted_key = wallet.decrypt_private_key(encrypted_data, password)

    assert decrypted_key == str(wallet.private_key)


@pytest.mark.unit
def test_private_key_decryption_wrong_password():
    """Test that wrong password fails decryption"""
    wallet = Wallet()
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    # Try to decrypt with wrong password
    with pytest.raises(Exception):
        wallet.decrypt_private_key(encrypted_data, "wrongpassword")


@pytest.mark.unit
def test_private_key_export():
    """Test private key export functionality"""
    wallet = Wallet()
    wallet.create_wallet()

    password = "testpassword123"
    export_data = wallet.export_private_key(password)

    assert "encrypted_private_key" in export_data
    assert "public_key" in export_data
    assert "address" in export_data
    assert export_data["address"] == str(wallet.address)


@pytest.mark.unit
def test_private_key_encryption():
    """Test private key encryption and decryption"""
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    assert encrypted_data is not None
    assert len(encrypted_data) > 0
    assert (
        "encrypted_private_key" not in encrypted_data
    )  # Plain key not in encrypted data


@pytest.mark.unit
def test_private_key_decryption():
    """Test private key decryption"""
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    # Decrypt
    decrypted_key = wallet.decrypt_private_key(encrypted_data, password)

    assert decrypted_key == str(wallet.private_key)


@pytest.mark.unit
def test_private_key_decryption_wrong_password():
    """Test that wrong password fails decryption"""
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    # Try to decrypt with wrong password
    with pytest.raises(Exception):
        wallet.decrypt_private_key(encrypted_data, "wrongpassword")


@pytest.mark.unit
def test_private_key_export():
    """Test private key export functionality"""
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    password = "testpassword123"
    export_data = wallet.export_private_key(password)

    assert "encrypted_private_key" in export_data
    assert "public_key" in export_data
    assert "address" in export_data


@pytest.mark.unit
def test_encrypted_private_key_import():
    """Test importing encrypted private key"""
    wallet1 = Wallet(password="test_password")
    wallet1.create_wallet()

    password = "testpassword123"
    export_data = wallet1.export_private_key(password)

    # Import into new wallet
    wallet2 = Wallet(password="testpassword123")
    wallet2.import_encrypted_private_key(export_data, password)

    assert wallet2.address == wallet1.address
    assert str(wallet2.private_key) == str(wallet1.private_key)


@pytest.mark.unit
def test_get_mosaic_name():
    """Test mosaic name resolution"""
    wallet = Wallet()

    # XYM mosaic ID (hex and decimal)
    xym_hex = "0x6bed913fa20223f8"
    xym_dec = 7777031834025731064

    name1 = wallet.get_mosaic_name(int(xym_hex, 16))
    name2 = wallet.get_mosaic_name(xym_dec)

    assert name1 == "XYM"
    assert name2 == "XYM"
