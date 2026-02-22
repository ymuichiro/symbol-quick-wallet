## Fix error handling for network timeouts

- **Status**: completed
- **Priority**: high

The wallet currently doesn't handle network timeouts gracefully. When a node is slow or unresponsive, the UI freezes without clear feedback to the user.
**Improvements needed:**
- Add timeout configuration
- Show loading indicators during network operations
- Display meaningful error messages
- Implement retry logic with exponential backoff
---
---
---
---
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
---
---
---
---
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
---
---
---
---
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
---
---
---
---
---
---

---

## Add transaction confirmation status polling

- **Status**: completed
- **Priority**: medium

After submitting a transaction, the app should poll for confirmation status and update the UI accordingly instead of just showing a loading indicator.
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
---

---

## Split oversized screens.py module

- **Status**: pending
- **Priority**: high

`src/screens.py` is 2918 lines, making it difficult to maintain and navigate.
**Issues:**
- All 40+ modal screens in a single file
- Hard to find specific screen implementations
- Difficult to understand feature boundaries
- Slow code navigation and IDE performance
**Required changes:**
- [ ] Create `src/features/transfer/screens.py` for transfer-related screens
- [ ] Create `src/features/address_book/screens.py` for address book screens
- [ ] Create `src/features/mosaic/screens.py` for mosaic screens
- [ ] Create `src/features/account/screens.py` for account management screens
- [ ] Keep shared/common screens in `src/screens.py` (base classes, loading, etc.)
---

---

## Refactor oversized __main__.py

- **Status**: pending
- **Priority**: high

`src/__main__.py` is 2943 lines with all application logic in one file.
**Issues:**
- UI composition mixed with business logic
- Event handlers are very long
- Difficult to test individual features
- Violates single responsibility principle
**Required changes:**
- [ ] Extract transfer-related handlers to `src/features/transfer/handlers.py`
- [ ] Extract address book handlers to `src/features/address_book/handlers.py`
- [ ] Extract account management logic to `src/features/account/service.py`
- [ ] Keep only app initialization and routing in `__main__.py`
---

---

## Add comprehensive type hints

- **Status**: pending
- **Priority**: medium

Some parts of the codebase lack proper type annotations.
**Issues:**
- Function parameters without types
- Return types not documented
- `Any` used where specific types are known
- Protocol classes could be better utilized
**Required changes:**
- [ ] Run `uv run ty check src/` and fix all errors
- [ ] Add return type hints to all public methods
- [ ] Replace `Any` with specific types where possible
- [ ] Add Protocol classes for dependency injection points
---

---

## Migrate tests to feature structure

- **Status**: pending
- **Priority**: medium

Tests are currently flat in `tests/` but should mirror the feature module structure.
**Issues:**
- Tests not organized by feature
- Hard to find tests for specific functionality
- Doesn't match AGENTS.md specification
**Required changes:**
- [ ] Create `tests/features/transfer/` directory
- [ ] Create `tests/features/address_book/` directory
- [ ] Create `tests/features/mosaic/` directory
- [ ] Move existing tests to appropriate feature directories
- [ ] Create `tests/shared/` for shared utility tests
---

---

## Add integration tests for real blockchain

- **Status**: pending
- **Priority**: medium

Need more integration tests against real Symbol testnet nodes.
**Issues:**
- Most tests are mocked unit tests
- Real blockchain behavior not verified
- Transaction workflows not end-to-end tested
**Required changes:**
- [ ] Add `@pytest.mark.integration` tests for account operations
- [ ] Add integration tests for transfer on testnet
- [ ] Add integration tests for mosaic operations
- [ ] Document test account credentials for CI/CD
- [ ] Ensure tests can run with `uv run pytest -m integration`
---

---

## Improve logging and error messages

- **Status**: pending
- **Priority**: low

Some error scenarios lack user-friendly messages and logging.
**Issues:**
- Debug logs expose too much detail in production
- Some errors show raw exception messages
- Missing context in error logs
**Required changes:**
- [ ] Add log level configuration (DEBUG for dev, INFO for prod)
- [ ] Sanitize sensitive data in logs (no private keys)
- [ ] Create user-friendly error message mapping
- [ ] Add structured logging with context fields
