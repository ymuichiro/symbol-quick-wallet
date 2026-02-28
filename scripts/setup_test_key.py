#!/usr/bin/env python
"""Setup test wallet key for integration tests.

Usage:
    uv run python scripts/setup_test_key.py [FILE_PATH]

Default file path: .test_key

This will:
1. Generate a new private key
2. Save it to the specified file
3. Print the address for funding

After running this script, send some XYM to the displayed address,
then run tests with:
    uv run pytest --test-key-file=.test_key
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Setup test wallet key for integration tests"
    )
    parser.add_argument(
        "file_path",
        nargs="?",
        default=".test_key",
        help="Path to save the private key (default: .test_key)",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing key file",
    )
    args = parser.parse_args()

    key_file = Path(args.file_path)

    if key_file.exists() and not args.force:
        print(f"Key file already exists: {key_file}")
        print("Use --force to overwrite, or use existing key.")
        print()
        _show_address(key_file)
        return 0

    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    key_file.write_text(str(private_key))
    key_file.chmod(0o600)

    print("=" * 60)
    print("Test wallet key created!")
    print("=" * 60)
    print(f"Private key saved to: {key_file.absolute()}")
    print(f"Testnet address: {account.address}")
    print()
    print("Next steps:")
    print("1. Send some XYM to the address above (use faucet or transfer)")
    print("2. Run tests with:")
    print(f"   uv run pytest --test-key-file={key_file}")
    print("=" * 60)

    return 0


def _show_address(key_file: Path) -> None:
    private_key_hex = key_file.read_text().strip()
    facade = SymbolFacade("testnet")
    private_key = PrivateKey(private_key_hex)
    account = facade.create_account(private_key)
    print(f"Testnet address: {account.address}")


if __name__ == "__main__":
    sys.exit(main())
