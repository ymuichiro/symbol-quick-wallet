from __future__ import annotations

from getpass import getpass
from pathlib import Path

from src.wallet import Wallet


def main() -> int:
    wallet = Wallet(network_name="testnet")

    if not wallet.wallet_file.exists():
        print(f"wallet file not found: {wallet.wallet_file}")
        return 1

    password = getpass("Wallet password: ")
    if not password:
        print("password is required")
        return 1

    try:
        wallet.load_wallet_from_storage(password)
    except Exception as exc:
        print(f"failed to decrypt wallet: {exc}")
        return 1

    private_key = str(wallet.private_key)
    target = Path("tests/live_test_key.py")
    target.write_text(
        '"""Hardcoded key for live transfer integration tests."""\n\n'
        f'HARDCODED_TEST_PRIVATE_KEY = "{private_key}"\n',
        encoding="utf-8",
    )

    print(f"updated {target}")
    print(f"address: {wallet.address}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
