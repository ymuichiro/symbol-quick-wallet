"""Unit tests for network timeout and retry logic."""

import pytest
from unittest.mock import Mock, patch
from requests.exceptions import Timeout, ConnectionError, HTTPError

from src.shared.network import (
    NetworkClient,
    NetworkError,
    NetworkErrorType,
    TimeoutConfig,
    RetryConfig,
    classify_error,
    create_network_error,
    should_retry,
    DEFAULT_TIMEOUT_CONFIG,
    DEFAULT_RETRY_CONFIG,
)


class TestTimeoutConfig:
    def test_default_values(self):
        config = TimeoutConfig()
        assert config.connect_timeout == 5.0
        assert config.read_timeout == 15.0
        assert config.operation_timeout == 30.0

    def test_custom_values(self):
        config = TimeoutConfig(
            connect_timeout=10.0,
            read_timeout=30.0,
            operation_timeout=60.0,
        )
        assert config.connect_timeout == 10.0
        assert config.read_timeout == 30.0
        assert config.operation_timeout == 60.0

    def test_request_timeout_tuple(self):
        config = TimeoutConfig(connect_timeout=3.0, read_timeout=10.0)
        assert config.request_timeout == (3.0, 10.0)


class TestRetryConfig:
    def test_default_values(self):
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0

    def test_default_retryable_status_codes(self):
        config = RetryConfig()
        assert 408 in config.retryable_status_codes
        assert 429 in config.retryable_status_codes
        assert 500 in config.retryable_status_codes
        assert 502 in config.retryable_status_codes
        assert 503 in config.retryable_status_codes
        assert 504 in config.retryable_status_codes

    def test_calculate_delay_exponential_growth(self):
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=30.0)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0

    def test_calculate_delay_respects_max_delay(self):
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=10.0)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(5) == 10.0

    def test_custom_values(self):
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=60.0,
            exponential_base=3.0,
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 60.0
        assert config.exponential_base == 3.0


class TestClassifyError:
    def test_classify_timeout(self):
        error = Timeout("Connection timed out")
        assert classify_error(error) == NetworkErrorType.TIMEOUT

    def test_classify_connection_error(self):
        error = ConnectionError("Cannot connect to host")
        assert classify_error(error) == NetworkErrorType.CONNECTION_ERROR

    def test_classify_http_error(self):
        response = Mock()
        response.status_code = 500
        error = HTTPError(response=response)
        assert classify_error(error) == NetworkErrorType.HTTP_ERROR

    def test_classify_unknown_error(self):
        error = ValueError("Some error")
        assert classify_error(error) == NetworkErrorType.UNKNOWN


class TestCreateNetworkError:
    def test_create_timeout_error(self):
        error = Timeout("Connection timed out")
        network_error = create_network_error(error, "http://example.com", "test")
        assert network_error.error_type == NetworkErrorType.TIMEOUT
        assert "timeout" in network_error.message.lower()
        assert "example.com" in network_error.message
        assert network_error.original_error == error

    def test_create_connection_error(self):
        error = ConnectionError("Cannot connect")
        network_error = create_network_error(error, "http://example.com", "fetch")
        assert network_error.error_type == NetworkErrorType.CONNECTION_ERROR
        assert "connect" in network_error.message.lower()
        assert "example.com" in network_error.message

    def test_create_http_error(self):
        response = Mock()
        response.status_code = 500
        response.text = "Internal Server Error"
        error = HTTPError(response=response)
        network_error = create_network_error(error, "http://example.com", "api call")
        assert network_error.error_type == NetworkErrorType.HTTP_ERROR
        assert network_error.status_code == 500
        assert network_error.response_text == "Internal Server Error"
        assert "500" in network_error.message

    def test_create_unknown_error(self):
        error = ValueError("Unknown error")
        network_error = create_network_error(error, "http://example.com")
        assert network_error.error_type == NetworkErrorType.UNKNOWN
        assert "Unknown error" in network_error.message


class TestShouldRetry:
    def test_should_retry_timeout(self):
        config = RetryConfig()
        error = Timeout("Connection timed out")
        assert should_retry(error, config) is True

    def test_should_retry_connection_error(self):
        config = RetryConfig()
        error = ConnectionError("Cannot connect")
        assert should_retry(error, config) is True

    def test_should_retry_http_error_retryable_codes(self):
        config = RetryConfig()
        for status_code in [408, 429, 500, 502, 503, 504]:
            response = Mock()
            response.status_code = status_code
            error = HTTPError(response=response)
            assert should_retry(error, config) is True, f"Should retry on {status_code}"

    def test_should_not_retry_http_error_non_retryable_codes(self):
        config = RetryConfig()
        for status_code in [400, 401, 403, 404, 410]:
            response = Mock()
            response.status_code = status_code
            error = HTTPError(response=response)
            assert should_retry(error, config) is False, (
                f"Should not retry on {status_code}"
            )

    def test_should_not_retry_unknown_errors(self):
        config = RetryConfig()
        error = ValueError("Unknown error")
        assert should_retry(error, config) is False


class TestNetworkClient:
    def test_init_default_config(self):
        client = NetworkClient("http://example.com")
        assert client.node_url == "http://example.com"
        assert client.timeout_config == DEFAULT_TIMEOUT_CONFIG
        assert client.retry_config == DEFAULT_RETRY_CONFIG

    def test_init_custom_config(self):
        timeout_config = TimeoutConfig(connect_timeout=2.0, read_timeout=5.0)
        retry_config = RetryConfig(max_retries=5, base_delay=0.5)
        client = NetworkClient(
            "http://example.com",
            timeout_config=timeout_config,
            retry_config=retry_config,
        )
        assert client.timeout_config == timeout_config
        assert client.retry_config == retry_config

    def test_init_strips_trailing_slash(self):
        client = NetworkClient("http://example.com/")
        assert client.node_url == "http://example.com"

    def test_on_retry_callback_called(self):
        retry_calls = []

        def on_retry(attempt, error, delay):
            retry_calls.append((attempt, str(error), delay))

        config = RetryConfig(max_retries=2, base_delay=0.01)
        client = NetworkClient(
            "http://example.com",
            retry_config=config,
            on_retry=on_retry,
        )

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Timeout("Timeout")
            with pytest.raises(NetworkError):
                client.get("/test")

        assert len(retry_calls) == 2
        assert retry_calls[0][0] == 1
        assert retry_calls[1][0] == 2

    def test_get_success(self):
        client = NetworkClient("http://example.com")

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_get.return_value = mock_response

            result = client.get("/endpoint")
            assert result == {"data": "test"}
            mock_get.assert_called_once()

    def test_get_404_raises_http_error(self):
        client = NetworkClient("http://example.com")

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = HTTPError(
                response=mock_response
            )
            mock_get.return_value = mock_response

            with pytest.raises(NetworkError) as exc_info:
                client.get("/endpoint")

            assert exc_info.value.error_type == NetworkErrorType.HTTP_ERROR

    def test_get_optional_returns_none_on_404(self):
        client = NetworkClient("http://example.com")

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = client.get_optional("/endpoint")
            assert result is None

    def test_retry_on_timeout(self):
        client = NetworkClient(
            "http://example.com",
            retry_config=RetryConfig(max_retries=2, base_delay=0.01),
        )

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Timeout("Timeout")
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            return mock_response

        with patch("requests.get", side_effect=mock_get):
            result = client.get("/endpoint")
            assert result == {"success": True}
            assert call_count == 3

    def test_retry_on_connection_error(self):
        client = NetworkClient(
            "http://example.com",
            retry_config=RetryConfig(max_retries=2, base_delay=0.01),
        )

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Cannot connect")
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            return mock_response

        with patch("requests.get", side_effect=mock_get):
            result = client.get("/endpoint")
            assert result == {"success": True}
            assert call_count == 2

    def test_max_retries_exceeded_raises_network_error(self):
        client = NetworkClient(
            "http://example.com",
            retry_config=RetryConfig(max_retries=2, base_delay=0.01),
        )

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Timeout("Always timeout")

            with pytest.raises(NetworkError) as exc_info:
                client.get("/endpoint")

            assert exc_info.value.error_type == NetworkErrorType.TIMEOUT

    def test_post_success(self):
        client = NetworkClient("http://example.com")

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"created": True}
            mock_post.return_value = mock_response

            result = client.post("/endpoint", json={"key": "value"})
            assert result == {"created": True}
            mock_post.assert_called_once()

    def test_put_success(self):
        client = NetworkClient("http://example.com")

        with patch("requests.put") as mock_put:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"updated": True}
            mock_put.return_value = mock_response

            result = client.put("/endpoint", data={"key": "value"})
            assert result == {"updated": True}

    def test_put_with_text_response(self):
        client = NetworkClient("http://example.com")

        with patch("requests.put") as mock_put:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b"OK"
            mock_response.text = "OK"
            mock_response.json.side_effect = ValueError()
            mock_put.return_value = mock_response

            result = client.put("/endpoint")
            assert result == {"message": "OK"}

    def test_timeout_config_applied(self):
        timeout_config = TimeoutConfig(connect_timeout=3.0, read_timeout=10.0)
        client = NetworkClient(
            "http://example.com",
            timeout_config=timeout_config,
        )

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_get.return_value = mock_response

            client.get("/endpoint")

            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["timeout"] == (3.0, 10.0)


class TestNetworkError:
    def test_str_representation(self):
        error = NetworkError(
            error_type=NetworkErrorType.TIMEOUT,
            message="Connection timeout",
        )
        assert str(error) == "Connection timeout"

    def test_with_original_error(self):
        original = Timeout("Original timeout")
        error = NetworkError(
            error_type=NetworkErrorType.TIMEOUT,
            message="Connection timeout",
            original_error=original,
        )
        assert error.original_error == original

    def test_with_http_details(self):
        error = NetworkError(
            error_type=NetworkErrorType.HTTP_ERROR,
            message="Server error",
            status_code=500,
            response_text="Internal Server Error",
        )
        assert error.status_code == 500
        assert error.response_text == "Internal Server Error"
