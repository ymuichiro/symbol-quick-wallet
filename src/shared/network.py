"""Network utilities for Symbol Quick Wallet with timeout handling and retry logic."""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout

logger = logging.getLogger(__name__)

T = TypeVar("T")


class NetworkErrorType(Enum):
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    UNKNOWN = "unknown"


@dataclass
class NetworkError(Exception):
    error_type: NetworkErrorType
    message: str
    original_error: Exception | None = None
    status_code: int | None = None
    response_text: str | None = None

    def __str__(self) -> str:
        return self.message


@dataclass
class TimeoutConfig:
    connect_timeout: float = 5.0
    read_timeout: float = 15.0
    operation_timeout: float = 30.0

    @property
    def request_timeout(self) -> tuple[float, float]:
        return (self.connect_timeout, self.read_timeout)


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    retryable_status_codes: set[int] = field(
        default_factory=lambda: {408, 429, 500, 502, 503, 504}
    )

    def calculate_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.exponential_base**attempt)
        return min(delay, self.max_delay)


DEFAULT_TIMEOUT_CONFIG = TimeoutConfig()
DEFAULT_RETRY_CONFIG = RetryConfig()


def classify_error(error: Exception) -> NetworkErrorType:
    if isinstance(error, Timeout):
        return NetworkErrorType.TIMEOUT
    elif isinstance(error, ConnectionError):
        return NetworkErrorType.CONNECTION_ERROR
    elif isinstance(error, HTTPError):
        return NetworkErrorType.HTTP_ERROR
    return NetworkErrorType.UNKNOWN


def create_network_error(
    error: Exception, node_url: str, context: str = ""
) -> NetworkError:
    error_type = classify_error(error)
    context_prefix = f"{context}: " if context else ""

    if error_type == NetworkErrorType.TIMEOUT:
        message = (
            f"{context_prefix}Connection timeout. Node may be unavailable: {node_url}"
        )
    elif error_type == NetworkErrorType.CONNECTION_ERROR:
        message = (
            f"{context_prefix}Cannot connect to node: {node_url}. "
            "Check your network connection."
        )
    elif error_type == NetworkErrorType.HTTP_ERROR:
        status_code = getattr(error.response, "status_code", None)
        response_text = getattr(error.response, "text", None)
        message = f"{context_prefix}HTTP error {status_code}: {response_text or 'Unknown error'}"
        return NetworkError(
            error_type=error_type,
            message=message,
            original_error=error,
            status_code=status_code,
            response_text=response_text,
        )
    else:
        message = f"{context_prefix}Network error: {str(error)}"

    return NetworkError(
        error_type=error_type,
        message=message,
        original_error=error,
    )


def should_retry(error: Exception, retry_config: RetryConfig) -> bool:
    if isinstance(error, Timeout):
        return True
    if isinstance(error, ConnectionError):
        return True
    if isinstance(error, HTTPError):
        status_code = getattr(error.response, "status_code", None)
        if status_code and status_code in retry_config.retryable_status_codes:
            return True
    return False


class NetworkClient:
    def __init__(
        self,
        node_url: str,
        timeout_config: TimeoutConfig | None = None,
        retry_config: RetryConfig | None = None,
        on_retry: Callable[[int, Exception, float], None] | None = None,
    ):
        self.node_url = node_url.rstrip("/")
        self.timeout_config = timeout_config or DEFAULT_TIMEOUT_CONFIG
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self.on_retry = on_retry

    def _execute_with_retry(
        self,
        operation: Callable[[], T],
        context: str = "",
    ) -> T:
        last_error: Exception | None = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                return operation()
            except Exception as e:
                last_error = e

                if attempt < self.retry_config.max_retries and should_retry(
                    e, self.retry_config
                ):
                    delay = self.retry_config.calculate_delay(attempt)
                    logger.warning(
                        "Network operation failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        self.retry_config.max_retries + 1,
                        delay,
                        str(e),
                    )

                    if self.on_retry:
                        self.on_retry(attempt + 1, e, delay)

                    time.sleep(delay)
                else:
                    break

        raise create_network_error(
            last_error or Exception("Unknown error"), self.node_url, context
        )

    def get(
        self,
        endpoint: str,
        context: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        url = f"{self.node_url}{endpoint}"
        timeout = kwargs.pop("timeout", self.timeout_config.request_timeout)

        def operation() -> dict[str, Any]:
            response = requests.get(url, timeout=timeout, **kwargs)
            if response.status_code == 404:
                raise HTTPError(response=response)
            response.raise_for_status()
            return response.json()

        return self._execute_with_retry(operation, context)

    def get_optional(
        self,
        endpoint: str,
        context: str = "",
        **kwargs,
    ) -> dict[str, Any] | None:
        url = f"{self.node_url}{endpoint}"
        timeout = kwargs.pop("timeout", self.timeout_config.request_timeout)

        def operation() -> dict[str, Any] | None:
            response = requests.get(url, timeout=timeout, **kwargs)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

        return self._execute_with_retry(operation, context)

    def put(
        self,
        endpoint: str,
        context: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        url = f"{self.node_url}{endpoint}"
        timeout = kwargs.pop("timeout", self.timeout_config.request_timeout)

        def operation() -> dict[str, Any]:
            response = requests.put(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            if response.content:
                try:
                    return response.json()
                except ValueError:
                    return {"message": response.text}
            return {"message": ""}

        return self._execute_with_retry(operation, context)

    def post(
        self,
        endpoint: str,
        context: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        url = f"{self.node_url}{endpoint}"
        timeout = kwargs.pop("timeout", self.timeout_config.request_timeout)

        def operation() -> dict[str, Any]:
            response = requests.post(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response.json()

        return self._execute_with_retry(operation, context)

    def test_connection(self) -> dict[str, Any]:
        health_data = self.get("/node/health", context="Node health check")
        network_data = self.get("/node/info", context="Node info fetch")

        status = health_data.get("status", {})
        api_node = status.get("apiNode", "down")
        db_node = status.get("dbNode", "down")
        is_healthy = api_node == "up"
        network_height = network_data.get("networkHeight", 0)

        logger.info(
            "Node connection test: %s - Healthy: %s, Height: %s",
            self.node_url,
            is_healthy,
            network_height,
        )

        return {
            "healthy": is_healthy,
            "apiNode": api_node,
            "dbNode": db_node,
            "networkHeight": network_height,
            "url": self.node_url,
        }
