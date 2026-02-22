import pytest
from decimal import Decimal

from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.wallet import Wallet, AccountInfo, WalletConfig
from src.transaction import TransactionManager
from src.shared.validation import (
    AddressValidator,
    AmountValidator,
    MosaicIdValidator,
    ValidationResult,
)
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


@pytest.fixture
def loaded_wallet(wallet):
    wallet.create_wallet()
    return wallet


@pytest.fixture
def transaction_manager(loaded_wallet):
    return TransactionManager(loaded_wallet)


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
        truncated_password = "a" * 32
        decrypted = wallet.decrypt_private_key(encrypted, truncated_password)
        assert decrypted == str(wallet.private_key)

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


class TestTransactionBuilding:
    @pytest.mark.unit
    def test_create_transfer_transaction_basic(
        self, transaction_manager, loaded_wallet
    ):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        tx = transaction_manager.create_transfer_transaction(recipient, mosaics)
        assert tx is not None
        assert tx.size > 0

    @pytest.mark.unit
    def test_create_transfer_with_message(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        message = "Hello Symbol!"
        tx = transaction_manager.create_transfer_transaction(
            recipient, mosaics, message
        )
        assert tx is not None

    @pytest.mark.unit
    def test_create_transfer_empty_message(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        tx = transaction_manager.create_transfer_transaction(recipient, mosaics, "")
        assert tx is not None

    @pytest.mark.unit
    def test_create_transfer_with_multiple_mosaics(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [
            {"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000},
            {"mosaic_id": "0x1234567890ABCDEF", "amount": 500},
        ]
        tx = transaction_manager.create_transfer_transaction(recipient, mosaics)
        assert tx is not None

    @pytest.mark.unit
    def test_create_transfer_aggregates_same_mosaic(self, transaction_manager):
        mosaics = [
            {"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000},
            {"mosaic_id": "0x6BED913FA20223F8", "amount": 500000},
        ]
        normalized = transaction_manager.normalize_mosaics(mosaics)
        assert len(normalized) == 1
        assert normalized[0]["amount"] == 1500000

    @pytest.mark.unit
    def test_create_transfer_without_wallet_raises(self, wallet):
        manager = TransactionManager(wallet)
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        with pytest.raises(ValueError, match="Wallet is not loaded"):
            manager.create_transfer_transaction(recipient, mosaics)

    @pytest.mark.unit
    def test_address_normalization_in_transaction(self, transaction_manager):
        recipient_with_dashes = "TD5Z-P2WO-JKFM-GCVC-3GO3-2CQJ-SU6J-F3TZ-LOIJ-2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        tx = transaction_manager.create_transfer_transaction(
            recipient_with_dashes, mosaics
        )
        assert tx is not None

    @pytest.mark.unit
    def test_mosaic_id_normalization_hex_string(self, transaction_manager):
        mosaics = [{"mosaic_id": "6BED913FA20223F8", "amount": 1000000}]
        normalized = transaction_manager.normalize_mosaics(mosaics)
        assert normalized[0]["mosaic_id"] == 0x6BED913FA20223F8

    @pytest.mark.unit
    def test_mosaic_id_normalization_with_0x_prefix(self, transaction_manager):
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        normalized = transaction_manager.normalize_mosaics(mosaics)
        assert normalized[0]["mosaic_id"] == 0x6BED913FA20223F8

    @pytest.mark.unit
    def test_mosaic_id_normalization_integer(self, transaction_manager):
        mosaics = [{"mosaic_id": 0x6BED913FA20223F8, "amount": 1000000}]
        normalized = transaction_manager.normalize_mosaics(mosaics)
        assert normalized[0]["mosaic_id"] == 0x6BED913FA20223F8


class TestTransactionSigning:
    @pytest.mark.unit
    def test_sign_transaction_returns_signature(
        self, transaction_manager, loaded_wallet
    ):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        tx = transaction_manager.create_transfer_transaction(recipient, mosaics)
        signature = transaction_manager.sign_transaction(tx)
        assert signature is not None

    @pytest.mark.unit
    def test_attach_signature_returns_payload(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        tx = transaction_manager.create_transfer_transaction(recipient, mosaics)
        signature = transaction_manager.sign_transaction(tx)
        payload = transaction_manager.attach_signature(tx, signature)
        assert payload is not None
        assert len(payload) > 0

    @pytest.mark.unit
    def test_calculate_transaction_hash(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        tx = transaction_manager.create_transfer_transaction(recipient, mosaics)
        signature = transaction_manager.sign_transaction(tx)
        payload = transaction_manager.attach_signature(tx, signature)
        tx_hash = transaction_manager.calculate_transaction_hash_from_signed_payload(
            payload
        )
        assert tx_hash is not None
        assert len(tx_hash) == 64

    @pytest.mark.unit
    def test_same_transaction_same_hash(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        tx = transaction_manager.create_transfer_transaction(recipient, mosaics)
        signature = transaction_manager.sign_transaction(tx)
        payload = transaction_manager.attach_signature(tx, signature)
        hash1 = transaction_manager.calculate_transaction_hash_from_signed_payload(
            payload
        )
        hash2 = transaction_manager.calculate_transaction_hash_from_signed_payload(
            payload
        )
        assert hash1 == hash2

    @pytest.mark.unit
    def test_sign_without_wallet_raises(self, wallet):
        manager = TransactionManager(wallet)
        facade = SymbolFacade("testnet")
        tx_dict = {
            "type": "transfer_transaction_v1",
            "signer_public_key": "A" * 64,
            "deadline": 1234567890000,
            "recipient_address": "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA",
            "mosaics": [],
            "message": "",
        }
        tx = facade.transaction_factory.create(tx_dict)
        with pytest.raises(ValueError, match="Wallet is not loaded"):
            manager.sign_transaction(tx)


class TestTransactionMessageValidation:
    @pytest.mark.unit
    def test_message_within_limit(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        message = "A" * 1000
        tx = transaction_manager.create_transfer_transaction(
            recipient, mosaics, message
        )
        assert tx is not None

    @pytest.mark.unit
    def test_message_exactly_max_bytes(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        message = "A" * 1023
        tx = transaction_manager.create_transfer_transaction(
            recipient, mosaics, message
        )
        assert tx is not None

    @pytest.mark.unit
    def test_message_exceeds_max_bytes(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        message = "A" * 1024
        with pytest.raises(ValueError, match="Message is too long"):
            transaction_manager.create_transfer_transaction(recipient, mosaics, message)

    @pytest.mark.unit
    def test_unicode_message_byte_count(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        message = "日本語" * 100
        tx = transaction_manager.create_transfer_transaction(
            recipient, mosaics, message
        )
        assert tx is not None

    @pytest.mark.unit
    def test_none_message_treated_as_empty(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 1000000}]
        tx = transaction_manager.create_transfer_transaction(recipient, mosaics, None)
        assert tx is not None


class TestAddressValidation:
    @pytest.mark.unit
    def test_valid_testnet_address(self):
        result = AddressValidator.validate("TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA")
        assert result.is_valid is True
        assert result.normalized_value.startswith("T")

    @pytest.mark.unit
    def test_valid_mainnet_address(self):
        result = AddressValidator.validate("ND5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA")
        assert result.is_valid is True
        assert result.normalized_value.startswith("N")

    @pytest.mark.unit
    def test_address_with_dashes_normalized(self):
        result = AddressValidator.validate(
            "TD5Z-P2WO-JKFM-GCVC-3GO3-2CQJ-SU6J-F3TZ-LOIJ-2HA"
        )
        assert result.is_valid is True
        assert "-" not in result.normalized_value

    @pytest.mark.unit
    def test_empty_address(self):
        result = AddressValidator.validate("")
        assert result.is_valid is False
        assert "required" in result.error_message.lower()

    @pytest.mark.unit
    def test_whitespace_only_address(self):
        result = AddressValidator.validate("   ")
        assert result.is_valid is False

    @pytest.mark.unit
    def test_short_address(self):
        result = AddressValidator.validate("TD5ZP2")
        assert result.is_valid is False
        assert "short" in result.error_message.lower()

    @pytest.mark.unit
    def test_long_address(self):
        result = AddressValidator.validate(
            "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HAAAAAA"
        )
        assert result.is_valid is False
        assert "long" in result.error_message.lower()

    @pytest.mark.unit
    def test_invalid_starting_char(self):
        result = AddressValidator.validate("AD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA")
        assert result.is_valid is False

    @pytest.mark.unit
    def test_lowercase_address_is_uppercased(self):
        result = AddressValidator.validate("td5zp2wojkfmgcvc3go32cqjsu6jf3tzloij2ha")
        assert result.is_valid is True
        assert result.normalized_value.isupper()

    @pytest.mark.unit
    def test_address_with_spaces(self):
        result = AddressValidator.validate("TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA")
        assert result.is_valid is True

    @pytest.mark.unit
    def test_min_length_address(self):
        result = AddressValidator.validate("T" + "A" * 38)
        assert result.is_valid is True
        assert len(result.normalized_value) == 39

    @pytest.mark.unit
    def test_max_length_address(self):
        result = AddressValidator.validate("T" + "A" * 39)
        assert result.is_valid is True
        assert len(result.normalized_value) == 40

    @pytest.mark.unit
    def test_address_with_special_characters(self):
        result = AddressValidator.validate("TD5Z@P2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA")
        assert result.is_valid is False

    @pytest.mark.unit
    def test_none_address(self):
        result = AddressValidator.validate(None)
        assert result.is_valid is False


class TestMosaicAmountConversion:
    @pytest.mark.unit
    def test_parse_integer_amount(self):
        result = AmountValidator.parse_human_amount("100")
        assert result.is_valid is True
        assert result.normalized_value == Decimal("100")

    @pytest.mark.unit
    def test_parse_decimal_amount(self):
        result = AmountValidator.parse_human_amount("1.5")
        assert result.is_valid is True
        assert result.normalized_value == Decimal("1.5")

    @pytest.mark.unit
    def test_parse_with_commas(self):
        result = AmountValidator.parse_human_amount("1,000,000")
        assert result.is_valid is True
        assert result.normalized_value == Decimal("1000000")

    @pytest.mark.unit
    def test_parse_with_spaces(self):
        result = AmountValidator.parse_human_amount("1 000 000")
        assert result.is_valid is True
        assert result.normalized_value == Decimal("1000000")

    @pytest.mark.unit
    def test_parse_empty_string(self):
        result = AmountValidator.parse_human_amount("")
        assert result.is_valid is False
        assert "required" in result.error_message.lower()

    @pytest.mark.unit
    def test_parse_negative_amount(self):
        result = AmountValidator.parse_human_amount("-100")
        assert result.is_valid is False
        assert "positive" in result.error_message.lower()

    @pytest.mark.unit
    def test_parse_zero_amount(self):
        result = AmountValidator.parse_human_amount("0")
        assert result.is_valid is False
        assert "zero" in result.error_message.lower()

    @pytest.mark.unit
    def test_parse_invalid_characters(self):
        result = AmountValidator.parse_human_amount("abc")
        assert result.is_valid is False

    @pytest.mark.unit
    def test_parse_with_plus_sign(self):
        result = AmountValidator.parse_human_amount("+100")
        assert result.is_valid is False

    @pytest.mark.unit
    def test_convert_to_micro_units_basic(self):
        result = AmountValidator.convert_to_micro_units(Decimal("1"), 6)
        assert result.is_valid is True
        assert result.normalized_value == 1_000_000

    @pytest.mark.unit
    def test_convert_to_micro_units_decimal(self):
        result = AmountValidator.convert_to_micro_units(Decimal("1.5"), 6)
        assert result.is_valid is True
        assert result.normalized_value == 1_500_000

    @pytest.mark.unit
    def test_convert_to_micro_units_zero_divisibility(self):
        result = AmountValidator.convert_to_micro_units(Decimal("100"), 0)
        assert result.is_valid is True
        assert result.normalized_value == 100

    @pytest.mark.unit
    def test_convert_to_micro_units_max_amount(self):
        result = AmountValidator.convert_to_micro_units(
            Decimal("9223372036854775807"), 0
        )
        assert result.is_valid is True

    @pytest.mark.unit
    def test_convert_exceeds_max_amount(self):
        result = AmountValidator.convert_to_micro_units(
            Decimal("9223372036854775808"), 0
        )
        assert result.is_valid is False
        assert "maximum" in result.error_message.lower()

    @pytest.mark.unit
    def test_validate_decimal_places_within_limit(self):
        result = AmountValidator.validate_decimal_places(Decimal("1.123456"), 6)
        assert result.is_valid is True

    @pytest.mark.unit
    def test_validate_decimal_places_exceeds_limit(self):
        result = AmountValidator.validate_decimal_places(Decimal("1.1234567"), 6)
        assert result.is_valid is False

    @pytest.mark.unit
    def test_validate_decimal_places_zero_divisibility_with_decimal(self):
        result = AmountValidator.validate_decimal_places(Decimal("1.5"), 0)
        assert result.is_valid is False

    @pytest.mark.unit
    def test_validate_full_pipeline(self):
        result = AmountValidator.validate_full("1.5", 6, 2_000_000)
        assert result.is_valid is True
        assert result.normalized_value == 1_500_000

    @pytest.mark.unit
    def test_validate_full_insufficient_balance(self):
        result = AmountValidator.validate_full("100", 0, 50)
        assert result.is_valid is False
        assert "Insufficient" in result.error_message

    @pytest.mark.unit
    def test_validate_full_exact_balance(self):
        result = AmountValidator.validate_full("100", 0, 100)
        assert result.is_valid is True

    @pytest.mark.unit
    def test_validate_full_without_balance_check(self):
        result = AmountValidator.validate_full("1000000", 0)
        assert result.is_valid is True


class TestMosaicIdValidation:
    @pytest.mark.unit
    def test_valid_hex_string(self):
        result = MosaicIdValidator.validate("6BED913FA20223F8")
        assert result.is_valid is True
        assert result.normalized_value == 0x6BED913FA20223F8

    @pytest.mark.unit
    def test_valid_hex_with_prefix(self):
        result = MosaicIdValidator.validate("0x6BED913FA20223F8")
        assert result.is_valid is True
        assert result.normalized_value == 0x6BED913FA20223F8

    @pytest.mark.unit
    def test_valid_integer(self):
        result = MosaicIdValidator.validate(0x6BED913FA20223F8)
        assert result.is_valid is True
        assert result.normalized_value == 0x6BED913FA20223F8

    @pytest.mark.unit
    def test_empty_string(self):
        result = MosaicIdValidator.validate("")
        assert result.is_valid is False

    @pytest.mark.unit
    def test_invalid_hex_characters(self):
        result = MosaicIdValidator.validate("GGGG")
        assert result.is_valid is False

    @pytest.mark.unit
    def test_negative_integer(self):
        result = MosaicIdValidator.validate(-1)
        assert result.is_valid is False

    @pytest.mark.unit
    def test_zero_is_invalid(self):
        result = MosaicIdValidator.validate(0)
        assert result.is_valid is False

    @pytest.mark.unit
    def test_lowercase_hex(self):
        result = MosaicIdValidator.validate("6bed913fa20223f8")
        assert result.is_valid is True
        assert result.normalized_value == 0x6BED913FA20223F8

    @pytest.mark.unit
    def test_whitespace_is_trimmed(self):
        result = MosaicIdValidator.validate("  6BED913FA20223F8  ")
        assert result.is_valid is True


class TestErrorScenarios:
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
    def test_transaction_invalid_mosaic_id(self, transaction_manager):
        recipient = "TD5ZP2WOJKFMGCVC3GO32CQJSU6JF3TZLOIJ2HA"
        mosaics = [{"mosaic_id": "invalid", "amount": 1000000}]
        with pytest.raises(ValueError):
            transaction_manager.create_transfer_transaction(recipient, mosaics)

    @pytest.mark.unit
    def test_transaction_missing_mosaic_id(self, transaction_manager):
        mosaics = [{"amount": 1000000}]
        with pytest.raises(ValueError, match="Missing mosaic_id"):
            transaction_manager.normalize_mosaics(mosaics)

    @pytest.mark.unit
    def test_transaction_negative_amount(self, transaction_manager):
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": -100}]
        with pytest.raises(ValueError):
            transaction_manager.normalize_mosaics(mosaics)

    @pytest.mark.unit
    def test_transaction_zero_amount(self, transaction_manager):
        mosaics = [{"mosaic_id": "0x6BED913FA20223F8", "amount": 0}]
        with pytest.raises(ValueError):
            transaction_manager.normalize_mosaics(mosaics)

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


class TestAccountInfo:
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


class TestValidationResult:
    @pytest.mark.unit
    def test_valid_result(self):
        result = ValidationResult(is_valid=True, normalized_value=123)
        assert result.is_valid is True
        assert result.error_message is None
        assert result.normalized_value == 123

    @pytest.mark.unit
    def test_invalid_result(self):
        result = ValidationResult(is_valid=False, error_message="Test error")
        assert result.is_valid is False
        assert result.error_message == "Test error"
        assert result.normalized_value is None

    @pytest.mark.unit
    def test_result_with_all_fields(self):
        result = ValidationResult(
            is_valid=True, error_message=None, normalized_value="normalized"
        )
        assert result.is_valid is True
        assert result.normalized_value == "normalized"
