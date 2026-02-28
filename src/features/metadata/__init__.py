"""Metadata feature module for Symbol Quick Wallet.

Provides functionality to attach key-value metadata to accounts, mosaics, and namespaces.
"""

from src.features.metadata.service import (
    MetadataInfo,
    MetadataService,
    MetadataTargetType,
)
from src.features.metadata.handlers import MetadataHandlersMixin

__all__ = [
    "MetadataService",
    "MetadataInfo",
    "MetadataTargetType",
    "MetadataHandlersMixin",
]
