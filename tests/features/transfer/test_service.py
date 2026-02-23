import pytest

from src.transaction import TransactionManager
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


@pytest.fixture
def loaded_wallet(wallet):
    wallet.create_wallet()
    return wallet


@pytest.fixture
def transaction_manager(loaded_wallet):
    return TransactionManager(loaded_wallet)


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
        from symbolchain.facade.SymbolFacade import SymbolFacade

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


class TestTransactionErrors:
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
