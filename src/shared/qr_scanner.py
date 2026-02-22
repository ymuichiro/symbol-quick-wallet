"""QR code scanner utility for Symbol wallet addresses and transactions."""

import base64
import json
import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)


class QRCodeType(Enum):
    ADDRESS = "address"
    TRANSACTION = "transaction"
    UNKNOWN = "unknown"


@dataclass
class ScannedQRData:
    qr_type: QRCodeType
    address: str | None = None
    mosaics: list[dict] | None = None
    message: str | None = None
    raw_data: str | None = None
    error: str | None = None


class QRScanner:
    def __init__(self):
        self._running = False
        self._capture = None
        self._thread: threading.Thread | None = None
        self._on_scan_callback: Callable[[ScannedQRData], None] | None = None
        self._on_error_callback: Callable[[str], None] | None = None

    def is_camera_available(self) -> bool:
        try:
            import cv2

            capture = cv2.VideoCapture(0)
            available = capture.isOpened()
            capture.release()
            return available
        except Exception as e:
            logger.warning(f"Camera check failed: {e}")
            return False

    def start_scanning(
        self,
        on_scan: Callable[[ScannedQRData], None],
        on_error: Callable[[str], None] | None = None,
    ) -> bool:
        if self._running:
            logger.warning("Scanner already running")
            return False

        self._on_scan_callback = on_scan
        self._on_error_callback = on_error
        self._running = True

        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        return True

    def stop_scanning(self) -> None:
        self._running = False
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _scan_loop(self) -> None:
        try:
            import cv2
            from pyzbar import pyzbar
        except ImportError as e:
            error_msg = f"Required libraries not installed: {e}"
            logger.error(error_msg)
            if self._on_error_callback:
                self._on_error_callback(error_msg)
            return

        try:
            self._capture = cv2.VideoCapture(0)
            if not self._capture.isOpened():
                error_msg = "Could not open camera"
                logger.error(error_msg)
                if self._on_error_callback:
                    self._on_error_callback(error_msg)
                return

            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            while self._running:
                ret, frame = self._capture.read()
                if not ret:
                    continue

                barcodes = pyzbar.decode(frame)

                for barcode in barcodes:
                    if barcode.type == "QRCODE":
                        qr_data = barcode.data.decode("utf-8", errors="ignore")
                        logger.info(f"QR code detected: {qr_data[:50]}...")
                        parsed = self.parse_symbol_qr(qr_data)
                        if self._on_scan_callback:
                            self._on_scan_callback(parsed)
                        self.stop_scanning()
                        return

        except Exception as e:
            error_msg = f"Scanning error: {e}"
            logger.error(error_msg, exc_info=True)
            if self._on_error_callback:
                self._on_error_callback(error_msg)
        finally:
            if self._capture is not None:
                try:
                    self._capture.release()
                except Exception:
                    pass
                self._capture = None
            self._running = False

    @staticmethod
    def parse_symbol_qr(data: str) -> ScannedQRData:
        if not data:
            return ScannedQRData(qr_type=QRCodeType.UNKNOWN, error="Empty QR data")

        if data.startswith("{") and data.endswith("}"):
            return QRScanner._parse_json_qr(data)

        if QRScanner._is_symbol_address(data):
            return ScannedQRData(
                qr_type=QRCodeType.ADDRESS, address=data.strip(), raw_data=data
            )

        return ScannedQRData(qr_type=QRCodeType.UNKNOWN, raw_data=data)

    @staticmethod
    def _is_symbol_address(data: str) -> bool:
        cleaned = data.strip().replace("-", "").replace(" ", "").upper()
        if len(cleaned) != 39:
            return False
        if cleaned[0] not in ("T", "N"):
            return False
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
        return all(c in valid_chars for c in cleaned)

    @staticmethod
    def _parse_json_qr(data: str) -> ScannedQRData:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return ScannedQRData(
                qr_type=QRCodeType.UNKNOWN, raw_data=data, error="Invalid JSON"
            )

        if isinstance(parsed, dict):
            if "address" in parsed:
                mosaics = parsed.get("mosaics", [])
                if mosaics and isinstance(mosaics, list):
                    normalized_mosaics = []
                    for m in mosaics:
                        if isinstance(m, dict):
                            mosaic_id = m.get("id") or m.get("mosaicId")
                            amount = m.get("amount") or m.get("amount_", 0)
                            if mosaic_id is not None:
                                if isinstance(mosaic_id, str):
                                    mosaic_id = mosaic_id.lower()
                                    if mosaic_id.startswith("0x"):
                                        mosaic_id = int(mosaic_id, 16)
                                    else:
                                        mosaic_id = int(mosaic_id)
                                normalized_mosaics.append(
                                    {"mosaic_id": int(mosaic_id), "amount": int(amount)}
                                )
                    return ScannedQRData(
                        qr_type=QRCodeType.TRANSACTION,
                        address=parsed.get("address"),
                        mosaics=normalized_mosaics if normalized_mosaics else None,
                        message=parsed.get("message") or parsed.get("payload"),
                        raw_data=data,
                    )
                return ScannedQRData(
                    qr_type=QRCodeType.ADDRESS,
                    address=parsed.get("address"),
                    raw_data=data,
                )

            if "v" in parsed and "data" in parsed:
                return QRScanner._parse_symbol_qr_payload(parsed, data)

        return ScannedQRData(qr_type=QRCodeType.UNKNOWN, raw_data=data)

    @staticmethod
    def _parse_symbol_qr_payload(parsed: dict, raw_data: str) -> ScannedQRData:
        version = parsed.get("v")
        payload = parsed.get("data")

        if not payload:
            return ScannedQRData(qr_type=QRCodeType.UNKNOWN, raw_data=raw_data)

        try:
            if isinstance(payload, str):
                decoded = base64.b64decode(payload)
                inner = json.loads(decoded)
            elif isinstance(payload, dict):
                inner = payload
            else:
                return ScannedQRData(qr_type=QRCodeType.UNKNOWN, raw_data=raw_data)

            if "address" in inner:
                return ScannedQRData(
                    qr_type=QRCodeType.TRANSACTION,
                    address=inner.get("address"),
                    mosaics=inner.get("mosaics"),
                    message=inner.get("message") or inner.get("payload"),
                    raw_data=raw_data,
                )

        except Exception as e:
            logger.debug(f"Failed to parse Symbol QR payload: {e}")

        return ScannedQRData(qr_type=QRCodeType.UNKNOWN, raw_data=raw_data)


def scan_qr_from_camera(
    on_scan: Callable[[ScannedQRData], None],
    on_error: Callable[[str], None] | None = None,
) -> QRScanner:
    scanner = QRScanner()
    scanner.start_scanning(on_scan, on_error)
    return scanner
