"""Lock transaction feature module for Symbol Quick Wallet.

Supports hash lock and secret lock transactions for:
- Cross-chain atomic swaps
- Conditional payments
- Aggregate bonded transaction locking

Usage:
    from src.features.lock import LockService, LockHashAlgorithm
    from src.features.lock import SecretProofPair, SecretLockInfo, HashLockInfo
"""

from src.features.lock.service import (
    HashLockInfo,
    LockHashAlgorithm,
    LockService,
    SecretLockInfo,
    SecretProofPair,
    HASH_LOCK_AMOUNT,
    HASH_LOCK_DURATION,
)
from src.features.lock.screen import (
    LocksOverviewScreen,
    SecretLockCreateScreen,
    SecretProofCreateScreen,
    LockResultScreen,
)
from src.features.lock.handlers import LockHandlersMixin

__all__ = [
    "LockService",
    "LockHashAlgorithm",
    "SecretProofPair",
    "SecretLockInfo",
    "HashLockInfo",
    "HASH_LOCK_AMOUNT",
    "HASH_LOCK_DURATION",
    "LocksOverviewScreen",
    "SecretLockCreateScreen",
    "SecretProofCreateScreen",
    "LockResultScreen",
    "LockHandlersMixin",
]
