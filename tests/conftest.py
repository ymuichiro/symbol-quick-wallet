import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import pytest
import requests
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.wallet import Wallet

TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"
TESTNET_XYM_MOSAIC_ID = 0x72C0212E67A08BCE


def _test_key_address_sidecar(key_file: Path) -> Path:
    return key_file.with_name(f"{key_file.name}.address")


def _read_expected_address_from_sidecar(test_key_file: Path | None) -> str | None:
    if test_key_file is None:
        return None
    sidecar = _test_key_address_sidecar(test_key_file)
    if not sidecar.exists():
        return None
    expected = sidecar.read_text().strip().upper()
    return expected or None


def _iter_testnet_node_candidates() -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []

    env_single = os.getenv("SYMBOL_TEST_NODE_URL", "").strip()
    env_multi = os.getenv("SYMBOL_TEST_NODE_URLS", "")
    env_nodes = [n.strip() for n in env_multi.split(",") if n.strip()]

    for raw in [env_single, *env_nodes, TESTNET_NODE, "http://sym-test-03.opening-line.jp:3000"]:
        if not raw:
            continue
        node = raw.rstrip("/")
        if node in seen:
            continue
        seen.add(node)
        candidates.append(node)

    return candidates


def _select_reachable_testnet_node() -> str:
    for node_url in _iter_testnet_node_candidates():
        try:
            response = requests.get(f"{node_url}/node/health", timeout=(3, 5))
            if response.status_code != 200:
                continue
            payload = response.json()
            status = payload.get("status", {}) if isinstance(payload, dict) else {}
            if status.get("apiNode") == "up":
                return node_url
        except Exception:
            continue

    # Keep deterministic fallback to avoid changing behavior when all checks fail.
    return TESTNET_NODE


def _normalize_mosaic_hex(mosaic_id: object) -> str:
    if isinstance(mosaic_id, int):
        return f"{mosaic_id:016X}"
    raw = str(mosaic_id).strip().upper()
    if raw.startswith("0X"):
        raw = raw[2:]
    return raw


def _estimate_spendable_xym_micro(
    wallet: Any,
    total_xym_micro: int,
) -> tuple[int, int]:
    """Estimate spendable XYM by subtracting active hash locks from total balance.

    Returns a tuple: (estimated_spendable_micro, active_locked_micro).
    """
    node_url = str(getattr(wallet, "node_url", "")).strip().rstrip("/")
    if not node_url:
        return total_xym_micro, 0

    address_value = getattr(wallet, "address", "")
    normalized_address = str(address_value).replace("-", "").strip().upper()
    if not normalized_address:
        return total_xym_micro, 0

    try:
        chain_info = requests.get(f"{node_url}/chain/info", timeout=(3, 10)).json()
        chain_height = int(chain_info.get("height", "0"))

        locks_response = requests.get(
            f"{node_url}/lock/hash",
            params={"address": normalized_address, "pageSize": 100},
            timeout=(3, 10),
        ).json()
        locks_data = (
            locks_response.get("data", []) if isinstance(locks_response, dict) else []
        )

        currency_mosaic_id = (
            wallet.get_currency_mosaic_id()
            if hasattr(wallet, "get_currency_mosaic_id")
            else TESTNET_XYM_MOSAIC_ID
        )
        target_mosaic = _normalize_mosaic_hex(currency_mosaic_id or TESTNET_XYM_MOSAIC_ID)

        active_locked = 0
        for entry in locks_data:
            if not isinstance(entry, dict):
                continue
            lock = entry.get("lock", {})
            if not isinstance(lock, dict):
                continue

            try:
                status = int(lock.get("status", 1))
                amount = int(lock.get("amount", "0"))
                end_height = int(lock.get("endHeight", "0"))
            except Exception:
                continue

            mosaic_hex = _normalize_mosaic_hex(lock.get("mosaicId", ""))
            if mosaic_hex and mosaic_hex != target_mosaic:
                continue
            if status != 0:
                continue
            if chain_height and end_height and end_height < chain_height:
                continue
            if amount <= 0:
                continue
            active_locked += amount

        spendable = max(total_xym_micro - active_locked, 0)
        return spendable, active_locked
    except Exception:
        return total_xym_micro, 0


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--test-key-file",
        action="store",
        default=".test_key",
        help="Path to file containing test wallet private key",
    )
    parser.addoption(
        "--require-live-key",
        action="store_true",
        default=False,
        help="Fail instead of skip when live-key fixtures are requested but unavailable",
    )
    parser.addoption(
        "--expected-test-address",
        action="store",
        default="",
        help=(
            "Expected address for the live test key. "
            "If set, tests fail when the loaded key resolves to a different address."
        ),
    )


@pytest.fixture
def test_key_file(request: pytest.FixtureRequest) -> Path | None:
    key_file = Path(request.config.getoption("--test-key-file")).expanduser()
    if not key_file.exists():
        return None
    return key_file


@pytest.fixture
def require_live_key(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--require-live-key"))


@pytest.fixture
def expected_test_address(request: pytest.FixtureRequest) -> str | None:
    option_value = str(request.config.getoption("--expected-test-address", "")).strip()
    if option_value:
        return option_value.upper()

    env_value = os.getenv("SYMBOL_TEST_EXPECTED_ADDRESS", "").strip()
    if env_value:
        return env_value.upper()
    return None


@pytest.fixture
def test_private_key(test_key_file: Path | None) -> PrivateKey | None:
    private_key_hex = ""
    source = ""

    if test_key_file is not None:
        private_key_hex = test_key_file.read_text().strip()
        source = f"file: {test_key_file}"
    else:
        private_key_hex = os.getenv("SYMBOL_TEST_PRIVATE_KEY", "").strip()
        source = "environment variable: SYMBOL_TEST_PRIVATE_KEY"

    if not private_key_hex:
        return None

    try:
        return PrivateKey(private_key_hex)
    except Exception as exc:
        pytest.fail(f"Invalid test private key in {source}: {exc}")


@pytest.fixture
def testnet_wallet():
    """Fixture providing an unloaded testnet wallet."""
    node_url = _select_reachable_testnet_node()
    wallet = Wallet(network_name="testnet")
    wallet.node_url = node_url
    wallet._update_node_url(node_url)
    return wallet


@pytest.fixture
def loaded_testnet_wallet(
    test_key_file: Path | None,
    test_private_key: PrivateKey | None,
    expected_test_address: str | None,
    require_live_key: bool,
):
    """Fixture providing a loaded testnet wallet with private key from --test-key-file."""
    if test_private_key is None:
        message = (
            "No test private key available. "
            "Run: uv run python scripts/setup_test_key.py "
            "or set SYMBOL_TEST_PRIVATE_KEY."
        )
        if require_live_key:
            pytest.fail(message)
        pytest.skip(message)

    node_url = _select_reachable_testnet_node()
    wallet = Wallet(network_name="testnet")
    wallet.node_url = node_url
    wallet._update_node_url(node_url)
    wallet.facade = SymbolFacade("testnet")
    wallet.private_key = test_private_key
    account = wallet.facade.create_account(wallet.private_key)
    wallet.public_key = account.public_key
    wallet.address = account.address

    actual_address = str(wallet.address).upper()
    expected_from_sidecar = _read_expected_address_from_sidecar(test_key_file)
    sidecar_path = _test_key_address_sidecar(test_key_file) if test_key_file else None

    if (
        expected_test_address is not None
        and expected_from_sidecar is not None
        and sidecar_path is not None
        and expected_test_address != expected_from_sidecar
    ):
        pytest.fail(
            "Mismatch between --expected-test-address/SYMBOL_TEST_EXPECTED_ADDRESS "
            f"({expected_test_address}) and key sidecar "
            f"({sidecar_path}) value ({expected_from_sidecar})."
        )

    for expected in [expected_test_address, expected_from_sidecar]:
        if expected is None:
            continue
        if actual_address != expected:
            pytest.fail(
                "Live test key address mismatch. "
                f"expected={expected} actual={actual_address}"
            )

    return wallet


@pytest.fixture
def ensure_live_min_balance() -> Callable[..., int]:
    """Return a helper that skips live tests when account balance is below threshold."""

    def _ensure(
        wallet: Any,
        min_balance_micro: int,
        *,
        label: str = "Insufficient balance",
    ) -> int:
        before = wallet.get_xym_balance()
        total = int(before.get("xym_micro", 0))
        available, locked = _estimate_spendable_xym_micro(wallet, total)
        required = max(int(min_balance_micro), 0)
        if available < required:
            pytest.skip(
                f"{label}: spendable={available} micro XYM "
                f"(total={total}, active_locked={locked}, need {required})"
            )
        return available

    return _ensure


@pytest.fixture
def testnet_facade():
    """Fixture providing testnet Symbol facade"""
    return SymbolFacade("testnet")


@pytest.fixture
def mainnet_facade():
    """Fixture providing mainnet Symbol facade"""
    return SymbolFacade("mainnet")


@pytest.fixture
def random_private_key():
    """Fixture providing a random private key"""
    return PrivateKey.random()


@pytest.fixture
def testnet_account(random_private_key):
    """Fixture providing a testnet account"""
    facade = SymbolFacade("testnet")
    return facade.create_account(random_private_key)


@pytest.fixture
def mainnet_account(random_private_key):
    """Fixture providing a mainnet account"""
    facade = SymbolFacade("mainnet")
    return facade.create_account(random_private_key)


@pytest.fixture
def xym_mosaic_id():
    """Fixture providing XYM mosaic ID"""
    return 0x6BED913FA20223F8


@pytest.fixture
def xym_mosaic_id_decimal():
    """Fixture providing XYM mosaic ID in decimal"""
    return 7777031834025731064


@pytest.fixture
def testnet_node_url():
    """Fixture providing testnet node URL"""
    return _select_reachable_testnet_node()


@pytest.fixture
def mainnet_node_url():
    """Fixture providing mainnet node URL"""
    return "http://sym-main-01.opening-line.jp:3000"


@pytest.fixture(autouse=True)
def isolate_wallet_storage(monkeypatch, request):
    """Run tests with isolated wallet storage unless explicitly running live transfer."""
    if (
        request.node.get_closest_marker("integration")
        and request.node.name == "test_live_send_and_confirm_transaction"
    ):
        yield
        return

    with tempfile.TemporaryDirectory(prefix="symbol-wallet-test-") as tmp_dir:
        monkeypatch.setenv("SYMBOL_WALLET_DIR", str(Path(tmp_dir)))
        yield
