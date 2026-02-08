import pytest
import tempfile
from pathlib import Path
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade


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
    if request.node.get_closest_marker("integration") and request.node.name == "test_live_send_and_confirm_transaction":
        yield
        return

    with tempfile.TemporaryDirectory(prefix="symbol-wallet-test-") as tmp_dir:
        monkeypatch.setenv("SYMBOL_WALLET_DIR", str(Path(tmp_dir)))
        yield
