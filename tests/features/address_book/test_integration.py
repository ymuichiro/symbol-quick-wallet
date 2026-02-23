import pytest


TESTNET_NODE = "http://sym-test-01.opening-line.jp:3000"


@pytest.fixture
def testnet_wallet():
    from src.wallet import Wallet

    wallet = Wallet(network_name="testnet")
    wallet.node_url = TESTNET_NODE
    wallet._update_node_url(TESTNET_NODE)
    return wallet


@pytest.mark.integration
class TestWalletAddressBook:
    def test_address_book_operations(self, testnet_wallet):
        test_address = "TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ"
        testnet_wallet.add_address(test_address, "Test Contact", "Test note")

        addresses = testnet_wallet.get_addresses()
        assert test_address in addresses
        assert addresses[test_address]["name"] == "Test Contact"

        info = testnet_wallet.get_address_info(test_address)
        assert info["name"] == "Test Contact"
        assert info["note"] == "Test note"

        testnet_wallet.update_address(test_address, "Updated Name", "Updated note")
        updated_info = testnet_wallet.get_address_info(test_address)
        assert updated_info["name"] == "Updated Name"

        testnet_wallet.remove_address(test_address)
        assert test_address not in testnet_wallet.get_addresses()

    def test_contact_groups(self, testnet_wallet):
        group_id = testnet_wallet.create_contact_group("Test Group", "#FF0000")
        assert group_id in testnet_wallet.get_contact_groups()

        group = testnet_wallet.get_contact_group(group_id)
        assert group["name"] == "Test Group"

        testnet_wallet.update_contact_group(group_id, "Renamed Group", "#00FF00")
        updated_group = testnet_wallet.get_contact_group(group_id)
        assert updated_group["name"] == "Renamed Group"

        testnet_wallet.delete_contact_group(group_id)
        assert group_id not in testnet_wallet.get_contact_groups()
