"""Symbol Quick Wallet - A terminal-first TUI cryptocurrency wallet.

This package is organized into feature-based modules:
- features.transfer: Transfer transactions and templates
- features.address_book: Contact and group management
- features.mosaic: Mosaic creation and metadata
- shared: Shared utilities (network, validation, etc.)
"""

from src.transaction import TransactionManager
from src.wallet import Wallet
from src.shared import (
    AddressValidator,
    AmountValidator,
    MosaicIdValidator,
    NetworkClient,
    NetworkError,
    NetworkErrorType,
    RetryConfig,
    TimeoutConfig,
    ValidationResult,
)

__version__ = "0.6.0"
__all__ = [
    "Wallet",
    "TransactionManager",
    "NetworkClient",
    "NetworkError",
    "NetworkErrorType",
    "RetryConfig",
    "TimeoutConfig",
    "AddressValidator",
    "AmountValidator",
    "MosaicIdValidator",
    "ValidationResult",
]
