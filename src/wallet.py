import json
import base64
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade
import logging

from src.shared.network import (
    NetworkClient,
    NetworkError,
    RetryConfig,
    TimeoutConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            Path.home() / ".config" / "symbol-quick-wallet" / "wallet.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class WalletConfig:
    timeout_config: TimeoutConfig | None = None
    retry_config: RetryConfig | None = None

    def __post_init__(self):
        if self.timeout_config is None:
            self.timeout_config = TimeoutConfig()
        if self.retry_config is None:
            self.retry_config = RetryConfig()


@dataclass
class AccountInfo:
    address: str
    public_key: str
    encrypted_private_key: str
    label: str = ""
    address_book_shared: bool = True

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "public_key": self.public_key,
            "encrypted_private_key": self.encrypted_private_key,
            "label": self.label,
            "address_book_shared": self.address_book_shared,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AccountInfo":
        return cls(
            address=data.get("address", ""),
            public_key=data.get("public_key", ""),
            encrypted_private_key=data.get("encrypted_private_key", ""),
            label=data.get("label", ""),
            address_book_shared=data.get("address_book_shared", True),
        )


MULTI_ACCOUNT_VERSION = 1


class Wallet:
    XYM_MOSAIC_ID = 0x6BED913FA20223F8
    TESTNET_XYM_MOSAIC_ID = 0x72C0212E67A08BCE
    XYM_DIVISIBILITY = 6

    @classmethod
    def _resolve_storage_dir(cls, storage_dir: str | Path | None = None) -> Path:
        if storage_dir:
            return Path(storage_dir).expanduser()

        env_dir = os.getenv("SYMBOL_WALLET_DIR")
        if env_dir:
            return Path(env_dir).expanduser()

        legacy_dir = Path.home() / ".symbol-quick-wallet"
        config_dir = Path.home() / ".config" / "symbol-quick-wallet"

        legacy_wallet = legacy_dir / "wallet.json"
        config_wallet = config_dir / "wallet.json"

        if config_wallet.exists():
            return config_dir
        if legacy_wallet.exists():
            return legacy_dir
        if config_dir.exists():
            return config_dir
        if legacy_dir.exists():
            return legacy_dir
        return config_dir

    def __init__(
        self, network_name="testnet", password=None, storage_dir=None, config=None
    ):
        self.network_name = network_name
        self.facade = SymbolFacade(network_name)
        wallet_dir = self._resolve_storage_dir(storage_dir)
        wallet_dir.mkdir(parents=True, exist_ok=True)
        self.wallet_dir = wallet_dir
        self.wallet_file = self.wallet_dir / "wallet.json"
        self.accounts_file = self.wallet_dir / "accounts.json"
        self.address_book_file = self.wallet_dir / "address_book.json"
        self.shared_address_book_file = self.wallet_dir / "shared_address_book.json"
        self.contact_groups_file = self.wallet_dir / "contact_groups.json"
        self.config_file = self.wallet_dir / "config.json"
        self.window_size = "80x24"
        self.theme = "dark"
        self.password = password
        self.private_key = None
        self.public_key = None
        self.address = None
        self.config = config or WalletConfig()
        self._load_config()
        self.facade = SymbolFacade(self.network_name)
        self._currency_mosaic_id: int | None = None
        self._accounts: list[AccountInfo] = []
        self._current_account_index: int = 0
        self._load_accounts_registry()
        self._load_address_book()
        self._load_contact_groups()
        self._network_client = NetworkClient(
            node_url=self.node_url,
            timeout_config=self.config.timeout_config,
            retry_config=self.config.retry_config,
        )

    @staticmethod
    def _normalize_address(address: str) -> str:
        return address.replace("-", "").strip().upper()

    @staticmethod
    def _normalize_mosaic_id(mosaic_id: Any) -> int | None:
        if isinstance(mosaic_id, int):
            return mosaic_id

        if isinstance(mosaic_id, str):
            value = mosaic_id.strip().lower()
            if not value:
                return None
            if value.startswith("0x"):
                value = value[2:]
            try:
                return int(value, 16)
            except ValueError:
                try:
                    return int(value)
                except ValueError:
                    return None

        return None

    @staticmethod
    def _normalize_amount(amount: Any) -> int:
        try:
            return int(amount)
        except (ValueError, TypeError):
            return 0

    def _normalize_mosaics(self, mosaics: list[dict[str, Any]]) -> list[dict[str, int]]:
        normalized = []
        for mosaic in mosaics:
            mosaic_id = self._normalize_mosaic_id(mosaic.get("id"))
            if mosaic_id is None:
                continue
            normalized.append(
                {
                    "id": mosaic_id,
                    "amount": self._normalize_amount(mosaic.get("amount", 0)),
                }
            )
        return normalized

    def _fetch_account_data(self, address: str | None = None) -> dict[str, Any] | None:
        target_address = address or (str(self.address) if self.address else "")
        if not target_address:
            return None

        normalized_address = self._normalize_address(target_address)
        try:
            return self._network_client.get_optional(
                f"/accounts/{normalized_address}",
                context="Fetch account data",
            )
        except NetworkError:
            return None

    def _update_node_url(self, node_url: str) -> None:
        self.node_url = node_url
        self._network_client = NetworkClient(
            node_url=node_url,
            timeout_config=self.config.timeout_config,
            retry_config=self.config.retry_config,
        )

    def _load_config(self):
        if self.config_file.exists():
            with open(self.config_file, "r") as f:
                config = json.load(f)
                self.node_url = config.get(
                    "node_url", "http://sym-test-01.opening-line.jp:3000"
                )
                self.network_name = config.get("network", "testnet")
                self.window_size = config.get("window_size", "80x24")
                self.theme = config.get("theme", "dark")
                timeout_cfg = config.get("timeout", {})
                if timeout_cfg:
                    self.config.timeout_config = TimeoutConfig(
                        connect_timeout=timeout_cfg.get("connect_timeout", 5.0),
                        read_timeout=timeout_cfg.get("read_timeout", 15.0),
                        operation_timeout=timeout_cfg.get("operation_timeout", 30.0),
                    )
                retry_cfg = config.get("retry", {})
                if retry_cfg:
                    self.config.retry_config = RetryConfig(
                        max_retries=retry_cfg.get("max_retries", 3),
                        base_delay=retry_cfg.get("base_delay", 1.0),
                        max_delay=retry_cfg.get("max_delay", 30.0),
                    )
        else:
            self.node_url = "http://sym-test-01.opening-line.jp:3000"
            self.network_name = "testnet"
            self.window_size = "80x24"
            self.theme = "dark"
            self._save_config()

    def _save_config(self):
        timeout_cfg = self.config.timeout_config or TimeoutConfig()
        retry_cfg = self.config.retry_config or RetryConfig()
        config = {
            "node_url": self.node_url,
            "network": self.network_name,
            "window_size": self.window_size,
            "theme": self.theme,
            "timeout": {
                "connect_timeout": timeout_cfg.connect_timeout,
                "read_timeout": timeout_cfg.read_timeout,
                "operation_timeout": timeout_cfg.operation_timeout,
            },
            "retry": {
                "max_retries": retry_cfg.max_retries,
                "base_delay": retry_cfg.base_delay,
                "max_delay": retry_cfg.max_delay,
            },
        }
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def set_window_size(self, size):
        self.window_size = size
        self._save_config()

    def set_theme(self, theme):
        self.theme = theme
        self._save_config()

    def _load_wallet(self):
        pass

    def has_wallet(self):
        if not self.wallet_file.exists():
            return False
        try:
            with open(self.wallet_file, "r") as f:
                data = json.load(f)
                encrypted_key = data.get("encrypted_private_key")
                public_key = data.get("public_key")

                if not encrypted_key or not isinstance(encrypted_key, str):
                    logger.warning(
                        "Wallet file missing or invalid encrypted_private_key"
                    )
                    return False

                if not public_key or not isinstance(public_key, str):
                    logger.warning("Wallet file missing or invalid public_key")
                    return False

                if len(public_key) != 64:
                    logger.warning("Wallet file has invalid public_key length")
                    return False

                try:
                    int(public_key, 16)
                except ValueError:
                    logger.warning(
                        "Wallet file has invalid public_key format (not hex)"
                    )
                    return False

                return True
        except Exception as e:
            logger.warning(f"Wallet file exists but is corrupted or invalid: {str(e)}")
            return False

    def is_first_run(self):
        return not self.has_wallet()

    def load_wallet_from_storage(self, password=None):
        if self.wallet_file.exists():
            if not password:
                raise Exception("Password is required to load wallet")
            with open(self.wallet_file, "r") as f:
                data = json.load(f)
            encrypted_key = data.get("encrypted_private_key")
            if not encrypted_key:
                raise Exception(
                    "Wallet file is not encrypted. Please re-create wallet."
                )
            try:
                private_key_hex = self.decrypt_private_key(encrypted_key, password)
                self.private_key = PrivateKey(private_key_hex)
                account = self.facade.create_account(self.private_key)
                self.public_key = account.public_key
                self.address = account.address
                self.password = password
                logger.info(f"Wallet loaded successfully: {self.address}")
            except Exception as e:
                logger.error(f"Failed to decrypt wallet: {str(e)}")
                raise Exception("Invalid password. Please try again.")
        else:
            self.private_key = None
            self.public_key = None
            self.address = None

    def _save_wallet(self):
        if not self.password:
            raise Exception("Password is required to save wallet")
        encrypted_private_key = self.encrypt_private_key(self.password)
        data = {
            "encrypted_private_key": encrypted_private_key,
            "public_key": str(self.public_key),
        }
        with open(self.wallet_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Wallet saved with encrypted private key")

    def create_wallet(self):
        account = self.facade.create_account(PrivateKey.random())
        self.private_key = account.key_pair.private_key
        self.public_key = account.public_key
        self.address = account.address
        self._save_wallet()
        logger.info(f"New wallet created: {self.address}")
        return self.address

    def import_wallet(self, private_key_hex):
        self.private_key = PrivateKey(private_key_hex)
        account = self.facade.create_account(self.private_key)
        self.public_key = account.public_key
        self.address = account.address
        self._save_wallet()
        logger.info(f"Wallet imported: {self.address}")
        return self.address

    def get_address(self):
        return str(self.address)

    def get_balance(self, address=None):
        try:
            account_data = self._fetch_account_data(address=address)
            if not account_data:
                return []
            logger.info(f"Balance fetched for {address or self.address}")
            mosaics = account_data.get("mosaics", [])
            return self._normalize_mosaics(mosaics)
        except NetworkError as e:
            logger.error(f"Network error fetching balance: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            raise Exception(f"Error fetching balance: {str(e)}")

    def get_account_balances(self, address: str | None = None) -> dict[str, Any]:
        target_address = address or (str(self.address) if self.address else "")
        if not target_address:
            return {
                "address": None,
                "xym_micro": 0,
                "xym": 0.0,
                "mosaics": [],
            }

        normalized_address = self._normalize_address(target_address)
        mosaics = self.get_balance(address=normalized_address)

        network_currency_id = self.get_currency_mosaic_id()
        known_currency_ids = {self.XYM_MOSAIC_ID, self.TESTNET_XYM_MOSAIC_ID}
        xym_match_ids = (
            {network_currency_id}
            if network_currency_id is not None
            else known_currency_ids
        )

        xym_micro = 0
        detailed_mosaics = []
        for mosaic in mosaics:
            mosaic_id = mosaic["id"]
            amount = mosaic["amount"]
            if mosaic_id in xym_match_ids:
                xym_micro = amount
            detailed_mosaics.append(
                {
                    "id": mosaic_id,
                    "id_hex": hex(mosaic_id),
                    "name": self.get_mosaic_name(mosaic_id),
                    "amount": amount,
                    "amount_xym": amount / 1_000_000
                    if mosaic_id in xym_match_ids
                    else None,
                }
            )

        return {
            "address": normalized_address,
            "xym_micro": xym_micro,
            "xym": xym_micro / 1_000_000,
            "mosaics": detailed_mosaics,
        }

    def get_xym_balance(self, address: str | None = None) -> dict[str, Any]:
        account_balances = self.get_account_balances(address=address)
        return {
            "address": account_balances["address"],
            "xym_micro": account_balances["xym_micro"],
            "xym": account_balances["xym"],
        }

    def get_registered_address_balances(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for address, info in self.address_book.items():
            try:
                results[address] = {
                    "name": info.get("name", ""),
                    "note": info.get("note", ""),
                    "address": address,
                    "balance": self.get_account_balances(address),
                }
            except Exception as exc:
                results[address] = {
                    "name": info.get("name", ""),
                    "note": info.get("note", ""),
                    "address": address,
                    "balance": None,
                    "error": str(exc),
                }
        return results

    def _load_address_book(self):
        if self.address_book_file.exists():
            with open(self.address_book_file, "r") as f:
                self.address_book = json.load(f)
        else:
            self.address_book = {}

    def _load_contact_groups(self):
        if self.contact_groups_file.exists():
            with open(self.contact_groups_file, "r") as f:
                self.contact_groups = json.load(f)
        else:
            self.contact_groups = {}

    def _save_contact_groups(self):
        account = self.get_current_account()
        if account and not account.address_book_shared:
            groups_file = self._get_contact_groups_path(account.address)
            with open(groups_file, "w") as f:
                json.dump(self.contact_groups, f, indent=2)
        else:
            with open(self.contact_groups_file, "w") as f:
                json.dump(self.contact_groups, f, indent=2)

    def _get_contact_groups_path(self, address: str) -> Path:
        normalized = self._normalize_address(address)
        return self.wallet_dir / f"contact_groups_{normalized}.json"

    def create_contact_group(self, name: str, color: str = "") -> str:
        import uuid

        group_id = str(uuid.uuid4())[:8]
        self.contact_groups[group_id] = {
            "id": group_id,
            "name": name,
            "color": color,
        }
        self._save_contact_groups()
        logger.info(f"Contact group created: {name} ({group_id})")
        return group_id

    def update_contact_group(self, group_id: str, name: str, color: str = "") -> bool:
        if group_id in self.contact_groups:
            self.contact_groups[group_id]["name"] = name
            self.contact_groups[group_id]["color"] = color
            self._save_contact_groups()
            logger.info(f"Contact group updated: {name} ({group_id})")
            return True
        return False

    def delete_contact_group(self, group_id: str) -> bool:
        if group_id in self.contact_groups:
            for addr, info in self.address_book.items():
                if info.get("group_id") == group_id:
                    info["group_id"] = None
            del self.contact_groups[group_id]
            self._save_contact_groups()
            self._save_address_book()
            logger.info(f"Contact group deleted: {group_id}")
            return True
        return False

    def get_contact_groups(self) -> dict[str, dict[str, str]]:
        return self.contact_groups.copy()

    def get_contact_group(self, group_id: str) -> dict[str, str] | None:
        return self.contact_groups.get(group_id)

    def get_addresses_by_group(self, group_id: str | None) -> dict[str, dict[str, str]]:
        if group_id is None:
            return {
                addr: info
                for addr, info in self.address_book.items()
                if not info.get("group_id")
            }
        return {
            addr: info
            for addr, info in self.address_book.items()
            if info.get("group_id") == group_id
        }

    def add_address(self, address, name, note="", group_id=None):
        self.address_book[address] = {
            "name": name,
            "address": address,
            "note": note,
            "group_id": group_id,
        }
        self._save_address_book()
        logger.info(f"Address added to book: {name} ({address})")

    def update_address(self, address, name, note, group_id=None):
        if address in self.address_book:
            self.address_book[address] = {
                "name": name,
                "address": address,
                "note": note,
                "group_id": group_id,
            }
            self._save_address_book()

    def remove_address(self, address):
        if address in self.address_book:
            del self.address_book[address]
            self._save_address_book()

    def get_addresses(self):
        return self.address_book

    def get_address_info(self, address):
        return self.address_book.get(
            address, {"name": "", "address": address, "note": "", "group_id": None}
        )

    def encrypt_private_key(self, password):
        key = base64.urlsafe_b64encode(password.encode().ljust(32)[:32])
        cipher = Fernet(key)
        encrypted = cipher.encrypt(str(self.private_key).encode())
        return encrypted.decode()

    def decrypt_private_key(self, encrypted_key, password):
        key = base64.urlsafe_b64encode(password.encode().ljust(32)[:32])
        cipher = Fernet(key)
        try:
            decrypted = cipher.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as e:
            raise Exception(f"Failed to decrypt private key: {str(e)}")

    def export_private_key(self, password):
        if not self.private_key:
            raise Exception("No wallet loaded")
        encrypted = self.encrypt_private_key(password)
        return {
            "encrypted_private_key": encrypted,
            "public_key": str(self.public_key),
            "address": str(self.address),
        }

    def import_encrypted_private_key(self, encrypted_data, password):
        encrypted_key = encrypted_data.get("encrypted_private_key")
        if not encrypted_key:
            raise Exception("Invalid encrypted data")
        private_key_hex = self.decrypt_private_key(encrypted_key, password)
        self.import_wallet(private_key_hex)

    def get_transaction_history(self, limit=20):
        try:
            if not self.address:
                return []
            result = self._network_client.get_optional(
                f"/accounts/{str(self.address)}/transactions?limit={limit}",
                context="Fetch transaction history",
            )
            if result is None:
                return []
            return result.get("data", [])
        except NetworkError:
            raise
        except Exception as e:
            raise Exception(f"Error fetching transaction history: {str(e)}")

    def get_transaction_status(self, tx_hash: str) -> dict[str, Any]:
        groups = ("confirmed", "unconfirmed", "partial")
        normalized_hash = tx_hash.strip().upper()
        for group in groups:
            result = self._network_client.get_optional(
                f"/transactions/{group}/{normalized_hash}",
                context="Fetch transaction status",
            )
            if result is not None:
                return {"hash": normalized_hash, "group": group, "data": result}

        return {"hash": normalized_hash, "group": "not_found", "data": None}

    def wait_for_transaction_confirmation(
        self,
        tx_hash: str,
        timeout_seconds: int = 120,
        poll_interval_seconds: int = 5,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        latest_status = {"hash": tx_hash, "group": "not_found", "data": None}

        while time.time() < deadline:
            latest_status = self.get_transaction_status(tx_hash)
            if latest_status["group"] == "confirmed":
                return latest_status
            time.sleep(poll_interval_seconds)

        raise TimeoutError(
            f"Transaction {tx_hash} was not confirmed within {timeout_seconds} seconds "
            f"(latest status: {latest_status['group']})."
        )

    def wait_for_confirmed_transaction(
        self,
        signer_public_key: str,
        message: str | None = None,
        timeout_seconds: int = 180,
        poll_interval_seconds: int = 5,
        page_size: int = 100,
    ) -> dict[str, Any]:
        signer = signer_public_key.upper()

        encoded_message = (message or "").encode("utf-8").hex().upper()
        deadline = time.time() + timeout_seconds
        latest_count = 0

        while time.time() < deadline:
            result = self._network_client.get(
                f"/transactions/confirmed?limit={page_size}&order=desc",
                context="Wait for confirmed transaction",
            )
            data = result.get("data", [])
            latest_count = len(data)

            for tx in data:
                tx_body = tx.get("transaction", {})
                if tx_body.get("signerPublicKey", "").upper() != signer:
                    continue

                if encoded_message:
                    tx_message = tx_body.get("message", "").upper()
                    if encoded_message not in tx_message:
                        continue

                return tx

            time.sleep(poll_interval_seconds)

        raise TimeoutError(
            f"No matching confirmed transaction found within {timeout_seconds} seconds "
            f"(last scanned items: {latest_count})."
        )

    def get_mosaic_info(self, mosaic_id):
        try:
            return self._network_client.get_optional(
                f"/mosaics/{mosaic_id}",
                context="Fetch mosaic info",
            )
        except Exception:
            return None

    def get_mosaic_metadata(self, mosaic_id: int) -> list[dict[str, Any]]:
        metadata_type = 1
        try:
            result = self._network_client.get_optional(
                f"/metadata?targetId={mosaic_id}&metadataType={metadata_type}",
                context="Fetch mosaic metadata",
            )
            if result is None:
                return []
            data = result.get("data", [])
            metadata_list = []
            for entry in data:
                metadata_entry = entry.get("metadataEntry", {})
                value_hex = metadata_entry.get("value", "")
                try:
                    value = bytes.fromhex(value_hex).decode("utf-8")
                except (ValueError, UnicodeDecodeError):
                    value = value_hex
                metadata_list.append(
                    {
                        "key": hex(metadata_entry.get("scopedMetadataKey", 0)),
                        "value": value,
                        "source_address": metadata_entry.get("sourceAddress", ""),
                        "target_address": metadata_entry.get("targetAddress", ""),
                    }
                )
            return metadata_list
        except Exception:
            return []

    def get_mosaic_namespace_name(self, mosaic_id: int) -> str | None:
        try:
            result = self._network_client.get_optional(
                f"/namespaces/mosaic/{mosaic_id}",
                context="Fetch mosaic namespace",
            )
            if result is None:
                return None
            data = result.get("data", [])
            if not data:
                return None
            namespace_info = data[0].get("namespace", {})
            name = namespace_info.get("name", "")
            return name if name else None
        except Exception:
            return None

    def get_mosaic_full_info(self, mosaic_id: int) -> dict[str, Any]:
        mosaic_info = self.get_mosaic_info(mosaic_id)
        if mosaic_info is None:
            return {
                "mosaic_id": mosaic_id,
                "mosaic_id_hex": hex(mosaic_id),
                "found": False,
            }

        mosaic_data = mosaic_info.get("mosaic", mosaic_info)

        flags_value = mosaic_data.get("flags", 0)
        flags = {
            "supply_mutable": bool(flags_value & 0x02),
            "transferable": bool(flags_value & 0x01),
            "restrictable": bool(flags_value & 0x04),
            "revokable": bool(flags_value & 0x08),
        }

        owner_address_raw = mosaic_data.get("ownerAddress", "")
        if owner_address_raw:
            try:
                if owner_address_raw.startswith("0x"):
                    owner_address_raw = owner_address_raw[2:]
                owner_address = owner_address_raw
            except Exception:
                owner_address = owner_address_raw
        else:
            owner_address = ""

        namespace_name = self.get_mosaic_namespace_name(mosaic_id)
        mosaic_name = (
            namespace_name if namespace_name else self.get_mosaic_name(mosaic_id)
        )

        metadata = self.get_mosaic_metadata(mosaic_id)

        description = ""
        for meta in metadata:
            key = meta.get("key", "")
            if key.lower() in ("0x0", "0x00", "0"):
                description = meta.get("value", "")
                break

        return {
            "mosaic_id": mosaic_id,
            "mosaic_id_hex": hex(mosaic_id),
            "found": True,
            "name": mosaic_name,
            "divisibility": mosaic_data.get("divisibility", 0),
            "supply": int(mosaic_data.get("supply", 0)),
            "owner_address": owner_address,
            "flags": flags,
            "duration": int(mosaic_data.get("duration", 0)),
            "start_height": int(mosaic_data.get("startHeight", 0)),
            "metadata": metadata,
            "description": description,
        }

    def get_currency_mosaic_id(self) -> int | None:
        if self._currency_mosaic_id is not None:
            return self._currency_mosaic_id

        try:
            properties = self._network_client.get(
                "/network/properties",
                context="Fetch network properties",
            )
            value = (
                properties.get("chain", {})
                .get("currencyMosaicId", "")
                .replace("'", "")
                .strip()
                .lower()
            )
            if value.startswith("0x"):
                self._currency_mosaic_id = int(value, 16)
                return self._currency_mosaic_id
        except Exception:
            pass

        fallback = (
            self.TESTNET_XYM_MOSAIC_ID
            if str(self.network_name).lower() == "testnet"
            else self.XYM_MOSAIC_ID
        )
        self._currency_mosaic_id = fallback
        return self._currency_mosaic_id

    def get_mosaic_name(self, mosaic_id):
        if mosaic_id is None:
            return "unknown"

        if isinstance(mosaic_id, str):
            normalized = mosaic_id.lower()
            if normalized.startswith("0x"):
                normalized = normalized[2:]
            try:
                int(normalized, 16)
            except ValueError:
                return mosaic_id
            mosaic_id_hex = f"0x{normalized}"
        else:
            mosaic_id_hex = hex(mosaic_id)

        known_mosaics = {
            "0x6bed913fa20223f8": "XYM",
            "6bed913fa20223f8": "XYM",
            "0x72c0212e67a08bce": "XYM",
            "72c0212e67a08bce": "XYM",
        }
        currency_id = self.get_currency_mosaic_id()
        if (
            currency_id is not None
            and mosaic_id_hex.lower() == hex(currency_id).lower()
        ):
            return "XYM"
        if mosaic_id_hex.lower() in known_mosaics:
            return known_mosaics[mosaic_id_hex.lower()]
        return mosaic_id_hex

    def test_node_connection(self, node_url=None):
        """Test if a node is accessible and healthy."""
        url = node_url if node_url else self.node_url
        test_client = NetworkClient(
            node_url=url,
            timeout_config=self.config.timeout_config,
            retry_config=self.config.retry_config,
        )
        try:
            return test_client.test_connection()
        except NetworkError as e:
            logger.error(f"Node connection test failed: {e.message}")
            raise Exception(e.message)

    def create_mosaic_transaction(
        self,
        supply,
        divisibility=0,
        transferable=True,
        supply_mutable=False,
        revokable=False,
    ):
        """Create a mosaic definition transaction."""
        deadline_timestamp = self.facade.network.from_datetime(
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).timestamp

        mosaic_flags = 0
        if transferable:
            mosaic_flags |= 0x1
        if supply_mutable:
            mosaic_flags |= 0x2
        if revokable:
            mosaic_flags |= 0x4

        mosaic_dict = {
            "type": "mosaic_definition_transaction_v1",
            "signer_public_key": str(self.public_key),
            "deadline": deadline_timestamp,
            "divisibility": divisibility,
            "flags": mosaic_flags,
            "supply": supply,
        }

        mosaic_tx = self.facade.transaction_factory.create(mosaic_dict)

        logger.info(
            f"Mosaic definition transaction created: supply={supply}, divisibility={divisibility}"
        )
        return mosaic_tx

    def get_harvesting_status(self):
        """Get harvesting status of account."""
        try:
            if not self.address:
                return {
                    "is_harvesting": False,
                    "is_remote": False,
                    "linked_public_key": None,
                }
            result = self._network_client.get_optional(
                f"/accounts/{str(self.address)}",
                context="Fetch harvesting status",
            )
            if result is None:
                logger.warning(f"Account not found: {self.address}")
                return {
                    "is_harvesting": False,
                    "is_remote": False,
                    "linked_public_key": None,
                }
            account_data = result.get("account", {})
            remote_account = account_data.get("remoteAccount", None)
            logger.info(
                f"Harvesting status fetched: is_remote={remote_account is not None}"
            )
            return {
                "is_harvesting": True,
                "is_remote": remote_account is not None,
                "linked_public_key": remote_account,
            }
        except NetworkError:
            raise
        except Exception as e:
            logger.error(f"Error fetching harvesting status: {str(e)}")
            raise Exception(f"Error fetching harvesting status: {str(e)}")

    def link_harvesting_account(self, remote_public_key):
        """Link account to a remote harvesting account."""
        from symbolchain.CryptoTypes import PublicKey

        linked_key = PublicKey(remote_public_key)
        deadline_timestamp = self.facade.network.from_datetime(
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).timestamp

        link_dict = {
            "type": "account_key_link_transaction_v1",
            "signer_public_key": str(self.public_key),
            "deadline": deadline_timestamp,
            "link_action": "link",
            "linked_public_key": str(linked_key),
        }

        link_tx = self.facade.transaction_factory.create(link_dict)
        logger.info(f"Harvesting link transaction created for {self.address}")
        return link_tx

    def unlink_harvesting_account(self):
        """Unlink the remote harvesting account."""
        deadline_timestamp = self.facade.network.from_datetime(
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).timestamp

        link_dict = {
            "type": "account_key_link_transaction_v1",
            "signer_public_key": str(self.public_key),
            "deadline": deadline_timestamp,
            "link_action": "unlink",
            "linked_public_key": str(self.public_key),
        }

        link_tx = self.facade.transaction_factory.create(link_dict)
        logger.info(f"Harvesting unlink transaction created for {self.address}")
        return link_tx

    def _load_accounts_registry(self):
        if self.accounts_file.exists():
            try:
                with open(self.accounts_file, "r") as f:
                    data = json.load(f)
                    version = data.get("version", 0)
                    if version >= MULTI_ACCOUNT_VERSION:
                        self._accounts = [
                            AccountInfo.from_dict(acc)
                            for acc in data.get("accounts", [])
                        ]
                        self._current_account_index = data.get(
                            "current_account_index", 0
                        )
                    else:
                        self._migrate_legacy_wallet_to_accounts()
            except Exception as e:
                logger.warning(f"Failed to load accounts registry: {e}")
                self._accounts = []
                self._current_account_index = 0
        else:
            self._accounts = []
            self._current_account_index = 0
            if self.has_wallet():
                self._migrate_legacy_wallet_to_accounts()

    def _migrate_legacy_wallet_to_accounts(self):
        if self.wallet_file.exists():
            try:
                with open(self.wallet_file, "r") as f:
                    data = json.load(f)
                encrypted_key = data.get("encrypted_private_key")
                public_key = data.get("public_key")
                if encrypted_key and public_key:
                    legacy_account = AccountInfo(
                        address="",
                        public_key=public_key,
                        encrypted_private_key=encrypted_key,
                        label="Main Account",
                        address_book_shared=True,
                    )
                    self._accounts = [legacy_account]
                    self._current_account_index = 0
                    self._save_accounts_registry()
                    logger.info("Migrated legacy wallet to multi-account format")
            except Exception as e:
                logger.warning(f"Failed to migrate legacy wallet: {e}")

    def _save_accounts_registry(self):
        data = {
            "version": MULTI_ACCOUNT_VERSION,
            "accounts": [acc.to_dict() for acc in self._accounts],
            "current_account_index": self._current_account_index,
        }
        with open(self.accounts_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved accounts registry with {len(self._accounts)} accounts")

    def get_accounts(self) -> list[AccountInfo]:
        return self._accounts.copy()

    def get_current_account(self) -> AccountInfo | None:
        if 0 <= self._current_account_index < len(self._accounts):
            return self._accounts[self._current_account_index]
        return None

    def get_current_account_index(self) -> int:
        return self._current_account_index

    def create_account(
        self, label: str = "", address_book_shared: bool = True
    ) -> AccountInfo:
        if not self.password:
            raise Exception("Password is required to create account")
        new_account = self.facade.create_account(PrivateKey.random())
        encrypted_private_key = self._encrypt_private_key_for_account(
            str(new_account.key_pair.private_key), self.password
        )
        account_info = AccountInfo(
            address=str(new_account.address),
            public_key=str(new_account.public_key),
            encrypted_private_key=encrypted_private_key,
            label=label or f"Account {len(self._accounts) + 1}",
            address_book_shared=address_book_shared,
        )
        self._accounts.append(account_info)
        self._save_accounts_registry()
        if not account_info.address_book_shared:
            self._ensure_account_address_book(account_info.address)
        logger.info(f"Created new account: {account_info.address}")
        return account_info

    def import_account(
        self, private_key_hex: str, label: str = "", address_book_shared: bool = True
    ) -> AccountInfo:
        if not self.password:
            raise Exception("Password is required to import account")
        private_key = PrivateKey(private_key_hex)
        account = self.facade.create_account(private_key)
        encrypted_private_key = self._encrypt_private_key_for_account(
            str(private_key), self.password
        )
        for existing in self._accounts:
            if existing.address == str(account.address):
                raise Exception(f"Account {account.address} already exists")
        account_info = AccountInfo(
            address=str(account.address),
            public_key=str(account.public_key),
            encrypted_private_key=encrypted_private_key,
            label=label or f"Account {len(self._accounts) + 1}",
            address_book_shared=address_book_shared,
        )
        self._accounts.append(account_info)
        self._save_accounts_registry()
        if not account_info.address_book_shared:
            self._ensure_account_address_book(account_info.address)
        logger.info(f"Imported account: {account_info.address}")
        return account_info

    def switch_account(self, index: int) -> bool:
        if 0 <= index < len(self._accounts):
            self._current_account_index = index
            self._save_accounts_registry()
            account = self._accounts[index]
            self._load_account_into_session(account)
            logger.info(f"Switched to account: {account.label} ({account.address})")
            return True
        return False

    def _load_account_into_session(self, account: AccountInfo):
        if not self.password:
            raise Exception("Password is required to load account")
        try:
            private_key_hex = self._decrypt_private_key_for_account(
                account.encrypted_private_key, self.password
            )
            self.private_key = PrivateKey(private_key_hex)
            loaded_account = self.facade.create_account(self.private_key)
            self.public_key = loaded_account.public_key
            self.address = loaded_account.address
            self._load_address_book_for_account(account)
        except Exception as e:
            logger.error(f"Failed to load account: {e}")
            raise

    def _load_address_book_for_account(self, account: AccountInfo):
        if account.address_book_shared:
            self._load_address_book()
            self._load_contact_groups()
        else:
            account_book_file = self._get_account_address_book_path(account.address)
            if account_book_file.exists():
                with open(account_book_file, "r") as f:
                    self.address_book = json.load(f)
            else:
                self.address_book = {}
            groups_file = self._get_contact_groups_path(account.address)
            if groups_file.exists():
                with open(groups_file, "r") as f:
                    self.contact_groups = json.load(f)
            else:
                self.contact_groups = {}

    def _get_account_address_book_path(self, address: str) -> Path:
        normalized = self._normalize_address(address)
        return self.wallet_dir / f"address_book_{normalized}.json"

    def _ensure_account_address_book(self, address: str):
        path = self._get_account_address_book_path(address)
        if not path.exists():
            with open(path, "w") as f:
                json.dump({}, f)

    def _encrypt_private_key_for_account(self, private_key: str, password: str) -> str:
        key = base64.urlsafe_b64encode(password.encode().ljust(32)[:32])
        cipher = Fernet(key)
        encrypted = cipher.encrypt(private_key.encode())
        return encrypted.decode()

    def _decrypt_private_key_for_account(
        self, encrypted_key: str, password: str
    ) -> str:
        key = base64.urlsafe_b64encode(password.encode().ljust(32)[:32])
        cipher = Fernet(key)
        try:
            decrypted = cipher.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as e:
            raise Exception(f"Failed to decrypt private key: {str(e)}")

    def delete_account(self, index: int) -> bool:
        if len(self._accounts) <= 1:
            logger.warning("Cannot delete the last account")
            return False
        if 0 <= index < len(self._accounts):
            account = self._accounts[index]
            if not account.address_book_shared:
                book_path = self._get_account_address_book_path(account.address)
                if book_path.exists():
                    book_path.unlink()
            del self._accounts[index]
            if self._current_account_index >= len(self._accounts):
                self._current_account_index = len(self._accounts) - 1
            self._save_accounts_registry()
            logger.info(f"Deleted account: {account.address}")
            return True
        return False

    def update_account_label(self, index: int, label: str) -> bool:
        if 0 <= index < len(self._accounts):
            self._accounts[index].label = label
            self._save_accounts_registry()
            logger.info(f"Updated account {index} label to: {label}")
            return True
        return False

    def update_account_address_book_shared(self, index: int, shared: bool) -> bool:
        if 0 <= index < len(self._accounts):
            account = self._accounts[index]
            old_shared = account.address_book_shared
            account.address_book_shared = shared
            self._save_accounts_registry()
            if old_shared and not shared:
                self._ensure_account_address_book(account.address)
            elif not old_shared and shared:
                book_path = self._get_account_address_book_path(account.address)
                if book_path.exists():
                    book_path.unlink()
            logger.info(f"Updated account {index} address_book_shared to: {shared}")
            return True
        return False

    def load_current_account(self):
        if not self.password:
            raise Exception("Password is required")
        account = self.get_current_account()
        if account:
            self._load_account_into_session(account)
            return True
        return False

    def _save_address_book(self):
        account = self.get_current_account()
        if account and not account.address_book_shared:
            book_path = self._get_account_address_book_path(account.address)
            with open(book_path, "w") as f:
                json.dump(self.address_book, f, indent=2)
        else:
            with open(self.address_book_file, "w") as f:
                json.dump(self.address_book, f, indent=2)
