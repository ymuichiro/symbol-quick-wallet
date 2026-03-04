"""Tests for aggregate transaction service."""

import json
import os
from unittest.mock import MagicMock

import pytest
import requests
from symbolchain import sc
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.features.aggregate.service import (
    HASH_LOCK_AMOUNT,
    HASH_LOCK_DURATION,
    MAX_COSIGNERS,
    MAX_INNER_TRANSACTIONS,
    AggregateService,
    CosignerInfo,
    InnerTransaction,
    PartialTransactionInfo,
)


def _is_aggregate_prohibited(status: dict[str, object]) -> bool:
    if status.get("group") != "failed":
        return False
    code = str(status.get("code", ""))
    return code.startswith("Failure_Aggregate_") and code.endswith("_Prohibited")


def _select_reachable_testnet_node() -> str:
    seen: set[str] = set()
    env_single = os.getenv("SYMBOL_TEST_NODE_URL", "").strip()
    env_multi = os.getenv("SYMBOL_TEST_NODE_URLS", "")
    env_nodes = [n.strip() for n in env_multi.split(",") if n.strip()]
    candidates = [
        env_single,
        *env_nodes,
        "http://sym-test-01.opening-line.jp:3000",
        "http://sym-test-03.opening-line.jp:3000",
    ]

    for raw in candidates:
        node_url = raw.rstrip("/")
        if not node_url or node_url in seen:
            continue
        seen.add(node_url)
        try:
            response = requests.get(f"{node_url}/node/health", timeout=(3, 5))
            if response.status_code != 200:
                continue
            payload = response.json()
            status = payload.get("status", {}) if isinstance(payload, dict) else {}
            if status.get("apiNode") == "up":
                return node_url
        except requests.RequestException:
            continue

    return "http://sym-test-01.opening-line.jp:3000"


@pytest.fixture
def testnet_facade():
    return SymbolFacade("testnet")


@pytest.fixture
def mock_wallet(testnet_facade):
    wallet = MagicMock()
    wallet.facade = testnet_facade
    wallet.network_name = "testnet"
    wallet.node_url = "http://sym-test-01.opening-line.jp:3000"
    wallet.address = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"

    private_key = PrivateKey.random()
    account = testnet_facade.create_account(private_key)
    wallet.private_key = private_key
    wallet.public_key = str(account.public_key)
    wallet.get_currency_mosaic_id.return_value = 0x6BED913FA20223F8

    return wallet


@pytest.fixture
def aggregate_service(mock_wallet):
    return AggregateService(mock_wallet)


class TestInnerTransactionDataclass:
    def test_inner_transaction_creation(self):
        inner = InnerTransaction(
            type="transfer",
            signer_public_key="abc123",
            recipient_address="TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX",
        )
        assert inner.type == "transfer"
        assert inner.signer_public_key == "abc123"
        assert inner.mosaics == []
        assert inner.message == ""

    def test_inner_transaction_with_mosaics(self):
        inner = InnerTransaction(
            type="transfer",
            signer_public_key="abc123",
            mosaics=[{"mosaic_id": 0x6BED913FA20223F8, "amount": 1000000}],
        )
        assert len(inner.mosaics) == 1
        assert inner.mosaics[0]["mosaic_id"] == 0x6BED913FA20223F8


class TestCosignerInfoDataclass:
    def test_cosigner_info_creation(self):
        cosigner = CosignerInfo(
            public_key="cosigner123",
            address="TCOSIGNER5ADDRESS",
            has_signed=True,
        )
        assert cosigner.public_key == "cosigner123"
        assert cosigner.has_signed is True


class TestPartialTransactionInfoDataclass:
    def test_partial_transaction_info_creation(self):
        partial = PartialTransactionInfo(
            hash="ABC123DEF456",
            signer_public_key="signer123",
            deadline=1234567890,
            expires_in=3600,
        )
        assert partial.hash == "ABC123DEF456"
        assert partial.expires_in == 3600
        assert partial.inner_transactions == []
        assert partial.cosignatures == []


class TestAggregateServiceInit:
    def test_service_initialization(self, mock_wallet):
        service = AggregateService(mock_wallet)
        assert service.wallet == mock_wallet
        assert service.facade == mock_wallet.facade

    def test_service_with_custom_node_url(self, mock_wallet):
        custom_url = "http://custom-node:3000"
        service = AggregateService(mock_wallet, node_url=custom_url)
        assert service.node_url == custom_url


class TestCreateEmbeddedTransfer:
    def test_create_embedded_transfer_basic(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="Test message",
        )
        assert embedded is not None
        assert isinstance(embedded, sc.EmbeddedTransaction)

    def test_create_embedded_transfer_with_mosaics(
        self, aggregate_service, mock_wallet
    ):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        mosaics = [{"mosaic_id": 0x6BED913FA20223F8, "amount": 1000000}]
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=mosaics,
            message="",
        )
        assert embedded is not None


class TestCreateAggregateComplete:
    def test_create_aggregate_complete_basic(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="Inner tx",
        )
        aggregate = aggregate_service.create_aggregate_complete([inner_tx])
        assert aggregate is not None

    def test_create_aggregate_complete_multiple_inner(
        self, aggregate_service, mock_wallet
    ):
        recipient1 = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        recipient2 = "TDWBA6L3CZ6VTZAZPAISL3RWM5VKMHM6J6IM3LY"
        inner1 = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient1,
            mosaics=[],
            message="Inner 1",
        )
        inner2 = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient2,
            mosaics=[],
            message="Inner 2",
        )
        aggregate = aggregate_service.create_aggregate_complete([inner1, inner2])
        assert aggregate is not None


class TestCreateAggregateBonded:
    def test_create_aggregate_bonded_basic(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="Bonded inner tx",
        )
        aggregate = aggregate_service.create_aggregate_bonded([inner_tx])
        assert aggregate is not None


class TestCreateHashLock:
    def test_create_hash_lock_basic(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_bonded([inner_tx])
        hash_lock = aggregate_service.create_hash_lock(aggregate)
        assert hash_lock is not None

    def test_create_hash_lock_custom_amount(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_bonded([inner_tx])
        custom_amount = 20_000_000
        hash_lock = aggregate_service.create_hash_lock(
            aggregate, lock_amount=custom_amount
        )
        assert hash_lock is not None


class TestTransactionSigning:
    def test_sign_transaction(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([inner_tx])
        signature = aggregate_service.sign_transaction(aggregate)
        assert signature is not None

    def test_cosign_transaction(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_bonded([inner_tx])
        cosignature = aggregate_service.cosign_transaction(aggregate)
        assert cosignature is not None


class TestTransactionHash:
    def test_calculate_transaction_hash(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([inner_tx])
        tx_hash = aggregate_service.calculate_transaction_hash(aggregate)
        assert tx_hash is not None
        assert len(tx_hash) == 64


class TestFeeCalculation:
    def test_calculate_fee_basic(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([inner_tx])
        fee = aggregate_service.calculate_fee(aggregate, num_cosignatures=0)
        assert fee > 0

    def test_calculate_fee_with_cosignatures(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([inner_tx])
        fee_no_cosig = aggregate_service.calculate_fee(aggregate, num_cosignatures=0)
        fee_with_cosig = aggregate_service.calculate_fee(aggregate, num_cosignatures=2)
        assert fee_with_cosig > fee_no_cosig


class TestNormalizeAddress:
    def test_normalize_address_with_hyphens(self, aggregate_service):
        address = "TBTZ-K5C5-LQZS-H7HG-WOY4-L6UB-QGHI-Q6QQ-HRTH-RBX"
        normalized = aggregate_service._normalize_address(address)
        assert "-" not in normalized
        assert normalized == "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"

    def test_normalize_address_lowercase(self, aggregate_service):
        address = "tbtzk5c5lqzsh7hgwoy4l6ubqghiq6qqhrthrbx"
        normalized = aggregate_service._normalize_address(address)
        assert normalized.isupper()


class TestParseInnerTransactions:
    def test_parse_inner_transactions_empty(self, aggregate_service):
        tx_body = {"transactions": []}
        result = aggregate_service._parse_inner_transactions(tx_body)
        assert result == []

    def test_parse_inner_transactions_with_transfer(self, aggregate_service):
        tx_body = {
            "transactions": [
                {
                    "type": 16724,
                    "signerPublicKey": "ABC123",
                    "recipientAddress": "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX",
                    "mosaics": [{"id": "6BED913FA20223F8", "amount": "1000000"}],
                    "message": "0048656C6C6F",
                }
            ]
        }
        result = aggregate_service._parse_inner_transactions(tx_body)
        assert len(result) == 1
        assert result[0].type == "transfer"


class TestParseMosaics:
    def test_parse_mosaics_empty(self, aggregate_service):
        result = aggregate_service._parse_mosaics([])
        assert result == []

    def test_parse_mosaics_with_mosaic(self, aggregate_service):
        mosaics = [{"id": "6BED913FA20223F8", "amount": "1000000"}]
        result = aggregate_service._parse_mosaics(mosaics)
        assert len(result) == 1
        assert result[0]["mosaic_id"] == 0x6BED913FA20223F8
        assert result[0]["amount"] == 1000000


class TestParseMessage:
    def test_parse_message_empty(self, aggregate_service):
        result = aggregate_service._parse_message("")
        assert result == ""

    def test_parse_message_plain_text(self, aggregate_service):
        message_hex = "0048656C6C6F"
        result = aggregate_service._parse_message(message_hex)
        assert result == "Hello"


class TestTxTypeToName:
    def test_tx_type_to_name_transfer(self, aggregate_service):
        result = aggregate_service._tx_type_to_name(16724)
        assert result == "transfer"

    def test_tx_type_to_name_aggregate_complete(self, aggregate_service):
        result = aggregate_service._tx_type_to_name(16705)
        assert result == "aggregate_complete"

    def test_tx_type_to_name_aggregate_bonded(self, aggregate_service):
        result = aggregate_service._tx_type_to_name(16961)
        assert result == "aggregate_bonded"

    def test_tx_type_to_name_unknown(self, aggregate_service):
        result = aggregate_service._tx_type_to_name(99999)
        assert "type_99999" in result


class TestConstants:
    def test_hash_lock_amount(self):
        assert HASH_LOCK_AMOUNT == 10_000_000

    def test_hash_lock_duration(self):
        assert HASH_LOCK_DURATION == 480

    def test_max_inner_transactions(self):
        assert MAX_INNER_TRANSACTIONS == 100

    def test_max_cosigners(self):
        assert MAX_COSIGNERS == 25


class TestAttachSignature:
    def test_attach_signature(self, aggregate_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        inner_tx = aggregate_service.create_embedded_transfer(
            signer_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([inner_tx])
        signature = aggregate_service.sign_transaction(aggregate)
        payload = aggregate_service.attach_signature(aggregate, signature)
        assert payload is not None
        assert len(payload) > 0


class TestBuildCosignaturePayload:
    def test_build_cosignature_payload(self, aggregate_service):
        tx_hash = "ABC123DEF456789ABC123DEF456789ABC123DEF456789ABC123DEF456789AB12"
        payload = aggregate_service._build_cosignature_payload(tx_hash)
        payload_dict = json.loads(payload)
        assert "payload" in payload_dict


@pytest.mark.integration
class TestAggregateServiceIntegration:
    """Integration tests that hit the real testnet.

    Run with: uv run pytest tests/features/aggregate/test_service.py -m integration -v
    """

    def test_fetch_partial_transactions_real_node(self, mock_wallet):
        """Test fetching partial transactions from a real testnet node."""
        import requests

        response = requests.get(f"{mock_wallet.node_url}/node/health", timeout=10)
        if response.status_code != 200:
            pytest.skip("Node not available")

        service = AggregateService(mock_wallet)
        result = service.fetch_partial_transactions()

        assert isinstance(result, list)

    def test_poll_for_transaction_status_nonexistent(self, mock_wallet):
        """Test polling transaction status for non-existent hash raises TimeoutError."""
        import requests

        response = requests.get(f"{mock_wallet.node_url}/node/health", timeout=10)
        if response.status_code != 200:
            pytest.skip("Node not available")

        service = AggregateService(mock_wallet)

        with pytest.raises(TimeoutError, match="Transaction status not found"):
            service.poll_for_transaction_status(
                "A000000000000000000000000000000000000000000000000000000000000000",
                timeout_seconds=5,
                poll_interval_seconds=1,
            )


@pytest.mark.integration
@pytest.mark.slow
class TestAggregateTransactionIntegration:
    """Slow integration tests for aggregate transactions on testnet.

    These tests create real transactions and require funded accounts.
    Run with: uv run pytest tests/features/aggregate/test_service.py -m "integration and slow" -v

    Note: Provide a test key via --test-key-file (recommended) or SYMBOL_TEST_PRIVATE_KEY.
    The account needs at least 20 XYM for aggregate and hash lock fees.
    """

    @pytest.fixture
    def real_wallet(
        self,
        test_private_key: PrivateKey | None,
        request: pytest.FixtureRequest,
    ):
        """Create a real wallet from test private key."""
        if test_private_key is None:
            message = (
                "No test private key available. "
                "Run: uv run python scripts/setup_test_key.py "
                "or set SYMBOL_TEST_PRIVATE_KEY."
            )
            if request.config.getoption("--require-live-key"):
                pytest.fail(message)
            pytest.skip(message)

        facade = SymbolFacade("testnet")
        account = facade.create_account(test_private_key)

        wallet = MagicMock()
        wallet.facade = facade
        wallet.network_name = "testnet"
        wallet.node_url = _select_reachable_testnet_node()
        wallet.address = str(account.address)
        wallet.private_key = test_private_key
        wallet.public_key = str(account.public_key)
        wallet.get_currency_mosaic_id.return_value = 0x72C0212E67A08BCE

        return wallet

    def test_create_aggregate_complete_transaction(self, real_wallet):
        """Test creating an aggregate complete transaction (without announcing)."""
        service = AggregateService(real_wallet)

        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"

        embedded = service.create_embedded_transfer(
            signer_public_key=str(real_wallet.public_key),
            recipient_address=recipient,
            mosaics=[],
            message="Integration test message",
        )

        assert embedded is not None

        aggregate = service.create_aggregate_complete([embedded], fee_multiplier=100)

        assert aggregate is not None

        signature = service.sign_transaction(aggregate)
        assert signature is not None

        tx_hash = service.calculate_transaction_hash(aggregate)
        assert len(tx_hash) == 64

    def test_create_aggregate_bonded_transaction(self, real_wallet):
        """Test creating an aggregate bonded transaction (without announcing)."""
        service = AggregateService(real_wallet)

        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"

        embedded = service.create_embedded_transfer(
            signer_public_key=str(real_wallet.public_key),
            recipient_address=recipient,
            mosaics=[],
            message="Bonded test message",
        )

        assert embedded is not None

        aggregate = service.create_aggregate_bonded([embedded], fee_multiplier=100)

        assert aggregate is not None

        hash_lock = service.create_hash_lock(aggregate)

        assert hash_lock is not None

        signature = service.sign_transaction(hash_lock)
        assert signature is not None

        tx_hash = service.calculate_transaction_hash(hash_lock)
        assert len(tx_hash) == 64

    def test_create_aggregate_complete_with_mosaic(self, real_wallet):
        """Test creating an aggregate complete with mosaic transfer (without announcing)."""
        service = AggregateService(real_wallet)

        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        mosaics = [{"mosaic_id": 0x72C0212E67A08BCE, "amount": 1000000}]

        embedded = service.create_embedded_transfer(
            signer_public_key=str(real_wallet.public_key),
            recipient_address=recipient,
            mosaics=mosaics,
            message="Test mosaic transfer",
        )

        assert embedded is not None

        aggregate = service.create_aggregate_complete([embedded], fee_multiplier=100)

        assert aggregate is not None

        fee = service.calculate_fee(aggregate, num_cosignatures=0)
        assert fee > 0

    def test_create_aggregate_with_multiple_inner_transactions(self, real_wallet):
        """Test creating an aggregate with multiple inner transactions."""
        service = AggregateService(real_wallet)

        recipient1 = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        recipient2 = "TCOMA5VG67TZH4X55HGZOXOFP7S232CYEQMOS7Q"

        embedded1 = service.create_embedded_transfer(
            signer_public_key=str(real_wallet.public_key),
            recipient_address=recipient1,
            mosaics=[],
            message="Inner tx 1",
        )

        embedded2 = service.create_embedded_transfer(
            signer_public_key=str(real_wallet.public_key),
            recipient_address=recipient2,
            mosaics=[],
            message="Inner tx 2",
        )

        aggregate = service.create_aggregate_complete(
            [embedded1, embedded2], fee_multiplier=100
        )

        assert aggregate is not None

        signature = service.sign_transaction(aggregate)
        assert signature is not None

        payload = service.attach_signature(aggregate, signature)
        assert payload is not None
        assert len(payload) > 0

    def test_cosignature_creation(self, real_wallet):
        """Test creating a cosignature for an aggregate transaction."""
        service = AggregateService(real_wallet)

        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"

        embedded = service.create_embedded_transfer(
            signer_public_key=str(real_wallet.public_key),
            recipient_address=recipient,
            mosaics=[],
            message="Cosignature test",
        )

        aggregate = service.create_aggregate_bonded([embedded], fee_multiplier=100)

        cosignature = service.cosign_transaction(aggregate)

        assert cosignature is not None
        assert str(cosignature.signer_public_key) == real_wallet.public_key


@pytest.mark.integration
@pytest.mark.slow
class TestAggregateAnnounceIntegration:
    """Live integration tests that announce transactions to testnet.

    WARNING: These tests spend real XYM from the test account!
    Run with: uv run pytest tests/features/aggregate/test_service.py -m "integration and slow" -v -k "Announce"

    Requirements:
    - test key via --test-key-file (recommended) or SYMBOL_TEST_PRIVATE_KEY
    - Account needs at least 1 XYM for aggregate complete test
    - Account needs at least 11 XYM for aggregate bonded test (10 XYM for hash lock)
    """

    @pytest.fixture
    def real_wallet(
        self,
        test_private_key: PrivateKey | None,
        request: pytest.FixtureRequest,
    ):
        """Create a real wallet from test private key."""
        if test_private_key is None:
            message = (
                "No test private key available. "
                "Run: uv run python scripts/setup_test_key.py "
                "or set SYMBOL_TEST_PRIVATE_KEY."
            )
            if request.config.getoption("--require-live-key"):
                pytest.fail(message)
            pytest.skip(message)

        facade = SymbolFacade("testnet")
        account = facade.create_account(test_private_key)

        wallet = MagicMock()
        wallet.facade = facade
        wallet.network_name = "testnet"
        wallet.node_url = "http://sym-test-01.opening-line.jp:3000"
        wallet.address = str(account.address)
        wallet.private_key = test_private_key
        wallet.public_key = str(account.public_key)
        wallet.get_currency_mosaic_id.return_value = 0x72C0212E67A08BCE

        return wallet

    def test_node_availability(self, real_wallet):
        """Test that the testnet node is available."""
        response = requests.get(f"{real_wallet.node_url}/node/health", timeout=(3, 10))
        assert response.status_code == 200

    def test_announce_aggregate_complete_no_mosaic(self, real_wallet):
        """Test announcing aggregate complete with no mosaic (message only).

        This test costs minimal fees (~0.1 XYM).
        """
        service = AggregateService(real_wallet)

        # Use a known-valid testnet address to avoid checksum-related false negatives.
        recipient = str(real_wallet.address)

        embedded = service.create_embedded_transfer(
            signer_public_key=str(real_wallet.public_key),
            recipient_address=recipient,
            mosaics=[],
            message="Aggregate complete integration test",
        )

        result = service.create_and_announce_aggregate_complete(
            [embedded], fee_multiplier=1000
        )

        assert "hash" in result
        assert len(result["hash"]) == 64

        status = service.poll_for_transaction_status(
            result["hash"], timeout_seconds=120, poll_interval_seconds=5
        )
        if _is_aggregate_prohibited(status):
            pytest.skip(
                f"Aggregate transactions are prohibited by this node/network: {status.get('code')}"
            )

        assert status.get("group") == "confirmed", (
            f"Aggregate complete failed with code={status.get('code')}"
        )
