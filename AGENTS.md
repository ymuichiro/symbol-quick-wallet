# AGENTS.md

Guidelines and fast-start context for AI coding agents working on `symbol-quick-wallet`.

Last synced with `origin/main` commit `05763cd` on 2026-02-28.

## Project Summary
- Terminal-first Symbol wallet built with Python + Textual.
- Primary entrypoint: `symbol-quick-wallet = src.__main__:main`.
- Supports account management, transfer, aggregate tx, namespace, metadata, multisig, lock, monitoring, and address book operations.

## Current Architecture (After Main Update)

### App Composition
- `src/__main__.py`
  - `WalletApp` is the main Textual app.
  - Uses mixins for feature handlers:
    - `TransferHandlersMixin`
    - `AddressBookHandlersMixin`
    - `AccountHandlersMixin`
    - `MosaicHandlersMixin`
    - `NamespaceHandlersMixin`
    - `MultisigHandlersMixin`
    - `MetadataHandlersMixin`
    - `LockHandlersMixin`
    - `AggregateHandlersMixin`
  - Initializes queue/template/monitoring infrastructure:
    - `TransactionQueue`
    - `TemplateStorage`
    - `ConnectionMonitor`
    - `TransactionMonitor`

### Feature Modules (`src/features/`)
Implemented features are split by domain and typically contain `handlers.py`, `service.py`, `screen.py`:
- `account`
- `address_book`
- `aggregate`
- `lock`
- `metadata`
- `monitoring` (service-focused)
- `mosaic`
- `multisig`
- `namespace`
- `transfer`

### Shared Modules (`src/shared/`)
Cross-feature utilities are centralized here:
- `clipboard.py`
- `connection_state.py`
- `logging.py`
- `network.py`
- `protocols.py`
- `qr_scanner.py`
- `styles.py`
- `transaction_queue.py`
- `transaction_template.py`
- `validation.py`

### Legacy/Core Modules Still Used
- `src/wallet.py`
- `src/transaction.py`
- `src/screens.py` (shared modals and dialogs)

## Testing Structure (Now Feature-Based)
Tests are reorganized to mirror features:
- `tests/features/{feature}/...`
- `tests/shared/...`

Important fixtures/config:
- `tests/conftest.py`
  - Adds `--test-key-file` option.
  - Adds `--require-live-key` option (fail instead of skip when live key is missing).
  - Provides `loaded_testnet_wallet` fixture (skips if no key unless `--require-live-key`).
  - Selects reachable testnet node dynamically from:
    1. `SYMBOL_TEST_NODE_URL`
    2. `SYMBOL_TEST_NODE_URLS` (comma-separated)
    3. fallback defaults (`sym-test-01`, `sym-test-03`)
  - Isolates wallet storage with `SYMBOL_WALLET_DIR` temp dir for most tests.

## Live Test Key Workflow
- Generate a disposable key file (do not commit):
```bash
uv run python scripts/setup_test_key.py
```
- Preferred execution style for strict live runs:
```bash
SYMBOL_TEST_RUN_LIVE=1 uv run pytest -q \
  --test-key-file /path/to/.test_key \
  --require-live-key \
  -m "integration and slow"
```
- Key resolution order in tests:
  1. `--test-key-file`
  2. `SYMBOL_TEST_PRIVATE_KEY`
- Removed legacy hardcoded-key helpers:
  - `tests/live_test_key.py` (deleted)
  - `scripts/set_live_test_key.py` (deleted)

### Live Test Key Immutability Rule (Important)
- Once a test key file has been funded and used for live tests, **do not overwrite/regenerate it**.
- In stable local environments, avoid any operation that changes the funded test-account key because it effectively "resets" account state and breaks balance continuity.
- Do not run `scripts/setup_test_key.py` with `--force` against an existing funded key file.
- Use a persistent path (not `/tmp`) for stable local environments, for example:
  - `/Users/you/.config/symbol-quick-wallet/keys/testnet_live.key`
- If you need guardrails during pytest runs, set expected address checks:
  - `--expected-test-address <ADDRESS>` or `SYMBOL_TEST_EXPECTED_ADDRESS=<ADDRESS>`

## On-Chain Flow Notes (Important)
- `Wallet.get_balance` and account balance parsing now unwrap `/accounts/{address}` responses with `{"account": ...}`.
- Mosaic creation flow is now two-step:
  1. `mosaic_definition_transaction_v1`
  2. `mosaic_supply_change_transaction_v1`
- Previously skipped mosaic transaction-creation integration tests are re-enabled and passing.
- Mosaic REST lookups require 16-hex mosaic IDs (no `0x` prefix). `Wallet.get_mosaic_info` and namespace lookup normalize this.
- Namespace ID/path generation now uses Symbol SDK `IdGenerator` in both wallet and namespace service.
- Namespace resolution integration tests for `symbol.xym` are enabled and passing on testnet.
- Aggregate live tests must handle node capability limits:
  - aggregate transaction announce now uses v3 descriptors (`aggregate_complete_transaction_v3` / `aggregate_bonded_transaction_v3`).
  - some nodes still return unavailable bonded visibility despite successful announce/confirmation flow.
  - slow live aggregate tests skip in those capability-limited conditions instead of false-failing.
- Slow live confirmation tests use `SYMBOL_TEST_CONFIRM_TIMEOUT` (default 300s) to reduce transient network flakiness.

## Blockchain Testing Policy
This is a blockchain wallet project. Prefer real-node verification for blockchain behavior.
- Integration tests use Symbol testnet nodes.
- Live transaction tests are gated by environment flags and key availability.

Useful setup:
```bash
uv run python scripts/setup_test_key.py
# creates .test_key for integration/live scenarios

# strict mode: fail fast if no live key is available
uv run pytest --test-key-file .test_key --require-live-key -m "integration and slow" -q
```

## Useful Commands
```bash
# Run app
uv run symbol-quick-wallet

# Lint / type
uv run ruff check src/
uv run ty check src/

# Tests
uv run pytest -q
uv run pytest -m unit -q
uv run pytest -m "integration and not slow" -q
uv run pytest -m "slow and integration" -q
```

## Verified Status (Local, 2026-03-01 Latest)
- `uv run ruff check .`: pass
- `uv run ty check src`: pass
- `uv run ty check`: fail (34 diagnostics in test typing assertions; non-blocking for runtime code)
- `SYMBOL_TEST_RUN_LIVE=1 uv run pytest -q -m 'integration and not slow' --test-key-file /tmp/symbol-quick-wallet-test-key --require-live-key -rs .`: pass (`91 passed, 409 deselected`)
- `SYMBOL_TEST_RUN_LIVE=1 uv run pytest -q -m 'integration and slow' --test-key-file /tmp/symbol-quick-wallet-test-key --require-live-key -rs .`: pass (`19 passed, 2 skipped, 479 deselected`)

## Known Issues / Tech Debt
- Version mismatch remains:
  - `pyproject.toml`: `0.6.2`
  - `src/__init__.py`: `__version__ = "0.6.0"`
- Repository URLs in `pyproject.toml` still use `yourusername` placeholders.
- `docs/quick_learning_symbol_v3` exists as a gitlink, but `.gitmodules` is missing.
- Type-checking currently not green (`ty` failures listed above).
- Aggregate v3 is implemented and confirmed on testnet, but bonded visibility can still be unavailable on some nodes; 2 aggregate slow tests may skip by design.

## Agent Working Rules for This Repo
- Prefer editing inside feature modules first; avoid adding new cross-feature coupling in `src/__main__.py` unless orchestration is required.
- Keep shared concerns in `src/shared/`.
- When adding feature behavior, add corresponding tests under `tests/features/<feature>/`.
- For blockchain transaction logic changes, run at least:
  - targeted feature tests
  - `integration and not slow`
  - and live/slow tests if behavior affects on-chain confirmation semantics.
- While working, keep an execution memory log under `docs/memory/**`.
  - Record key decisions, implementation intent, scope changes, and test outcomes.
  - Append entries during the task (not only at completion).
  - Use dated files such as `docs/memory/2026-02-28.md`.
  - Never store secrets (private keys, tokens, passwords) in memory logs.

## Fast Start Checklist
1. Confirm branch state and latest `origin/main`.
2. Read this file + relevant feature module files.
3. Run targeted tests for touched feature.
4. Run `ruff` and `ty` before finalizing.
5. If touching on-chain flow, run integration tests and report what was skipped vs executed.
