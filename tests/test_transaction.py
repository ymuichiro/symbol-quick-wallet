import pytest
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade
from datetime import timedelta, datetime, timezone


@pytest.mark.unit
def test_transaction_creation():
    """Test transaction creation using Symbol SDK"""
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    deadline_timestamp = int(
        (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp() * 1000
    )

    transfer_dict = {
        "type": "transfer_transaction_v1",
        "signer_public_key": str(account.public_key),
        "deadline": deadline_timestamp,
        "recipient_address": str(account.address),
        "mosaics": [{"mosaic_id": 0x6BED913FA20223F8, "amount": 1000000}],
        "message": "",
    }

    transfer = facade.transaction_factory.create(transfer_dict)

    assert transfer is not None
    assert transfer.size > 0


@pytest.mark.unit
def test_transaction_signing():
    """Test transaction signing"""
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    deadline_timestamp = int(
        (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp() * 1000
    )

    transfer_dict = {
        "type": "transfer_transaction_v1",
        "signer_public_key": str(account.public_key),
        "deadline": deadline_timestamp,
        "recipient_address": str(account.address),
        "mosaics": [{"mosaic_id": 0x6BED913FA20223F8, "amount": 1000000}],
        "message": "Test message",
    }

    transfer = facade.transaction_factory.create(transfer_dict)
    signature = account.sign_transaction(transfer)

    assert signature is not None


@pytest.mark.unit
def test_signature_attachment():
    """Test signature attachment to transaction"""
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    deadline_timestamp = int(
        (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp() * 1000
    )

    transfer_dict = {
        "type": "transfer_transaction_v1",
        "signer_public_key": str(account.public_key),
        "deadline": deadline_timestamp,
        "recipient_address": str(account.address),
        "mosaics": [{"mosaic_id": 0x6BED913FA20223F8, "amount": 1000000}],
        "message": "Test message",
    }

    transfer = facade.transaction_factory.create(transfer_dict)
    signature = account.sign_transaction(transfer)
    signed_payload = facade.transaction_factory.attach_signature(transfer, signature)

    assert signed_payload is not None
    assert len(signed_payload) > 0
    assert "payload" in signed_payload.lower() or len(signed_payload) > 100


@pytest.mark.unit
def test_multiple_mosaics_in_transaction():
    """Test transaction with multiple mosaics"""
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    deadline_timestamp = int(
        (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp() * 1000
    )

    # Note: mosaics must be sorted by mosaic_id for SDK
    mosaics = [
        {"mosaic_id": 0x6BED913FA20223F8, "amount": 2000000},
        {"mosaic_id": 0x6BED913FA20223F8, "amount": 1000000},
    ]

    transfer_dict = {
        "type": "transfer_transaction_v1",
        "signer_public_key": str(account.public_key),
        "deadline": deadline_timestamp,
        "recipient_address": str(account.address),
        "mosaics": mosaics,
        "message": "",
    }

    # Multiple mosaics with same ID will be combined by SDK
    transfer = facade.transaction_factory.create(transfer_dict)

    assert transfer is not None


@pytest.mark.unit
def test_transaction_with_message():
    """Test transaction with plain message"""
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    deadline_timestamp = int(
        (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp() * 1000
    )

    message = "Hello Symbol!"

    transfer_dict = {
        "type": "transfer_transaction_v1",
        "signer_public_key": str(account.public_key),
        "deadline": deadline_timestamp,
        "recipient_address": str(account.address),
        "mosaics": [{"mosaic_id": 0x6BED913FA20223F8, "amount": 1000000}],
        "message": message,
    }

    transfer = facade.transaction_factory.create(transfer_dict)
    signature = account.sign_transaction(transfer)

    assert transfer is not None
    assert signature is not None
