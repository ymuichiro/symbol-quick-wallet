import json
import base64
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from cryptography.fernet import Fernet
from symbolchain.CryptoTypes import PrivateKey
from symbolchain.facade.SymbolFacade import SymbolFacade
import logging

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

    def __init__(self, network_name="testnet", password=None, storage_dir=None):
        self.network_name = network_name
        self.facade = SymbolFacade(network_name)
        wallet_dir = self._resolve_storage_dir(storage_dir)
        wallet_dir.mkdir(parents=True, exist_ok=True)
        self.wallet_dir = wallet_dir
        self.wallet_file = self.wallet_dir / "wallet.json"
        self.address_book_file = self.wallet_dir / "address_book.json"
        self.config_file = self.wallet_dir / "config.json"
        self.window_size = "80x24"
        self.theme = "dark"
        self.password = password
        self.private_key = None
        self.public_key = None
        self.address = None
        self._load_config()
        self.facade = SymbolFacade(self.network_name)
        self._currency_mosaic_id: int | None = None
        self._load_address_book()

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
                {"id": mosaic_id, "amount": self._normalize_amount(mosaic.get("amount", 0))}
            )
        return normalized

    def _fetch_account_data(self, address: str | None = None) -> dict[str, Any] | None:
        target_address = address or (str(self.address) if self.address else "")
        if not target_address:
            return None

        normalized_address = self._normalize_address(target_address)
        url = f"{self.node_url}/accounts/{normalized_address}"
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("account", {})

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
        else:
            self.node_url = "http://sym-test-01.opening-line.jp:3000"
            self.network_name = "testnet"
            self.window_size = "80x24"
            self.theme = "dark"
            self._save_config()

    def _save_config(self):
        config = {
            "node_url": self.node_url,
            "network": self.network_name,
            "window_size": self.window_size,
            "theme": self.theme,
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
        except requests.exceptions.Timeout:
            logger.error(f"Connection timeout fetching balance: {self.node_url}")
            raise Exception(
                f"Connection timeout. Node may be unavailable: {self.node_url}"
            )
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to node: {self.node_url}")
            raise Exception(
                f"Cannot connect to node: {self.node_url}. Check your network connection."
            )
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching balance: {e.response.status_code}")
            raise Exception(f"HTTP error: {e.response.status_code} - {e.response.text}")
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

    def _save_address_book(self):
        with open(self.address_book_file, "w") as f:
            json.dump(self.address_book, f, indent=2)

    def add_address(self, address, name, note=""):
        self.address_book[address] = {"name": name, "address": address, "note": note}
        self._save_address_book()
        logger.info(f"Address added to book: {name} ({address})")

    def update_address(self, address, name, note):
        if address in self.address_book:
            self.address_book[address] = {
                "name": name,
                "address": address,
                "note": note,
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
            address, {"name": "", "address": address, "note": ""}
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
            url = f"{self.node_url}/accounts/{str(self.address)}/transactions?limit={limit}"
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            transactions = response.json()
            return transactions.get("data", [])
        except requests.exceptions.Timeout:
            raise Exception(
                f"Connection timeout. Node may be unavailable: {self.node_url}"
            )
        except requests.exceptions.ConnectionError:
            raise Exception(
                f"Cannot connect to node: {self.node_url}. Check your network connection."
            )
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Error fetching transaction history: {str(e)}")

    def get_transaction_status(self, tx_hash: str) -> dict[str, Any]:
        groups = ("confirmed", "unconfirmed", "partial")
        normalized_hash = tx_hash.strip().upper()
        for group in groups:
            url = f"{self.node_url}/transactions/{group}/{normalized_hash}"
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            return {"hash": normalized_hash, "group": group, "data": response.json()}

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
            url = f"{self.node_url}/transactions/confirmed?limit={page_size}&order=desc"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json().get("data", [])
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
            url = f"{self.node_url}/mosaics/{mosaic_id}"
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def get_currency_mosaic_id(self) -> int | None:
        if self._currency_mosaic_id is not None:
            return self._currency_mosaic_id

        try:
            url = f"{self.node_url}/network/properties"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            properties = response.json()
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
        if currency_id is not None and mosaic_id_hex.lower() == hex(currency_id).lower():
            return "XYM"
        if mosaic_id_hex.lower() in known_mosaics:
            return known_mosaics[mosaic_id_hex.lower()]
        return mosaic_id_hex

    def test_node_connection(self, node_url=None):
        """Test if a node is accessible and healthy."""
        url = node_url if node_url else self.node_url
        try:
            # Test node health
            health_url = f"{url}/node/health"
            response = requests.get(health_url, timeout=10)
            response.raise_for_status()
            health_data = response.json()

            # Test network info
            network_url = f"{url}/node/info"
            network_response = requests.get(network_url, timeout=10)
            network_response.raise_for_status()
            network_data = network_response.json()

            status = health_data.get("status", {})
            api_node = status.get("apiNode", "down")
            db_node = status.get("dbNode", "down")

            is_healthy = api_node == "up"
            network_height = network_data.get("networkHeight", 0)

            logger.info(
                f"Node connection test: {url} - Healthy: {is_healthy}, Height: {network_height}"
            )

            return {
                "healthy": is_healthy,
                "apiNode": api_node,
                "dbNode": db_node,
                "networkHeight": network_height,
                "url": url,
            }
        except requests.exceptions.Timeout:
            logger.error(f"Node connection timeout: {url}")
            raise Exception(f"Connection timeout. Node at {url} may be unavailable.")
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to node: {url}")
            raise Exception(
                f"Cannot connect to node. Check your network and node URL: {url}"
            )
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error testing node: {e.response.status_code}")
            raise Exception(
                f"Node returned HTTP error {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Error testing node connection: {str(e)}")
            raise Exception(f"Error testing node: {str(e)}")

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
            url = f"{self.node_url}/accounts/{str(self.address)}"
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                logger.warning(f"Account not found: {self.address}")
                return {
                    "is_harvesting": False,
                    "is_remote": False,
                    "linked_public_key": None,
                }
            response.raise_for_status()
            account_info = response.json()
            account_data = account_info.get("account", {})
            remote_account = account_data.get("remoteAccount", None)
            logger.info(
                f"Harvesting status fetched: is_remote={remote_account is not None}"
            )
            return {
                "is_harvesting": True,
                "is_remote": remote_account is not None,
                "linked_public_key": remote_account,
            }
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
