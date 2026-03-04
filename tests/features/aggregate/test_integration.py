"""Integration tests for aggregate bonded transactions against real Symbol testnet."""

from __future__ import annotations

import os
import time

import pytest

from src.features.aggregate.service import (
    HASH_LOCK_AMOUNT,
    AggregateService,
    PartialTransactionInfo,
)

TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"
TESTNET_XYM_MOSAIC_ID = 0x72C0212E67A08BCE


def _is_aggregate_prohibited(status: dict[str, object]) -> bool:
    if status.get("group") != "failed":
        return False
    code = str(status.get("code", ""))
    return code.startswith("Failure_Aggregate_") and code.endswith("_Prohibited")


def _fetch_tx_status(
    service: AggregateService, tx_hash: str
) -> dict[str, object] | None:
    response = service._network_client.post(  # noqa: SLF001
        "/transactionStatus",
        context="Fetch transaction status",
        json={"hashes": [tx_hash.strip().upper()]},
    )
    if not isinstance(response, list) or not response:
        return None
    first = response[0]
    if not isinstance(first, dict):
        return None
    return first


def _is_confirmed_by_hash(service: AggregateService, tx_hash: str) -> bool:
    try:
        result = service._network_client.get_optional(  # noqa: SLF001
            f"/transactions/confirmed/{tx_hash.strip().upper()}",
            context="Fetch confirmed transaction by hash",
        )
        return result is not None
    except Exception:
        return False


@pytest.fixture
def aggregate_service(loaded_testnet_wallet):
    return AggregateService(loaded_testnet_wallet, loaded_testnet_wallet.node_url)


@pytest.mark.integration
class TestAggregateServiceReadOperations:
    """Integration tests for read-only aggregate operations."""

    def test_fetch_partial_transactions_empty_or_list(self, aggregate_service):
        result = aggregate_service.fetch_partial_transactions()
        assert isinstance(result, list)

    def test_fetch_partial_transactions_by_address(self, aggregate_service):
        result = aggregate_service.fetch_partial_transactions(
            address=str(aggregate_service.wallet.address)
        )
        assert isinstance(result, list)

    def test_fetch_partial_by_nonexistent_hash(self, aggregate_service):
        fake_hash = "A" * 64
        result = aggregate_service.fetch_partial_by_hash(fake_hash)
        assert result is None

    def test_get_currency_mosaic_id(self, aggregate_service):
        mosaic_id = aggregate_service.wallet.get_currency_mosaic_id()
        assert mosaic_id == TESTNET_XYM_MOSAIC_ID


@pytest.mark.integration
class TestAggregateCompleteTransactionCreation:
    """Integration tests for aggregate complete transaction creation."""

    def test_create_embedded_transfer(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="Test embedded transfer",
        )
        assert embedded is not None

    def test_create_embedded_transfer_with_mosaic(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[{"mosaic_id": TESTNET_XYM_MOSAIC_ID, "amount": 1000000}],
            message="",
        )
        assert embedded is not None

    def test_create_aggregate_complete_single_inner(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="Single inner transaction",
        )
        aggregate = aggregate_service.create_aggregate_complete([embedded])
        assert aggregate is not None

    def test_create_aggregate_complete_multiple_inner(self, aggregate_service):
        embedded1 = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="Inner 1",
        )
        embedded2 = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="Inner 2",
        )
        aggregate = aggregate_service.create_aggregate_complete([embedded1, embedded2])
        assert aggregate is not None


@pytest.mark.integration
class TestAggregateBondedTransactionCreation:
    """Integration tests for aggregate bonded transaction creation."""

    def test_create_aggregate_bonded(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="Bonded test",
        )
        aggregate = aggregate_service.create_aggregate_bonded([embedded])
        assert aggregate is not None

    def test_create_hash_lock(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_bonded([embedded])
        hash_lock = aggregate_service.create_hash_lock(aggregate)
        assert hash_lock is not None

    def test_create_hash_lock_custom_amount(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_bonded([embedded])
        custom_amount = 20_000_000
        hash_lock = aggregate_service.create_hash_lock(
            aggregate, lock_amount=custom_amount
        )
        assert hash_lock is not None


@pytest.mark.integration
class TestAggregateTransactionSigning:
    """Integration tests for aggregate transaction signing."""

    def test_sign_aggregate_complete(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([embedded])
        signature = aggregate_service.sign_transaction(aggregate)
        assert signature is not None

    def test_sign_hash_lock(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_bonded([embedded])
        hash_lock = aggregate_service.create_hash_lock(aggregate)
        signature = aggregate_service.sign_transaction(hash_lock)
        assert signature is not None

    def test_calculate_aggregate_hash(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([embedded])
        tx_hash = aggregate_service.calculate_transaction_hash(aggregate)
        assert len(tx_hash) == 64

    def test_attach_signature_to_aggregate(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([embedded])
        signature = aggregate_service.sign_transaction(aggregate)
        payload = aggregate_service.attach_signature(aggregate, signature)
        assert payload is not None
        assert len(payload) > 0


@pytest.mark.integration
class TestAggregateFeeCalculation:
    """Integration tests for aggregate fee calculation."""

    def test_calculate_fee_no_cosignatures(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([embedded])
        fee = aggregate_service.calculate_fee(aggregate, num_cosignatures=0)
        assert fee > 0

    def test_calculate_fee_with_cosignatures(self, aggregate_service):
        embedded = aggregate_service.create_embedded_transfer(
            signer_public_key=str(aggregate_service.wallet.public_key),
            recipient_address=str(aggregate_service.wallet.address),
            mosaics=[],
            message="",
        )
        aggregate = aggregate_service.create_aggregate_complete([embedded])
        fee_no_cosig = aggregate_service.calculate_fee(aggregate, num_cosignatures=0)
        fee_with_cosig = aggregate_service.calculate_fee(aggregate, num_cosignatures=2)
        assert fee_with_cosig > fee_no_cosig


@pytest.mark.integration
@pytest.mark.slow
class TestAggregateCompleteLiveTransaction:
    """Live integration tests for aggregate complete transactions on testnet.

    WARNING: These tests spend real XYM from the test account!
    Run with: uv run pytest tests/features/aggregate/test_integration.py -m "integration and slow" -v

    Requirements:
    - test key via --test-key-file (recommended) or SYMBOL_TEST_PRIVATE_KEY
    - Account needs at least 1 XYM for aggregate complete test
    """

    def test_live_aggregate_complete_message_only(self, loaded_testnet_wallet):
        """Test aggregate complete with message only (minimal fees)."""
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live aggregate tests")

        wallet = loaded_testnet_wallet
        before = wallet.get_xym_balance()

        min_balance = 500_000
        if before["xym_micro"] < min_balance:
            pytest.skip(f"Insufficient balance: {before['xym_micro']} micro XYM")

        service = AggregateService(wallet, wallet.node_url)

        embedded = service.create_embedded_transfer(
            signer_public_key=str(wallet.public_key),
            recipient_address=str(wallet.address),
            mosaics=[],
            message=f"Aggregate complete test {int(time.time())}",
        )

        result = service.create_and_announce_aggregate_complete(
            [embedded], fee_multiplier=100
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
        assert status.get("group") == "confirmed"

    def test_live_aggregate_complete_multiple_inner(self, loaded_testnet_wallet):
        """Test aggregate complete with multiple inner transactions."""
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live aggregate tests")

        wallet = loaded_testnet_wallet
        before = wallet.get_xym_balance()

        min_balance = 1_000_000
        if before["xym_micro"] < min_balance:
            pytest.skip(f"Insufficient balance: {before['xym_micro']} micro XYM")

        service = AggregateService(wallet, wallet.node_url)

        embedded1 = service.create_embedded_transfer(
            signer_public_key=str(wallet.public_key),
            recipient_address=str(wallet.address),
            mosaics=[],
            message=f"Inner 1 - {int(time.time())}",
        )

        embedded2 = service.create_embedded_transfer(
            signer_public_key=str(wallet.public_key),
            recipient_address=str(wallet.address),
            mosaics=[],
            message=f"Inner 2 - {int(time.time())}",
        )

        result = service.create_and_announce_aggregate_complete(
            [embedded1, embedded2], fee_multiplier=100
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
        assert status.get("group") == "confirmed"


@pytest.mark.integration
@pytest.mark.slow
class TestAggregateBondedLiveTransaction:
    """Live integration tests for aggregate bonded transactions on testnet.

    WARNING: These tests spend real XYM from the test account!
    Run with: uv run pytest tests/features/aggregate/test_integration.py -m "integration and slow" -v

    Requirements:
    - test key via --test-key-file (recommended) or SYMBOL_TEST_PRIVATE_KEY
    - Account needs at least 11 XYM for aggregate bonded test (10 XYM for hash lock)
    """

    def test_live_aggregate_bonded_full_workflow(self, loaded_testnet_wallet):
        """Test full aggregate bonded workflow: hash lock -> aggregate -> confirmed/partial."""
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live aggregate tests")

        wallet = loaded_testnet_wallet
        before = wallet.get_xym_balance()

        min_balance = HASH_LOCK_AMOUNT + 1_000_000
        if before["xym_micro"] < min_balance:
            pytest.skip(
                f"Insufficient balance: {before['xym_micro']} micro XYM (need {min_balance})"
            )

        service = AggregateService(wallet, wallet.node_url)

        embedded = service.create_embedded_transfer(
            signer_public_key=str(wallet.public_key),
            recipient_address=str(wallet.address),
            mosaics=[],
            message=f"Bonded test {int(time.time())}",
        )

        status_updates = []

        def on_status(stage: str, message: str):
            status_updates.append({"stage": stage, "message": message})

        result = service.create_and_announce_aggregate_bonded(
            [embedded],
            lock_amount=HASH_LOCK_AMOUNT,
            fee_multiplier=100,
            wait_for_hash_lock=True,
            timeout_seconds=300,
            on_status_update=on_status,
        )

        assert "hash_lock_hash" in result
        assert "aggregate_hash" in result
        assert len(result["hash_lock_hash"]) == 64
        assert len(result["aggregate_hash"]) == 64

        hash_lock_status = service.poll_for_transaction_status(
            result["hash_lock_hash"], timeout_seconds=120, poll_interval_seconds=5
        )
        assert hash_lock_status.get("group") == "confirmed"

        aggregate_status: dict[str, object] | None = None
        try:
            aggregate_status = service.poll_for_transaction_status(
                result["aggregate_hash"], timeout_seconds=120, poll_interval_seconds=5
            )
        except TimeoutError:
            pass

        if aggregate_status is not None:
            if _is_aggregate_prohibited(aggregate_status):
                pytest.skip(
                    "Aggregate bonded transactions are prohibited by this node/network: "
                    f"{aggregate_status.get('code')}"
                )
            if aggregate_status.get("group") == "confirmed":
                return
        elif _is_confirmed_by_hash(service, result["aggregate_hash"]):
            return

        partial = None
        for _ in range(12):
            partial = service.fetch_partial_by_hash(result["aggregate_hash"])
            if partial is not None:
                break
            time.sleep(5)

        if partial is None:
            status = _fetch_tx_status(service, result["aggregate_hash"])
            if status is None:
                if _is_confirmed_by_hash(service, result["aggregate_hash"]):
                    return
                pytest.skip(
                    "Aggregate bonded transaction status was unavailable and no partial "
                    "transaction was observable on this node."
                )
            if status.get("group") == "confirmed":
                return
            if _is_aggregate_prohibited(status):
                pytest.skip(
                    "Aggregate bonded transactions are prohibited by this node/network: "
                    f"{status.get('code')}"
                )

        assert partial is not None
        assert partial.hash == result["aggregate_hash"]

    def test_live_aggregate_bonded_reaches_partial_or_confirmed(
        self, loaded_testnet_wallet
    ):
        """Test that aggregate bonded reaches partial or confirmed state."""
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live aggregate tests")

        wallet = loaded_testnet_wallet
        before = wallet.get_xym_balance()

        min_balance = HASH_LOCK_AMOUNT + 1_000_000
        if before["xym_micro"] < min_balance:
            pytest.skip(
                f"Insufficient balance: {before['xym_micro']} micro XYM (need {min_balance})"
            )

        service = AggregateService(wallet, wallet.node_url)

        embedded = service.create_embedded_transfer(
            signer_public_key=str(wallet.public_key),
            recipient_address=str(wallet.address),
            mosaics=[],
            message=f"Partial test {int(time.time())}",
        )

        result = service.create_and_announce_aggregate_bonded(
            [embedded],
            lock_amount=HASH_LOCK_AMOUNT,
            fee_multiplier=100,
            wait_for_hash_lock=True,
            timeout_seconds=300,
        )

        aggregate_status: dict[str, object] | None = None
        try:
            aggregate_status = service.poll_for_transaction_status(
                result["aggregate_hash"], timeout_seconds=120, poll_interval_seconds=5
            )
        except TimeoutError:
            pass

        if aggregate_status is not None:
            if _is_aggregate_prohibited(aggregate_status):
                pytest.skip(
                    "Aggregate bonded transactions are prohibited by this node/network: "
                    f"{aggregate_status.get('code')}"
                )
            if aggregate_status.get("group") == "confirmed":
                return
        elif _is_confirmed_by_hash(service, result["aggregate_hash"]):
            return

        partials: list[PartialTransactionInfo] = []
        for _ in range(12):
            partials = service.fetch_partial_transactions(str(wallet.address))
            if partials:
                break
            time.sleep(5)

        if not partials:
            status = _fetch_tx_status(service, result["aggregate_hash"])
            if status is None:
                if _is_confirmed_by_hash(service, result["aggregate_hash"]):
                    return
                pytest.skip(
                    "Aggregate bonded transaction status was unavailable and no partial "
                    "transactions were observable on this node."
                )
            if status.get("group") == "confirmed":
                return
            if _is_aggregate_prohibited(status):
                pytest.skip(
                    "Aggregate bonded transactions are prohibited by this node/network: "
                    f"{status.get('code')}"
                )

        found = any(p.hash == result["aggregate_hash"] for p in partials)
        assert found, "Aggregate bonded not found in partial transactions"
