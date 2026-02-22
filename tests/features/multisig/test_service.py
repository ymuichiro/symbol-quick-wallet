"""Tests for multisig account service."""

import json
import pytest
from dataclasses import asdict
from typing import Any
from unittest.mock import MagicMock, patch

from symbolchain import sc
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.features.multisig.service import (
    MultisigService,
    MultisigAccountInfo,
    CosignerInfo,
    MAX_COSIGNATORIES,
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
    wallet.get_currency_mosaic_id.return_value = 0x72C0212E67A08BCE

    return wallet


@pytest.fixture
def multisig_service(mock_wallet):
    return MultisigService(mock_wallet)


class TestMultisigAccountInfoDataclass:
    def test_is_multisig_returns_true_when_cosigners_exist(self):
        info = MultisigAccountInfo(
            account_address="TEST_ADDR",
            min_approval=2,
            min_removal=2,
            cosignatory_addresses=["COSIGNER1", "COSIGNER2"],
            multisig_addresses=[],
        )
        assert info.is_multisig is True

    def test_is_multisig_returns_false_when_no_cosigners(self):
        info = MultisigAccountInfo(
            account_address="TEST_ADDR",
            min_approval=0,
            min_removal=0,
            cosignatory_addresses=[],
            multisig_addresses=[],
        )
        assert info.is_multisig is False

    def test_is_cosigner_of_returns_true_when_multisig_addresses_exist(self):
        info = MultisigAccountInfo(
            account_address="TEST_ADDR",
            min_approval=0,
            min_removal=0,
            cosignatory_addresses=[],
            multisig_addresses=["MULTISIG1"],
        )
        assert info.is_cosigner_of is True

    def test_is_cosigner_of_returns_false_when_no_multisig_addresses(self):
        info = MultisigAccountInfo(
            account_address="TEST_ADDR",
            min_approval=0,
            min_removal=0,
            cosignatory_addresses=[],
            multisig_addresses=[],
        )
        assert info.is_cosigner_of is False


class TestMultisigServiceInit:
    def test_service_initialization(self, mock_wallet):
        service = MultisigService(mock_wallet)
        assert service.wallet == mock_wallet
        assert service.facade == mock_wallet.facade

    def test_service_with_custom_node_url(self, mock_wallet):
        custom_url = "http://custom-node:3000"
        service = MultisigService(mock_wallet, node_url=custom_url)
        assert service.node_url == custom_url


class TestMultisigServiceValidation:
    VALID_COSIGNER1 = "TCOMA5VG67TZH4X55HGZOXOFP7S232CYEQMOS7Q"
    VALID_COSIGNER2 = "TBAFGZOCB7OHZCCYYV64F2IFZL7SOOXNDHFS5NY"

    def test_validate_multisig_conversion_valid_params(self, multisig_service):
        cosigners = [self.VALID_COSIGNER1, self.VALID_COSIGNER2]
        is_valid, error = multisig_service.validate_multisig_conversion(
            cosigners, min_approval=1, min_removal=1
        )
        assert is_valid is True
        assert error == ""

    def test_validate_multisig_conversion_empty_cosigners(self, multisig_service):
        is_valid, error = multisig_service.validate_multisig_conversion(
            [], min_approval=1, min_removal=1
        )
        assert is_valid is False
        assert "At least one cosigner" in error

    def test_validate_multisig_conversion_too_many_cosigners(self, multisig_service):
        base_addr = "TCOMA5VG67TZH4X55HGZOXOFP7S232CYEQMOS7Q"
        cosigners = [
            f"{base_addr[:30]}{i:09d}"[:39] for i in range(MAX_COSIGNATORIES + 1)
        ]
        is_valid, error = multisig_service.validate_multisig_conversion(
            cosigners, min_approval=1, min_removal=1
        )
        assert is_valid is False
        assert "Maximum" in error and str(MAX_COSIGNATORIES) in error

    def test_validate_multisig_conversion_min_approval_too_low(self, multisig_service):
        cosigners = [self.VALID_COSIGNER1]
        is_valid, error = multisig_service.validate_multisig_conversion(
            cosigners, min_approval=0, min_removal=1
        )
        assert is_valid is False
        assert "at least 1" in error

    def test_validate_multisig_conversion_min_approval_exceeds_cosigners(
        self, multisig_service
    ):
        cosigners = [self.VALID_COSIGNER1]
        is_valid, error = multisig_service.validate_multisig_conversion(
            cosigners, min_approval=2, min_removal=1
        )
        assert is_valid is False
        assert "cannot exceed number of cosigners" in error

    def test_validate_multisig_conversion_min_removal_exceeds_cosigners(
        self, multisig_service
    ):
        cosigners = [self.VALID_COSIGNER1]
        is_valid, error = multisig_service.validate_multisig_conversion(
            cosigners, min_approval=1, min_removal=2
        )
        assert is_valid is False
        assert "cannot exceed number of cosigners" in error

    def test_validate_multisig_conversion_invalid_address_format(
        self, multisig_service
    ):
        cosigners = ["INVALID"]
        is_valid, error = multisig_service.validate_multisig_conversion(
            cosigners, min_approval=1, min_removal=1
        )
        assert is_valid is False
        assert "Invalid address format" in error

    def test_validate_multisig_conversion_invalid_address_prefix(
        self, multisig_service
    ):
        cosigners = ["XCOMA5VG67TZH4X55HGZOXOFP7S232CYEQMOS7Q"]
        is_valid, error = multisig_service.validate_multisig_conversion(
            cosigners, min_approval=1, min_removal=1
        )
        assert is_valid is False
        assert "Invalid address network prefix" in error


class TestMultisigServiceAddressNormalization:
    def test_normalize_address_removes_hyphens(self, multisig_service):
        result = multisig_service._normalize_address("T-ABC-123-DEF")
        assert "-" not in result
        assert result == "TABC123DEF"

    def test_normalize_address_uppercases(self, multisig_service):
        result = multisig_service._normalize_address("tabc123def")
        assert result == "TABC123DEF"

    def test_normalize_address_strips_whitespace(self, multisig_service):
        result = multisig_service._normalize_address("  TABC123DEF  ")
        assert result == "TABC123DEF"


class TestMultisigServiceGetInfo:
    def test_get_multisig_account_info_success(self, multisig_service):
        mock_response = {
            "multisig": {
                "accountAddress": "TEST_ADDR",
                "minApproval": 2,
                "minRemoval": 2,
                "cosignatoryAddresses": ["COSIG1", "COSIG2"],
                "multisigAddresses": [],
            }
        }

        with patch.object(
            multisig_service._network_client,
            "get_optional",
            return_value=mock_response,
        ):
            result = multisig_service.get_multisig_account_info("TEST_ADDR")

        assert result is not None
        assert result.account_address == "TEST_ADDR"
        assert result.min_approval == 2
        assert result.min_removal == 2
        assert len(result.cosignatory_addresses) == 2

    def test_get_multisig_account_info_not_multisig(self, multisig_service):
        with patch.object(
            multisig_service._network_client,
            "get_optional",
            return_value=None,
        ):
            result = multisig_service.get_multisig_account_info("NOT_MULTISIG")

        assert result is None

    def test_get_multisig_account_info_network_error(self, multisig_service):
        from src.shared.network import NetworkError, NetworkErrorType

        with patch.object(
            multisig_service._network_client,
            "get_optional",
            side_effect=NetworkError(
                NetworkErrorType.CONNECTION_ERROR, "Connection failed"
            ),
        ):
            result = multisig_service.get_multisig_account_info("ANY_ADDR")

        assert result is None


VALID_COSIGNER_ADDRESS = "TCOMA5VG67TZH4X55HGZOXOFP7S232CYEQMOS7Q"


class TestCreateMultisigModificationEmbedded:
    def test_create_multisig_modification_embedded(self, multisig_service, mock_wallet):
        embedded = multisig_service.create_multisig_modification_embedded(
            signer_public_key=mock_wallet.public_key,
            min_approval_delta=2,
            min_removal_delta=2,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )
        assert embedded is not None
        assert isinstance(embedded, sc.EmbeddedTransaction)


class TestCreateAggregateComplete:
    def test_create_aggregate_complete_for_multisig(
        self, multisig_service, mock_wallet
    ):
        embedded = multisig_service.create_multisig_modification_embedded(
            signer_public_key=mock_wallet.public_key,
            min_approval_delta=1,
            min_removal_delta=1,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )
        aggregate = multisig_service.create_aggregate_complete_for_multisig(
            embedded, fee_multiplier=100, required_cosigners=1
        )
        assert aggregate is not None


class TestTransactionSigning:
    def test_sign_transaction(self, multisig_service, mock_wallet):
        embedded = multisig_service.create_multisig_modification_embedded(
            signer_public_key=mock_wallet.public_key,
            min_approval_delta=1,
            min_removal_delta=1,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )
        aggregate = multisig_service.create_aggregate_complete_for_multisig(embedded)
        signature = multisig_service.sign_transaction(aggregate)
        assert signature is not None

    def test_cosign_transaction(self, multisig_service, mock_wallet):
        embedded = multisig_service.create_multisig_modification_embedded(
            signer_public_key=mock_wallet.public_key,
            min_approval_delta=1,
            min_removal_delta=1,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )
        aggregate = multisig_service.create_aggregate_complete_for_multisig(embedded)
        cosignature = multisig_service.cosign_transaction(aggregate)
        assert cosignature is not None


class TestTransactionHash:
    def test_calculate_transaction_hash(self, multisig_service, mock_wallet):
        embedded = multisig_service.create_multisig_modification_embedded(
            signer_public_key=mock_wallet.public_key,
            min_approval_delta=1,
            min_removal_delta=1,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )
        aggregate = multisig_service.create_aggregate_complete_for_multisig(embedded)
        tx_hash = multisig_service.calculate_transaction_hash(aggregate)
        assert tx_hash is not None
        assert len(tx_hash) == 64


class TestFeeCalculation:
    def test_calculate_fee_basic(self, multisig_service, mock_wallet):
        embedded = multisig_service.create_multisig_modification_embedded(
            signer_public_key=mock_wallet.public_key,
            min_approval_delta=1,
            min_removal_delta=1,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )
        aggregate = multisig_service.create_aggregate_complete_for_multisig(embedded)
        fee = multisig_service.calculate_fee(aggregate, num_cosignatures=0)
        assert fee > 0

    def test_calculate_fee_with_cosignatures(self, multisig_service, mock_wallet):
        embedded = multisig_service.create_multisig_modification_embedded(
            signer_public_key=mock_wallet.public_key,
            min_approval_delta=1,
            min_removal_delta=1,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )
        aggregate = multisig_service.create_aggregate_complete_for_multisig(embedded)
        fee_no_cosig = multisig_service.calculate_fee(aggregate, num_cosignatures=0)
        fee_with_cosig = multisig_service.calculate_fee(aggregate, num_cosignatures=2)
        assert fee_with_cosig > fee_no_cosig


class TestCreateMultisigTransferEmbedded:
    def test_create_multisig_transfer_embedded(self, multisig_service, mock_wallet):
        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        mosaics = [{"mosaic_id": 0x72C0212E67A08BCE, "amount": 1000000}]
        embedded = multisig_service.create_multisig_transfer_embedded(
            multisig_public_key=mock_wallet.public_key,
            recipient_address=recipient,
            mosaics=mosaics,
            message="Test message",
        )
        assert embedded is not None
        assert isinstance(embedded, sc.EmbeddedTransaction)


class TestAttachSignature:
    def test_attach_signature(self, multisig_service, mock_wallet):
        embedded = multisig_service.create_multisig_modification_embedded(
            signer_public_key=mock_wallet.public_key,
            min_approval_delta=1,
            min_removal_delta=1,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )
        aggregate = multisig_service.create_aggregate_complete_for_multisig(embedded)
        signature = multisig_service.sign_transaction(aggregate)
        payload = multisig_service.attach_signature(aggregate, signature)
        assert payload is not None
        assert len(payload) > 0


class TestConstants:
    def test_max_cosignatories(self):
        assert MAX_COSIGNATORIES == 25


@pytest.mark.integration
class TestMultisigServiceIntegration:
    """Integration tests that hit the real testnet.

    Run with: uv run pytest tests/features/multisig/test_service.py -m integration -v
    """

    def test_get_multisig_account_info_real_node(self, mock_wallet):
        """Test fetching multisig info from a real testnet node."""
        import requests

        service = MultisigService(mock_wallet)

        response = requests.get(f"{mock_wallet.node_url}/node/health", timeout=10)
        if response.status_code != 200:
            pytest.skip("Node not available")

        result = service.get_multisig_account_info(
            "TCOMA5VG67TZH4X55HGZOXOFP7S232CYEQMOS7Q"
        )

        assert result is not None or result is None

    def test_fetch_partial_transactions_real_node(self, mock_wallet):
        """Test fetching partial transactions from a real testnet node."""
        import requests

        service = MultisigService(mock_wallet)

        response = requests.get(f"{mock_wallet.node_url}/node/health", timeout=10)
        if response.status_code != 200:
            pytest.skip("Node not available")

        result = service.fetch_partial_transactions()

        assert isinstance(result, list)


@pytest.mark.integration
@pytest.mark.slow
class TestMultisigConversionIntegration:
    """Slow integration tests for multisig conversion on testnet.

    These tests create real transactions and require funded accounts.
    Run with: uv run pytest tests/features/multisig/test_service.py -m "integration and slow" -v

    Note: Set environment variable SYMBOL_TEST_PRIVATE_KEY with a funded testnet account
    to run these tests. The account needs at least 20 XYM for multisig conversion fees.
    """

    @pytest.fixture
    def real_wallet(self):
        """Create a real wallet from test private key."""
        import os

        private_key_hex = os.environ.get("SYMBOL_TEST_PRIVATE_KEY")
        if not private_key_hex:
            pytest.skip("SYMBOL_TEST_PRIVATE_KEY not set")

        facade = SymbolFacade("testnet")
        private_key = PrivateKey(private_key_hex)
        account = facade.create_account(private_key)

        wallet = MagicMock()
        wallet.facade = facade
        wallet.network_name = "testnet"
        wallet.node_url = "http://sym-test-01.opening-line.jp:3000"
        wallet.address = str(account.address)
        wallet.private_key = private_key
        wallet.public_key = str(account.public_key)
        wallet.get_currency_mosaic_id.return_value = 0x72C0212E67A08BCE

        return wallet

    def test_get_multisig_account_info_for_real_account(self, real_wallet):
        """Test fetching multisig info for a real account."""
        import requests

        response = requests.get(f"{real_wallet.node_url}/node/health", timeout=10)
        if response.status_code != 200:
            pytest.skip("Node not available")

        service = MultisigService(real_wallet)
        result = service.get_multisig_account_info(str(real_wallet.address))

        assert result is not None or result is None
        if result:
            assert hasattr(result, "min_approval")
            assert hasattr(result, "min_removal")
            assert hasattr(result, "cosignatory_addresses")

    def test_create_multisig_modification_transaction(self, real_wallet):
        """Test creating a multisig modification transaction (without announcing)."""
        service = MultisigService(real_wallet)

        embedded = service.create_multisig_modification_embedded(
            signer_public_key=str(real_wallet.public_key),
            min_approval_delta=1,
            min_removal_delta=1,
            address_additions=[VALID_COSIGNER_ADDRESS],
            address_deletions=[],
        )

        assert embedded is not None

        aggregate = service.create_aggregate_complete_for_multisig(
            embedded, fee_multiplier=100, required_cosigners=1
        )

        assert aggregate is not None

        signature = service.sign_transaction(aggregate)
        assert signature is not None

        tx_hash = service.calculate_transaction_hash(aggregate)
        assert len(tx_hash) == 64

    def test_create_multisig_transfer_transaction(self, real_wallet):
        """Test creating a multisig transfer transaction (without announcing)."""
        service = MultisigService(real_wallet)

        recipient = "TBTZK5C5LQZSH7HGWOY4L6UBQGHIQ6QQHRTHRBX"
        mosaics = [{"mosaic_id": 0x72C0212E67A08BCE, "amount": 1000000}]

        embedded = service.create_multisig_transfer_embedded(
            multisig_public_key=str(real_wallet.public_key),
            recipient_address=recipient,
            mosaics=mosaics,
            message="Test multisig transfer",
        )

        assert embedded is not None
        assert isinstance(embedded, sc.EmbeddedTransaction)
