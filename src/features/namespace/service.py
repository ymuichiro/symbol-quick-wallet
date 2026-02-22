"""Namespace business logic service for Symbol Quick Wallet."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from src.features.namespace.validators import NamespaceValidator, ValidationResult
from src.shared.protocols import WalletProtocol

logger = logging.getLogger(__name__)


@dataclass
class NamespaceInfo:
    namespace_id: int
    name: str
    full_name: str
    registration_type: int
    depth: int
    owner_address: str
    start_height: int
    end_height: int
    active: bool
    alias_type: int
    alias_address: str | None = None
    alias_mosaic_id: int | None = None

    @property
    def is_root(self) -> bool:
        return self.registration_type == 0

    @property
    def has_address_alias(self) -> bool:
        return self.alias_type == 2

    @property
    def has_mosaic_alias(self) -> bool:
        return self.alias_type == 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace_id": self.namespace_id,
            "namespace_id_hex": hex(self.namespace_id),
            "name": self.name,
            "full_name": self.full_name,
            "registration_type": self.registration_type,
            "registration_type_name": "root" if self.is_root else "sub",
            "depth": self.depth,
            "owner_address": self.owner_address,
            "start_height": self.start_height,
            "end_height": self.end_height,
            "active": self.active,
            "alias_type": self.alias_type,
            "alias_address": self.alias_address,
            "alias_mosaic_id": self.alias_mosaic_id,
            "alias_mosaic_id_hex": (
                hex(self.alias_mosaic_id) if self.alias_mosaic_id else None
            ),
        }


class TransactionManagerProtocol(Protocol):
    def create_sign_and_announce_root_namespace(
        self, name: str, duration_blocks: int
    ) -> dict[str, Any]: ...

    def create_sign_and_announce_sub_namespace(
        self, name: str, parent_name: str
    ) -> dict[str, Any]: ...

    def create_sign_and_announce_address_alias(
        self, namespace_name: str, address: str, link_action: str
    ) -> dict[str, Any]: ...

    def create_sign_and_announce_mosaic_alias(
        self, namespace_name: str, mosaic_id: int, link_action: str
    ) -> dict[str, Any]: ...


class NamespaceService:
    BLOCK_TIME_SECONDS = 30

    def __init__(
        self,
        wallet: WalletProtocol,
        network_client: Any,
        transaction_manager: TransactionManagerProtocol | None = None,
    ):
        self.wallet = wallet
        self.network_client = network_client
        self.transaction_manager = transaction_manager

    def validate_namespace_name(self, name: str) -> ValidationResult:
        return NamespaceValidator.validate_name(name)

    def validate_full_namespace_name(self, full_name: str) -> ValidationResult:
        return NamespaceValidator.validate_full_name(full_name)

    def validate_duration(self, duration_days: int) -> ValidationResult:
        return NamespaceValidator.validate_duration(duration_days)

    def generate_namespace_id(self, name: str, parent_id: int = 0) -> int:
        name_bytes = name.encode("utf-8")
        namespace_id = parent_id
        for i, char_byte in enumerate(name_bytes):
            namespace_id = (namespace_id * 31 + char_byte) & 0xFFFFFFFFFFFFFFFF
            if i == 0:
                namespace_id = namespace_id | 0x8000000000000000
        return namespace_id

    def generate_namespace_path(self, full_name: str) -> list[int]:
        parts = full_name.lower().split(".")
        path = [0]
        for part in parts:
            parent_id = path[-1]
            namespace_id = self.generate_namespace_id(part, parent_id)
            path.append(namespace_id)
        return path[1:]

    def get_namespace_id(self, full_name: str) -> int:
        path = self.generate_namespace_path(full_name)
        return path[-1] if path else 0

    def fetch_namespace_info(self, namespace_id: int) -> NamespaceInfo | None:
        try:
            response = self.network_client.get_optional(
                f"/namespaces/{hex(namespace_id).upper()[2:]}",
                context="Fetch namespace info",
            )
            if response is None:
                return None

            ns_data = response.get("namespace", response)
            meta = response.get("meta", {})

            alias = ns_data.get("alias", {})
            alias_type = alias.get("type", 0)

            full_name = self._reconstruct_namespace_name(ns_data, namespace_id)

            return NamespaceInfo(
                namespace_id=namespace_id,
                name=full_name.split(".")[-1] if "." in full_name else full_name,
                full_name=full_name,
                registration_type=ns_data.get("registrationType", 0),
                depth=ns_data.get("depth", 1),
                owner_address=ns_data.get("ownerAddress", ""),
                start_height=int(ns_data.get("startHeight", 0)),
                end_height=int(ns_data.get("endHeight", 0)),
                active=meta.get("active", False),
                alias_type=alias_type,
                alias_address=alias.get("address") if alias_type == 2 else None,
                alias_mosaic_id=(
                    int(alias.get("mosaicId", "0"), 16) if alias_type == 1 else None
                ),
            )
        except Exception as e:
            logger.error("Failed to fetch namespace info: %s", str(e))
            return None

    def _reconstruct_namespace_name(
        self, ns_data: dict[str, Any], namespace_id: int
    ) -> str:
        depth = ns_data.get("depth", 1)
        levels = []
        for i in range(depth):
            level_key = f"level{i}"
            if level_key in ns_data:
                level_hex = ns_data[level_key]
                try:
                    level_info = self.network_client.get_optional(
                        f"/namespaces/{level_hex}",
                        context=f"Fetch level {i} namespace",
                    )
                    if level_info:
                        levels.append(level_info.get("namespace", {}).get("name", ""))
                except Exception:
                    pass
        return ".".join(levels) if levels else hex(namespace_id)

    def resolve_namespace_to_address(self, full_name: str) -> str | None:
        namespace_id = self.get_namespace_id(full_name)
        info = self.fetch_namespace_info(namespace_id)
        if info and info.has_address_alias:
            return info.alias_address
        return None

    def resolve_namespace_to_mosaic_id(self, full_name: str) -> int | None:
        namespace_id = self.get_namespace_id(full_name)
        info = self.fetch_namespace_info(namespace_id)
        if info and info.has_mosaic_alias:
            return info.alias_mosaic_id
        return None

    def fetch_owned_namespaces(self, address: str | None = None) -> list[NamespaceInfo]:
        target_address = address or str(self.wallet.address)
        if not target_address:
            return []

        try:
            response = self.network_client.post(
                "/namespaces/account/names",
                context="Fetch owned namespaces",
                json={"addresses": [target_address.replace("-", "").upper()]},
            )

            account_names = response.get("accountNames", [])
            namespaces = []

            for account_name in account_names:
                for ns_name in account_name.get("names", []):
                    name = ns_name.get("name", "")
                    if name:
                        namespace_id = self.get_namespace_id(name)
                        info = self.fetch_namespace_info(namespace_id)
                        if info:
                            namespaces.append(info)

            return namespaces
        except Exception as e:
            logger.error("Failed to fetch owned namespaces: %s", str(e))
            return []

    def calculate_expiration(
        self, end_height: int, current_height: int
    ) -> dict[str, Any]:
        remaining_blocks = max(0, end_height - current_height)
        remaining_seconds = remaining_blocks * self.BLOCK_TIME_SECONDS
        remaining_days = remaining_seconds / (24 * 60 * 60)

        return {
            "end_height": end_height,
            "current_height": current_height,
            "remaining_blocks": remaining_blocks,
            "remaining_seconds": remaining_seconds,
            "remaining_days": round(remaining_days, 1),
            "is_expired": remaining_blocks == 0,
        }

    def fetch_rental_fees(self) -> dict[str, Any]:
        try:
            response = self.network_client.get(
                "/network/fees/rental",
                context="Fetch rental fees",
            )

            root_fee_per_block = int(
                response.get("effectiveRootNamespaceRentalFeePerBlock", 0)
            )
            child_fee = int(response.get("effectiveChildNamespaceRentalFee", 0))

            root_fee_30d = root_fee_per_block * (
                30 * 24 * 60 * 60 // self.BLOCK_TIME_SECONDS
            )
            root_fee_365d = root_fee_per_block * (
                365 * 24 * 60 * 60 // self.BLOCK_TIME_SECONDS
            )

            return {
                "root_fee_per_block": root_fee_per_block,
                "child_fee": child_fee,
                "root_fee_30d": root_fee_30d,
                "root_fee_365d": root_fee_365d,
                "root_fee_30d_xym": root_fee_30d / 1_000_000,
                "root_fee_365d_xym": root_fee_365d / 1_000_000,
                "child_fee_xym": child_fee / 1_000_000,
            }
        except Exception as e:
            logger.error("Failed to fetch rental fees: %s", str(e))
            return {
                "root_fee_per_block": 0,
                "child_fee": 0,
                "root_fee_30d": 0,
                "root_fee_365d": 0,
                "root_fee_30d_xym": 0.0,
                "root_fee_365d_xym": 0.0,
                "child_fee_xym": 0.0,
            }

    def estimate_root_namespace_cost(self, duration_days: int) -> dict[str, Any]:
        fees = self.fetch_rental_fees()
        duration_blocks = int(duration_days * 24 * 60 * 60 / self.BLOCK_TIME_SECONDS)
        total_fee = fees["root_fee_per_block"] * duration_blocks

        return {
            "duration_days": duration_days,
            "duration_blocks": duration_blocks,
            "rental_fee": total_fee,
            "rental_fee_xym": total_fee / 1_000_000,
            "network_fee_estimate": 50_000,
            "network_fee_xym": 0.05,
            "total_fee": total_fee + 50_000,
            "total_fee_xym": (total_fee + 50_000) / 1_000_000,
        }

    def create_root_namespace(self, name: str, duration_days: int) -> dict[str, Any]:
        name_result = self.validate_namespace_name(name)
        if not name_result.is_valid:
            raise ValueError(name_result.error_message)

        duration_result = self.validate_duration(duration_days)
        if not duration_result.is_valid:
            raise ValueError(duration_result.error_message)

        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required to create namespaces")

        duration_blocks = duration_result.normalized_value
        return self.transaction_manager.create_sign_and_announce_root_namespace(
            name_result.normalized_value, duration_blocks
        )

    def create_sub_namespace(self, name: str, parent_name: str) -> dict[str, Any]:
        name_result = self.validate_namespace_name(name)
        if not name_result.is_valid:
            raise ValueError(name_result.error_message)

        parent_result = self.validate_full_namespace_name(parent_name)
        if not parent_result.is_valid:
            raise ValueError(parent_result.error_message)

        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required to create namespaces")

        return self.transaction_manager.create_sign_and_announce_sub_namespace(
            name_result.normalized_value, parent_result.normalized_value
        )

    def link_address_alias(
        self, namespace_name: str, address: str, link_action: str = "link"
    ) -> dict[str, Any]:
        full_name_result = self.validate_full_namespace_name(namespace_name)
        if not full_name_result.is_valid:
            raise ValueError(full_name_result.error_message)

        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required to link aliases")

        return self.transaction_manager.create_sign_and_announce_address_alias(
            full_name_result.normalized_value,
            address.replace("-", "").upper(),
            link_action,
        )

    def link_mosaic_alias(
        self, namespace_name: str, mosaic_id: int, link_action: str = "link"
    ) -> dict[str, Any]:
        full_name_result = self.validate_full_namespace_name(namespace_name)
        if not full_name_result.is_valid:
            raise ValueError(full_name_result.error_message)

        if self.transaction_manager is None:
            raise ValueError("Transaction manager is required to link aliases")

        return self.transaction_manager.create_sign_and_announce_mosaic_alias(
            full_name_result.normalized_value, mosaic_id, link_action
        )

    def unlink_address_alias(self, namespace_name: str, address: str) -> dict[str, Any]:
        return self.link_address_alias(namespace_name, address, "unlink")

    def unlink_mosaic_alias(
        self, namespace_name: str, mosaic_id: int
    ) -> dict[str, Any]:
        return self.link_mosaic_alias(namespace_name, mosaic_id, "unlink")
