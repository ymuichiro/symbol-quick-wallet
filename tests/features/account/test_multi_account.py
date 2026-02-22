import json
import pytest
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.wallet import Wallet, AccountInfo, MULTI_ACCOUNT_VERSION


@pytest.fixture
def temp_wallet_dir(tmp_path):
    return tmp_path / "wallet"


@pytest.fixture
def wallet(temp_wallet_dir):
    temp_wallet_dir.mkdir(parents=True, exist_ok=True)
    w = Wallet(
        network_name="testnet", password="testpassword123", storage_dir=temp_wallet_dir
    )
    w.password = "testpassword123"
    return w


@pytest.mark.unit
def test_account_info_to_dict():
    account = AccountInfo(
        address="TTEST123456789",
        public_key="ABCDEF1234567890",
        encrypted_private_key="encrypted123",
        label="Test Account",
        address_book_shared=True,
    )
    data = account.to_dict()
    assert data["address"] == "TTEST123456789"
    assert data["public_key"] == "ABCDEF1234567890"
    assert data["encrypted_private_key"] == "encrypted123"
    assert data["label"] == "Test Account"
    assert data["address_book_shared"] is True


@pytest.mark.unit
def test_account_info_from_dict():
    data = {
        "address": "TTEST123456789",
        "public_key": "ABCDEF1234567890",
        "encrypted_private_key": "encrypted123",
        "label": "Test Account",
        "address_book_shared": False,
    }
    account = AccountInfo.from_dict(data)
    assert account.address == "TTEST123456789"
    assert account.public_key == "ABCDEF1234567890"
    assert account.encrypted_private_key == "encrypted123"
    assert account.label == "Test Account"
    assert account.address_book_shared is False


@pytest.mark.unit
def test_create_account(wallet):
    account = wallet.create_account(label="Primary", address_book_shared=True)
    assert account.label == "Primary"
    assert account.address_book_shared is True
    assert account.address.startswith("T")
    assert len(account.public_key) == 64
    assert len(wallet.get_accounts()) == 1


@pytest.mark.unit
def test_import_account(wallet):
    private_key = PrivateKey.random()
    private_key_hex = str(private_key)
    account = wallet.import_account(
        private_key_hex, label="Imported", address_book_shared=False
    )
    assert account.label == "Imported"
    assert account.address_book_shared is False
    assert len(wallet.get_accounts()) == 1


@pytest.mark.unit
def test_duplicate_account_prevention(wallet):
    private_key = PrivateKey.random()
    private_key_hex = str(private_key)
    wallet.import_account(private_key_hex, label="First")
    with pytest.raises(Exception, match="already exists"):
        wallet.import_account(private_key_hex, label="Second")


@pytest.mark.unit
def test_switch_account(wallet):
    wallet.create_account(label="Account 1")
    wallet.create_account(label="Account 2")
    assert wallet.get_current_account_index() == 0
    assert wallet.switch_account(1) is True
    assert wallet.get_current_account_index() == 1
    assert wallet.switch_account(0) is True
    assert wallet.get_current_account_index() == 0


@pytest.mark.unit
def test_switch_invalid_account(wallet):
    wallet.create_account(label="Only Account")
    assert wallet.switch_account(99) is False
    assert wallet.get_current_account_index() == 0


@pytest.mark.unit
def test_delete_account(wallet):
    wallet.create_account(label="Account 1")
    wallet.create_account(label="Account 2")
    wallet.create_account(label="Account 3")
    assert len(wallet.get_accounts()) == 3
    assert wallet.delete_account(1) is True
    assert len(wallet.get_accounts()) == 2
    remaining = wallet.get_accounts()
    assert remaining[0].label == "Account 1"
    assert remaining[1].label == "Account 3"


@pytest.mark.unit
def test_delete_last_account_prevented(wallet):
    wallet.create_account(label="Only Account")
    assert wallet.delete_account(0) is False
    assert len(wallet.get_accounts()) == 1


@pytest.mark.unit
def test_update_account_label(wallet):
    wallet.create_account(label="Original")
    assert wallet.update_account_label(0, "Updated") is True
    assert wallet.get_accounts()[0].label == "Updated"


@pytest.mark.unit
def test_update_account_address_book_shared(wallet):
    wallet.create_account(label="Test", address_book_shared=True)
    assert wallet.update_account_address_book_shared(0, False) is True
    assert wallet.get_accounts()[0].address_book_shared is False


@pytest.mark.unit
def test_accounts_registry_persistence(wallet, temp_wallet_dir):
    wallet.create_account(label="Account 1")
    wallet.create_account(label="Account 2")
    wallet.switch_account(1)
    accounts_file = temp_wallet_dir / "accounts.json"
    assert accounts_file.exists()
    with open(accounts_file, "r") as f:
        data = json.load(f)
    assert data["version"] == MULTI_ACCOUNT_VERSION
    assert len(data["accounts"]) == 2
    assert data["current_account_index"] == 1


@pytest.mark.unit
def test_load_accounts_registry(wallet, temp_wallet_dir):
    wallet.create_account(label="Account 1")
    wallet.create_account(label="Account 2")
    wallet.switch_account(1)
    wallet2 = Wallet(
        network_name="testnet", password="testpassword123", storage_dir=temp_wallet_dir
    )
    wallet2.password = "testpassword123"
    accounts = wallet2.get_accounts()
    assert len(accounts) == 2
    assert wallet2.get_current_account_index() == 1


@pytest.mark.unit
def test_private_address_book(wallet, temp_wallet_dir):
    wallet.create_account(label="Private Account", address_book_shared=False)
    wallet.add_address("TADDRESS1", "Contact 1", "Note 1")
    book_path = wallet._get_account_address_book_path(wallet.get_accounts()[0].address)
    assert book_path.exists()


@pytest.mark.unit
def test_shared_address_book(wallet, temp_wallet_dir):
    wallet.create_account(label="Shared Account", address_book_shared=True)
    wallet.add_address("TADDRESS1", "Contact 1", "Note 1")
    assert wallet.address_book_file.exists()
