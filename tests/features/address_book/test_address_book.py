import json
import os
import tempfile
from pathlib import Path

import pytest

from src.wallet import Wallet


@pytest.mark.unit
def test_address_book_operations():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmpfile:
        json.dump({}, tmpfile)

    wallet = Wallet()
    wallet.address_book_file = Path(tmpfile.name)
    wallet._load_address_book()

    wallet.add_address(
        "TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I", "Test User", "Test note"
    )
    wallet.add_address("TBI7VJYLRJ7VJXZ4D7J6Z5V6X5V6X5V6X5V6", "Faucet")

    addresses = wallet.get_addresses()
    assert len(addresses) == 2
    assert "TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I" in addresses
    assert "TBI7VJYLRJ7VJXZ4D7J6Z5V6X5V6X5V6X5V6" in addresses
    assert addresses["TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I"]["name"] == "Test User"
    assert addresses["TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I"]["note"] == "Test note"
    assert addresses["TBI7VJYLRJ7VJXZ4D7J6Z5V6X5V6X5V6X5V6"]["name"] == "Faucet"

    wallet.update_address(
        "TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I", "Updated User", "Updated note"
    )
    addresses = wallet.get_addresses()
    assert (
        addresses["TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I"]["name"] == "Updated User"
    )
    assert (
        addresses["TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I"]["note"] == "Updated note"
    )

    wallet.remove_address("TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I")
    addresses = wallet.get_addresses()
    assert len(addresses) == 1
    assert "TCHBDENCLKEBILBPWP3JPB2XNY64OE7PYHHE32I" not in addresses
    assert "TBI7VJYLRJ7VJXZ4D7J6Z5V6X5V6X5V6X5V6" in addresses

    os.unlink(wallet.address_book_file)
