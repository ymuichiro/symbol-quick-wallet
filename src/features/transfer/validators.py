"""Transfer-specific validators for Symbol Quick Wallet."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass
class TransferValidationResult:
    is_valid: bool
    error_message: str | None = None
    normalized_value: Any = None


class TransferAmountValidator:
    """Validator for transfer amounts with mosaic divisibility support."""

    MAX_AMOUNT = 9_223_372_036_854_775_807

    @staticmethod
    def parse_human_amount(value: str) -> TransferValidationResult:
        if not value or not value.strip():
            return TransferValidationResult(
                is_valid=False,
                error_message="Amount is required",
            )

        raw_amount = value.strip().replace(",", "").replace(" ", "")

        if raw_amount.startswith("-") or raw_amount.startswith("+"):
            return TransferValidationResult(
                is_valid=False,
                error_message="Amount must be a positive number",
            )

        try:
            amount_decimal = Decimal(raw_amount)
        except (InvalidOperation, ValueError):
            return TransferValidationResult(
                is_valid=False,
                error_message="Amount must be a valid number",
            )

        if amount_decimal < 0:
            return TransferValidationResult(
                is_valid=False,
                error_message="Amount cannot be negative",
            )

        if amount_decimal == 0:
            return TransferValidationResult(
                is_valid=False,
                error_message="Amount must be greater than zero",
            )

        if amount_decimal.as_tuple().exponent is None:
            return TransferValidationResult(
                is_valid=False,
                error_message="Invalid numeric format (special value detected)",
            )

        return TransferValidationResult(
            is_valid=True,
            normalized_value=amount_decimal,
        )

    @staticmethod
    def validate_decimal_places(
        amount: Decimal, divisibility: int
    ) -> TransferValidationResult:
        exponent = amount.as_tuple().exponent
        if not isinstance(exponent, int):
            return TransferValidationResult(
                is_valid=False,
                error_message="Invalid numeric format",
            )

        decimal_places = max(0, -exponent)
        if decimal_places > divisibility:
            if divisibility == 0:
                return TransferValidationResult(
                    is_valid=False,
                    error_message="This mosaic does not support decimal amounts (divisibility: 0)",
                )
            return TransferValidationResult(
                is_valid=False,
                error_message=f"Too many decimal places. Maximum {divisibility} allowed for this mosaic",
            )

        return TransferValidationResult(is_valid=True)

    @staticmethod
    def convert_to_micro_units(
        amount: Decimal, divisibility: int
    ) -> TransferValidationResult:
        try:
            scale = Decimal(10) ** divisibility
            micro_units = int(amount * scale)
        except (TypeError, ValueError, OverflowError):
            return TransferValidationResult(
                is_valid=False,
                error_message="Failed to convert amount to micro units",
            )

        if micro_units <= 0:
            return TransferValidationResult(
                is_valid=False,
                error_message="Amount must be greater than zero",
            )

        if micro_units > TransferAmountValidator.MAX_AMOUNT:
            return TransferValidationResult(
                is_valid=False,
                error_message="Amount exceeds maximum allowed value",
            )

        return TransferValidationResult(
            is_valid=True,
            normalized_value=micro_units,
        )

    @staticmethod
    def validate_against_balance(
        micro_units: int, owned_amount: int
    ) -> TransferValidationResult:
        if micro_units > owned_amount:
            return TransferValidationResult(
                is_valid=False,
                error_message=f"Insufficient balance. You have {owned_amount:,} micro units available",
            )

        return TransferValidationResult(is_valid=True)

    @classmethod
    def validate_full(
        cls,
        value: str,
        divisibility: int,
        owned_amount: int | None = None,
    ) -> TransferValidationResult:
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

        return TransferValidationResult(
            is_valid=True,
            normalized_value=micro_units,
        )
