import os
import time

import pytest
import requests
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.transaction import TransactionManager
from src.wallet import Wallet
from tests.live_test_key import HARDCODED_TEST_PRIVATE_KEY


class DummyResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)
        self.content = str(payload).encode("utf-8")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def create_loaded_wallet(network_name: str = "testnet") -> Wallet:
    wallet = Wallet(network_name=network_name)
    wallet.network_name = network_name
    wallet.facade = SymbolFacade(network_name)

    private_key = PrivateKey.random()
    account = wallet.facade.create_account(private_key)
    wallet.private_key = private_key
    wallet.public_key = account.public_key
    wallet.address = account.address

    return wallet


@pytest.mark.unit
def test_get_account_balances_normalizes_mosaics(monkeypatch):
    account_payload = {
        "account": {
            "mosaics": [
                {"id": "6BED913FA20223F8", "amount": "1234567"},
                {"id": "0x72C0212E67A08BCE", "amount": "42"},
            ]
        }
    }

    def fake_get(url, timeout):
        return DummyResponse(200, account_payload)

    monkeypatch.setattr(requests, "get", fake_get)

    wallet = create_loaded_wallet()
    wallet._currency_mosaic_id = Wallet.XYM_MOSAIC_ID
    result = wallet.get_account_balances("TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ")

    assert result["address"] == "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
    assert result["xym_micro"] == 1234567
    assert result["xym"] == pytest.approx(1.234567)
    assert len(result["mosaics"]) == 2
    assert result["mosaics"][0]["name"] == "XYM"


@pytest.mark.unit
def test_get_registered_address_balances(monkeypatch):
    wallet = create_loaded_wallet()
    currency_mosaic_id = wallet.get_currency_mosaic_id()
    account_payload = {
        "account": {
            "mosaics": [{"id": f"{currency_mosaic_id:016X}", "amount": "2000000"}],
        }
    }

    def fake_get(url, timeout):
        return DummyResponse(200, account_payload)

    monkeypatch.setattr(requests, "get", fake_get)

    wallet.address_book = {
        "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ": {
            "name": "Alice",
            "note": "friend",
            "address": "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ",
        }
    }

    result = wallet.get_registered_address_balances()

    assert "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ" in result
    assert (
        result["TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"]["balance"]["xym_micro"]
        == 2000000
    )


@pytest.mark.unit
def test_wait_for_transaction_confirmation(monkeypatch):
    wallet = create_loaded_wallet()
    statuses = [
        {"hash": "A" * 64, "group": "not_found", "data": None},
        {"hash": "A" * 64, "group": "unconfirmed", "data": {"meta": {}}},
        {
            "hash": "A" * 64,
            "group": "confirmed",
            "data": {"meta": {"hash": "A" * 64}},
        },
    ]

    monkeypatch.setattr(wallet, "get_transaction_status", lambda _hash: statuses.pop(0))
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)

    result = wallet.wait_for_transaction_confirmation(
        "A" * 64,
        timeout_seconds=5,
        poll_interval_seconds=1,
    )

    assert result["group"] == "confirmed"
    assert result["data"]["meta"]["hash"] == "A" * 64


@pytest.mark.unit
def test_transaction_manager_normalize_mosaics_merges_and_sorts():
    wallet = create_loaded_wallet()
    manager = TransactionManager(wallet, wallet.node_url)

    mosaics = manager.normalize_mosaics(
        [
            {"mosaic_id": "6BED913FA20223F8", "amount": "100"},
            {"mosaic_id": 0x72C0212E67A08BCE, "amount": 2},
            {"mosaic_id": "0x6BED913FA20223F8", "amount": 50},
        ]
    )

    assert mosaics == [
        {"mosaic_id": 0x6BED913FA20223F8, "amount": 150},
        {"mosaic_id": 0x72C0212E67A08BCE, "amount": 2},
    ]


@pytest.mark.unit
def test_transaction_manager_calculates_hash_and_uses_json_payload(monkeypatch):
    wallet = create_loaded_wallet()
    manager = TransactionManager(wallet, wallet.node_url)
    currency_mosaic_id = manager.get_currency_mosaic_id()

    transfer = manager.create_transfer_transaction(
        str(wallet.address),
        [{"mosaic_id": currency_mosaic_id, "amount": 1000000}],
        "hello",
    )
    signature = manager.sign_transaction(transfer)
    signed_payload = manager.attach_signature(transfer, signature)
    tx_hash = manager.calculate_transaction_hash_from_signed_payload(signed_payload)

    captured = {}

    def fake_put(url, data, headers, timeout):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse(202, {"message": "accepted"})

    monkeypatch.setattr(requests, "put", fake_put)
    announce_result = manager.announce_transaction("ABCDEF")

    assert len(tx_hash) == 64
    assert captured["data"] == "ABCDEF"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert announce_result["message"] == "accepted"


@pytest.mark.integration
@pytest.mark.slow
def test_live_send_and_confirm_transaction():
    if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
        pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live transfer tests")

    private_key_hex = HARDCODED_TEST_PRIVATE_KEY.strip()
    if not private_key_hex:
        # Fallback only for emergency/manual override.
        private_key_hex = os.getenv("SYMBOL_TEST_PRIVATE_KEY", "").strip()
    if not private_key_hex:
        pytest.skip(
            "Set HARDCODED_TEST_PRIVATE_KEY in tests/live_test_key.py "
            "or SYMBOL_TEST_PRIVATE_KEY."
        )

    network_name = os.getenv("SYMBOL_TEST_NETWORK", "testnet")
    node_url = os.getenv("SYMBOL_TEST_NODE_URL", "http://sym-test-01.opening-line.jp:3000")
    transfer_micro = int(os.getenv("SYMBOL_TEST_TRANSFER_MICRO", "100000"))
    recipient_address_override = os.getenv("SYMBOL_TEST_RECIPIENT_ADDRESS", "").strip()
    confirm_timeout = int(os.getenv("SYMBOL_TEST_CONFIRM_TIMEOUT", "180"))

    wallet = Wallet(network_name=network_name)
    wallet.network_name = network_name
    wallet.node_url = node_url
    wallet.facade = SymbolFacade(network_name)

    wallet.private_key = PrivateKey(private_key_hex)
    account = wallet.facade.create_account(wallet.private_key)
    wallet.public_key = account.public_key
    wallet.address = account.address

    recipient_address = recipient_address_override or str(wallet.address)

    before = wallet.get_xym_balance()
    assert before["xym_micro"] > transfer_micro, (
        f"Insufficient balance: {before['xym_micro']} micro XYM available"
    )

    manager = TransactionManager(wallet, node_url)
    currency_mosaic_id = manager.get_currency_mosaic_id()
    message = f"symbol-quick-wallet-integration-{int(time.time())}"
    result = manager.create_sign_and_announce(
        recipient_address,
        [{"mosaic_id": currency_mosaic_id, "amount": transfer_micro}],
        message,
    )

    tx_hash = result["hash"]
    assert len(tx_hash) == 64

    status = manager.wait_for_transaction_status(
        tx_hash,
        timeout_seconds=confirm_timeout,
        poll_interval_seconds=5,
    )
    assert status["hash"].upper() == tx_hash.upper()
    assert status["group"] in {"confirmed", "failed"}
    assert status["group"] == "confirmed", f"tx failed with code: {status.get('code')}"
