"""Namespace feature module for Symbol Quick Wallet.

This module provides namespace management functionality including:
- Register root and sub-namespaces
- Link namespaces to addresses and mosaics
- View namespace ownership and expiration
- Resolve namespace names to addresses/mosaics
"""

from src.features.namespace.handlers import NamespaceHandlersMixin
from src.features.namespace.screen import (
    LinkAddressAliasScreen,
    LinkAddressAliasSubmitted,
    LinkMosaicAliasScreen,
    LinkMosaicAliasSubmitted,
    NamespaceInfoScreen,
    RegisterRootNamespaceScreen,
    RegisterRootNamespaceSubmitted,
    RegisterSubNamespaceScreen,
    RegisterSubNamespaceSubmitted,
    ResolveNamespaceScreen,
    ResolveNamespaceSubmitted,
)
from src.features.namespace.service import NamespaceInfo, NamespaceService
from src.features.namespace.validators import NamespaceValidator, ValidationResult

__all__ = [
    "LinkAddressAliasScreen",
    "LinkAddressAliasSubmitted",
    "LinkMosaicAliasScreen",
    "LinkMosaicAliasSubmitted",
    "NamespaceHandlersMixin",
    "NamespaceInfo",
    "NamespaceInfoScreen",
    "NamespaceService",
    "NamespaceValidator",
    "RegisterRootNamespaceScreen",
    "RegisterRootNamespaceSubmitted",
    "RegisterSubNamespaceScreen",
    "RegisterSubNamespaceSubmitted",
    "ResolveNamespaceScreen",
    "ResolveNamespaceSubmitted",
    "ValidationResult",
]
