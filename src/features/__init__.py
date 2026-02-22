"""Feature modules for Symbol Quick Wallet.

This package contains self-contained feature modules organized by functionality:

- transfer: Transfer transactions, templates, and queue management
- address_book: Contact and group management
- mosaic: Mosaic creation and metadata viewing
- namespace: Namespace registration and alias management
"""

from src.features import transfer
from src.features import address_book
from src.features import mosaic
from src.features import namespace

__all__ = ["transfer", "address_book", "mosaic", "namespace"]
