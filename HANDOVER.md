# Handover (2026-03-07)

## Current Status
- Aggregate bonded live failures were investigated and fixed in test/runtime flow.
- Balance-gate behavior for live slow tests was hardened using spendable-balance estimation.
- Targeted and strict live suites are green (slow suite has expected balance-based skips only).

## Implemented Changes
- `src/features/aggregate/service.py`
  - Hash-lock now supports explicit aggregate hash input.
  - Added hash calculation from signed payload.
  - Aggregate bonded workflow now signs aggregate first, derives hash from signed payload, then creates hash lock with that hash.
- `tests/conftest.py`
  - Added spendable XYM estimator (subtract active hash locks from total).
  - Live min-balance fixture now gates by spendable amount and reports total/locked/spendable.
- `tests/features/aggregate/test_service.py`
  - Added regression tests for explicit hash-lock hash usage.
  - Added regression test for signed-payload hash consistency.
- `docs/memory/2026-03-07.md`
  - Execution notes and validation logs.

## Validation Snapshot
- `uv run ruff check src/features/aggregate/service.py tests/conftest.py tests/features/aggregate/test_service.py`
  - pass
- `uv run pytest -q -c pyproject.toml tests/features/aggregate/test_service.py -m "not slow" -rs`
  - `40 passed, 7 deselected`
- strict live (fixed key + expected address)
  - `-m "integration and not slow"`: `96 passed, 423 deselected`
  - `-m "integration and slow"`: `20 passed, 6 skipped, 493 deselected` (no failures)
- `uv run pytest -q -c pyproject.toml tests -m unit -rs`
  - `114 passed, 405 deselected`

## Remaining Work (For Next Engineer)
1. If policy requires slow live tests to be fully `pass` (not skip), fund the fixed test account until spendable balance exceeds all thresholds (recommended `>= 50 XYM`).
2. Re-run strict slow suite and confirm skipped mosaic/aggregate balance gates become passing:
   - `SYMBOL_TEST_RUN_LIVE=1 uv run pytest -q -c pyproject.toml tests --test-key-file /Users/you/.config/symbol-quick-wallet/keys/testnet_live.key --require-live-key --expected-test-address TBXMLQGINECK33QR4SQJOACJB7NS7NZS2IGUILY -m "integration and slow" -rs`
3. Continue pending UI polish track (enterprise-level layout/design refinement) as a separate task stream.
4. Optional repository hygiene (not part of this fix):
   - reconcile version mismatch (`pyproject.toml` vs `src/__init__.py`)
   - address `ty check` full-repo diagnostics in tests

## Operational Notes
- Do not overwrite the existing live test key in this environment unless explicitly rotating the account.
- Keep expected-address guard enabled in strict runs:
  - `--expected-test-address TBXMLQGINECK33QR4SQJOACJB7NS7NZS2IGUILY`
