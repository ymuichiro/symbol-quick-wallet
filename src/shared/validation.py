"""Input validation utilities for transfer amounts and other user inputs."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from symbolchain.facade.SymbolFacade import SymbolFacade


@dataclass
class ValidationResult:
    is_valid: bool
    error_message: str | None = None
    normalized_value: Any = None


class AmountValidator:
    MAX_AMOUNT = 9_223_372_036_854_775_807

    @staticmethod
    def parse_human_amount(value: str) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Amount is required",
            )

        raw_amount = value.strip().replace(",", "").replace(" ", "")

        if raw_amount.startswith("-") or raw_amount.startswith("+"):
            return ValidationResult(
                is_valid=False,
                error_message="Amount must be a positive number",
            )

        try:
            amount_decimal = Decimal(raw_amount)
        except (InvalidOperation, ValueError):
            return ValidationResult(
                is_valid=False,
                error_message="Amount must be a valid number",
            )

        if amount_decimal < 0:
            return ValidationResult(
                is_valid=False,
                error_message="Amount cannot be negative",
            )

        if amount_decimal == 0:
            return ValidationResult(
                is_valid=False,
                error_message="Amount must be greater than zero",
            )

        if amount_decimal.as_tuple().exponent is None:
            return ValidationResult(
                is_valid=False,
                error_message="Invalid numeric format (special value detected)",
            )

        return ValidationResult(
            is_valid=True,
            normalized_value=amount_decimal,
        )

    @staticmethod
    def validate_decimal_places(amount: Decimal, divisibility: int) -> ValidationResult:
        exponent = amount.as_tuple().exponent
        if not isinstance(exponent, int):
            return ValidationResult(
                is_valid=False,
                error_message="Invalid numeric format",
            )

        decimal_places = max(0, -exponent)
        if decimal_places > divisibility:
            if divisibility == 0:
                return ValidationResult(
                    is_valid=False,
                    error_message="This mosaic does not support decimal amounts (divisibility: 0)",
                )
            return ValidationResult(
                is_valid=False,
                error_message=f"Too many decimal places. Maximum {divisibility} allowed for this mosaic",
            )

        return ValidationResult(is_valid=True)

    @staticmethod
    def convert_to_micro_units(amount: Decimal, divisibility: int) -> ValidationResult:
        try:
            scale = Decimal(10) ** divisibility
            micro_units = int(amount * scale)
        except (TypeError, ValueError, OverflowError):
            return ValidationResult(
                is_valid=False,
                error_message="Failed to convert amount to micro units",
            )

        if micro_units <= 0:
            return ValidationResult(
                is_valid=False,
                error_message="Amount must be greater than zero",
            )

        if micro_units > AmountValidator.MAX_AMOUNT:
            return ValidationResult(
                is_valid=False,
                error_message="Amount exceeds maximum allowed value",
            )

        return ValidationResult(
            is_valid=True,
            normalized_value=micro_units,
        )

    @staticmethod
    def validate_against_balance(
        micro_units: int, owned_amount: int
    ) -> ValidationResult:
        if micro_units > owned_amount:
            return ValidationResult(
                is_valid=False,
                error_message=f"Insufficient balance. You have {owned_amount:,} micro units available",
            )

        return ValidationResult(is_valid=True)

    @classmethod
    def validate_full(
        cls,
        value: str,
        divisibility: int,
        owned_amount: int | None = None,
    ) -> ValidationResult:
        parse_result = cls.parse_human_amount(value)
        if not parse_result.is_valid:
            return parse_result

        amount = parse_result.normalized_value

        decimal_result = cls.validate_decimal_places(amount, divisibility)
        if not decimal_result.is_valid:
            return decimal_result

        micro_result = cls.convert_to_micro_units(amount, divisibility)
        if not micro_result.is_valid:
            return micro_result

        micro_units = micro_result.normalized_value

        if owned_amount is not None:
            balance_result = cls.validate_against_balance(micro_units, owned_amount)
            if not balance_result.is_valid:
                return balance_result

        return ValidationResult(
            is_valid=True,
            normalized_value=micro_units,
        )


class AddressValidator:
    MIN_ADDRESS_LENGTH = 39
    MAX_ADDRESS_LENGTH = 40
    _facade_cache: dict[str, SymbolFacade] = {}

    @classmethod
    def _get_facade(cls, network_name: str) -> SymbolFacade:
        normalized = network_name.lower()
        if normalized not in cls._facade_cache:
            cls._facade_cache[normalized] = SymbolFacade(normalized)
        return cls._facade_cache[normalized]

    @classmethod
    def validate(
        cls, value: str, expected_network: str | None = None
    ) -> ValidationResult:
        if not value or not value.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Address is required",
            )

        normalized = value.strip().replace("-", "").upper()

        if len(normalized) < cls.MIN_ADDRESS_LENGTH:
            return ValidationResult(
                is_valid=False,
                error_message=f"Address too short. Expected {cls.MIN_ADDRESS_LENGTH}-{cls.MAX_ADDRESS_LENGTH} characters",
            )

        if len(normalized) > cls.MAX_ADDRESS_LENGTH:
            return ValidationResult(
                is_valid=False,
                error_message=f"Address too long. Expected {cls.MIN_ADDRESS_LENGTH}-{cls.MAX_ADDRESS_LENGTH} characters",
            )

        try:
            int(normalized, 36)
        except ValueError:
            if not all(c.isalnum() for c in normalized):
                return ValidationResult(
                    is_valid=False,
                    error_message="Address contains invalid characters",
                )

        if normalized[0] not in ("T", "N"):
            return ValidationResult(
                is_valid=False,
                error_message="Address must start with 'T' (testnet) or 'N' (mainnet)",
            )

        target_network: str
        if expected_network:
            expected = expected_network.lower()
            if expected.startswith("test"):
                target_network = "testnet"
            elif expected.startswith("main"):
                target_network = "mainnet"
            else:
                target_network = "testnet" if normalized.startswith("T") else "mainnet"

            expected_prefix = "T" if target_network == "testnet" else "N"
            if normalized[0] != expected_prefix:
                return ValidationResult(
                    is_valid=False,
                    error_message=(
                        "Address network mismatch. "
                        f"Expected {target_network} address (prefix '{expected_prefix}')"
                    ),
                )
        else:
            target_network = "testnet" if normalized.startswith("T") else "mainnet"

        try:
            facade = cls._get_facade(target_network)
            if not facade.network.is_valid_address_string(normalized):
                return ValidationResult(
                    is_valid=False,
                    error_message="Address checksum is invalid",
                )
        except Exception:
            return ValidationResult(
                is_valid=False,
                error_message="Address format is invalid",
            )

        return ValidationResult(
            is_valid=True,
            normalized_value=normalized,
        )


class MosaicIdValidator:
    @staticmethod
    def validate(value: str | int) -> ValidationResult:
        if isinstance(value, int):
            if value <= 0:
                return ValidationResult(
                    is_valid=False,
                    error_message="Mosaic ID must be a positive integer",
                )
            return ValidationResult(is_valid=True, normalized_value=value)

        if not value or not value.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Mosaic ID is required",
            )

        normalized = value.strip().lower()

        if normalized.startswith("0x"):
            hex_part = normalized[2:]
        else:
            hex_part = normalized

        if not hex_part:
            return ValidationResult(
                is_valid=False,
                error_message="Mosaic ID cannot be empty",
            )

        if not all(c in "0123456789abcdef" for c in hex_part):
            return ValidationResult(
                is_valid=False,
                error_message="Mosaic ID must be a valid hexadecimal number",
            )

        try:
            mosaic_id = int(hex_part, 16)
        except ValueError:
            return ValidationResult(
                is_valid=False,
                error_message="Invalid mosaic ID format",
            )

        return ValidationResult(
            is_valid=True,
            normalized_value=mosaic_id,
        )
