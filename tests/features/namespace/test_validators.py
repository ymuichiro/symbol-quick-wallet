"""Tests for namespace validators."""

import pytest

from src.features.namespace.validators import (
    MAX_NAMESPACE_LENGTH,
    NamespaceValidator,
    ValidationResult,
)


class TestNamespaceValidator:
    def test_validate_name_valid_lowercase(self):
        result = NamespaceValidator.validate_name("mynamespace")
        assert result.is_valid is True
        assert result.normalized_value == "mynamespace"

    def test_validate_name_valid_with_numbers(self):
        result = NamespaceValidator.validate_name("my123namespace")
        assert result.is_valid is True
        assert result.normalized_value == "my123namespace"

    def test_validate_name_valid_with_underscore(self):
        result = NamespaceValidator.validate_name("my_namespace")
        assert result.is_valid is True
        assert result.normalized_value == "my_namespace"

    def test_validate_name_valid_with_hyphen(self):
        result = NamespaceValidator.validate_name("my-namespace")
        assert result.is_valid is True
        assert result.normalized_value == "my-namespace"

    def test_validate_name_empty(self):
        result = NamespaceValidator.validate_name("")
        assert result.is_valid is False
        assert "required" in result.error_message.lower()

    def test_validate_name_whitespace_only(self):
        result = NamespaceValidator.validate_name("   ")
        assert result.is_valid is False

    def test_validate_name_uppercase_normalized(self):
        result = NamespaceValidator.validate_name("MYNAMESPACE")
        assert result.is_valid is True
        assert result.normalized_value == "mynamespace"

    def test_validate_name_too_long(self):
        long_name = "a" * (MAX_NAMESPACE_LENGTH + 1)
        result = NamespaceValidator.validate_name(long_name)
        assert result.is_valid is False
        assert "exceeds" in result.error_message.lower()

    def test_validate_name_invalid_chars(self):
        result = NamespaceValidator.validate_name("my@namespace")
        assert result.is_valid is False
        assert "a-z" in result.error_message.lower()

    def test_validate_name_starts_with_hyphen(self):
        result = NamespaceValidator.validate_name("-mynamespace")
        assert result.is_valid is False
        assert "start" in result.error_message.lower()

    def test_validate_name_ends_with_hyphen(self):
        result = NamespaceValidator.validate_name("mynamespace-")
        assert result.is_valid is False
        assert "end" in result.error_message.lower()

    def test_validate_full_name_single_level(self):
        result = NamespaceValidator.validate_full_name("mynamespace")
        assert result.is_valid is True
        assert result.normalized_value == "mynamespace"

    def test_validate_full_name_two_levels(self):
        result = NamespaceValidator.validate_full_name("parent.child")
        assert result.is_valid is True
        assert result.normalized_value == "parent.child"

    def test_validate_full_name_three_levels(self):
        result = NamespaceValidator.validate_full_name("parent.child.grandchild")
        assert result.is_valid is True
        assert result.normalized_value == "parent.child.grandchild"

    def test_validate_full_name_too_many_levels(self):
        result = NamespaceValidator.validate_full_name("a.b.c.d")
        assert result.is_valid is False
        assert "3" in result.error_message

    def test_validate_full_name_empty(self):
        result = NamespaceValidator.validate_full_name("")
        assert result.is_valid is False

    def test_validate_duration_minimum(self):
        result = NamespaceValidator.validate_duration(30)
        assert result.is_valid is True
        assert result.normalized_value == 86400

    def test_validate_duration_maximum(self):
        result = NamespaceValidator.validate_duration(1825)
        assert result.is_valid is True

    def test_validate_duration_below_minimum(self):
        result = NamespaceValidator.validate_duration(29)
        assert result.is_valid is False
        assert "30" in result.error_message

    def test_validate_duration_above_maximum(self):
        result = NamespaceValidator.validate_duration(1826)
        assert result.is_valid is False
        assert "1825" in result.error_message

    def test_validate_duration_365_days(self):
        result = NamespaceValidator.validate_duration(365)
        assert result.is_valid is True
        expected_blocks = int(365 * 24 * 60 * 60 / 30)
        assert result.normalized_value == expected_blocks

    def test_is_valid_namespace_name_valid(self):
        assert NamespaceValidator.is_valid_namespace_name("valid") is True

    def test_is_valid_namespace_name_invalid(self):
        assert NamespaceValidator.is_valid_namespace_name("") is False
