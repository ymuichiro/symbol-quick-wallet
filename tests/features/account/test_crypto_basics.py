import pytest
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade


@pytest.mark.unit
def test_private_key_generation():
    private_key = PrivateKey.random()
    assert private_key is not None
    assert len(str(private_key)) == 64


@pytest.mark.unit
def test_address_derivation():
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account = facade.create_account(private_key)

    assert account.public_key is not None
    assert account.address is not None
    assert str(account.address).startswith("T")


@pytest.mark.unit
def test_network_address_prefix():
    testnet_facade = SymbolFacade("testnet")
    mainnet_facade = SymbolFacade("mainnet")

    private_key = PrivateKey.random()
    testnet_account = testnet_facade.create_account(private_key)
    mainnet_account = mainnet_facade.create_account(private_key)

    assert str(testnet_account.address).startswith("T")
    assert str(mainnet_account.address).startswith("N")


@pytest.mark.unit
def test_account_key_pair():
    facade = SymbolFacade("testnet")
    private_key = PrivateKey.random()
    account1 = facade.create_account(private_key)
    account2 = facade.create_account(private_key)

    assert account1.public_key == account2.public_key
    assert account1.address == account2.address
