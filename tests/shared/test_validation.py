
from src.shared.validation import (
    AddressValidator,
    AmountValidator,
    MosaicIdValidator,
    ValidationResult,
)


class TestValidationResult:
    def test_valid_result(self):
        result = ValidationResult(is_valid=True, normalized_value=123)
        assert result.is_valid is True
        assert result.error_message is None
        assert result.normalized_value == 123

    def test_invalid_result(self):
        result = ValidationResult(is_valid=False, error_message="Test error")
        assert result.is_valid is False
        assert result.error_message == "Test error"
        assert result.normalized_value is None


class TestAmountValidatorParseHumanAmount:
    def test_valid_integer(self):
        result = AmountValidator.parse_human_amount("100")
        assert result.is_valid is True
        assert result.normalized_value == 100

    def test_valid_decimal(self):
        result = AmountValidator.parse_human_amount("1.5")
        assert result.is_valid is True
        assert result.normalized_value == 1.5

    def test_valid_with_commas(self):
        result = AmountValidator.parse_human_amount("1,000.5")
        assert result.is_valid is True
        assert result.normalized_value == 1000.5

    def test_empty_string(self):
        result = AmountValidator.parse_human_amount("")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "required" in result.error_message.lower()

    def test_whitespace_only(self):
        result = AmountValidator.parse_human_amount("   ")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "required" in result.error_message.lower()

    def test_negative_amount(self):
        result = AmountValidator.parse_human_amount("-10")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "positive" in result.error_message.lower()

    def test_zero_amount(self):
        result = AmountValidator.parse_human_amount("0")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "zero" in result.error_message.lower()

    def test_invalid_characters(self):
        result = AmountValidator.parse_human_amount("abc")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "valid number" in result.error_message.lower()

    def test_multiple_decimals(self):
        result = AmountValidator.parse_human_amount("1.2.3")
        assert result.is_valid is False


class TestAmountValidatorDecimalPlaces:
    def test_within_divisibility(self):
        from decimal import Decimal

        result = AmountValidator.validate_decimal_places(Decimal("1.5"), 6)
        assert result.is_valid is True

    def test_exact_divisibility(self):
        from decimal import Decimal

        result = AmountValidator.validate_decimal_places(Decimal("1.123456"), 6)
        assert result.is_valid is True

    def test_exceeds_divisibility(self):
        from decimal import Decimal

        result = AmountValidator.validate_decimal_places(Decimal("1.1234567"), 6)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "6" in result.error_message

    def test_zero_divisibility_with_decimal(self):
        from decimal import Decimal

        result = AmountValidator.validate_decimal_places(Decimal("1.5"), 0)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "divisibility: 0" in result.error_message

    def test_zero_divisibility_no_decimal(self):
        from decimal import Decimal

        result = AmountValidator.validate_decimal_places(Decimal("1"), 0)
        assert result.is_valid is True


class TestAmountValidatorConvertToMicroUnits:
    def test_convert_with_divisibility(self):
        from decimal import Decimal

        result = AmountValidator.convert_to_micro_units(Decimal("1.5"), 6)
        assert result.is_valid is True
        assert result.normalized_value == 1_500_000

    def test_convert_zero_divisibility(self):
        from decimal import Decimal

        result = AmountValidator.convert_to_micro_units(Decimal("100"), 0)
        assert result.is_valid is True
        assert result.normalized_value == 100

    def test_large_amount(self):
        from decimal import Decimal

        result = AmountValidator.convert_to_micro_units(
            Decimal("9223372036854775807"), 0
        )
        assert result.is_valid is True
        assert result.normalized_value == 9_223_372_036_854_775_807


class TestAmountValidatorValidateAgainstBalance:
    def test_within_balance(self):
        result = AmountValidator.validate_against_balance(100, 200)
        assert result.is_valid is True

    def test_exact_balance(self):
        result = AmountValidator.validate_against_balance(100, 100)
        assert result.is_valid is True

    def test_exceeds_balance(self):
        result = AmountValidator.validate_against_balance(200, 100)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "Insufficient" in result.error_message


class TestAmountValidatorValidateFull:
    def test_valid_full_validation(self):
        result = AmountValidator.validate_full("1.5", 6, 2_000_000)
        assert result.is_valid is True
        assert result.normalized_value == 1_500_000

    def test_invalid_decimal_places(self):
        result = AmountValidator.validate_full("1.1234567", 6, 1_000_000_000)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "decimal" in result.error_message.lower()

    def test_insufficient_balance(self):
        result = AmountValidator.validate_full("100", 0, 50)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "Insufficient" in result.error_message

    def test_without_balance_check(self):
        result = AmountValidator.validate_full("1.5", 6)
        assert result.is_valid is True
        assert result.normalized_value == 1_500_000


class TestAddressValidator:
    def test_valid_testnet_address(self):
        result = AddressValidator.validate("TCWYXKVYBMO4NBCUF3AXKJMXCGVSYQOS7ZG2TLI")
        assert result.is_valid is True
        assert result.normalized_value.startswith("T")

    def test_valid_mainnet_address(self):
        result = AddressValidator.validate("NCWYXKVYBMO4NBCUF3AXKJMXCGVSYQOS72UNKDY")
        assert result.is_valid is True
        assert result.normalized_value.startswith("N")

    def test_address_with_dashes(self):
        result = AddressValidator.validate(
            "TCWY-XKVY-BMO4-NBCU-F3AX-KJMX-CGVS-YQOS-7ZG2-TLI"
        )
        assert result.is_valid is True

    def test_empty_address(self):
        result = AddressValidator.validate("")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "required" in result.error_message.lower()

    def test_short_address(self):
        result = AddressValidator.validate("TD5ZP2")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "short" in result.error_message.lower()

    def test_long_address(self):
        result = AddressValidator.validate("TCWYXKVYBMO4NBCUF3AXKJMXCGVSYQOS7ZG2TLIAAAA")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "long" in result.error_message.lower()

    def test_invalid_starting_char(self):
        result = AddressValidator.validate("ACWYXKVYBMO4NBCUF3AXKJMXCGVSYQOS7ZG2TLI")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "T" in result.error_message or "N" in result.error_message

    def test_network_mismatch(self):
        result = AddressValidator.validate(
            "NCWYXKVYBMO4NBCUF3AXKJMXCGVSYQOS72UNKDY",
            expected_network="testnet",
        )
        assert result.is_valid is False
        assert result.error_message is not None
        assert "mismatch" in result.error_message.lower()

    def test_checksum_invalid(self):
        result = AddressValidator.validate("TCWYXKVYBMO4NBCUF3AXKJMXCGVSYQOS7ZG2TLA")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "checksum" in result.error_message.lower()


class TestMosaicIdValidator:
    def test_valid_hex_string(self):
        result = MosaicIdValidator.validate("6BED913FA20223F8")
        assert result.is_valid is True
        assert result.normalized_value == 0x6BED913FA20223F8

    def test_valid_hex_with_prefix(self):
        result = MosaicIdValidator.validate("0x6BED913FA20223F8")
        assert result.is_valid is True
        assert result.normalized_value == 0x6BED913FA20223F8

    def test_valid_integer(self):
        result = MosaicIdValidator.validate(0x6BED913FA20223F8)
        assert result.is_valid is True
        assert result.normalized_value == 0x6BED913FA20223F8

    def test_empty_string(self):
        result = MosaicIdValidator.validate("")
        assert result.is_valid is False
        assert result.error_message is not None
        assert "required" in result.error_message.lower()

    def test_invalid_characters(self):
        result = MosaicIdValidator.validate("GGGG")
        assert result.is_valid is False

    def test_negative_integer(self):
        result = MosaicIdValidator.validate(-1)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "positive" in result.error_message.lower()
