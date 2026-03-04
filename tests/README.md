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
3. prints the testnet address for funding

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

## Markers

- `unit`: isolated/unit-level tests
- `integration`: real node interaction
- `slow`: longer-running / confirmation-waiting tests

## Live Test Safety

Slow integration tests can announce transactions and spend testnet XYM.

Recommended safeguards:
- use a dedicated test account
- keep only minimal balance for test scenarios
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
