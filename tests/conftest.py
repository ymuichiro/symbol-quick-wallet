import os
import pytest
import tempfile
from pathlib import Path
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade

from src.wallet import Wallet

TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"
TESTNET_XYM_MOSAIC_ID = 0x72C0212E67A08BCE


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--test-key-file",
        action="store",
        default=".test_key",
        help="Path to file containing test wallet private key",
    )


@pytest.fixture
def test_key_file(request: pytest.FixtureRequest) -> Path | None:
    key_file = Path(request.config.getoption("--test-key-file"))
    if not key_file.exists():
        return None
    return key_file


@pytest.fixture
def test_private_key(test_key_file: Path | None) -> PrivateKey | None:
    if test_key_file is None:
        return None
    private_key_hex = test_key_file.read_text().strip()
    if not private_key_hex:
        return None
    return PrivateKey(private_key_hex)


@pytest.fixture
def testnet_wallet():
    """Fixture providing an unloaded testnet wallet."""
    wallet = Wallet(network_name="testnet")
    wallet.node_url = TESTNET_NODE
    wallet._update_node_url(TESTNET_NODE)
    return wallet


@pytest.fixture
def loaded_testnet_wallet(test_private_key: PrivateKey | None):
    """Fixture providing a loaded testnet wallet with private key from --test-key-file."""
    if test_private_key is None:
        pytest.skip(
            "No test private key available. Run: uv run python scripts/setup_test_key.py"
        )

    wallet = Wallet(network_name="testnet")
    wallet.node_url = TESTNET_NODE
    wallet._update_node_url(TESTNET_NODE)
    wallet.facade = SymbolFacade("testnet")
    wallet.private_key = test_private_key
    account = wallet.facade.create_account(wallet.private_key)
    wallet.public_key = account.public_key
    wallet.address = account.address
    return wallet


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
    return "http://sym-test-01.opening-line.jp:3000"


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
