"""Real-time transaction monitoring via WebSocket for Symbol Quick Wallet.

This module provides WebSocket-based monitoring for:
- Incoming confirmed/unconfirmed transactions to watched addresses
- Block finalization notifications
- Cosignature requests (partial/aggregate bonded transactions)
- Transaction status updates
"""

import json
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

import websocket

logger = logging.getLogger(__name__)


class ListenerChannel(Enum):
    BLOCK = "block"
    CONFIRMED_ADDED = "confirmedAdded"
    UNCONFIRMED_ADDED = "unconfirmedAdded"
    UNCONFIRMED_REMOVED = "unconfirmedRemoved"
    PARTIAL_ADDED = "partialAdded"
    PARTIAL_REMOVED = "partialRemoved"
    COSIGNATURE = "cosignature"
    MODIFY_MULTISIG_ACCOUNT = "modifyMultisigAccount"
    STATUS = "status"
    FINALIZED_BLOCK = "finalizedBlock"


@dataclass
class TransactionNotification:
    transaction: dict[str, Any]
    meta: dict[str, Any]
    channel: ListenerChannel
    address: str | None = None


@dataclass
class BlockNotification:
    block: dict[str, Any]
    meta: dict[str, Any]


@dataclass
class CosignatureNotification:
    parent_hash: str
    signature: str
    signer_public_key: str
    version: int


@dataclass
class TransactionStatusNotification:
    address: str
    hash: str
    code: str
    group: str


@dataclass
class MonitoringConfig:
    reconnect_delay: float = 5.0
    max_reconnect_delay: float = 60.0
    ping_interval: float = 30.0
    connection_timeout: float = 10.0
    auto_reconnect: bool = True


class TransactionMonitor:
    DEFAULT_WS_PORT = 3001

    def __init__(
        self,
        node_url: str,
        config: MonitoringConfig | None = None,
        on_connected: Callable[[], None] | None = None,
        on_disconnected: Callable[[], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_confirmed_transaction: Callable[[TransactionNotification], None]
        | None = None,
        on_unconfirmed_transaction: Callable[[TransactionNotification], None]
        | None = None,
        on_partial_transaction: Callable[[TransactionNotification], None] | None = None,
        on_block: Callable[[BlockNotification], None] | None = None,
        on_finalized_block: Callable[[BlockNotification], None] | None = None,
        on_cosignature: Callable[[CosignatureNotification], None] | None = None,
        on_transaction_status: Callable[[TransactionStatusNotification], None]
        | None = None,
    ):
        self.node_url = node_url.rstrip("/")
        self.ws_url = self._build_ws_url(node_url)
        self.config = config or MonitoringConfig()

        self._callbacks: dict[str, list[Callable[[Any], None]]] = {
            "on_connected": [on_connected] if on_connected else [],
            "on_disconnected": [on_disconnected] if on_disconnected else [],
            "on_error": [on_error] if on_error else [],
            ListenerChannel.CONFIRMED_ADDED.value: [on_confirmed_transaction]
            if on_confirmed_transaction
            else [],
            ListenerChannel.UNCONFIRMED_ADDED.value: [on_unconfirmed_transaction]
            if on_unconfirmed_transaction
            else [],
            ListenerChannel.PARTIAL_ADDED.value: [on_partial_transaction]
            if on_partial_transaction
            else [],
            ListenerChannel.BLOCK.value: [on_block] if on_block else [],
            ListenerChannel.FINALIZED_BLOCK.value: [on_finalized_block]
            if on_finalized_block
            else [],
            ListenerChannel.COSIGNATURE.value: [on_cosignature]
            if on_cosignature
            else [],
            ListenerChannel.STATUS.value: [on_transaction_status]
            if on_transaction_status
            else [],
        }

        self._uid: str | None = None
        self._ws: websocket.WebSocketApp | None = None
        self._running = False
        self._connected = False
        self._reconnect_delay = self.config.reconnect_delay
        self._subscribed_channels: set[str] = set()
        self._watched_addresses: set[str] = set()
        self._lock = threading.Lock()
        self._ws_thread: threading.Thread | None = None
        self._ping_thread: threading.Thread | None = None

    def _build_ws_url(self, node_url: str) -> str:
        url = node_url.rstrip("/")
        if url.startswith("https://"):
            url = url.replace("https://", "wss://")
        elif url.startswith("http://"):
            url = url.replace("http://", "ws://")

        if ":3000" in url:
            url = url.replace(":3000", f":{self.DEFAULT_WS_PORT}")
        elif not any(port in url for port in [":3001", ":3002"]):
            if url.startswith("ws://"):
                url = url.replace("ws://", f"ws://{self.DEFAULT_WS_PORT}")
            elif url.startswith("wss://"):
                url = url.replace("wss://", f"wss://{self.DEFAULT_WS_PORT}")

        return f"{url}/ws"

    def add_callback(self, event_type: str, callback: Callable[[Any], None]) -> None:
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def remove_callback(self, event_type: str, callback: Callable[[Any], None]) -> None:
        if event_type in self._callbacks:
            try:
                self._callbacks[event_type].remove(callback)
            except ValueError:
                pass

    def _invoke_callbacks(self, event_type: str, data: Any) -> None:
        callbacks = self._callbacks.get(event_type, [])
        for callback in callbacks:
            if callback is None:
                continue
            try:
                callback(data)
            except Exception as e:
                logger.error("Error in callback for %s: %s", event_type, e)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def uid(self) -> str | None:
        return self._uid

    def _on_ws_message(self, ws, message: str) -> None:
        try:
            data = json.loads(message)

            if "uid" in data:
                self._uid = data["uid"]
                self._connected = True
                self._reconnect_delay = self.config.reconnect_delay
                logger.info("WebSocket connected, uid=%s", self._uid)
                self._resubscribe_channels()
                self._invoke_callbacks("on_connected", None)
                return

            topic = data.get("topic", "")
            payload = data.get("data", {})

            self._handle_message(topic, payload)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse WebSocket message: %s", e)
        except Exception as e:
            logger.error("Error handling WebSocket message: %s", e)

    def _handle_message(self, topic: str, payload: dict[str, Any]) -> None:
        if "/" in topic:
            channel_name, address = topic.split("/", 1)
        else:
            channel_name = topic
            address = None

        try:
            channel = ListenerChannel(channel_name)
        except ValueError:
            logger.debug("Unknown channel: %s", channel_name)
            return

        if channel in (
            ListenerChannel.CONFIRMED_ADDED,
            ListenerChannel.UNCONFIRMED_ADDED,
            ListenerChannel.PARTIAL_ADDED,
        ):
            notification = TransactionNotification(
                transaction=payload.get("transaction", {}),
                meta=payload.get("meta", {}),
                channel=channel,
                address=address,
            )
            self._invoke_callbacks(channel.value, notification)

        elif channel == ListenerChannel.BLOCK:
            notification = BlockNotification(
                block=payload.get("block", {}),
                meta=payload.get("meta", {}),
            )
            self._invoke_callbacks(channel.value, notification)

        elif channel == ListenerChannel.FINALIZED_BLOCK:
            notification = BlockNotification(
                block=payload.get("block", payload),
                meta=payload.get("meta", {}),
            )
            self._invoke_callbacks(channel.value, notification)

        elif channel == ListenerChannel.COSIGNATURE:
            notification = CosignatureNotification(
                parent_hash=payload.get("parentHash", ""),
                signature=payload.get("signature", ""),
                signer_public_key=payload.get("signerPublicKey", ""),
                version=payload.get("version", 0),
            )
            self._invoke_callbacks(channel.value, notification)

        elif channel == ListenerChannel.STATUS:
            notification = TransactionStatusNotification(
                address=payload.get("address", ""),
                hash=payload.get("hash", ""),
                code=payload.get("code", ""),
                group=payload.get("group", ""),
            )
            self._invoke_callbacks(channel.value, notification)

    def _on_ws_error(self, ws, error) -> None:
        logger.error("WebSocket error: %s", error)
        self._invoke_callbacks("on_error", error)

    def _on_ws_close(self, ws, close_status_code, close_msg) -> None:
        logger.info("WebSocket closed: code=%s, msg=%s", close_status_code, close_msg)
        self._connected = False
        self._uid = None
        self._invoke_callbacks("on_disconnected", None)

        if self._running and self.config.auto_reconnect:
            self._schedule_reconnect()

    def _on_ws_open(self, ws) -> None:
        logger.info("WebSocket connection opened to %s", self.ws_url)

    def _schedule_reconnect(self) -> None:
        logger.info("Scheduling reconnect in %.1f seconds", self._reconnect_delay)
        time.sleep(self._reconnect_delay)
        self._reconnect_delay = min(
            self._reconnect_delay * 2, self.config.max_reconnect_delay
        )

        if self._running and not self._connected:
            logger.info("Attempting to reconnect...")
            self._connect_internal()

    def _connect_internal(self) -> None:
        try:
            self._ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
                on_open=self._on_ws_open,
            )
            self._ws.run_forever()
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)
            if self._running and self.config.auto_reconnect:
                self._schedule_reconnect()

    def _ping_loop(self) -> None:
        while self._running:
            time.sleep(self.config.ping_interval)
            if self._connected and self._ws:
                try:
                    self._ws.send(
                        json.dumps(
                            {"uid": self._uid, "subscribe": ListenerChannel.BLOCK.value}
                        )
                    )
                except Exception as e:
                    logger.debug("Ping failed: %s", e)

    def _resubscribe_channels(self) -> None:
        with self._lock:
            channels_to_subscribe = list(self._subscribed_channels)
            addresses_to_watch = list(self._watched_addresses)

        if self._uid is None:
            return

        for channel in channels_to_subscribe:
            self._send_subscribe(channel)

        for address in addresses_to_watch:
            self.subscribe_address(address)

    def _send_subscribe(self, channel: str) -> bool:
        if not self._uid or not self._ws:
            logger.warning("Cannot subscribe: not connected")
            return False

        try:
            message = json.dumps({"uid": self._uid, "subscribe": channel})
            self._ws.send(message)
            with self._lock:
                self._subscribed_channels.add(channel)
            logger.debug("Subscribed to channel: %s", channel)
            return True
        except Exception as e:
            logger.error("Failed to subscribe to %s: %s", channel, e)
            return False

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._ws_thread = threading.Thread(target=self._connect_internal, daemon=True)
        self._ws_thread.start()

        self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._ping_thread.start()

        logger.info("Transaction monitor started for %s", self.ws_url)

    def stop(self) -> None:
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self._connected = False
        self._uid = None
        logger.info("Transaction monitor stopped")

    def subscribe_block(self) -> bool:
        return self._send_subscribe(ListenerChannel.BLOCK.value)

    def subscribe_finalized_block(self) -> bool:
        return self._send_subscribe(ListenerChannel.FINALIZED_BLOCK.value)

    def subscribe_address(
        self,
        address: str,
        include_confirmed: bool = True,
        include_unconfirmed: bool = True,
        include_partial: bool = True,
        include_status: bool = True,
        include_cosignature: bool = True,
    ) -> bool:
        normalized_address = address.replace("-", "").upper()
        success = True

        with self._lock:
            self._watched_addresses.add(normalized_address)

        if include_confirmed:
            channel = f"{ListenerChannel.CONFIRMED_ADDED.value}/{normalized_address}"
            if not self._send_subscribe(channel):
                success = False

        if include_unconfirmed:
            channel = f"{ListenerChannel.UNCONFIRMED_ADDED.value}/{normalized_address}"
            if not self._send_subscribe(channel):
                success = False

        if include_partial:
            channel = f"{ListenerChannel.PARTIAL_ADDED.value}/{normalized_address}"
            if not self._send_subscribe(channel):
                success = False

        if include_status:
            channel = f"{ListenerChannel.STATUS.value}/{normalized_address}"
            if not self._send_subscribe(channel):
                success = False

        if include_cosignature:
            channel = f"{ListenerChannel.COSIGNATURE.value}/{normalized_address}"
            if not self._send_subscribe(channel):
                success = False

        logger.info(
            "Subscribed to address: %s (success=%s)", normalized_address, success
        )
        return success

    def unsubscribe_address(self, address: str) -> None:
        normalized_address = address.replace("-", "").upper()
        with self._lock:
            self._watched_addresses.discard(normalized_address)

    def update_node_url(self, node_url: str) -> None:
        was_running = self._running
        watched_addresses = list(self._watched_addresses)

        self.stop()

        self.node_url = node_url.rstrip("/")
        self.ws_url = self._build_ws_url(node_url)
        self._subscribed_channels.clear()

        if was_running:
            self.start()
            for _ in range(10):
                if self._connected:
                    break
                time.sleep(0.5)

            for addr in watched_addresses:
                self.subscribe_address(addr)

        logger.info("Node URL updated to: %s (ws: %s)", node_url, self.ws_url)

    def wait_for_connection(self, timeout_seconds: float = 10.0) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self._connected and self._uid:
                return True
            time.sleep(0.1)
        return False
