"""Namespace validation utilities for Symbol Quick Wallet."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    is_valid: bool
    error_message: str | None = None
    normalized_value: Any = None


NAMESPACE_PATTERN = re.compile(r"^[a-z0-9_\-]+$")
MAX_NAMESPACE_LENGTH = 64
MIN_ROOT_DURATION_BLOCKS = 25920
MAX_ROOT_DURATION_BLOCKS = 1576800


class NamespaceValidator:
    VALID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_-")

    @classmethod
    def validate_name(cls, name: str) -> ValidationResult:
        if not name or not name.strip():
            return ValidationResult(
                is_valid=False, error_message="Namespace name is required"
            )

        normalized = name.strip().lower()

        if len(normalized) > MAX_NAMESPACE_LENGTH:
            return ValidationResult(
                is_valid=False,
                error_message=f"Namespace name exceeds {MAX_NAMESPACE_LENGTH} characters",
            )

        if not NAMESPACE_PATTERN.match(normalized):
            return ValidationResult(
                is_valid=False,
                error_message="Namespace can only contain a-z, 0-9, _, and -",
            )

        if normalized.startswith("-") or normalized.endswith("-"):
            return ValidationResult(
                is_valid=False,
                error_message="Namespace cannot start or end with a hyphen",
            )

        return ValidationResult(is_valid=True, normalized_value=normalized)

    @classmethod
    def validate_full_name(cls, full_name: str) -> ValidationResult:
        if not full_name or not full_name.strip():
            return ValidationResult(
                is_valid=False, error_message="Namespace name is required"
            )

        parts = full_name.strip().lower().split(".")
        if len(parts) > 3:
            return ValidationResult(
                is_valid=False,
                error_message="Namespace can have at most 3 levels (root.sub.sub)",
            )

        for part in parts:
            result = cls.validate_name(part)
            if not result.is_valid:
                return result

        return ValidationResult(is_valid=True, normalized_value=".".join(parts))

    @classmethod
    def validate_duration(cls, duration_days: int) -> ValidationResult:
        if duration_days < 30:
            return ValidationResult(
                is_valid=False,
                error_message="Minimum rental duration is 30 days",
            )

        if duration_days > 1825:
            return ValidationResult(
                is_valid=False,
                error_message="Maximum rental duration is 1825 days (5 years)",
            )

        duration_blocks = int(duration_days * 24 * 60 * 60 / 30)
        return ValidationResult(is_valid=True, normalized_value=duration_blocks)

    @classmethod
    def is_valid_namespace_name(cls, name: str) -> bool:
        result = cls.validate_name(name)
        return result.is_valid
