"""Tests for lock transaction service."""

from __future__ import annotations

import hashlib
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from symbolchain.CryptoTypes import PrivateKey, PublicKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.features.lock.service import (
    HASH_LOCK_AMOUNT,
    HASH_LOCK_DURATION,
    HashLockInfo,
    LockHashAlgorithm,
    LockService,
    SecretLockInfo,
    SecretProofPair,
)


class MockWallet:
    def __init__(self, network_name: str = "testnet"):
        self.facade = SymbolFacade(network_name)
        self.account = self.facade.create_account(PrivateKey.random())
        self.address = self.account.address
        self.public_key = self.account.public_key
        self.private_key = self.account.key_pair.private_key
        self.network_name = network_name
        self.node_url = "http://sym-test-01.opening-line.jp:3000"
        self._currency_mosaic_id = 0x72C0212E67A08BCE

    def get_currency_mosaic_id(self) -> int | None:
        return self._currency_mosaic_id


class TestSecretProofPair:
    def test_generate_sha3_256(self):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)

        assert len(pair.secret) == 32
        assert len(pair.proof) == 20
        assert pair.algorithm == LockHashAlgorithm.SHA3_256

        expected_secret = hashlib.sha3_256(pair.proof).digest()
        assert pair.secret == expected_secret

    def test_generate_hash_256(self):
        pair = SecretProofPair.generate(LockHashAlgorithm.HASH_256)

        assert len(pair.secret) == 32
        assert len(pair.proof) == 20
        assert pair.algorithm == LockHashAlgorithm.HASH_256

        expected_secret = hashlib.sha256(pair.proof).digest()
        assert pair.secret == expected_secret

    def test_generate_hash_160(self):
        pair = SecretProofPair.generate(LockHashAlgorithm.HASH_160)

        assert len(pair.secret) == 20
        assert len(pair.proof) == 20
        assert pair.algorithm == LockHashAlgorithm.HASH_160

        expected_secret = hashlib.new(
            "ripemd160", hashlib.sha256(pair.proof).digest()
        ).digest()
        assert pair.secret == expected_secret

    def test_from_proof(self):
        proof = os.urandom(20)
        pair = SecretProofPair.from_proof(proof, LockHashAlgorithm.SHA3_256)

        assert pair.proof == proof
        expected_secret = hashlib.sha3_256(proof).digest()
        assert pair.secret == expected_secret

    def test_secret_hex(self):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)
        assert pair.secret_hex == pair.secret.hex().upper()

    def test_proof_hex(self):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)
        assert pair.proof_hex == pair.proof.hex().upper()


class TestSecretLockInfo:
    def test_from_api_response(self):
        data = {
            "lock": {
                "compositeHash": "ABC123",
                "ownerAddress": "OWNER_ADDRESS",
                "recipientAddress": "RECIPIENT_ADDRESS",
                "mosaicId": "0x72C0212E67A08BCE",
                "amount": "1000000",
                "endHeight": "100000",
                "hashAlgorithm": 0,
                "secret": "SECRET_HEX",
                "status": 0,
            }
        }

        lock_info = SecretLockInfo.from_api_response(data)

        assert lock_info.composite_hash == "ABC123"
        assert lock_info.owner_address == "OWNER_ADDRESS"
        assert lock_info.recipient_address == "RECIPIENT_ADDRESS"
        assert lock_info.mosaic_id == 0x72C0212E67A08BCE
        assert lock_info.amount == 1000000
        assert lock_info.end_height == 100000
        assert lock_info.hash_algorithm == 0
        assert lock_info.secret == "SECRET_HEX"
        assert lock_info.status == 0

    def test_from_api_response_with_int_mosaic_id(self):
        data = {
            "lock": {
                "compositeHash": "ABC123",
                "ownerAddress": "OWNER",
                "recipientAddress": "RECIPIENT",
                "mosaicId": 0x72C0212E67A08BCE,
                "amount": "500000",
                "endHeight": "50000",
                "hashAlgorithm": 1,
                "secret": "SECRET",
                "status": 1,
            }
        }

        lock_info = SecretLockInfo.from_api_response(data)

        assert lock_info.mosaic_id == 0x72C0212E67A08BCE
        assert lock_info.hash_algorithm == 1
        assert lock_info.status == 1


class TestHashLockInfo:
    def test_from_api_response(self):
        data = {
            "lock": {
                "compositeHash": "HASH123",
                "ownerAddress": "OWNER_ADDR",
                "mosaicId": "0x72C0212E67A08BCE",
                "amount": "10000000",
                "endHeight": "200000",
                "hash": "TXHASH123",
                "status": 0,
            }
        }

        lock_info = HashLockInfo.from_api_response(data)

        assert lock_info.composite_hash == "HASH123"
        assert lock_info.owner_address == "OWNER_ADDR"
        assert lock_info.mosaic_id == 0x72C0212E67A08BCE
        assert lock_info.amount == 10000000
        assert lock_info.end_height == 200000
        assert lock_info.hash == "TXHASH123"
        assert lock_info.status == 0


class TestLockService:
    @pytest.fixture
    def mock_wallet(self):
        return MockWallet()

    @pytest.fixture
    def lock_service(self, mock_wallet):
        return LockService(mock_wallet)

    def test_init(self, lock_service, mock_wallet):
        assert lock_service.wallet == mock_wallet
        assert lock_service.facade == mock_wallet.facade
        assert lock_service.node_url == mock_wallet.node_url

    def test_generate_secret_proof(self, lock_service):
        pair = lock_service.generate_secret_proof(LockHashAlgorithm.SHA3_256)

        assert isinstance(pair, SecretProofPair)
        assert len(pair.secret) == 32
        assert len(pair.proof) == 20

    def test_create_secret_lock(self, lock_service):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)
        recipient_address = "TBTWKXCNROT65CJHEBPL7F6DRHX7UKSUPD7EUGA"

        tx = lock_service.create_secret_lock(
            recipient_address=recipient_address,
            mosaic_id=0x72C0212E67A08BCE,
            amount=1000000,
            secret=pair.secret,
            duration=480,
            algorithm=LockHashAlgorithm.SHA3_256,
        )

        assert tx is not None
        assert tx.type_.value == 0x4152

    def test_create_secret_proof(self, lock_service):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)
        recipient_address = "TBTWKXCNROT65CJHEBPL7F6DRHX7UKSUPD7EUGA"

        tx = lock_service.create_secret_proof(
            recipient_address=recipient_address,
            secret=pair.secret,
            proof=pair.proof,
            algorithm=LockHashAlgorithm.SHA3_256,
        )

        assert tx is not None
        assert tx.type_.value == 0x4252

    def test_create_hash_lock(self, lock_service, mock_wallet):
        from datetime import datetime, timezone, timedelta

        deadline_timestamp = mock_wallet.facade.network.from_datetime(
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).timestamp

        aggregate_dict = {
            "type": "aggregate_bonded_transaction_v1",
            "signer_public_key": str(mock_wallet.public_key),
            "deadline": deadline_timestamp,
            "transactions": [],
        }

        aggregate_tx = mock_wallet.facade.transaction_factory.create(aggregate_dict)

        hash_lock_tx = lock_service.create_hash_lock(aggregate_tx)

        assert hash_lock_tx is not None
        assert hash_lock_tx.type_.value == 0x4148

    def test_sign_transaction(self, lock_service):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)
        tx = lock_service.create_secret_proof(
            recipient_address="TBTWKXCNROT65CJHEBPL7F6DRHX7UKSUPD7EUGA",
            secret=pair.secret,
            proof=pair.proof,
        )

        signature = lock_service.sign_transaction(tx)

        assert signature is not None
        assert len(signature.bytes) == 64

    def test_calculate_transaction_hash(self, lock_service):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)
        tx = lock_service.create_secret_proof(
            recipient_address="TBTWKXCNROT65CJHEBPL7F6DRHX7UKSUPD7EUGA",
            secret=pair.secret,
            proof=pair.proof,
        )

        tx_hash = lock_service.calculate_transaction_hash(tx)

        assert tx_hash is not None
        assert len(tx_hash) == 64

    def test_calculate_fee(self, lock_service):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)
        tx = lock_service.create_secret_proof(
            recipient_address="TBTWKXCNROT65CJHEBPL7F6DRHX7UKSUPD7EUGA",
            secret=pair.secret,
            proof=pair.proof,
            fee_multiplier=100,
        )

        fee = lock_service.calculate_fee(tx)

        assert fee > 0
        assert fee == tx.size * 100

    @patch("src.features.lock.service.NetworkClient")
    def test_fetch_secret_locks(self, mock_client_class, lock_service):
        mock_client = MagicMock()
        mock_client.get.return_value = {
            "data": [
                {
                    "lock": {
                        "compositeHash": "ABC123",
                        "ownerAddress": "OWNER",
                        "recipientAddress": "RECIPIENT",
                        "mosaicId": "0x72C0212E67A08BCE",
                        "amount": "1000000",
                        "endHeight": "100000",
                        "hashAlgorithm": 0,
                        "secret": "SECRET",
                        "status": 0,
                    }
                }
            ]
        }
        lock_service._network_client = mock_client

        locks = lock_service.fetch_secret_locks("SOME_ADDRESS")

        assert len(locks) == 1
        assert locks[0].composite_hash == "ABC123"
        mock_client.get.assert_called_once()

    @patch("src.features.lock.service.NetworkClient")
    def test_fetch_hash_locks(self, mock_client_class, lock_service):
        mock_client = MagicMock()
        mock_client.get.return_value = {
            "data": [
                {
                    "lock": {
                        "compositeHash": "HASH123",
                        "ownerAddress": "OWNER",
                        "mosaicId": "0x72C0212E67A08BCE",
                        "amount": "10000000",
                        "endHeight": "200000",
                        "hash": "TXHASH",
                        "status": 0,
                    }
                }
            ]
        }
        lock_service._network_client = mock_client

        locks = lock_service.fetch_hash_locks("SOME_ADDRESS")

        assert len(locks) == 1
        assert locks[0].composite_hash == "HASH123"
        mock_client.get.assert_called_once()

    def test_normalize_address(self, lock_service):
        assert lock_service._normalize_address("tbtw-kxcn-rot6") == "TBTWKXCNROT6"
        assert lock_service._normalize_address("  TBTWKXCN  ") == "TBTWKXCN"


class TestLockServiceIntegration:
    @pytest.fixture
    def mock_wallet(self):
        return MockWallet()

    @pytest.fixture
    def lock_service(self, mock_wallet):
        return LockService(mock_wallet)

    @pytest.mark.integration
    def test_create_and_announce_secret_lock_mocked(self, lock_service):
        with patch.object(lock_service, "announce_transaction") as mock_announce:
            mock_announce.return_value = {"message": "success"}

            result = lock_service.create_and_announce_secret_lock(
                recipient_address="TBTWKXCNROT65CJHEBPL7F6DRHX7UKSUPD7EUGA",
                mosaic_id=0x72C0212E67A08BCE,
                amount=1000000,
                duration=480,
                algorithm=LockHashAlgorithm.SHA3_256,
            )

            assert "hash" in result
            assert "secret" in result
            assert "proof" in result
            assert "api_message" in result
            mock_announce.assert_called_once()

    @pytest.mark.integration
    def test_create_and_announce_secret_proof_mocked(self, lock_service):
        pair = SecretProofPair.generate(LockHashAlgorithm.SHA3_256)

        with patch.object(lock_service, "announce_transaction") as mock_announce:
            mock_announce.return_value = {"message": "success"}

            result = lock_service.create_and_announce_secret_proof(
                recipient_address="TBTWKXCNROT65CJHEBPL7F6DRHX7UKSUPD7EUGA",
                secret=pair.secret_hex,
                proof=pair.proof_hex,
                algorithm=LockHashAlgorithm.SHA3_256,
            )

            assert "hash" in result
            assert "secret" in result
            assert "proof" in result
            assert "api_message" in result
            mock_announce.assert_called_once()

    @pytest.mark.integration
    def test_create_and_announce_hash_lock_mocked(self, lock_service, mock_wallet):
        from datetime import datetime, timezone, timedelta

        deadline_timestamp = mock_wallet.facade.network.from_datetime(
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).timestamp

        aggregate_dict = {
            "type": "aggregate_bonded_transaction_v1",
            "signer_public_key": str(mock_wallet.public_key),
            "deadline": deadline_timestamp,
            "transactions": [],
        }

        aggregate_tx = mock_wallet.facade.transaction_factory.create(aggregate_dict)

        with patch.object(lock_service, "announce_transaction") as mock_announce:
            mock_announce.return_value = {"message": "success"}

            result = lock_service.create_and_announce_hash_lock(
                aggregate_tx=aggregate_tx,
                lock_amount=HASH_LOCK_AMOUNT,
                duration=HASH_LOCK_DURATION,
            )

            assert "hash" in result
            assert "aggregate_hash" in result
            assert "lock_amount" in result
            assert result["lock_amount"] == HASH_LOCK_AMOUNT
            mock_announce.assert_called_once()
