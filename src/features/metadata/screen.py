"""Metadata screens for Symbol Quick Wallet TUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from src.features.metadata.service import MetadataInfo, MetadataTargetType

if TYPE_CHECKING:
    from src.__main__ import WalletApp


@dataclass
class AddMetadataSubmitted:
    key: str
    value: str
    target_type: MetadataTargetType
    target_address: str
    target_id: int | None = None


@dataclass
class RemoveMetadataSubmitted:
    key: str
    target_type: MetadataTargetType
    target_address: str
    target_id: int | None = None


class AddMetadataScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    def __init__(
        self,
        target_type: MetadataTargetType,
        target_address: str,
        target_id: int | None = None,
    ):
        super().__init__()
        self.target_type = target_type
        self.target_address = target_address
        self.target_id = target_id

    def compose(self):
        type_name = self.target_type.name.capitalize()
        yield Label(f"📝 Add {type_name} Metadata")
        yield Static(f"Target: {self.target_address}")
        if self.target_id is not None:
            yield Static(f"Target ID: {hex(self.target_id)}")
        elif self.target_type != MetadataTargetType.ACCOUNT:
            yield Label("Target ID (hex):")
            yield Input(
                placeholder="0x...",
                id="target-id-input",
            )
        yield Label("Key:")
        yield Input(
            placeholder="Metadata key (e.g., 'user_name')",
            id="metadata-key-input",
        )
        yield Label("Value:")
        yield Input(
            placeholder="Metadata value (max 1024 bytes)",
            id="metadata-value-input",
        )
        yield Horizontal(
            Button("Add", id="add-metadata-submit", variant="primary"),
            Button("Cancel", id="add-metadata-cancel"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-metadata-cancel":
            self.app.pop_screen()
        elif event.button.id == "add-metadata-submit":
            key_input = self.query_one("#metadata-key-input", Input)
            value_input = self.query_one("#metadata-value-input", Input)

            key = key_input.value.strip()
            value = value_input.value.strip()

            if not key:
                self.app.notify("Key is required", severity="error")
                return
            if not value:
                self.app.notify("Value is required", severity="error")
                return

            target_id = self.target_id
            if target_id is None and self.target_type != MetadataTargetType.ACCOUNT:
                target_id_input = self.query_one("#target-id-input", Input)
                target_id_str = target_id_input.value.strip()
                if target_id_str:
                    try:
                        if target_id_str.startswith("0x"):
                            target_id = int(target_id_str, 16)
                        else:
                            target_id = int(target_id_str)
                    except ValueError:
                        self.app.notify("Invalid target ID format", severity="error")
                        return

            submitted_event = AddMetadataSubmitted(
                key=key,
                value=value,
                target_type=self.target_type,
                target_address=self.target_address,
                target_id=target_id,
            )
            self.app.pop_screen()
            cast("WalletApp", self.app).on_add_metadata_submitted(submitted_event)


class MetadataListScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def __init__(self, metadata_list: list[MetadataInfo]):
        super().__init__()
        self.metadata_list = metadata_list

    def compose(self):
        yield Label("📝 Metadata Entries", id="metadata-list-title")
        yield DataTable(id="metadata-list-table")
        yield Horizontal(
            Button("View Details", id="view-metadata-button", variant="primary"),
            Button("Close", id="close-metadata-list-button"),
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("Type", key="type")
        table.add_column("Key", key="key")
        table.add_column("Value", key="value")
        table.add_column("Target", key="target")

        for meta in self.metadata_list:
            value_display = (
                meta.value[:30] + "..." if len(meta.value) > 30 else meta.value
            )
            target_display = meta.target_id_hex if meta.target_id else "Account"
            table.add_row(
                meta.target_type_name,
                meta.key_hex,
                value_display,
                target_display,
                key=str(meta.key),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "view-metadata-list-button":
            table = self.query_one(DataTable)
            if table.cursor_row is not None and 0 <= table.cursor_row < len(
                self.metadata_list
            ):
                selected = self.metadata_list[table.cursor_row]
                self.app.push_screen(MetadataDetailScreen(selected))
        elif event.button.id == "close-metadata-list-button":
            self.app.pop_screen()


class MetadataDetailScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def __init__(self, metadata: MetadataInfo):
        super().__init__()
        self.metadata = metadata

    def compose(self):
        yield Label("📝 Metadata Details")
        yield Static(f"Type: {self.metadata.target_type_name}")
        yield Static(f"Key: {self.metadata.key_hex}")
        yield Static(f"Value Size: {self.metadata.value_size} bytes")
        yield Static("Value:")
        yield Static(self.metadata.value)
        yield Static(f"Target Address: {self.metadata.target_address}")
        yield Static(f"Source Address: {self.metadata.source_address}")
        if self.metadata.target_id:
            yield Static(f"Target ID: {self.metadata.target_id_hex}")
        yield Button("Close", id="close-detail-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-detail-button":
            self.app.pop_screen()


class RemoveMetadataScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Cancel")]

    def __init__(self, metadata_list: list[MetadataInfo]):
        super().__init__()
        self.metadata_list = metadata_list

    def compose(self):
        yield Label("🗑️ Remove Metadata", id="remove-meta-title")
        yield Static("Select metadata entry to remove:")
        yield DataTable(id="remove-metadata-table")
        yield Horizontal(
            Button("Remove", id="remove-metadata-submit", variant="error"),
            Button("Cancel", id="remove-metadata-cancel"),
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("Type", key="type")
        table.add_column("Key", key="key")
        table.add_column("Value", key="value")

        for meta in self.metadata_list:
            value_display = (
                meta.value[:30] + "..." if len(meta.value) > 30 else meta.value
            )
            table.add_row(
                meta.target_type_name,
                meta.key_hex,
                value_display,
                key=str(meta.key),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "remove-metadata-cancel":
            self.app.pop_screen()
        elif event.button.id == "remove-metadata-submit":
            table = self.query_one(DataTable)
            if table.cursor_row is None or not (
                0 <= table.cursor_row < len(self.metadata_list)
            ):
                self.app.notify("Please select an entry", severity="error")
                return

            selected = self.metadata_list[table.cursor_row]
            submitted_event = RemoveMetadataSubmitted(
                key=selected.key_hex,
                target_type=selected.target_type,
                target_address=selected.target_address,
                target_id=selected.target_id,
            )
            self.app.pop_screen()
            cast("WalletApp", self.app).on_remove_metadata_submitted(submitted_event)
