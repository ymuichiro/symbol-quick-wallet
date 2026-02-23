# Symbol Quick Wallet Test Suite

This directory contains the test suite for Symbol Quick Wallet, including unit tests and integration tests against real Symbol blockchain nodes.

## Test Organization

```
tests/
├── conftest.py              # Shared pytest fixtures
├── live_test_key.py         # Test private key for integration tests
├── features/
│   ├── account/             # Account feature tests
│   ├── address_book/        # Address book feature tests
│   ├── aggregate/           # Aggregate transaction tests
│   │   ├── test_service.py  # Unit and integration tests
│   │   └── test_integration.py  # Live blockchain integration tests
│   ├── lock/                # Hash lock feature tests
│   ├── metadata/            # Metadata feature tests
│   ├── mosaic/              # Mosaic feature tests
│   │   └── test_integration.py  # Live mosaic integration tests
│   ├── monitoring/          # Monitoring feature tests
│   ├── multisig/            # Multisig feature tests
│   ├── namespace/           # Namespace feature tests
│   └── transfer/            # Transfer feature tests
│       └── test_integration.py  # Live transfer integration tests
└── shared/                  # Shared utility tests
    └── test_integration_network.py  # Network client integration tests
```

## Running Tests

### Unit Tests

Run all unit tests:

```bash
uv run pytest -q                    # All tests (quiet mode)
uv run pytest -v                    # All tests (verbose mode)
uv run pytest -m unit               # Only unit tests
```

Run specific test files:

```bash
uv run pytest tests/features/transfer/test_service.py -v
uv run pytest tests/features/mosaic/ -v
```

### Integration Tests

Integration tests hit real Symbol testnet nodes. They are marked with `@pytest.mark.integration`.

Run integration tests:

```bash
uv run pytest -m integration -v
```

Run integration tests for specific features:

```bash
uv run pytest tests/features/transfer/test_integration.py -m integration -v
uv run pytest tests/features/mosaic/test_integration.py -m integration -v
uv run pytest tests/features/aggregate/test_integration.py -m integration -v
```

### Slow/Live Tests

Some integration tests create real transactions on the testnet and are marked with `@pytest.mark.slow`. These tests:

- Require a funded testnet account
- Spend real XYM (minimal amounts)
- Wait for transaction confirmations

Run slow tests:

```bash
# First, set the environment variables (see Test Account Setup below)
export SYMBOL_TEST_PRIVATE_KEY="your_private_key_here"
export SYMBOL_TEST_RUN_LIVE=1

uv run pytest -m "integration and slow" -v
```

## Test Account Setup

### Prerequisites

To run live integration tests that create real transactions, you need:

1. A funded Symbol testnet account
2. The private key for that account

### Getting Testnet XYM

1. Visit the Symbol Faucet: https://testnet.symbol.tools/faucet
2. Enter your testnet address
3. Complete the faucet request to receive testnet XYM

### Configuration

**Option 1: Environment Variable**

```bash
export SYMBOL_TEST_PRIVATE_KEY="YOUR_64_CHAR_HEX_PRIVATE_KEY"
```

**Option 2: Hardcoded Key (Development Only)**

Edit `tests/live_test_key.py`:

```python
HARDCODED_TEST_PRIVATE_KEY = "YOUR_64_CHAR_HEX_PRIVATE_KEY"
```

**⚠️ WARNING:** Never commit real private keys to the repository. The hardcoded key is for development only and should be a dedicated test account.

### Required Balance

Different tests require different minimum balances:

| Test Type | Minimum Balance |
|-----------|-----------------|
| Transfer tests | 1 XYM |
| Mosaic creation | 1 XYM |
| Aggregate complete | 1 XYM |
| Aggregate bonded | 11 XYM (10 XYM for hash lock) |

### CI/CD Configuration

For CI/CD pipelines, use the environment variable approach:

#### GitHub Actions Setup

1. **Create a Repository Secret:**
   - Go to your repository → Settings → Secrets and variables → Actions
   - Add a new repository secret named `SYMBOL_TEST_PRIVATE_KEY`
   - Set the value to your 64-character hex private key

2. **Workflow Configuration:**

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv run pytest -m unit -v

  integration-tests:
    runs-on: ubuntu-latest
    env:
      SYMBOL_TEST_PRIVATE_KEY: ${{ secrets.SYMBOL_TEST_PRIVATE_KEY }}
      SYMBOL_TEST_RUN_LIVE: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv run pytest -m "integration and not slow" -v

  live-tests:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    env:
      SYMBOL_TEST_PRIVATE_KEY: ${{ secrets.SYMBOL_TEST_PRIVATE_KEY }}
      SYMBOL_TEST_RUN_LIVE: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv run pytest -m "integration and slow" -v --timeout=600
```

#### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SYMBOL_TEST_PRIVATE_KEY` | For live tests | 64-character hex private key |
| `SYMBOL_TEST_RUN_LIVE` | For live tests | Set to `"1"` to enable live transaction tests |
| `SYMBOL_TEST_NETWORK` | Optional | Network name (`testnet` or `mainnet`, default: `testnet`) |
| `SYMBOL_TEST_NODE_URL` | Optional | Custom node URL (default: `http://sym-test-01.opening-line.jp:3000`) |
| `SYMBOL_TEST_TRANSFER_MICRO` | Optional | Transfer amount in micro XYM (default: `100000`) |
| `SYMBOL_TEST_CONFIRM_TIMEOUT` | Optional | Transaction confirmation timeout in seconds (default: `180`) |

**⚠️ Security Notes:**
- Never commit private keys to the repository
- Use repository secrets for CI/CD
- Use a dedicated test account (not your main wallet)
- Rotate keys if accidentally exposed

## Test Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.unit` | Fast unit tests with mocks |
| `@pytest.mark.integration` | Tests hitting real testnet nodes |
| `@pytest.mark.slow` | Tests that wait for transaction confirmations |

Run by marker:

```bash
uv run pytest -m unit -v
uv run pytest -m integration -v
uv run pytest -m "integration and not slow" -v
uv run pytest -m "integration and slow" -v
```

## Testnet Node

The default testnet node is: `http://sym-test-01.opening-line.jp:3000`

You can verify node availability:

```bash
curl http://sym-test-01.opening-line.jp:3000/node/health
```

## Writing New Integration Tests

When writing new integration tests:

1. Use `@pytest.mark.integration` for all tests hitting the network
2. Use `@pytest.mark.slow` for tests that create transactions
3. Check for `SYMBOL_TEST_RUN_LIVE=1` before running transaction tests
4. Skip tests if balance is insufficient
5. Use the `loaded_testnet_wallet` fixture for authenticated operations

Example:

```python
@pytest.mark.integration
@pytest.mark.slow
class TestMyFeatureLive:
    def test_live_operation(self, loaded_testnet_wallet):
        if os.getenv("SYMBOL_TEST_RUN_LIVE") != "1":
            pytest.skip("Set SYMBOL_TEST_RUN_LIVE=1 to run live tests")

        wallet = loaded_testnet_wallet
        before = wallet.get_xym_balance()

        if before["xym_micro"] < 1_000_000:
            pytest.skip("Insufficient balance")

        # Your test logic here
```

## Troubleshooting

### Node Connection Issues

If you see connection errors:

1. Check your internet connection
2. Verify the node is online: `curl http://sym-test-01.opening-line.jp:3000/node/health`
3. Try an alternative testnet node

### Insufficient Balance

If tests skip due to insufficient balance:

1. Visit the faucet to get more testnet XYM
2. Check your address: `uv run python -c "from src.wallet import Wallet; w = Wallet(); print(w.address)"` (after loading wallet)

### Transaction Failures

If transactions fail:

1. Check the transaction status in the Symbol explorer
2. Verify you have enough XYM for fees
3. Ensure your account is not locked
