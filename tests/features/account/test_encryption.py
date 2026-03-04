import pytest
from cryptography.fernet import Fernet
from symbolchain.CryptoTypes import PrivateKey

from src.wallet import Wallet


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


class TestWalletEncryptionDecryption:
    @pytest.mark.unit
    def test_encrypt_private_key_returns_encrypted_string(self, wallet):
        wallet.create_wallet()
        encrypted = wallet.encrypt_private_key("mypassword")
        assert encrypted is not None
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

    @pytest.mark.unit
    def test_decrypt_private_key_reproduces_original(self, wallet):
        wallet.create_wallet()
        original_key = str(wallet.private_key)
        password = "securepassword123"
        encrypted = wallet.encrypt_private_key(password)
        decrypted = wallet.decrypt_private_key(encrypted, password)
        assert decrypted == original_key

    @pytest.mark.unit
    def test_wrong_password_raises_exception(self, wallet):
        wallet.create_wallet()
        encrypted = wallet.encrypt_private_key("correctpassword")
        with pytest.raises(Exception, match="Failed to decrypt"):
            wallet.decrypt_private_key(encrypted, "wrongpassword")

    @pytest.mark.unit
    def test_encryption_is_deterministic_with_same_password(self, wallet):
        wallet.create_wallet()
        original_key = str(wallet.private_key)
        password = "samepassword"
        encrypted1 = wallet.encrypt_private_key(password)
        encrypted2 = wallet.encrypt_private_key(password)
        assert wallet.decrypt_private_key(encrypted1, password) == original_key
        assert wallet.decrypt_private_key(encrypted2, password) == original_key

    @pytest.mark.unit
    def test_empty_password_encryption(self, wallet):
        wallet.create_wallet()
        encrypted = wallet.encrypt_private_key("")
        decrypted = wallet.decrypt_private_key(encrypted, "")
        assert decrypted == str(wallet.private_key)

    @pytest.mark.unit
    def test_long_password_truncation(self, wallet):
        wallet.create_wallet()
        long_password = "a" * 100
        encrypted = wallet.encrypt_private_key(long_password)
        decrypted = wallet.decrypt_private_key(encrypted, long_password)
        assert decrypted == str(wallet.private_key)
        with pytest.raises(Exception, match="Failed to decrypt"):
            wallet.decrypt_private_key(encrypted, "a" * 32)

    @pytest.mark.unit
    def test_special_characters_in_password(self, wallet):
        wallet.create_wallet()
        password = "p@$$w0rd!#$%^&*()"
        encrypted = wallet.encrypt_private_key(password)
        decrypted = wallet.decrypt_private_key(encrypted, password)
        assert decrypted == str(wallet.private_key)

    @pytest.mark.unit
    def test_unicode_password(self, wallet):
        wallet.create_wallet()
        password = "пароль123"
        encrypted = wallet.encrypt_private_key(password)
        decrypted = wallet.decrypt_private_key(encrypted, password)
        assert decrypted == str(wallet.private_key)

    @pytest.mark.unit
    def test_encrypted_key_is_different_from_plain(self, wallet):
        wallet.create_wallet()
        plain_key = str(wallet.private_key)
        encrypted = wallet.encrypt_private_key("password")
        assert plain_key not in encrypted
        assert encrypted != plain_key

    @pytest.mark.unit
    def test_account_specific_encryption(self, wallet):
        private_key_hex = str(PrivateKey.random())
        encrypted = wallet._encrypt_private_key_for_account(
            private_key_hex, "testpassword"
        )
        decrypted = wallet._decrypt_private_key_for_account(encrypted, "testpassword")
        assert decrypted == private_key_hex

    @pytest.mark.unit
    def test_account_specific_encryption_wrong_password(self, wallet):
        private_key_hex = str(PrivateKey.random())
        encrypted = wallet._encrypt_private_key_for_account(
            private_key_hex, "correctpassword"
        )
        with pytest.raises(Exception, match="Failed to decrypt"):
            wallet._decrypt_private_key_for_account(encrypted, "wrongpassword")

    @pytest.mark.unit
    def test_tampered_encrypted_data_fails(self, wallet):
        wallet.create_wallet()
        encrypted = wallet.encrypt_private_key("password")
        tampered = encrypted[:-5] + "XXXXX"
        with pytest.raises(Exception):
            wallet.decrypt_private_key(tampered, "password")

    @pytest.mark.unit
    def test_decrypt_legacy_format_for_backward_compatibility(self, wallet):
        wallet.create_wallet()
        private_key_hex = str(wallet.private_key)
        password = "legacy-password"

        legacy_key = wallet._build_legacy_fernet_key(password)
        legacy_encrypted = Fernet(legacy_key).encrypt(private_key_hex.encode()).decode()

        decrypted = wallet.decrypt_private_key(legacy_encrypted, password)
        assert decrypted == private_key_hex
