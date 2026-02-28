import pytest
from symbolchain.CryptoTypes import PrivateKey

from src.wallet import Wallet, AccountInfo, WalletConfig
from src.shared.network import TimeoutConfig, RetryConfig


@pytest.fixture
def temp_wallet_dir(tmp_path):
    return tmp_path / "wallet"


@pytest.fixture
def wallet(temp_wallet_dir):
    temp_wallet_dir.mkdir(parents=True, exist_ok=True)
    w = Wallet(
        network_name="testnet",
        password="testpassword123",
        storage_dir=temp_wallet_dir,
    )
    return w


class TestWalletStorageOperations:
    @pytest.mark.unit
    def test_has_wallet_false_initially(self, wallet):
        assert wallet.has_wallet() is False

    @pytest.mark.unit
    def test_has_wallet_true_after_creation(self, wallet):
        wallet.create_wallet()
        assert wallet.has_wallet() is True

    @pytest.mark.unit
    def test_is_first_run_true_initially(self, wallet):
        assert wallet.is_first_run() is True

    @pytest.mark.unit
    def test_is_first_run_false_after_creation(self, wallet):
        wallet.create_wallet()
        assert wallet.is_first_run() is False

    @pytest.mark.unit
    def test_wallet_persistence(self, wallet, temp_wallet_dir):
        wallet.create_wallet()
        original_address = str(wallet.address)
        wallet2 = Wallet(
            network_name="testnet",
            password="testpassword123",
            storage_dir=temp_wallet_dir,
        )
        wallet2.load_wallet_from_storage("testpassword123")
        assert str(wallet2.address) == original_address

    @pytest.mark.unit
    def test_import_wallet(self, wallet):
        private_key = PrivateKey.random()
        address = wallet.import_wallet(str(private_key))
        assert address is not None
        assert str(address).startswith("T")


class TestWalletConfig:
    @pytest.mark.unit
    def test_default_config(self):
        config = WalletConfig()
        assert config.timeout_config is not None
        assert config.retry_config is not None

    @pytest.mark.unit
    def test_custom_timeout_config(self):
        timeout = TimeoutConfig(
            connect_timeout=10.0, read_timeout=30.0, operation_timeout=60.0
        )
        config = WalletConfig(timeout_config=timeout)
        assert config.timeout_config.connect_timeout == 10.0

    @pytest.mark.unit
    def test_custom_retry_config(self):
        retry = RetryConfig(max_retries=5, base_delay=2.0, max_delay=60.0)
        config = WalletConfig(retry_config=retry)
        assert config.retry_config.max_retries == 5


class TestAccountInfoDataclass:
    @pytest.mark.unit
    def test_to_dict_all_fields(self):
        account = AccountInfo(
            address="TTEST123",
            public_key="ABCDEF",
            encrypted_private_key="encrypted",
            label="Test",
            address_book_shared=False,
        )
        data = account.to_dict()
        assert data["address"] == "TTEST123"
        assert data["public_key"] == "ABCDEF"
        assert data["encrypted_private_key"] == "encrypted"
        assert data["label"] == "Test"
        assert data["address_book_shared"] is False

    @pytest.mark.unit
    def test_from_dict_missing_fields(self):
        data = {"address": "TTEST123"}
        account = AccountInfo.from_dict(data)
        assert account.address == "TTEST123"
        assert account.public_key == ""
        assert account.encrypted_private_key == ""
        assert account.label == ""
        assert account.address_book_shared is True

    @pytest.mark.unit
    def test_roundtrip(self):
        original = AccountInfo(
            address="TTEST123",
            public_key="ABCDEF",
            encrypted_private_key="encrypted",
            label="Test",
            address_book_shared=False,
        )
        data = original.to_dict()
        restored = AccountInfo.from_dict(data)
        assert restored.address == original.address
        assert restored.public_key == original.public_key
        assert restored.encrypted_private_key == original.encrypted_private_key
        assert restored.label == original.label
        assert restored.address_book_shared == original.address_book_shared


class TestWalletErrorScenarios:
    @pytest.mark.unit
    def test_wallet_export_without_wallet(self, wallet):
        with pytest.raises(Exception, match="No wallet loaded"):
            wallet.export_private_key("password")

    @pytest.mark.unit
    def test_wallet_save_without_password(self, wallet):
        wallet.create_wallet()
        wallet.password = None
        with pytest.raises(Exception, match="Password is required"):
            wallet._save_wallet()

    @pytest.mark.unit
    def test_load_wallet_without_password(self, wallet):
        wallet.create_wallet()
        wallet2 = Wallet(storage_dir=wallet.wallet_dir)
        with pytest.raises(Exception, match="Password is required"):
            wallet2.load_wallet_from_storage()

    @pytest.mark.unit
    def test_import_invalid_encrypted_data(self, wallet):
        invalid_data = {"encrypted_private_key": "not_valid_encrypted_data"}
        with pytest.raises(Exception):
            wallet.import_encrypted_private_key(invalid_data, "password")

    @pytest.mark.unit
    def test_import_encrypted_data_missing_key(self, wallet):
        invalid_data = {"some_other_key": "value"}
        with pytest.raises(Exception, match="Invalid encrypted data"):
            wallet.import_encrypted_private_key(invalid_data, "password")

    @pytest.mark.unit
    def test_create_account_without_password(self, wallet):
        wallet.password = None
        with pytest.raises(Exception, match="Password is required"):
            wallet.create_account()

    @pytest.mark.unit
    def test_import_account_without_password(self, wallet):
        wallet.password = None
        with pytest.raises(Exception, match="Password is required"):
            wallet.import_account("A" * 64)

    @pytest.mark.unit
    def test_load_current_account_without_password(self, wallet):
        wallet.create_account()
        wallet.password = None
        with pytest.raises(Exception, match="Password is required"):
            wallet.load_current_account()

    @pytest.mark.unit
    def test_delete_account_out_of_bounds(self, wallet):
        wallet.create_account()
        result = wallet.delete_account(99)
        assert result is False

    @pytest.mark.unit
    def test_switch_account_out_of_bounds(self, wallet):
        wallet.create_account()
        result = wallet.switch_account(99)
        assert result is False

    @pytest.mark.unit
    def test_update_label_out_of_bounds(self, wallet):
        wallet.create_account()
        result = wallet.update_account_label(99, "New Label")
        assert result is False
