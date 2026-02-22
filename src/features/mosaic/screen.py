"""Mosaic-related modal screens for Symbol Quick Wallet."""

import logging
from typing import Any, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

logger = logging.getLogger(__name__)


class BaseModalScreen(ModalScreen):
    """Base modal screen with common key bindings."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("tab", "action_focus_next", "Next"),
        ("shift+tab", "action_focus_previous", "Previous"),
    ]


class CreateMosaicScreen(BaseModalScreen):
    def __init__(self):
        super().__init__()
        self.transferable = True
        self.supply_mutable = False
        self.revokable = False

    def compose(self) -> ComposeResult:
        yield Label("🎨 Create Mosaic")
        yield Label("Supply (in micro-units):")
        yield Input(
            placeholder="1000000 (1 XYM)",
            id="supply-input",
            type="number",
        )
        yield Label("Divisibility (0-6):")
        yield Input(
            placeholder="0-6",
            id="divisibility-input",
            type="number",
            value="0",
        )
        yield Label(f"Transferable: {self.transferable}", id="transferable-label")
        yield Label(f"Supply Mutable: {self.supply_mutable}", id="mutable-label")
        yield Label(f"Revokable: {self.revokable}", id="revokable-label")
        yield Horizontal(
            Button("Toggle Transferable", id="toggle-transferable"),
            Button("Toggle Mutable", id="toggle-mutable"),
            Button("Toggle Revokable", id="toggle-revokable"),
        )
        yield Label(
            "💡 Transferable: Can be sent to others\n"
            "Supply Mutable: Can change supply later\n"
            "Revokable: Issuer can revoke mosaics"
        )
        yield Horizontal(
            Button("✓ Create", id="create-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "toggle-transferable":
            self.transferable = not self.transferable
            cast(Label, self.query_one("#transferable-label")).update(
                f"Transferable: {self.transferable}"
            )
        elif event.button.id == "toggle-mutable":
            self.supply_mutable = not self.supply_mutable
            cast(Label, self.query_one("#mutable-label")).update(
                f"Supply Mutable: {self.supply_mutable}"
            )
        elif event.button.id == "toggle-revokable":
            self.revokable = not self.revokable
            cast(Label, self.query_one("#revokable-label")).update(
                f"Revokable: {self.revokable}"
            )
        elif event.button.id == "create-button":
            supply_input = cast(Input, self.query_one("#supply-input"))
            divisibility_input = cast(Input, self.query_one("#divisibility-input"))
            supply = supply_input.value
            divisibility = divisibility_input.value
            if supply and divisibility:
                self.post_message(
                    CreateMosaicDialogSubmitted(
                        supply=int(supply),
                        divisibility=int(divisibility),
                        transferable=self.transferable,
                        supply_mutable=self.supply_mutable,
                        revokable=self.revokable,
                    )
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()


class CreateMosaicDialogSubmitted(Message):
    def __init__(self, supply, divisibility, transferable, supply_mutable, revokable):
        super().__init__()
        self.supply = supply
        self.divisibility = divisibility
        self.transferable = transferable
        self.supply_mutable = supply_mutable
        self.revokable = revokable


class MosaicMetadataScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("escape", "app.pop_screen", "Close")]

    def __init__(self, mosaic_info: dict[str, Any]):
        super().__init__()
        self.mosaic_info = mosaic_info

    def compose(self) -> ComposeResult:
        info = self.mosaic_info
        mosaic_id = info.get("mosaic_id_hex", hex(info.get("mosaic_id", 0)))
        name = info.get("name", "Unknown")

        yield Label(f"🎨 Mosaic Details: {name}", id="mosaic-title")
        yield Static("", id="mosaic-content")

        if info.get("found"):
            divisibility = info.get("divisibility", 0)
            supply = info.get("supply", 0)
            owner = info.get("owner_address", "")
            description = info.get("description", "")
            flags = info.get("flags", {})
            duration = info.get("duration", 0)
            start_height = info.get("start_height", 0)
            metadata = info.get("metadata", [])

            supply_display = f"{supply:,}"
            if divisibility > 0:
                human_supply = supply / (10**divisibility)
                supply_display = f"{human_supply:,.{divisibility}f} ({supply:,} base)"

            content_lines = [
                f"[bold]Mosaic ID:[/bold] {mosaic_id}",
                f"[bold]Name:[/bold] {name}",
                f"[bold]Divisibility:[/bold] {divisibility}",
                f"[bold]Supply:[/bold] {supply_display}",
                f"[bold]Owner Address:[/bold] {owner or 'N/A'}",
                "",
                "[bold]Properties:[/bold]",
                f"  • Transferable: {'✓' if flags.get('transferable') else '✗'}",
                f"  • Supply Mutable: {'✓' if flags.get('supply_mutable') else '✗'}",
                f"  • Restrictable: {'✓' if flags.get('restrictable') else '✗'}",
                f"  • Revokable: {'✓' if flags.get('revokable') else '✗'}",
            ]

            if duration > 0:
                content_lines.append(f"[bold]Duration:[/bold] {duration:,} blocks")
            else:
                content_lines.append("[bold]Duration:[/bold] Unlimited")

            if start_height > 0:
                content_lines.append(f"[bold]Start Height:[/bold] {start_height:,}")

            if description:
                content_lines.append("")
                content_lines.append("[bold]Description:[/bold]")
                content_lines.append(f"  {description}")

            if metadata:
                content_lines.append("")
                content_lines.append(
                    f"[bold]Metadata ({len(metadata)} entries):[/bold]"
                )
                for meta in metadata[:5]:
                    key = meta.get("key", "")
                    value = meta.get("value", "")
                    content_lines.append(f"  • {key}: {value}")
                if len(metadata) > 5:
                    content_lines.append(f"  ... and {len(metadata) - 5} more")

            self._content = "\n".join(content_lines)
        else:
            self._content = f"[red]Mosaic {mosaic_id} not found on the network.[/red]"

        yield Horizontal(
            Button("📋 Copy ID", id="copy-id-button"),
            Button("❌ Close", id="close-button"),
        )

    def on_mount(self) -> None:
        content_widget = cast(Static, self.query_one("#mosaic-content"))
        content_widget.update(self._content)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-id-button":
            import pyperclip

            mosaic_id = self.mosaic_info.get(
                "mosaic_id_hex", hex(self.mosaic_info.get("mosaic_id", 0))
            )
            pyperclip.copy(mosaic_id)
            self.notify(f"Copied: {mosaic_id}", severity="information")
        elif event.button.id == "close-button":
            self.app.pop_screen()
