"""Connection state monitoring for Symbol Quick Wallet.

This module provides offline/online state detection and notification
for network and node connectivity changes.
"""

import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    NODE_UNREACHABLE = "node_unreachable"
    UNKNOWN = "unknown"


@dataclass
class ConnectionStatus:
    state: ConnectionState = ConnectionState.UNKNOWN
    internet_available: bool = False
    node_reachable: bool = False
    last_check_time: float = 0.0
    last_online_time: float = 0.0
    last_node_reachable_time: float = 0.0
    error_message: str = ""
    consecutive_failures: int = 0


@dataclass
class ConnectionMonitorConfig:
    check_interval_seconds: float = 30.0
    internet_check_hosts: list[str] = field(
        default_factory=lambda: ["8.8.8.8", "1.1.1.1"]
    )
    internet_check_port: int = 53
    internet_check_timeout: float = 3.0
    node_check_timeout: float = 5.0
    failure_threshold: int = 3
    recovery_threshold: int = 1


class ConnectionMonitor:
    def __init__(
        self,
        node_url: str,
        config: ConnectionMonitorConfig | None = None,
        on_state_change: Callable[
            [ConnectionState, ConnectionState, ConnectionStatus], None
        ]
        | None = None,
    ):
        self.node_url = node_url.rstrip("/")
        self.config = config or ConnectionMonitorConfig()
        self.on_state_change = on_state_change
        self._status = ConnectionStatus()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def status(self) -> ConnectionStatus:
        with self._lock:
            return ConnectionStatus(
                state=self._status.state,
                internet_available=self._status.internet_available,
                node_reachable=self._status.node_reachable,
                last_check_time=self._status.last_check_time,
                last_online_time=self._status.last_online_time,
                last_node_reachable_time=self._status.last_node_reachable_time,
                error_message=self._status.error_message,
                consecutive_failures=self._status.consecutive_failures,
            )

    @property
    def is_online(self) -> bool:
        with self._lock:
            return self._status.internet_available

    @property
    def is_node_reachable(self) -> bool:
        with self._lock:
            return self._status.node_reachable

    @property
    def current_state(self) -> ConnectionState:
        with self._lock:
            return self._status.state

    def _determine_state(self) -> ConnectionState:
        if not self._status.internet_available:
            return ConnectionState.OFFLINE
        if not self._status.node_reachable:
            return ConnectionState.NODE_UNREACHABLE
        return ConnectionState.ONLINE

    def check_internet_connection(self) -> bool:
        for host in self.config.internet_check_hosts:
            try:
                socket.setdefaulttimeout(self.config.internet_check_timeout)
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
                    (host, self.config.internet_check_port)
                )
                return True
            except (socket.error, socket.timeout, OSError):
                continue
        return False

    def check_node_connection(self) -> tuple[bool, str]:
        try:
            import requests

            url = f"{self.node_url}/node/health"
            response = requests.get(url, timeout=self.config.node_check_timeout)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", {})
                api_node = status.get("apiNode", "down")
                db_node = status.get("dbNode", "down")
                if api_node == "up":
                    return True, ""
                return False, f"Node unhealthy: apiNode={api_node}, dbNode={db_node}"
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)

    def check_connection(self) -> ConnectionStatus:
        internet_ok = self.check_internet_connection()
        node_ok = False
        error_msg = ""

        if internet_ok:
            node_ok, error_msg = self.check_node_connection()

        with self._lock:
            old_state = self._status.state

            self._status.internet_available = internet_ok
            self._status.node_reachable = node_ok
            self._status.last_check_time = time.time()
            self._status.error_message = error_msg

            if internet_ok:
                self._status.last_online_time = time.time()
                if node_ok:
                    self._status.last_node_reachable_time = time.time()
                    self._status.consecutive_failures = 0
                else:
                    self._status.consecutive_failures += 1
            else:
                self._status.consecutive_failures += 1

            self._status.state = self._determine_state()

            new_state = self._status.state

        if old_state != new_state and self.on_state_change:
            try:
                self.on_state_change(old_state, new_state, self.status)
            except Exception as e:
                logger.error("Error in state change callback: %s", e)

        return self.status

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Connection monitor started")

    def stop(self) -> None:
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
        logger.info("Connection monitor stopped")

    def _monitor_loop(self) -> None:
        self.check_connection()

        while self._running:
            try:
                time.sleep(self.config.check_interval_seconds)
                if self._running:
                    self.check_connection()
            except Exception as e:
                logger.error("Error in connection monitor loop: %s", e)

    def update_node_url(self, node_url: str) -> None:
        with self._lock:
            self.node_url = node_url.rstrip("/")
            self._status.node_reachable = False
            self._status.state = ConnectionState.UNKNOWN
        logger.info("Node URL updated to: %s", node_url)


def get_connection_state_message(state: ConnectionState) -> tuple[str, str]:
    messages = {
        ConnectionState.ONLINE: (
            "Connection restored",
            "You are back online and connected to the node.",
        ),
        ConnectionState.OFFLINE: (
            "Network unavailable",
            "No internet connection detected. Please check your network settings.",
        ),
        ConnectionState.NODE_UNREACHABLE: (
            "Node connection lost",
            "Cannot reach the blockchain node. The node may be down or experiencing issues.",
        ),
        ConnectionState.UNKNOWN: (
            "Connection status unknown",
            "Unable to determine connection status.",
        ),
    }
    return messages.get(state, ("Unknown status", ""))
