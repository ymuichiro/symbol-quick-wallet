## Fix error handling for network timeouts

- **Status**: completed
- **Priority**: high

The wallet currently doesn't handle network timeouts gracefully. When a node is slow or unresponsive, the UI freezes without clear feedback to the user.
**Improvements needed:**
- Add timeout configuration
- Show loading indicators during network operations
- Display meaningful error messages
- Implement retry logic with exponential backoff
### Self-Check (Production Logic)
- [ ] Verify timeout occurs after configured duration
- [ ] Verify retry logic with exponential backoff
- [ ] Verify NetworkError contains meaningful message
- [ ] Test with unreachable node URL
---
---

---

## Add input validation for transfer amounts

- **Status**: completed
- **Priority**: high

Users can input invalid amounts (negative, too many decimals, etc.) which may cause confusing errors.
**Required:**
- Validate amount format before submission
- Check against mosaic divisibility
- Show inline validation errors
- Prevent submission of invalid data
### Self-Check (Production Logic)
- [ ] Verify negative amounts are rejected
- [ ] Verify amounts with too many decimals are rejected
- [ ] Verify amount exceeds balance is rejected
- [ ] Verify valid amounts are normalized correctly
---
---

---

## Improve test coverage

- **Status**: completed
- **Priority**: medium

Current test coverage is minimal. Need comprehensive tests for:
- Wallet encryption/decryption
- Transaction building and signing
- Address validation
- Mosaic amount conversion
- Error scenarios
### Self-Check (Production Logic)
- [ ] Run `uv run pytest -q` and verify all tests pass
- [ ] Run `uv run pytest -m unit -v` for unit tests
- [ ] Run `uv run pytest -m integration -v` for integration tests
---
---

---

## Handle offline/online state gracefully

- **Status**: completed
- **Priority**: medium

The app doesn't detect or handle network state changes. Users should be notified when:
- Network is unavailable
- Node connection is lost
- Connection is restored
### Self-Check (Production Logic)
- [ ] Start app with network unavailable and verify error displayed
- [ ] Restore network and verify connection state updates
- [ ] Verify periodic connection status checks
---
---

---

## Add transaction confirmation status polling

- **Status**: completed
- **Priority**: medium

After submitting a transaction, the app should poll for confirmation status and update the UI accordingly instead of just showing a loading indicator.
### Self-Check (Production Logic)
- [ ] Submit transfer on testnet and verify polling starts
- [ ] Verify UI updates when transaction confirmed
- [ ] Verify error handling for failed transaction
---
---

---

## Refactor to feature-based module structure

- **Status**: completed
- **Priority**: high

Current codebase uses top-level modules, but AGENTS.md specifies feature-based organization as the target architecture.
**Issues with current structure:**
- Features are not self-contained
- Cross-feature dependencies are unclear
- Tests don't mirror module structure
**Required changes:**
- [x] Create `src/features/transfer/` with service.py, screen.py, validators.py
- [x] Create `src/features/address_book/` with service.py, screen.py
- [x] Create `src/features/mosaic/` with service.py, screen.py
- [x] Move shared code to `src/shared/`
- [x] Create corresponding test directories under `tests/features/`
- [x] Update all imports and exports
- [x] Run full test suite to verify no regressions
### Self-Check (Production Logic)
- [ ] Verify `uv run ty check src/` passes
- [ ] Verify `uv run ruff check src/` passes
- [ ] Verify `uv run pytest -q` passes
---
---

---

## Split oversized screens.py module

- **Status**: completed
- **Priority**: high

`src/screens.py` is 2918 lines, making it difficult to maintain and navigate.
**Issues:**
- All 40+ modal screens in a single file
- Hard to find specific screen implementations
- Difficult to understand feature boundaries
- Slow code navigation and IDE performance
**Required changes:**
- [x] Create `src/features/transfer/screens.py` for transfer-related screens
- [x] Create `src/features/address_book/screens.py` for address book screens
- [x] Create `src/features/mosaic/screens.py` for mosaic screens
- [x] Create `src/features/account/screens.py` for account management screens
- [x] Keep shared/common screens in `src/screens.py` (base classes, loading, etc.)
### Self-Check (Production Logic)
- [x] Verify no import errors after split
- [x] Verify all screens load correctly
- [x] Verify `uv run ty check src/` passes after split
---
---

---

## Refactor oversized __main__.py

- **Status**: completed
- **Priority**: high

`src/__main__.py` is 2943 lines with all application logic in one file.
**Issues:**
- UI composition mixed with business logic
- Event handlers are very long
- Difficult to test individual features
- Violates single responsibility principle
**Required changes:**
- [x] Extract transfer-related handlers to `src/features/transfer/handlers.py`
- [x] Extract address book handlers to `src/features/address_book/handlers.py`
- [x] Extract account management logic to `src/features/account/service.py`
- [x] Create mosaic handlers in `src/features/mosaic/handlers.py`
- [x] Keep only app initialization and routing in `__main__.py`
### Self-Check (Production Logic)
- [x] Verify app starts correctly after refactor
- [x] Verify all menu items navigate correctly
- [x] Verify `uv run ty check src/` passes after refactor
---
---

---

## Add comprehensive type hints

- **Status**: completed
- **Priority**: medium

Some parts of the codebase lack proper type annotations.
**Issues:**
- Function parameters without types
- Return types not documented
- `Any` used where specific types are known
- Protocol classes could be better utilized
**Required changes:**
- [x] Run `uv run ty check src/` and fix all errors
- [x] Add return type hints to all public methods
- [x] Replace `Any` with specific types where possible
- [x] Add Protocol classes for dependency injection points
### Self-Check (Production Logic)
- [ ] Verify `uv run ty check src/` passes with no errors
---
---

---

## Migrate tests to feature structure

- **Status**: in_progress
- **Priority**: medium

Tests are currently flat in `tests/` but should mirror the feature module structure.
**Issues:**
- Tests not organized by feature
- Hard to find tests for specific functionality
- Doesn't match AGENTS.md specification
**Required changes:**
- [x] Create `tests/features/transfer/` directory
- [x] Create `tests/features/address_book/` directory
- [x] Create `tests/features/mosaic/` directory
- [x] Create `tests/features/account/` directory
- [x] Create `tests/features/aggregate/` directory
- [x] Create `tests/shared/` for shared utility tests
- [ ] Move remaining flat tests to appropriate feature directories
- [ ] Add integration tests for each feature
### Self-Check (Production Logic)
- [ ] Verify `uv run pytest tests/features/ -v` runs all feature tests
- [ ] Verify `uv run pytest tests/shared/ -v` runs all shared tests
- [ ] Verify `uv run pytest -m integration` for blockchain tests
---
---

---

## Add integration tests for real blockchain

- **Status**: in_progress
- **Priority**: medium

Need more integration tests against real Symbol testnet nodes.
**Issues:**
- Most tests are mocked unit tests
- Real blockchain behavior not verified
- Transaction workflows not end-to-end tested
**Required changes:**
- [x] Add `@pytest.mark.integration` tests for account operations
- [x] Add integration tests for transfer on testnet
- [ ] Add integration tests for mosaic operations
- [ ] Add integration tests for aggregate transactions
- [ ] Document test account credentials for CI/CD
- [ ] Ensure tests can run with `uv run pytest -m integration`
### Self-Check (Production Logic)
- [ ] Run transfer on testnet and verify confirmation
- [ ] Run mosaic creation on testnet and verify confirmation
- [ ] Run aggregate bonded workflow on testnet
- [ ] Verify all transactions appear in explorer
---
---

---

## Improve logging and error messages

- **Status**: completed
- **Priority**: low

Some error scenarios lack user-friendly messages and logging.
**Issues:**
- Debug logs expose too much detail in production
- Some errors show raw exception messages
- Missing context in error logs
**Required changes:**
- [x] Add log level configuration (DEBUG for dev, INFO for prod)
- [x] Sanitize sensitive data in logs (no private keys)
- [x] Create user-friendly error message mapping
- [x] Add structured logging with context fields
### Self-Check (Production Logic)
- [x] Verify private keys are not logged
- [x] Verify error messages are user-friendly
- [x] Verify log levels can be configured
