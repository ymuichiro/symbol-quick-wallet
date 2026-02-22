# AGENTS.md

Guidelines for AI coding agents working in the Symbol Quick Wallet repository.

## Project Overview

A terminal-first TUI cryptocurrency wallet for the Symbol blockchain built with Python and the Textual framework. Supports testnet/mainnet, encrypted wallet storage, XYM transfers, mosaic management, and address book features.

## Architecture Requirements

### Feature-Based Module Organization

This application must be organized into feature-based modules. Each feature should be self-contained with its own logic, UI components, and tests.

**Feature Module Structure:**
```
src/
  features/
    transfer/           # Transfer feature
      __init__.py
      service.py        # Business logic
      screen.py         # TUI screen
      validators.py     # Feature-specific validation
    address_book/       # Address book feature
      __init__.py
      service.py
      screen.py
    mosaic/             # Mosaic management feature
      __init__.py
      service.py
      screen.py
```

**Rules:**
- Each feature module must be independently testable
- Cross-feature dependencies should be minimized
- Shared utilities go in `src/utils/` or top-level modules
- Tests must mirror the module structure: `tests/features/transfer/test_service.py`

### Real Blockchain Integration Testing

**CRITICAL: This is a blockchain wallet application. Mock APIs are NOT permitted.**

All blockchain-related functionality MUST be tested against real Symbol blockchain nodes:

1. **Use Testnet for Development**: Default to `http://sym-test-01.opening-line.jp:3000` for testing
2. **Real Transaction Testing**: When implementing transaction features, actually announce transactions to the network and verify confirmation
3. **CLI Verification**: After implementing features, run the application via CLI and verify operations work:
   ```bash
   uv run symbol-quick-wallet
   ```
4. **SDK Documentation**: Reference implementation examples in `docs/quick_learning_symbol_v3/`:
   - `04_transaction.md` - Transaction creation, signing, announcing
   - `05_mosaic.md` - Mosaic operations
   - `03_account.md` - Account management
   - Other docs for advanced features

**Testing Workflow:**
```bash
# 1. Run unit tests
uv run pytest tests/test_validation.py -v

# 2. Run integration tests against real nodes
uv run pytest -m integration -v

# 3. Manual CLI verification
uv run symbol-quick-wallet
# Perform actual transfer on testnet and verify it confirms
```

**Integration Test Requirements:**
- Use `@pytest.mark.integration` for tests that hit real nodes
- Use `@pytest.mark.slow` for tests that wait for transaction confirmation
- Test on testnet first; mainnet tests require explicit user consent
- Verify transaction status via `/transactionStatus` endpoint
- Wait for `group: "confirmed"` before considering test passed

## Build/Lint/Test Commands

### Type Checking
```bash
uv run ty check src/
```

### Linting
```bash
uv run ruff check src/
uv run ruff check src/ --fix  # Auto-fix issues
```

### Formatting
```bash
uv run ruff format src/
uv run ruff format src/ --check  # Check without modifying
```

### Running Tests
```bash
uv run pytest -q                    # Run all tests (quiet)
uv run pytest -v                    # Run all tests (verbose)
uv run pytest tests/test_validation.py  # Run specific test file
uv run pytest tests/test_validation.py::TestAddressValidator -v  # Run specific test class
uv run pytest tests/test_validation.py::TestAddressValidator::test_valid_testnet_address -v  # Run single test
uv run pytest -m "not slow"         # Skip slow tests
uv run pytest -m integration        # Run only integration tests
uv run pytest -m unit               # Run only unit tests
```

### Running the Application
```bash
uv run symbol-quick-wallet          # Run the wallet application
```

## Code Style Guidelines

### Python Version
- Requires Python >=3.9.2, <4.0.0
- Use modern type hints: `str | None` instead of `Optional[str]`
- Use `list[dict[str, Any]]` instead of `List[Dict[str, Any]]`

### Imports
Group imports in this order, separated by blank lines:
1. Standard library (alphabetical)
2. Third-party packages (alphabetical)
3. Local imports from `src.` (alphabetical)

```python
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests
from symbolchain.facade.SymbolFacade import SymbolFacade
from textual.widgets import Button, Label

from src.network import NetworkClient, NetworkError
from src.validation import AmountValidator
```

### Naming Conventions
- **Modules**: `snake_case.py`
- **Classes**: `PascalCase` (e.g., `TransactionManager`, `AmountValidator`)
- **Functions/Methods**: `snake_case` (e.g., `parse_human_amount`, `validate_full`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_AMOUNT`, `XYM_MOSAIC_ID`)
- **Class attributes**: `snake_case` (e.g., `node_url`, `timeout_config`)
- **Private methods**: Prefix with `_` (e.g., `_normalize_address`, `_require_wallet_loaded`)

### Type Annotations
- Always add type hints to function parameters and return types
- Use `| None` for optional types
- Use `Any` sparingly, prefer specific types
- Use dataclasses for structured data:

```python
@dataclass
class ValidationResult:
    is_valid: bool
    error_message: str | None = None
    normalized_value: Any = None
```

### Error Handling
- Use custom exceptions inheriting from `Exception`
- Use the `ValidationResult` pattern for validation:
  ```python
  def validate(value: str) -> ValidationResult:
      if not value:
          return ValidationResult(is_valid=False, error_message="Value is required")
      return ValidationResult(is_valid=True, normalized_value=value.strip())
  ```
- Raise `ValueError` with descriptive messages for invalid arguments
- Use logging for errors: `logger.error("Failed to announce transaction: %s", e.message)`

### Logging
- Create module-level logger: `logger = logging.getLogger(__name__)`
- Use appropriate log levels: `logger.info()`, `logger.warning()`, `logger.error()`
- Use lazy formatting: `logger.info("Transaction sent to %s", address)`

### Classes
- Use `@dataclass` decorator for data-holding classes
- Define class constants at the top with `UPPER_SNAKE_CASE`
- Use `@classmethod` for factory methods
- Use `@staticmethod` for utility methods that don't need instance access
- Use Protocol classes for duck typing:

```python
class WalletLike(Protocol):
    def get_mosaic_name(self, mosaic_id: int) -> str: ...
```

### Docstrings
- Module-level docstring at the top of files
- Use double quotes for docstrings
- Keep docstrings concise and descriptive
- Use triple quotes for multiline docstrings

```python
"""Network utilities for Symbol Quick Wallet with timeout handling."""
```

### Code Formatting
- Maximum line length: 88 characters (ruff default)
- Use trailing commas in multi-line structures
- Use underscores in large numbers for readability: `1_000_000`, `9_223_372_036_854_775_807`

### Testing Conventions
- Test files: `tests/test_*.py`
- Test classes: `class Test*`
- Test methods: `def test_*`
- Use pytest fixtures from `conftest.py`
- Use markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
- Assert with descriptive messages where helpful
- **Feature module tests**: Place in `tests/features/{feature_name}/test_*.py`

```python
class TestAmountValidator:
    def test_valid_decimal(self):
        result = AmountValidator.parse_human_amount("1.5")
        assert result.is_valid is True
        assert result.normalized_value == 1.5
```

**Testing Feature Modules:**
```bash
# Test a specific feature module
uv run pytest tests/features/transfer/ -v

# Test a specific test in a feature module
uv run pytest tests/features/transfer/test_service.py::TestTransferService::test_send_transaction -v
```

### Textual Framework
- Inherit from `ModalScreen` for modal dialogs
- Use `BaseModalScreen` for consistent key bindings
- Define `BINDINGS` class attribute for keyboard shortcuts
- Use `compose()` method to define widget hierarchy
- CSS styles are defined in `src/styles.py`

## File Structure

### Current Structure (Top-Level Modules)
```
src/
  __init__.py          # Package exports
  __main__.py          # Application entry point (main TUI app)
  clipboard.py         # Clipboard utilities
  connection_state.py  # Connection status management
  network.py           # Network client with retry/timeout
  qr_scanner.py        # QR code scanning
  screens.py           # Modal screens and dialogs
  styles.py            # CSS styles for TUI
  transaction.py       # Transaction management
  transaction_queue.py # Batch transaction queue
  transaction_template.py # Transaction templates
  validation.py        # Input validation utilities
  wallet.py            # Wallet core functionality

tests/
  conftest.py          # Shared pytest fixtures
  test_*.py            # Test modules
```

### Target Structure (Feature-Based)
```
src/
  __init__.py          # Package exports
  __main__.py          # Application entry point
  features/
    transfer/
      __init__.py
      service.py       # Transfer business logic
      screen.py        # Transfer TUI screen
      validators.py    # Transfer-specific validation
    address_book/
      __init__.py
      service.py
      screen.py
    mosaic/
      __init__.py
      service.py
      screen.py
  shared/              # Shared utilities (network, validation, etc.)
    network.py
    validation.py
    clipboard.py
  styles.py            # CSS styles for TUI

tests/
  conftest.py          # Shared pytest fixtures
  features/
    transfer/
      test_service.py
      test_screen.py
    address_book/
      test_service.py
    mosaic/
      test_service.py
```

## Pre-commit Checklist
1. `uv run ruff check src/` - Fix lint issues
2. `uv run ruff format src/` - Format code
3. `uv run ty check src/` - Verify type checking passes
4. `uv run pytest -q` - Ensure all tests pass
