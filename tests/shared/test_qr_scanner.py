"""Tests for QR code scanner functionality."""

from src.shared.qr_scanner import QRCodeType, QRScanner, ScannedQRData

TESTNET_ADDRESS = "TBM3CJZ5HBKA7APH4S7Q3E7XUHGJZAQHDB3X5AB"
MAINNET_ADDRESS = "NBM3CJZ5HBKA7APH4S7Q3E7XUHGJZAQHDB3X5AB"


class TestQRScannerParsing:
    """Test QR code parsing functionality."""

    def test_parse_plain_address_testnet(self):
        """Test parsing a plain Symbol testnet address."""
        result = QRScanner.parse_symbol_qr(TESTNET_ADDRESS)

        assert result.qr_type == QRCodeType.ADDRESS
        assert result.address == TESTNET_ADDRESS
        assert result.error is None

    def test_parse_plain_address_mainnet(self):
        """Test parsing a plain Symbol mainnet address."""
        result = QRScanner.parse_symbol_qr(MAINNET_ADDRESS)

        assert result.qr_type == QRCodeType.ADDRESS
        assert result.address == MAINNET_ADDRESS
        assert result.error is None

    def test_parse_address_with_dashes(self):
        """Test parsing address with dashes (formatted)."""
        address = "TAAAAA-AAAAAA-AAAAAA-AAAAAA-AAAAAA-AAAAAA-AAA"
        result = QRScanner.parse_symbol_qr(address)

        assert result.qr_type == QRCodeType.ADDRESS
        assert result.address == address

    def test_parse_address_with_spaces(self):
        """Test parsing address with spaces."""
        address = "TAAAAA AAAAAA AAAAAA AAAAAA AAAAAA AAAAAA AAA"
        result = QRScanner.parse_symbol_qr(address)

        assert result.qr_type == QRCodeType.ADDRESS
        assert result.address == address

    def test_parse_empty_string(self):
        """Test parsing empty string returns error."""
        result = QRScanner.parse_symbol_qr("")

        assert result.qr_type == QRCodeType.UNKNOWN
        assert result.error == "Empty QR data"

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        result = QRScanner.parse_symbol_qr("{not valid json}")

        assert result.qr_type == QRCodeType.UNKNOWN
        assert result.error == "Invalid JSON"


class TestQRScannerJSONParsing:
    """Test JSON QR code parsing (transaction and address formats)."""

    def test_parse_json_address_only(self):
        """Test parsing JSON with only an address."""
        data = f'{{"address": "{TESTNET_ADDRESS}"}}'
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.ADDRESS
        assert result.address == TESTNET_ADDRESS

    def test_parse_json_transaction_with_mosaics(self):
        """Test parsing transaction QR with address and mosaics."""
        data = f'''{{
            "address": "{TESTNET_ADDRESS}",
            "mosaics": [{{"id": "0x6BED913FA20223F8", "amount": 1000000}}]
        }}'''
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.TRANSACTION
        assert result.address == TESTNET_ADDRESS
        assert result.mosaics is not None
        assert len(result.mosaics) == 1
        assert result.mosaics[0]["mosaic_id"] == 0x6BED913FA20223F8
        assert result.mosaics[0]["amount"] == 1000000

    def test_parse_json_transaction_with_message(self):
        """Test parsing transaction QR with message and mosaics."""
        data = f'''{{
            "address": "{TESTNET_ADDRESS}",
            "mosaics": [{{"id": "0x6BED913FA20223F8", "amount": 1000000}}],
            "message": "Hello World"
        }}'''
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.TRANSACTION
        assert result.address == TESTNET_ADDRESS
        assert result.message == "Hello World"

    def test_parse_json_transaction_with_payload(self):
        """Test parsing transaction QR with payload field as message."""
        data = f'''{{
            "address": "{TESTNET_ADDRESS}",
            "mosaics": [{{"id": "0x6BED913FA20223F8", "amount": 1000000}}],
            "payload": "Payment for services"
        }}'''
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.TRANSACTION
        assert result.message == "Payment for services"

    def test_parse_json_address_with_message_only(self):
        """Test parsing JSON with address and message but no mosaics."""
        data = f'''{{
            "address": "{TESTNET_ADDRESS}",
            "message": "Hello World"
        }}'''
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.ADDRESS
        assert result.address == TESTNET_ADDRESS

    def test_parse_json_mosaic_id_variations(self):
        """Test parsing mosaics with different ID field names."""
        data = f'''{{
            "address": "{TESTNET_ADDRESS}",
            "mosaics": [
                {{"mosaicId": "0x6BED913FA20223F8", "amount": 1000000}},
                {{"id": 7601236728629348984, "amount": 500000}}
            ]
        }}'''
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.TRANSACTION
        assert result.mosaics is not None
        assert len(result.mosaics) == 2

    def test_parse_json_amount_variations(self):
        """Test parsing mosaics with different amount field names."""
        data = f'''{{
            "address": "{TESTNET_ADDRESS}",
            "mosaics": [
                {{"id": "0x6BED913FA20223F8", "amount_": 1000000}}
            ]
        }}'''
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.TRANSACTION
        assert result.mosaics is not None
        assert result.mosaics[0]["amount"] == 1000000


class TestQRScannerSymbolFormat:
    """Test Symbol-specific QR code format parsing."""

    def test_parse_symbol_qr_with_version_and_data(self):
        """Test parsing Symbol QR format with v and data fields."""
        data = f'{{"v": 2, "data": {{"address": "{TESTNET_ADDRESS}"}}}}'
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.TRANSACTION
        assert result.address == TESTNET_ADDRESS

    def test_parse_symbol_qr_with_mosaics_in_data(self):
        """Test parsing Symbol QR format with mosaics in data."""
        data = f'''{{
            "v": 2,
            "data": {{
                "address": "{TESTNET_ADDRESS}",
                "mosaics": [{{"id": "0x6BED913FA20223F8", "amount": 1000000}}]
            }}
        }}'''
        result = QRScanner.parse_symbol_qr(data)

        assert result.qr_type == QRCodeType.TRANSACTION
        assert result.mosaics is not None
        assert len(result.mosaics) == 1


class TestQRScannerAddressValidation:
    """Test Symbol address validation."""

    def test_valid_testnet_address_length(self):
        """Test that testnet addresses are 39 characters."""
        assert QRScanner._is_symbol_address("T" + "A" * 38)
        assert not QRScanner._is_symbol_address("T" + "A" * 37)
        assert not QRScanner._is_symbol_address("T" + "A" * 39)

    def test_valid_mainnet_address_length(self):
        """Test that mainnet addresses are 39 characters."""
        assert QRScanner._is_symbol_address("N" + "A" * 38)
        assert not QRScanner._is_symbol_address("N" + "A" * 37)

    def test_invalid_starting_character(self):
        """Test that addresses must start with T or N."""
        assert not QRScanner._is_symbol_address("X" + "A" * 38)
        assert not QRScanner._is_symbol_address("1" + "A" * 38)

    def test_valid_base32_characters(self):
        """Test that addresses use valid Base32 characters."""
        assert QRScanner._is_symbol_address("TABCDEFGHIJKLMNOPQRSTUVWXYZ234567ABCDEF")
        assert not QRScanner._is_symbol_address(
            "T1234567890123456789012345678901234567"
        )


class TestScannedQRData:
    """Test ScannedQRData dataclass."""

    def test_address_data_creation(self):
        """Test creating ScannedQRData for address type."""
        data = ScannedQRData(
            qr_type=QRCodeType.ADDRESS,
            address=TESTNET_ADDRESS,
        )

        assert data.qr_type == QRCodeType.ADDRESS
        assert data.address == TESTNET_ADDRESS
        assert data.mosaics is None
        assert data.message is None
        assert data.error is None

    def test_transaction_data_creation(self):
        """Test creating ScannedQRData for transaction type."""
        data = ScannedQRData(
            qr_type=QRCodeType.TRANSACTION,
            address=TESTNET_ADDRESS,
            mosaics=[{"mosaic_id": 12345, "amount": 1000000}],
            message="Test message",
        )

        assert data.qr_type == QRCodeType.TRANSACTION
        assert data.address == TESTNET_ADDRESS
        assert data.mosaics is not None
        assert len(data.mosaics) == 1
        assert data.message == "Test message"

    def test_error_data_creation(self):
        """Test creating ScannedQRData with error."""
        data = ScannedQRData(
            qr_type=QRCodeType.UNKNOWN,
            raw_data="invalid data",
            error="Could not parse QR code",
        )

        assert data.qr_type == QRCodeType.UNKNOWN
        assert data.raw_data == "invalid data"
        assert data.error == "Could not parse QR code"
