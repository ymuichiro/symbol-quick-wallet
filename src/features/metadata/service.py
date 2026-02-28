"""Metadata business logic service for Symbol Quick Wallet.

Provides functionality to attach key-value metadata to accounts, mosaics, and namespaces.
Reference: docs/quick_learning_symbol_v3/07_metadata.md
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, cast

from src.shared.logging import get_logger
from src.shared.network import NetworkClient
from src.shared.protocols import WalletProtocol

logger = get_logger(__name__)

MAX_VALUE_SIZE = 1024


class MetadataTargetType(int, Enum):
    ACCOUNT = 0
    MOSAIC = 1
    NAMESPACE = 2


@dataclass
class MetadataInfo:
    key: int
    key_hex: str
    value: str
    value_size: int
    target_type: MetadataTargetType
    target_address: str
    source_address: str
    target_id: int | None = None
    composite_hash: str = ""

    @property
    def target_type_name(self) -> str:
        names = {0: "Account", 1: "Mosaic", 2: "Namespace"}
        return names.get(self.target_type, "Unknown")

    @property
    def target_id_hex(self) -> str | None:
        return hex(self.target_id) if self.target_id else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "key_hex": self.key_hex,
            "value": self.value,
            "value_size": self.value_size,
            "target_type": self.target_type,
            "target_type_name": self.target_type_name,
            "target_address": self.target_address,
            "source_address": self.source_address,
            "target_id": self.target_id,
            "target_id_hex": hex(self.target_id) if self.target_id else None,
            "composite_hash": self.composite_hash,
        }


class TransactionManagerProtocol(Protocol):
    def create_sign_and_announce_account_metadata(
        self,
        target_address: str,
        key: int,
        value: bytes,
        value_size_delta: int,
    ) -> dict[str, Any]: ...

    def create_sign_and_announce_mosaic_metadata(
        self,
        target_address: str,
        mosaic_id: int,
        key: int,
        value: bytes,
        value_size_delta: int,
    ) -> dict[str, Any]: ...

    def create_sign_and_announce_namespace_metadata(
        self,
        target_address: str,
        namespace_id: int,
        key: int,
        value: bytes,
        value_size_delta: int,
    ) -> dict[str, Any]: ...


class MetadataService:
    def __init__(
        self,
        wallet: WalletProtocol,
        network_client: NetworkClient | None = None,
        transaction_manager: TransactionManagerProtocol | None = None,
    ):
        self.wallet = wallet
        self.network_client = network_client or NetworkClient(node_url=wallet.node_url)
        self.transaction_manager = transaction_manager

    def generate_metadata_key(self, key_string: str) -> int:
        hasher = hashlib.sha3_256(key_string.encode("utf-8"))
        digest = hasher.digest()
        lower = int.from_bytes(digest[:4], byteorder="little")
        higher = int.from_bytes(digest[4:8], byteorder="little") | 0x80000000
        return lower + (higher << 32)

    def _xor_bytes(self, a: bytes, b: bytes) -> bytes:
        max_len = max(len(a), len(b))
        result = bytearray(max_len)
        for i in range(max_len):
            byte_a = a[i] if i < len(a) else 0
            byte_b = b[i] if i < len(b) else 0
            result[i] = byte_a ^ byte_b
        return bytes(result)

    def validate_key(self, key_string: str) -> tuple[bool, str | None]:
        if not key_string:
            return False, "Key cannot be empty"
        if len(key_string.encode("utf-8")) > 256:
            return False, "Key is too long (max 256 bytes)"
        return True, None

    def validate_value(self, value: str) -> tuple[bool, str | None]:
        if not value:
            return False, "Value cannot be empty"
        value_bytes = value.encode("utf-8")
        if len(value_bytes) > MAX_VALUE_SIZE:
            return False, f"Value exceeds maximum size of {MAX_VALUE_SIZE} bytes"
        return True, None

    def _normalize_address(self, address: str) -> str:
        return address.replace("-", "").strip().upper()

    def fetch_account_metadata(
        self,
        target_address: str,
        source_address: str | None = None,
    ) -> list[MetadataInfo]:
        target = self._normalize_address(target_address)
        source = self._normalize_address(source_address or str(self.wallet.address))

        try:
            params = {
                "targetAddress": target,
                "sourceAddress": source,
                "metadataType": MetadataTargetType.ACCOUNT.value,
            }
            query = "&".join(f"{k}={v}" for k, v in params.items())
            response = self.network_client.get(
                f"/metadata?{query}",
                context="Fetch account metadata",
            )
            return self._parse_metadata_response(response)
        except Exception as e:
            logger.error("Failed to fetch account metadata: %s", str(e))
            return []

    def fetch_mosaic_metadata(
        self,
        mosaic_id: int,
        source_address: str | None = None,
    ) -> list[MetadataInfo]:
        source = self._normalize_address(source_address or str(self.wallet.address))

        try:
            params = {
                "targetId": hex(mosaic_id).upper()[2:],
                "sourceAddress": source,
                "metadataType": MetadataTargetType.MOSAIC.value,
            }
            query = "&".join(f"{k}={v}" for k, v in params.items())
            response = self.network_client.get(
                f"/metadata?{query}",
                context="Fetch mosaic metadata",
            )
            return self._parse_metadata_response(response)
        except Exception as e:
            logger.error("Failed to fetch mosaic metadata: %s", str(e))
            return []

    def fetch_namespace_metadata(
        self,
        namespace_id: int,
        source_address: str | None = None,
    ) -> list[MetadataInfo]:
        source = self._normalize_address(source_address or str(self.wallet.address))

        try:
            params = {
                "targetId": hex(namespace_id).upper()[2:],
                "sourceAddress": source,
                "metadataType": MetadataTargetType.NAMESPACE.value,
            }
            query = "&".join(f"{k}={v}" for k, v in params.items())
            response = self.network_client.get(
                f"/metadata?{query}",
                context="Fetch namespace metadata",
            )
            return self._parse_metadata_response(response)
        except Exception as e:
            logger.error("Failed to fetch namespace metadata: %s", str(e))
            return []

    def fetch_all_metadata_for_account(
        self, address: str | None = None
    ) -> list[MetadataInfo]:
        target = self._normalize_address(address or str(self.wallet.address))

        try:
            params = {"targetAddress": target}
            query = "&".join(f"{k}={v}" for k, v in params.items())
            response = self.network_client.get(
                f"/metadata?{query}",
                context="Fetch all metadata for account",
            )
            return self._parse_metadata_response(response)
        except Exception as e:
            logger.error("Failed to fetch all metadata: %s", str(e))
            return []

    def _parse_metadata_response(self, response: dict[str, Any]) -> list[MetadataInfo]:
        metadata_list: list[MetadataInfo] = []
        data = response.get("data", [])

        for entry in cast(list[dict[str, Any]], data):
            try:
                meta_entry = entry.get("metadataEntry", {})
                value_hex = meta_entry.get("value", "")
                try:
                    value = (
                        bytes.fromhex(value_hex).decode("utf-8") if value_hex else ""
                    )
                except (ValueError, UnicodeDecodeError):
                    value = value_hex

                key = int(meta_entry.get("scopedMetadataKey", "0"), 16)
                target_type = MetadataTargetType(meta_entry.get("metadataType", 0))
                target_id_hex = meta_entry.get("targetId", "0")
                target_id = (
                    int(target_id_hex, 16)
                    if target_id_hex and target_id_hex != "0000000000000000"
                    else None
                )

                metadata_list.append(
                    MetadataInfo(
                        key=key,
                        key_hex=hex(key),
                        value=value,
                        value_size=meta_entry.get("valueSize", 0),
                        target_type=target_type,
                        target_address=meta_entry.get("targetAddress", ""),
                        source_address=meta_entry.get("sourceAddress", ""),
                        target_id=target_id,
                        composite_hash=meta_entry.get("compositeHash", ""),
                    )
                )
            except Exception as e:
                logger.warning("Failed to parse metadata entry: %s", e)
                continue

        return metadata_list

    def get_existing_metadata(
        self,
        key: int,
        target_type: MetadataTargetType,
        target_address: str,
        target_id: int | None = None,
    ) -> MetadataInfo | None:
        target = self._normalize_address(target_address)
        source = self._normalize_address(str(self.wallet.address))

        try:
            params = {
                "sourceAddress": source,
                "scopedMetadataKey": hex(key).upper()[2:],
                "metadataType": target_type.value,
            }

            if target_type == MetadataTargetType.ACCOUNT:
                params["targetAddress"] = target
            else:
                if target_id is None:
                    return None
                params["targetId"] = hex(target_id).upper()[2:]

            query = "&".join(f"{k}={v}" for k, v in params.items())
            response = self.network_client.get(
                f"/metadata?{query}",
                context="Check existing metadata",
            )

            metadata_list = self._parse_metadata_response(response)
            return metadata_list[0] if metadata_list else None
        except Exception as e:
            logger.debug("No existing metadata found: %s", e)
            return None

    def calculate_value_delta(
        self, new_value: str, existing_value: str
    ) -> tuple[bytes, int]:
        new_bytes = new_value.encode("utf-8")
        existing_bytes = existing_value.encode("utf-8")
        delta = self._xor_bytes(existing_bytes, new_bytes)
        size_delta = len(new_bytes) - len(existing_bytes)
        return delta, size_delta

    def prepare_metadata_update(
        self,
        key_string: str,
        new_value: str,
        target_type: MetadataTargetType,
        target_address: str,
        target_id: int | None = None,
    ) -> tuple[bytes, int]:
        key = self.generate_metadata_key(key_string)
        existing = self.get_existing_metadata(
            key, target_type, target_address, target_id
        )

        new_bytes = new_value.encode("utf-8")

        if existing:
            existing_bytes = existing.value.encode("utf-8")
            delta_value = self._xor_bytes(existing_bytes, new_bytes)
            size_delta = len(new_bytes) - len(existing_bytes)
        else:
            delta_value = new_bytes
            size_delta = len(new_bytes)

        return delta_value, size_delta

    def assign_account_metadata(
        self,
        key_string: str,
        value: str,
        target_address: str | None = None,
    ) -> dict[str, Any]:
        is_valid_key, key_error = self.validate_key(key_string)
        if not is_valid_key:
            raise ValueError(key_error)

        is_valid_value, value_error = self.validate_value(value)
        if not is_valid_value:
            raise ValueError(value_error)

        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required")

        target = self._normalize_address(target_address or str(self.wallet.address))

        delta_value, size_delta = self.prepare_metadata_update(
            key_string, value, MetadataTargetType.ACCOUNT, target
        )

        key = self.generate_metadata_key(key_string)
        return self.transaction_manager.create_sign_and_announce_account_metadata(
            target_address=target,
            key=key,
            value=delta_value,
            value_size_delta=size_delta,
        )

    def assign_mosaic_metadata(
        self,
        key_string: str,
        value: str,
        mosaic_id: int,
        owner_address: str | None = None,
    ) -> dict[str, Any]:
        is_valid_key, key_error = self.validate_key(key_string)
        if not is_valid_key:
            raise ValueError(key_error)

        is_valid_value, value_error = self.validate_value(value)
        if not is_valid_value:
            raise ValueError(value_error)

        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required")

        target = self._normalize_address(owner_address or str(self.wallet.address))

        delta_value, size_delta = self.prepare_metadata_update(
            key_string,
            value,
            MetadataTargetType.MOSAIC,
            target,
            mosaic_id,
        )

        key = self.generate_metadata_key(key_string)
        return self.transaction_manager.create_sign_and_announce_mosaic_metadata(
            target_address=target,
            mosaic_id=mosaic_id,
            key=key,
            value=delta_value,
            value_size_delta=size_delta,
        )

    def assign_namespace_metadata(
        self,
        key_string: str,
        value: str,
        namespace_id: int,
        owner_address: str | None = None,
    ) -> dict[str, Any]:
        is_valid_key, key_error = self.validate_key(key_string)
        if not is_valid_key:
            raise ValueError(key_error)

        is_valid_value, value_error = self.validate_value(value)
        if not is_valid_value:
            raise ValueError(value_error)

        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required")

        target = self._normalize_address(owner_address or str(self.wallet.address))

        delta_value, size_delta = self.prepare_metadata_update(
            key_string,
            value,
            MetadataTargetType.NAMESPACE,
            target,
            namespace_id,
        )

        key = self.generate_metadata_key(key_string)
        return self.transaction_manager.create_sign_and_announce_namespace_metadata(
            target_address=target,
            namespace_id=namespace_id,
            key=key,
            value=delta_value,
            value_size_delta=size_delta,
        )

    def remove_metadata(
        self,
        key_string: str,
        target_type: MetadataTargetType,
        target_address: str,
        target_id: int | None = None,
    ) -> dict[str, Any]:
        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required")

        key = self.generate_metadata_key(key_string)
        existing = self.get_existing_metadata(
            key, target_type, target_address, target_id
        )

        if not existing:
            raise ValueError("Metadata entry not found")

        existing_bytes = existing.value.encode("utf-8")
        delta_value = self._xor_bytes(existing_bytes, b"")
        size_delta = -len(existing_bytes)

        if target_type == MetadataTargetType.ACCOUNT:
            return self.transaction_manager.create_sign_and_announce_account_metadata(
                target_address=self._normalize_address(target_address),
                key=key,
                value=delta_value,
                value_size_delta=size_delta,
            )
        elif target_type == MetadataTargetType.MOSAIC:
            if target_id is None:
                raise ValueError("Mosaic ID is required for mosaic metadata")
            return self.transaction_manager.create_sign_and_announce_mosaic_metadata(
                target_address=self._normalize_address(target_address),
                mosaic_id=target_id,
                key=key,
                value=delta_value,
                value_size_delta=size_delta,
            )
        elif target_type == MetadataTargetType.NAMESPACE:
            if target_id is None:
                raise ValueError("Namespace ID is required for namespace metadata")
            return self.transaction_manager.create_sign_and_announce_namespace_metadata(
                target_address=self._normalize_address(target_address),
                namespace_id=target_id,
                key=key,
                value=delta_value,
                value_size_delta=size_delta,
            )
        else:
            raise ValueError(f"Unknown metadata target type: {target_type}")
