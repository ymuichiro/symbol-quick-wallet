#!/usr/bin/env python
"""Setup test wallet key for integration tests.

Usage:
    uv run python scripts/setup_test_key.py [FILE_PATH]

Default file path: .test_key

This will:
1. Generate a new private key
2. Save it to the specified file
3. Save a sidecar address file (`<key-file>.address`)
4. Print the address for funding

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


def _address_sidecar_path(key_file: Path) -> Path:
    return key_file.with_name(f"{key_file.name}.address")


def _derive_address(private_key_hex: str) -> str:
    facade = SymbolFacade("testnet")
    private_key = PrivateKey(private_key_hex)
    account = facade.create_account(private_key)
    return str(account.address)


def _write_address_sidecar(key_file: Path, address: str) -> Path:
    sidecar = _address_sidecar_path(key_file)
    sidecar.write_text(f"{address}\n")
    sidecar.chmod(0o644)
    return sidecar


def _is_temp_path(path: Path) -> bool:
    resolved = str(path.resolve())
    return resolved.startswith("/tmp/") or resolved.startswith("/private/tmp/")


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
    parser.add_argument(
        "--confirm-current-address",
        default="",
        help=(
            "Required with --force. Must match the current address in the existing "
            "key file to prevent accidental key rotation."
        ),
    )
    args = parser.parse_args()

    key_file = Path(args.file_path).expanduser()
    key_file.parent.mkdir(parents=True, exist_ok=True)

    if key_file.exists() and not args.force:
        try:
            current_address = _read_address(key_file)
        except Exception as exc:
            print(f"Key file exists but is invalid: {key_file}")
            print(f"Reason: {exc}")
            print()
            print(
                "To replace this broken file, run with: "
                "--force --confirm-current-address INVALID"
            )
            return 2

        sidecar = _write_address_sidecar(key_file, current_address)
        print(f"Key file already exists: {key_file}")
        print("Use --force to overwrite, or use existing key.")
        print()
        print(f"Testnet address: {current_address}")
        print(f"Address sidecar: {sidecar}")
        return 0

    if key_file.exists() and args.force:
        try:
            current_address = _read_address(key_file)
        except Exception:
            current_address = "INVALID"
        provided = args.confirm_current_address.strip().upper()
        required = current_address.strip().upper()
        if provided != required:
            print("=" * 60)
            print("Refusing to overwrite key without explicit address confirmation.")
            print("=" * 60)
            print(f"Existing key file: {key_file}")
            print(f"Current address : {current_address}")
            print()
            print("Re-run with:")
            print(
                "  uv run python scripts/setup_test_key.py "
                f"{key_file} --force --confirm-current-address {current_address}"
            )
            print("=" * 60)
            return 2

    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)
    address = str(account.address)

    key_file.write_text(str(private_key))
    key_file.chmod(0o600)
    sidecar = _write_address_sidecar(key_file, address)

    print("=" * 60)
    print("Test wallet key created!")
    print("=" * 60)
    print(f"Private key saved to: {key_file.absolute()}")
    print(f"Testnet address: {address}")
    print(f"Address sidecar: {sidecar.absolute()}")
    if _is_temp_path(key_file):
        print()
        print("WARNING: key file is under /tmp and may be removed by OS cleanup.")
        print("Use a persistent path if you need stable test addresses.")
    print()
    print("Next steps:")
    print("1. Send some XYM to the address above (use faucet or transfer)")
    print("2. Run tests with:")
    print(f"   uv run pytest --test-key-file={key_file}")
    print("=" * 60)

    return 0


def _read_address(key_file: Path) -> str:
    private_key_hex = key_file.read_text().strip()
    if not private_key_hex:
        raise ValueError("key file is empty")
    return _derive_address(private_key_hex)


if __name__ == "__main__":
    sys.exit(main())
