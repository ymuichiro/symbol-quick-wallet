# Symbol Quick Wallet Test Suite

This directory contains unit and integration tests for Symbol Quick Wallet.

## Test Layout

```
tests/
├── conftest.py
├── features/
│   ├── account/
│   ├── address_book/
│   ├── aggregate/
│   ├── lock/
│   ├── metadata/
│   ├── monitoring/
│   ├── mosaic/
│   ├── multisig/
│   ├── namespace/
│   └── transfer/
└── shared/
```

## Key Concept: Live Test Account Provisioning

Live on-chain tests require a funded testnet account.

This repository now supports provisioning a test key without committing secrets:

```bash
uv run python scripts/setup_test_key.py .test_key
```

The command:
1. generates a new private key
2. stores it in the given file (default `.test_key`)
3. stores the derived address in `<key-file>.address`
4. prints the testnet address for funding

If the key file already exists, it is reused by default.
`--force` overwrite now requires explicit current-address confirmation to avoid accidental key rotation.

After that, fund the printed address manually (faucet or transfer), then run tests with:

```bash
uv run pytest --test-key-file .test_key -m "integration and slow" -v
```

`.test_key` is ignored by git.

## How Tests Resolve Private Keys

`tests/conftest.py` resolves the live key in this order:
1. `--test-key-file` (default path: `.test_key`)
2. `SYMBOL_TEST_PRIVATE_KEY` environment variable (fallback)

If neither is available, live-key fixtures skip tests by default.

To make missing keys fail immediately:

```bash
uv run pytest --test-key-file .test_key --require-live-key -m "integration and slow" -v
```

To ensure the key address never changes unexpectedly in this environment:

```bash
uv run pytest --test-key-file .test_key \
  --expected-test-address <KNOWN_TEST_ADDRESS> \
  --require-live-key \
  -m "integration and slow" -v
```

You can also set `SYMBOL_TEST_EXPECTED_ADDRESS=<KNOWN_TEST_ADDRESS>`.
When set, pytest fails immediately if the loaded key resolves to a different address.

## Common Commands

```bash
# All tests
uv run pytest -q

# Unit tests only
uv run pytest -m unit -q

# Integration tests (read-heavy, no long waits)
uv run pytest -m "integration and not slow" -q

# Live on-chain tests (may spend XYM)
uv run pytest -m "integration and slow" -q
```

## Live Slow Test Runtime Knobs

The following environment variables are useful for `integration and slow` runs:

- `SYMBOL_TEST_MOSAIC_MIN_BALANCE_MICRO`:
  Minimum XYM (micro units) required before mosaic live tests start.
  Default is `50000000` (50 XYM) to avoid mid-run insufficient-balance failures.
- `SYMBOL_TEST_OBSERVER_VISIBILITY_TIMEOUT`:
  Timeout in seconds for aggregate bonded observer visibility checks.
  Default is `180`.
- `SYMBOL_TEST_OBSERVER_VISIBILITY_POLL`:
  Poll interval in seconds for observer visibility checks.
  Default is `10`.

Example:

```bash
SYMBOL_TEST_RUN_LIVE=1 \
SYMBOL_TEST_MOSAIC_MIN_BALANCE_MICRO=70000000 \
SYMBOL_TEST_OBSERVER_VISIBILITY_TIMEOUT=240 \
SYMBOL_TEST_OBSERVER_VISIBILITY_POLL=10 \
uv run pytest --test-key-file .test_key --require-live-key \
  --expected-test-address <KNOWN_TEST_ADDRESS> \
  -m "integration and slow" -v
```

## Markers

- `unit`: isolated/unit-level tests
- `integration`: real node interaction
- `slow`: longer-running / confirmation-waiting tests

## Feature Validation Matrix (Real Node)

| Feature | Read integration (`integration and not slow`) | Live write integration (`integration and slow`) | Known skip conditions in strict live mode |
| --- | --- | --- | --- |
| account | Yes | No (read-only coverage) | none |
| transfer | Yes | Yes | `SYMBOL_TEST_RUN_LIVE!=1`, missing live key, insufficient XYM balance |
| aggregate | Yes | Yes | `SYMBOL_TEST_RUN_LIVE!=1`, missing live key, insufficient XYM balance, node/network aggregate policy prohibitions |
| mosaic | Yes | Yes | `SYMBOL_TEST_RUN_LIVE!=1`, missing live key, insufficient XYM balance |
| namespace | Yes | No (read-only resolution coverage) | none |
| multisig | Yes | Yes | `SYMBOL_TEST_RUN_LIVE!=1`, missing live key, insufficient XYM balance, node unavailable |
| lock | Yes | Yes | `SYMBOL_TEST_RUN_LIVE!=1`, missing live key, insufficient XYM balance |
| metadata | Yes | Yes | `SYMBOL_TEST_RUN_LIVE!=1`, missing live key, insufficient XYM balance |
| monitoring | Yes | Partial (WS subscription path) | WebSocket listener/channel subscription may be unavailable on current node |

Notes:
- Aggregate bonded observability tests keep fail behavior when visibility cannot be confirmed; failures include per-node diagnostics to aid investigation.
- For strict runs, use `--require-live-key` to fail fast when no live key is available.

## Live Test Safety

Slow integration tests can announce transactions and spend testnet XYM.

Recommended safeguards:
- use a dedicated test account
- keep enough balance for a full slow run (recommended: at least 50 XYM)
- note that hash-lock and mosaic flows reduce currently available balance during the same run
- run slow tests explicitly, not in default CI path
- use `--require-live-key` in strict CI jobs where key presence is mandatory

## CI Notes

For CI, either:
- create a key file from secrets and pass `--test-key-file`, or
- set `SYMBOL_TEST_PRIVATE_KEY` as secret env var.

Example strict live job:

```bash
uv run pytest --require-live-key -m "integration and slow" -v
```
