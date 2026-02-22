"""Centralized logging configuration for Symbol Quick Wallet.

This module provides:
- Configurable log levels (DEBUG for dev, INFO for prod)
- Sensitive data sanitization (private keys, passwords)
- User-friendly error message mapping
- Structured logging with context fields
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LoggingConfig:
    log_level: LogLevel = LogLevel.INFO
    log_to_file: bool = True
    log_to_stdout: bool = False
    log_dir: Path | None = None
    log_filename: str = "wallet.log"
    sanitize_sensitive: bool = True
    include_context: bool = True

    @classmethod
    def from_environment(cls) -> "LoggingConfig":
        env_level = os.getenv("SYMBOL_WALLET_LOG_LEVEL", "INFO").upper()
        try:
            log_level = LogLevel(env_level)
        except ValueError:
            log_level = LogLevel.INFO

        log_to_stdout = os.getenv("SYMBOL_WALLET_LOG_STDOUT", "").lower() in (
            "1",
            "true",
            "yes",
        )

        return cls(
            log_level=log_level,
            log_to_stdout=log_to_stdout,
        )


SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(private[_-]?key['\"]?\s*[:=]\s*['\"]?)([A-Fa-f0-9]{64})",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(encrypted[_-]?private[_-]?key['\"]?\s*[:=]\s*['\"]?)([A-Za-z0-9+/=]{20,})",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(password['\"]?\s*[:=]\s*['\"]?)([^\s'\"]+)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"\b[A-Fa-f0-9]{64}\b"),
        "[KEY_REDACTED]",
    ),
]

ADDRESS_PATTERN = re.compile(r"\b[TN][A-Z0-9]{38,39}\b", re.IGNORECASE)


def sanitize_message(message: str, preserve_addresses: bool = True) -> str:
    if not message:
        return message

    sanitized = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    if not preserve_addresses and ADDRESS_PATTERN.search(sanitized):
        sanitized = ADDRESS_PATTERN.sub("[ADDRESS_REDACTED]", sanitized)

    return sanitized


def sanitize_dict(
    data: dict[str, Any], preserve_addresses: bool = True
) -> dict[str, Any]:
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(
            sensitive in key_lower
            for sensitive in ["private_key", "privatekey", "password", "secret"]
        ):
            result[key] = "[REDACTED]"
        elif isinstance(value, str):
            result[key] = sanitize_message(value, preserve_addresses)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, preserve_addresses)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, preserve_addresses)
                if isinstance(item, dict)
                else sanitize_message(str(item), preserve_addresses)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result


@dataclass
class ErrorMapping:
    error_pattern: str
    user_message: str
    log_level: LogLevel = LogLevel.ERROR
    suggest_action: str | None = None


ERROR_MAPPINGS: list[ErrorMapping] = [
    ErrorMapping(
        error_pattern="timeout|timed out",
        user_message="Connection timed out. The server may be slow or unavailable.",
        log_level=LogLevel.WARNING,
        suggest_action="Try again later or check your network connection.",
    ),
    ErrorMapping(
        error_pattern="connection refused|cannot connect|connection error",
        user_message="Unable to connect to the server.",
        log_level=LogLevel.WARNING,
        suggest_action="Check your internet connection and try again.",
    ),
    ErrorMapping(
        error_pattern="insufficient_balance|insufficient funds|not enough balance",
        user_message="Insufficient balance for this transaction.",
        log_level=LogLevel.WARNING,
        suggest_action="Ensure you have enough XYM for the transfer and fees.",
    ),
    ErrorMapping(
        error_pattern="invalid.*address|address.*invalid",
        user_message="The address provided is not valid.",
        log_level=LogLevel.WARNING,
        suggest_action="Please check the recipient address format.",
    ),
    ErrorMapping(
        error_pattern="invalid.*key|key.*invalid|invalid.*private",
        user_message="The provided key is not valid.",
        log_level=LogLevel.WARNING,
        suggest_action="Please verify the key format and try again.",
    ),
    ErrorMapping(
        error_pattern="unauthorized|forbidden|401|403",
        user_message="Access denied. Authentication failed.",
        log_level=LogLevel.WARNING,
        suggest_action="Check your credentials and permissions.",
    ),
    ErrorMapping(
        error_pattern="not found|404",
        user_message="The requested resource was not found.",
        log_level=LogLevel.WARNING,
        suggest_action="The item may have been deleted or never existed.",
    ),
    ErrorMapping(
        error_pattern="rate limit|too many requests|429",
        user_message="Too many requests. Please slow down.",
        log_level=LogLevel.WARNING,
        suggest_action="Wait a moment and try again.",
    ),
    ErrorMapping(
        error_pattern="network.*error|networkerror",
        user_message="A network error occurred.",
        log_level=LogLevel.WARNING,
        suggest_action="Check your internet connection.",
    ),
    ErrorMapping(
        error_pattern="signature.*invalid|invalid.*signature",
        user_message="Transaction signature verification failed.",
        log_level=LogLevel.ERROR,
        suggest_action="The transaction may have been tampered with.",
    ),
    ErrorMapping(
        error_pattern="deadline.*expired|expired.*deadline",
        user_message="Transaction deadline has expired.",
        log_level=LogLevel.WARNING,
        suggest_action="Create a new transaction with a fresh deadline.",
    ),
    ErrorMapping(
        error_pattern="insufficient fee|fee.*too low",
        user_message="Transaction fee is too low.",
        log_level=LogLevel.WARNING,
        suggest_action="Increase the fee multiplier and try again.",
    ),
]


def get_user_friendly_error(error: Exception | str) -> tuple[str, str | None]:
    error_message = str(error) if isinstance(error, Exception) else error
    error_lower = error_message.lower()

    for mapping in ERROR_MAPPINGS:
        if re.search(mapping.error_pattern, error_lower):
            return mapping.user_message, mapping.suggest_action

    return "An unexpected error occurred.", None


class StructuredFormatter(logging.Formatter):
    def __init__(
        self,
        sanitize: bool = True,
        include_context: bool = True,
        preserve_addresses: bool = True,
    ):
        super().__init__()
        self.sanitize = sanitize
        self.include_context = include_context
        self.preserve_addresses = preserve_addresses

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self.include_context:
            log_data["module"] = record.module
            log_data["function"] = record.funcName
            log_data["line"] = record.lineno

        extra_data = getattr(record, "context", None)
        if extra_data and isinstance(extra_data, dict):
            if self.sanitize:
                extra_data = sanitize_dict(extra_data, self.preserve_addresses)
            log_data["context"] = extra_data

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            if self.sanitize:
                exc_text = sanitize_message(exc_text, self.preserve_addresses)
            log_data["exception"] = exc_text

        if self.sanitize:
            log_data["message"] = sanitize_message(
                log_data["message"], self.preserve_addresses
            )

        try:
            return json.dumps(log_data)
        except (TypeError, ValueError):
            return f"{log_data['timestamp']} - {log_data['logger']} - {log_data['level']} - {log_data['message']}"


class HumanReadableFormatter(logging.Formatter):
    def __init__(
        self,
        sanitize: bool = True,
        preserve_addresses: bool = True,
    ):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.sanitize = sanitize
        self.preserve_addresses = preserve_addresses

    def format(self, record: logging.LogRecord) -> str:
        if self.sanitize and record.msg:
            record.msg = sanitize_message(str(record.msg), self.preserve_addresses)
            if record.args:
                sanitized_args = tuple(
                    sanitize_message(str(arg), self.preserve_addresses)
                    if isinstance(arg, str)
                    else arg
                    for arg in record.args
                )
                record.args = sanitized_args

        return super().format(record)


class ContextAdapter(logging.LoggerAdapter):
    def __init__(
        self,
        logger: logging.Logger,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(logger, context or {})

    def process(
        self,
        msg: str,
        kwargs: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra", {})
        if self.extra:
            extra = {**self.extra, **extra}
        kwargs["extra"] = extra
        return msg, kwargs

    def with_context(self, **kwargs: Any) -> "ContextAdapter":
        new_context = {**self.extra, **kwargs}
        return ContextAdapter(self.logger, new_context)


_logging_initialized = False


def setup_logging(config: LoggingConfig | None = None) -> None:
    global _logging_initialized

    if _logging_initialized:
        return

    if config is None:
        config = LoggingConfig.from_environment()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level.value))

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    log_format = (
        "json"
        if os.getenv("SYMBOL_WALLET_LOG_FORMAT", "human").lower() == "json"
        else "human"
    )

    handlers: list[logging.Handler] = []

    if config.log_to_file:
        if config.log_dir is None:
            config.log_dir = Path.home() / ".symbol-quick-wallet"
        config.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = config.log_dir / config.log_filename

        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        if log_format == "json":
            file_handler.setFormatter(
                StructuredFormatter(
                    sanitize=config.sanitize_sensitive,
                    include_context=config.include_context,
                )
            )
        else:
            file_handler.setFormatter(
                HumanReadableFormatter(sanitize=config.sanitize_sensitive)
            )
        handlers.append(file_handler)

    if config.log_to_stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        if log_format == "json":
            stdout_handler.setFormatter(
                StructuredFormatter(
                    sanitize=config.sanitize_sensitive,
                    include_context=config.include_context,
                )
            )
        else:
            stdout_handler.setFormatter(
                HumanReadableFormatter(sanitize=config.sanitize_sensitive)
            )
        handlers.append(stdout_handler)

    for handler in handlers:
        root_logger.addHandler(handler)

    _logging_initialized = True


def get_logger(
    name: str,
    context: dict[str, Any] | None = None,
) -> ContextAdapter:
    if not _logging_initialized:
        setup_logging()

    logger = logging.getLogger(name)
    return ContextAdapter(logger, context)


def log_with_context(
    logger: logging.Logger | ContextAdapter,
    level: int,
    message: str,
    **context: Any,
) -> None:
    if isinstance(logger, ContextAdapter):
        adapter = logger.with_context(**context)
        adapter.log(level, message)
    else:
        logger.log(level, message, extra={"context": context})


def format_error_for_user(error: Exception | str) -> str:
    user_message, suggestion = get_user_friendly_error(error)
    if suggestion:
        return f"{user_message} {suggestion}"
    return user_message


__all__ = [
    "LogLevel",
    "LoggingConfig",
    "ContextAdapter",
    "StructuredFormatter",
    "HumanReadableFormatter",
    "sanitize_message",
    "sanitize_dict",
    "get_user_friendly_error",
    "setup_logging",
    "get_logger",
    "log_with_context",
    "format_error_for_user",
]
