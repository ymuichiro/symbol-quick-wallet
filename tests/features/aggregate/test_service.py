"""Tests for aggregate transaction service."""

import json
from dataclasses import asdict
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from symbolchain import sc
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.features.aggregate.service import (
    HASH_LOCK_AMOUNT,
    HASH_LOCK_DURATION,
    MAX_COSIGNERS,
    MAX_INNER_TRANSACTIONS,
    AggregateService,
    AggregateTransactionInfo,
    CosignerInfo,
    InnerTransaction,
    PartialTransactionInfo,
)


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
        recipient2 = "TANOTHER5ADDRESS5HERE5XXXXXXXXXXX"
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
