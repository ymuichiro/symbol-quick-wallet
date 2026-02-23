import pytest

from src.wallet import Wallet


@pytest.mark.unit
def test_wallet_creation():
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    assert wallet.private_key is not None
    assert wallet.public_key is not None
    assert wallet.address is not None
    assert str(wallet.address).startswith("T")

    wallet2 = Wallet(password="test_password")
    wallet2.load_wallet_from_storage("test_password")
    assert str(wallet2.address) == str(wallet.address)
    assert str(wallet2.private_key) == str(wallet.private_key)


@pytest.mark.unit
def test_private_key_encryption():
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    assert encrypted_data is not None
    assert len(encrypted_data) > 0
    assert "encrypted_private_key" not in encrypted_data


@pytest.mark.unit
def test_private_key_decryption():
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    decrypted_key = wallet.decrypt_private_key(encrypted_data, password)

    assert decrypted_key == str(wallet.private_key)


@pytest.mark.unit
def test_private_key_decryption_wrong_password():
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    password = "testpassword123"
    encrypted_data = wallet.encrypt_private_key(password)

    with pytest.raises(Exception):
        wallet.decrypt_private_key(encrypted_data, "wrongpassword")


@pytest.mark.unit
def test_private_key_export():
    wallet = Wallet(password="test_password")
    wallet.create_wallet()

    password = "testpassword123"
    export_data = wallet.export_private_key(password)

    assert "encrypted_private_key" in export_data
    assert "public_key" in export_data
    assert "address" in export_data


@pytest.mark.unit
def test_encrypted_private_key_import():
    wallet1 = Wallet(password="test_password")
    wallet1.create_wallet()

    password = "testpassword123"
    export_data = wallet1.export_private_key(password)

    wallet2 = Wallet(password="testpassword123")
    wallet2.import_encrypted_private_key(export_data, password)

    assert wallet2.address == wallet1.address
    assert str(wallet2.private_key) == str(wallet1.private_key)


@pytest.mark.unit
def test_get_mosaic_name():
    wallet = Wallet()

    xym_hex = "0x6bed913fa20223f8"
    xym_dec = 7777031834025731064

    name1 = wallet.get_mosaic_name(int(xym_hex, 16))
    name2 = wallet.get_mosaic_name(xym_dec)

    assert name1 == "XYM"
    assert name2 == "XYM"
