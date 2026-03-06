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
from src.shared.network import NetworkClient

TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"
TESTNET_XYM_MOSAIC_ID = 0x72C0212E67A08BCE
AGGREGATE_COMPLETE_NUMERIC_TYPE = 16705
AGGREGATE_BONDED_NUMERIC_TYPE = 16961


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


def _iter_observer_nodes(primary_node_url: str) -> list[str]:
    seen: set[str] = set()
    nodes: list[str] = []

    env_single = os.getenv("SYMBOL_TEST_NODE_URL", "").strip()
    env_multi = [
        node.strip()
        for node in os.getenv("SYMBOL_TEST_NODE_URLS", "").split(",")
        if node.strip()
    ]

    for raw in [
        primary_node_url,
        env_single,
        *env_multi,
        TESTNET_NODE,
        "http://sym-test-03.opening-line.jp:3000",
    ]:
        if not raw:
            continue
        normalized = raw.rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        nodes.append(normalized)

    return nodes


def _fetch_tx_status_on_node(node_url: str, tx_hash: str) -> dict[str, object] | None:
    client = NetworkClient(node_url=node_url)
    try:
        response = client.post(
            "/transactionStatus",
            context=f"Fetch transaction status ({node_url})",
            json={"hashes": [tx_hash.strip().upper()]},
        )
    except Exception:
        return None

    if not isinstance(response, list) or not response:
        return None
    first = response[0]
    if not isinstance(first, dict):
        return None
    return first


def _is_confirmed_by_hash_on_node(node_url: str, tx_hash: str) -> bool:
    client = NetworkClient(node_url=node_url)
    try:
        result = client.get_optional(
            f"/transactions/confirmed/{tx_hash.strip().upper()}",
            context=f"Fetch confirmed transaction by hash ({node_url})",
        )
        return result is not None
    except Exception:
        return False


def _fetch_partial_hash_on_node(node_url: str, tx_hash: str) -> str | None:
    client = NetworkClient(node_url=node_url)
    try:
        result = client.get_optional(
            f"/transactions/partial/{tx_hash.strip().upper()}",
            context=f"Fetch partial transaction by hash ({node_url})",
        )
    except Exception:
        return None

    if not isinstance(result, dict):
        return None
    meta = result.get("meta", {})
    if not isinstance(meta, dict):
        return None
    partial_hash = str(meta.get("hash", "")).strip().upper()
    return partial_hash or None


def _positive_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _compact_message(value: object, max_length: int = 160) -> str:
    text = str(value).replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _collect_observer_node_diagnostics(
    node_url: str, normalized_hash: str
) -> dict[str, object]:
    client = NetworkClient(node_url=node_url)
    diagnostic: dict[str, object] = {
        "node_url": node_url,
        "transaction_status": None,
        "confirmed_by_hash": False,
        "partial_hash": None,
        "errors": {},
    }
    observed: dict[str, object] | None = None

    try:
        response = client.post(
            "/transactionStatus",
            context=f"Fetch transaction status ({node_url})",
            json={"hashes": [normalized_hash]},
        )
        if isinstance(response, list) and response and isinstance(response[0], dict):
            status = response[0]
            diagnostic["transaction_status"] = status
            group = str(status.get("group", ""))
            if group in {"confirmed", "failed"}:
                observed = {"node_url": node_url, "status": status}
    except Exception as exc:
        errors = diagnostic["errors"]
        if isinstance(errors, dict):
            errors["transactionStatus"] = _compact_message(exc)

    try:
        confirmed = (
            client.get_optional(
                f"/transactions/confirmed/{normalized_hash}",
                context=f"Fetch confirmed transaction by hash ({node_url})",
            )
            is not None
        )
        diagnostic["confirmed_by_hash"] = confirmed
        if observed is None and confirmed:
            observed = {
                "node_url": node_url,
                "status": {"group": "confirmed", "hash": normalized_hash},
            }
    except Exception as exc:
        errors = diagnostic["errors"]
        if isinstance(errors, dict):
            errors["confirmed"] = _compact_message(exc)

    try:
        partial_result = client.get_optional(
            f"/transactions/partial/{normalized_hash}",
            context=f"Fetch partial transaction by hash ({node_url})",
        )
        partial_hash = None
        if isinstance(partial_result, dict):
            meta = partial_result.get("meta", {})
            if isinstance(meta, dict):
                candidate = str(meta.get("hash", "")).strip().upper()
                partial_hash = candidate or None

        diagnostic["partial_hash"] = partial_hash
        if observed is None and partial_hash:
            observed = {
                "node_url": node_url,
                "status": {"group": "partial", "hash": partial_hash},
            }
    except Exception as exc:
        errors = diagnostic["errors"]
        if isinstance(errors, dict):
            errors["partial"] = _compact_message(exc)

    return {"observed": observed, "diagnostic": diagnostic}


def _observe_aggregate_visibility(
    tx_hash: str,
    primary_node_url: str,
    timeout_seconds: int | None = None,
    poll_interval_seconds: int | None = None,
) -> dict[str, object]:
    normalized_hash = tx_hash.strip().upper()
    timeout_seconds = timeout_seconds or _positive_env_int(
        "SYMBOL_TEST_OBSERVER_VISIBILITY_TIMEOUT", 180
    )
    poll_interval_seconds = poll_interval_seconds or _positive_env_int(
        "SYMBOL_TEST_OBSERVER_VISIBILITY_POLL", 10
    )
    deadline = time.time() + timeout_seconds

    attempts = 0
    last_diagnostics: list[dict[str, object]] = []
    while True:
        attempts += 1
        diagnostics: list[dict[str, object]] = []
        for node_url in _iter_observer_nodes(primary_node_url):
            observation = _collect_observer_node_diagnostics(node_url, normalized_hash)
            diagnostic = observation["diagnostic"]
            if isinstance(diagnostic, dict):
                diagnostics.append(diagnostic)
            observed = observation["observed"]
            if isinstance(observed, dict):
                return {
                    "observed": observed,
                    "diagnostics": diagnostics,
                    "attempts": attempts,
                    "timeout_seconds": timeout_seconds,
                    "poll_interval_seconds": poll_interval_seconds,
                }

        last_diagnostics = diagnostics
        if time.time() >= deadline:
            break
        time.sleep(poll_interval_seconds)

    return {
        "observed": None,
        "diagnostics": last_diagnostics,
        "attempts": attempts,
        "timeout_seconds": timeout_seconds,
        "poll_interval_seconds": poll_interval_seconds,
    }


def _format_observer_diagnostics(report: dict[str, object]) -> str:
    attempts = report.get("attempts")
    timeout_seconds = report.get("timeout_seconds")
    poll_interval_seconds = report.get("poll_interval_seconds")
    diagnostics = report.get("diagnostics", [])
    if not isinstance(diagnostics, list) or not diagnostics:
        return (
            f"attempts={attempts}, timeout={timeout_seconds}s, poll={poll_interval_seconds}s, "
            "nodes=none"
        )

    node_chunks: list[str] = []
    for node in diagnostics:
        if not isinstance(node, dict):
            continue
        node_url = str(node.get("node_url", "unknown"))
        status = node.get("transaction_status")
        group = "none"
        code = "-"
        if isinstance(status, dict):
            group = str(status.get("group", "none")) or "none"
            code = str(status.get("code", "-")) or "-"

        confirmed = bool(node.get("confirmed_by_hash", False))
        partial_value = node.get("partial_hash")
        partial_hash = str(partial_value).strip() if partial_value else "-"
        errors = node.get("errors", {})
        error_text = "-"
        if isinstance(errors, dict) and errors:
            error_text = ",".join(
                f"{key}:{_compact_message(value, max_length=120)}"
                for key, value in errors.items()
            )
        node_chunks.append(
            f"{node_url}[tx={group}:{code},confirmed={confirmed},partial={partial_hash},errors={error_text}]"
        )

    joined_nodes = " | ".join(node_chunks) if node_chunks else "none"
    return (
        f"attempts={attempts}, timeout={timeout_seconds}s, poll={poll_interval_seconds}s, "
        f"nodes={joined_nodes}"
    )


def _find_recent_confirmed_aggregate_hash(node_url: str, tx_type: int) -> str | None:
    client = NetworkClient(node_url=node_url)
    try:
        response = client.get(
            f"/transactions/confirmed?type={tx_type}&limit=20",
            context=f"Fetch confirmed aggregate transactions ({node_url})",
        )
    except Exception:
        return None

    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if not isinstance(data, list):
        return None

    for item in data:
        if not isinstance(item, dict):
            continue
        meta = item.get("meta")
        if not isinstance(meta, dict):
            continue
        tx_hash = str(meta.get("hash", "")).strip().upper()
        if len(tx_hash) == 64:
            return tx_hash
    return None


def _is_confirmed_on_node(node_url: str, tx_hash: str) -> bool:
    normalized_hash = tx_hash.strip().upper()
    status = _fetch_tx_status_on_node(node_url, normalized_hash)
    if isinstance(status, dict):
        status_hash = str(status.get("hash", "")).strip().upper()
        if status.get("group") == "confirmed" and status_hash == normalized_hash:
            return True
    return _is_confirmed_by_hash_on_node(node_url, normalized_hash)


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
class TestAggregateObserverVisibility:
    """Integration tests for multi-node aggregate transaction observability."""

    @pytest.mark.parametrize(
        ("tx_type", "tx_label"),
        [
            (AGGREGATE_COMPLETE_NUMERIC_TYPE, "aggregate_complete"),
            (AGGREGATE_BONDED_NUMERIC_TYPE, "aggregate_bonded"),
        ],
    )
    def test_recent_confirmed_aggregate_is_visible_on_observer_nodes(
        self,
        testnet_wallet,
        tx_type: int,
        tx_label: str,
    ):
        tx_hash = _find_recent_confirmed_aggregate_hash(testnet_wallet.node_url, tx_type)
        assert tx_hash is not None, f"No recent confirmed {tx_label} transaction found"

        observer_nodes = _iter_observer_nodes(testnet_wallet.node_url)[:2]
        assert len(observer_nodes) == 2

        confirmed_nodes = [
            node_url for node_url in observer_nodes if _is_confirmed_on_node(node_url, tx_hash)
        ]
        assert len(confirmed_nodes) == 2, (
            f"{tx_label} hash {tx_hash} not confirmed on all observer nodes: "
            f"{observer_nodes}; confirmed={confirmed_nodes}"
        )


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

    def test_live_aggregate_complete_message_only(
        self, loaded_testnet_wallet, ensure_live_min_balance
    ):
        """Test aggregate complete with message only (minimal fees)."""
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live aggregate tests")

        wallet = loaded_testnet_wallet
        min_balance = 500_000
        ensure_live_min_balance(wallet, min_balance)

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

    def test_live_aggregate_complete_multiple_inner(
        self, loaded_testnet_wallet, ensure_live_min_balance
    ):
        """Test aggregate complete with multiple inner transactions."""
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live aggregate tests")

        wallet = loaded_testnet_wallet
        min_balance = 1_000_000
        ensure_live_min_balance(wallet, min_balance)

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

    def test_live_aggregate_bonded_full_workflow(
        self, loaded_testnet_wallet, ensure_live_min_balance
    ):
        """Test full aggregate bonded workflow: hash lock -> aggregate -> confirmed/partial."""
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live aggregate tests")

        wallet = loaded_testnet_wallet
        min_balance = HASH_LOCK_AMOUNT + 1_000_000
        ensure_live_min_balance(wallet, min_balance)

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
                observed_report = _observe_aggregate_visibility(
                    result["aggregate_hash"], service.wallet.node_url
                )
                observed = observed_report["observed"]
                assert observed is not None, (
                    "Aggregate bonded visibility unavailable on all observer nodes. "
                    f"{_format_observer_diagnostics(observed_report)}"
                )
                observed_status = observed["status"]
                assert isinstance(observed_status, dict)
                observed_group = observed_status.get("group")
                if observed_group == "failed":
                    assert not _is_aggregate_prohibited(observed_status), (
                        "Aggregate bonded transactions are prohibited by observer "
                        f"node {observed.get('node_url')}: {observed_status.get('code')}"
                    )
                if observed_group == "partial":
                    assert observed_status.get("hash") == result["aggregate_hash"]
                return
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
        self, loaded_testnet_wallet, ensure_live_min_balance
    ):
        """Test that aggregate bonded reaches partial or confirmed state."""
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live aggregate tests")

        wallet = loaded_testnet_wallet
        min_balance = HASH_LOCK_AMOUNT + 1_000_000
        ensure_live_min_balance(wallet, min_balance)

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
                observed_report = _observe_aggregate_visibility(
                    result["aggregate_hash"], service.wallet.node_url
                )
                observed = observed_report["observed"]
                assert observed is not None, (
                    "Aggregate bonded visibility unavailable on all observer nodes. "
                    f"{_format_observer_diagnostics(observed_report)}"
                )
                observed_status = observed["status"]
                assert isinstance(observed_status, dict)
                observed_group = observed_status.get("group")
                if observed_group == "failed":
                    assert not _is_aggregate_prohibited(observed_status), (
                        "Aggregate bonded transactions are prohibited by observer "
                        f"node {observed.get('node_url')}: {observed_status.get('code')}"
                    )
                if observed_group == "partial":
                    assert observed_status.get("hash") == result["aggregate_hash"]
                return
            if status.get("group") == "confirmed":
                return
            if _is_aggregate_prohibited(status):
                pytest.skip(
                    "Aggregate bonded transactions are prohibited by this node/network: "
                    f"{status.get('code')}"
                )

        found = any(p.hash == result["aggregate_hash"] for p in partials)
        assert found, "Aggregate bonded not found in partial transactions"
