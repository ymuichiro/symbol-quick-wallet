"""Tests for transaction monitoring service."""

import pytest

from src.features.monitoring.service import (
    TransactionMonitor,
    MonitoringConfig,
    ListenerChannel,
    TransactionNotification,
    BlockNotification,
    CosignatureNotification,
    TransactionStatusNotification,
)


class TestMonitoringConfig:
    def test_default_config(self):
        config = MonitoringConfig()
        assert config.reconnect_delay == 5.0
        assert config.max_reconnect_delay == 60.0
        assert config.ping_interval == 30.0
        assert config.connection_timeout == 10.0
        assert config.auto_reconnect is True

    def test_custom_config(self):
        config = MonitoringConfig(
            reconnect_delay=10.0,
            max_reconnect_delay=120.0,
            ping_interval=60.0,
            connection_timeout=20.0,
            auto_reconnect=False,
        )
        assert config.reconnect_delay == 10.0
        assert config.max_reconnect_delay == 120.0
        assert config.ping_interval == 60.0
        assert config.connection_timeout == 20.0
        assert config.auto_reconnect is False


class TestListenerChannel:
    def test_channel_values(self):
        assert ListenerChannel.BLOCK.value == "block"
        assert ListenerChannel.CONFIRMED_ADDED.value == "confirmedAdded"
        assert ListenerChannel.UNCONFIRMED_ADDED.value == "unconfirmedAdded"
        assert ListenerChannel.UNCONFIRMED_REMOVED.value == "unconfirmedRemoved"
        assert ListenerChannel.PARTIAL_ADDED.value == "partialAdded"
        assert ListenerChannel.PARTIAL_REMOVED.value == "partialRemoved"
        assert ListenerChannel.COSIGNATURE.value == "cosignature"
        assert ListenerChannel.MODIFY_MULTISIG_ACCOUNT.value == "modifyMultisigAccount"
        assert ListenerChannel.STATUS.value == "status"
        assert ListenerChannel.FINALIZED_BLOCK.value == "finalizedBlock"


class TestTransactionMonitor:
    def test_build_ws_url_http_to_ws(self):
        monitor = TransactionMonitor("http://sym-test-01.opening-line.jp:3000")
        assert monitor.ws_url == "ws://sym-test-01.opening-line.jp:3001/ws"

    def test_build_ws_url_https_to_wss(self):
        monitor = TransactionMonitor("https://sym-test-01.opening-line.jp:3000")
        assert monitor.ws_url == "wss://sym-test-01.opening-line.jp:3001/ws"

    def test_build_ws_url_already_ws(self):
        monitor = TransactionMonitor("ws://sym-test-01.opening-line.jp:3001")
        assert monitor.ws_url == "ws://sym-test-01.opening-line.jp:3001/ws"

    def test_build_ws_url_already_wss(self):
        monitor = TransactionMonitor("wss://sym-test-01.opening-line.jp:3001")
        assert monitor.ws_url == "wss://sym-test-01.opening-line.jp:3001/ws"

    def test_build_ws_url_trailing_slash(self):
        monitor = TransactionMonitor("http://sym-test-01.opening-line.jp:3000/")
        assert monitor.ws_url == "ws://sym-test-01.opening-line.jp:3001/ws"

    def test_initial_state(self):
        monitor = TransactionMonitor("http://sym-test-01.opening-line.jp:3000")
        assert monitor.is_connected is False
        assert monitor.uid is None

    def test_add_callback(self):
        monitor = TransactionMonitor("http://sym-test-01.opening-line.jp:3000")
        callback_called = []

        def my_callback(data):
            callback_called.append(data)

        monitor.add_callback(ListenerChannel.BLOCK.value, my_callback)
        assert len(monitor._callbacks[ListenerChannel.BLOCK.value]) == 1

    def test_remove_callback(self):
        monitor = TransactionMonitor("http://sym-test-01.opening-line.jp:3000")

        def my_callback(data):
            pass

        monitor.add_callback(ListenerChannel.BLOCK.value, my_callback)
        monitor.remove_callback(ListenerChannel.BLOCK.value, my_callback)
        assert len(monitor._callbacks[ListenerChannel.BLOCK.value]) == 0

    def test_custom_callbacks_in_constructor(self):
        connected_called = []
        disconnected_called = []
        confirmed_called = []

        def on_connected():
            connected_called.append(True)

        def on_disconnected():
            disconnected_called.append(True)

        def on_confirmed(tx):
            confirmed_called.append(tx)

        monitor = TransactionMonitor(
            "http://sym-test-01.opening-line.jp:3000",
            on_connected=on_connected,
            on_disconnected=on_disconnected,
            on_confirmed_transaction=on_confirmed,
        )

        assert len(monitor._callbacks["on_connected"]) == 1
        assert len(monitor._callbacks["on_disconnected"]) == 1
        assert len(monitor._callbacks[ListenerChannel.CONFIRMED_ADDED.value]) == 1


class TestTransactionNotification:
    def test_transaction_notification(self):
        notification = TransactionNotification(
            transaction={
                "type": 16724,
                "mosaics": [{"id": "72C0212E67A08BCE", "amount": "1000000"}],
            },
            meta={"hash": "ABC123"},
            channel=ListenerChannel.CONFIRMED_ADDED,
            address="TBXUTAX6O6EUVPB6X7OBNX6UUXBMPPAFX7KE5TQ",
        )
        assert notification.channel == ListenerChannel.CONFIRMED_ADDED
        assert notification.address == "TBXUTAX6O6EUVPB6X7OBNX6UUXBMPPAFX7KE5TQ"
        assert notification.meta["hash"] == "ABC123"


class TestBlockNotification:
    def test_block_notification(self):
        notification = BlockNotification(
            block={"height": "1000", "timestamp": "12345678"},
            meta={"hash": "BLOCKHASH"},
        )
        assert notification.block["height"] == "1000"
        assert notification.meta["hash"] == "BLOCKHASH"


class TestCosignatureNotification:
    def test_cosignature_notification(self):
        notification = CosignatureNotification(
            parent_hash="ABC123DEF456",
            signature="SIG123",
            signer_public_key="PUBKEY123",
            version=1,
        )
        assert notification.parent_hash == "ABC123DEF456"
        assert notification.signature == "SIG123"
        assert notification.signer_public_key == "PUBKEY123"
        assert notification.version == 1


class TestTransactionStatusNotification:
    def test_transaction_status_notification(self):
        notification = TransactionStatusNotification(
            address="TBXUTAX6O6EUVPB6X7OBNX6UUXBMPPAFX7KE5TQ",
            hash="ABC123",
            code="Success",
            group="confirmed",
        )
        assert notification.address == "TBXUTAX6O6EUVPB6X7OBNX6UUXBMPPAFX7KE5TQ"
        assert notification.hash == "ABC123"
        assert notification.code == "Success"
        assert notification.group == "confirmed"


@pytest.mark.integration
class TestTransactionMonitorIntegration:
    def test_monitor_starts_and_stops(self):
        monitor = TransactionMonitor("http://sym-test-01.opening-line.jp:3000")
        monitor.start()
        assert monitor._running is True
        monitor.stop()
        assert monitor._running is False
        assert monitor.is_connected is False

    def test_subscribe_address_normalization(self):
        monitor = TransactionMonitor("http://sym-test-01.opening-line.jp:3000")
        monitor._uid = "test-uid"
        monitor._connected = True

        address = "tbxutax6o6euvpb6x7obnx6uuxbmppafx7ke5tq"
        monitor.subscribe_address(
            address,
            include_confirmed=True,
            include_unconfirmed=False,
            include_partial=False,
            include_status=False,
            include_cosignature=False,
        )

        normalized = address.upper().replace("-", "")
        assert normalized in monitor._watched_addresses
