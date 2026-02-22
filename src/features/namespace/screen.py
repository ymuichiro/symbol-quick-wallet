"""Namespace-related modal screens for Symbol Quick Wallet."""

from typing import Any, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from src.shared.logging import get_logger

logger = get_logger(__name__)


class BaseModalScreen(ModalScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("tab", "action_focus_next", "Next"),
        ("shift+tab", "action_focus_previous", "Previous"),
    ]


class RegisterRootNamespaceScreen(BaseModalScreen):
    def __init__(self, rental_fees: dict[str, Any] | None = None):
        super().__init__()
        self.rental_fees = rental_fees or {}

    def compose(self) -> ComposeResult:
        yield Label("📛 Register Root Namespace")
        yield Label("Name (a-z, 0-9, _, -):")
        yield Input(
            placeholder="mynamespace",
            id="name-input",
        )
        yield Label("Duration (days, 30-1825):")
        yield Input(
            placeholder="365",
            id="duration-input",
            type="integer",
            value="365",
        )
        yield Label("", id="cost-label")
        yield Label(
            "⚠️ Namespace rental requires XYM for the rental fee plus network fees."
        )
        yield Horizontal(
            Button("✓ Register", id="register-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_mount(self) -> None:
        self._update_cost_estimate()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in ("name-input", "duration-input"):
            self._update_cost_estimate()

    def _update_cost_estimate(self) -> None:
        duration_input = cast(Input, self.query_one("#duration-input"))
        try:
            duration = int(duration_input.value or "0")
            if duration < 30:
                cost_text = "Minimum duration is 30 days"
            elif duration > 1825:
                cost_text = "Maximum duration is 1825 days"
            else:
                root_fee_365d = self.rental_fees.get("root_fee_365d_xym", 0)
                estimated_cost = root_fee_365d * (duration / 365)
                cost_text = f"Estimated cost: ~{estimated_cost:.2f} XYM (rental) + ~0.05 XYM (network)"
        except ValueError:
            cost_text = "Invalid duration"

        cost_label = cast(Label, self.query_one("#cost-label"))
        cost_label.update(cost_text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "register-button":
            name_input = cast(Input, self.query_one("#name-input"))
            duration_input = cast(Input, self.query_one("#duration-input"))
            name = name_input.value.strip()
            duration = duration_input.value.strip()

            if name and duration:
                try:
                    self.post_message(
                        RegisterRootNamespaceSubmitted(
                            name=name.lower(),
                            duration_days=int(duration),
                        )
                    )
                    self.app.pop_screen()
                except ValueError:
                    self.notify("Invalid duration", severity="error")
        elif event.button.id == "cancel-button":
            self.app.pop_screen()


class RegisterRootNamespaceSubmitted(Message):
    def __init__(self, name: str, duration_days: int):
        super().__init__()
        self.name = name
        self.duration_days = duration_days


class RegisterSubNamespaceScreen(BaseModalScreen):
    def __init__(self, parent_namespaces: list[str] | None = None):
        super().__init__()
        self.parent_namespaces = parent_namespaces or []

    def compose(self) -> ComposeResult:
        yield Label("📛 Register Sub-Namespace")
        yield Label("Parent namespace (e.g., mynamespace):")
        yield Input(
            placeholder="parent",
            id="parent-input",
        )
        yield Label("Sub-namespace name (a-z, 0-9, _, -):")
        yield Input(
            placeholder="subname",
            id="name-input",
        )
        yield Label("💡 Sub-namespaces cost ~10 XYM (one-time fee).")
        yield Horizontal(
            Button("✓ Register", id="register-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "register-button":
            parent_input = cast(Input, self.query_one("#parent-input"))
            name_input = cast(Input, self.query_one("#name-input"))
            parent = parent_input.value.strip().lower()
            name = name_input.value.strip().lower()

            if parent and name:
                self.post_message(
                    RegisterSubNamespaceSubmitted(
                        name=name,
                        parent_name=parent,
                    )
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()


class RegisterSubNamespaceSubmitted(Message):
    def __init__(self, name: str, parent_name: str):
        super().__init__()
        self.name = name
        self.parent_name = parent_name


class LinkAddressAliasScreen(BaseModalScreen):
    def __init__(self, namespaces: list[str] | None = None, address: str = ""):
        super().__init__()
        self.namespaces = namespaces or []
        self.default_address = address

    def compose(self) -> ComposeResult:
        yield Label("🔗 Link Namespace to Address")
        yield Label("Namespace name:")
        yield Input(
            placeholder="mynamespace",
            id="namespace-input",
        )
        yield Label("Address to link:")
        yield Input(
            placeholder="Txxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            id="address-input",
            value=self.default_address,
        )
        yield Horizontal(
            Button("✓ Link", id="link-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "link-button":
            namespace_input = cast(Input, self.query_one("#namespace-input"))
            address_input = cast(Input, self.query_one("#address-input"))
            namespace = namespace_input.value.strip().lower()
            address = address_input.value.strip().replace("-", "").upper()

            if namespace and address:
                self.post_message(
                    LinkAddressAliasSubmitted(
                        namespace_name=namespace,
                        address=address,
                    )
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()


class LinkAddressAliasSubmitted(Message):
    def __init__(self, namespace_name: str, address: str):
        super().__init__()
        self.namespace_name = namespace_name
        self.address = address


class LinkMosaicAliasScreen(BaseModalScreen):
    def __init__(self, namespaces: list[str] | None = None, mosaic_id: str = ""):
        super().__init__()
        self.namespaces = namespaces or []
        self.default_mosaic_id = mosaic_id

    def compose(self) -> ComposeResult:
        yield Label("🔗 Link Namespace to Mosaic")
        yield Label("Namespace name:")
        yield Input(
            placeholder="mynamespace.mymosaic",
            id="namespace-input",
        )
        yield Label("Mosaic ID (hex):")
        yield Input(
            placeholder="0x72C0212E67A08BCE",
            id="mosaic-input",
            value=self.default_mosaic_id,
        )
        yield Horizontal(
            Button("✓ Link", id="link-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "link-button":
            namespace_input = cast(Input, self.query_one("#namespace-input"))
            mosaic_input = cast(Input, self.query_one("#mosaic-input"))
            namespace = namespace_input.value.strip().lower()
            mosaic_value = mosaic_input.value.strip().lower()

            if namespace and mosaic_value:
                try:
                    if mosaic_value.startswith("0x"):
                        mosaic_value = mosaic_value[2:]
                    mosaic_id = int(mosaic_value, 16)
                    self.post_message(
                        LinkMosaicAliasSubmitted(
                            namespace_name=namespace,
                            mosaic_id=mosaic_id,
                        )
                    )
                    self.app.pop_screen()
                except ValueError:
                    self.notify("Invalid mosaic ID", severity="error")
        elif event.button.id == "cancel-button":
            self.app.pop_screen()


class LinkMosaicAliasSubmitted(Message):
    def __init__(self, namespace_name: str, mosaic_id: int):
        super().__init__()
        self.namespace_name = namespace_name
        self.mosaic_id = mosaic_id


class NamespaceInfoScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("escape", "app.pop_screen", "Close")]

    def __init__(
        self, namespace_info: dict[str, Any], expiration: dict[str, Any] | None = None
    ):
        super().__init__()
        self.namespace_info = namespace_info
        self.expiration = expiration

    def compose(self) -> ComposeResult:
        info = self.namespace_info
        full_name = info.get("full_name", info.get("name", "Unknown"))

        yield Label(f"📛 Namespace: {full_name}", id="namespace-title")
        yield Static("", id="namespace-content")

        content_lines = [
            f"[bold]Namespace ID:[/bold] {info.get('namespace_id_hex', 'N/A')}",
            f"[bold]Type:[/bold] {'Root' if info.get('is_root') else 'Sub-namespace'}",
            f"[bold]Depth:[/bold] {info.get('depth', 1)}",
            f"[bold]Owner:[/bold] {info.get('owner_address', 'N/A')}",
            f"[bold]Status:[/bold] {'Active' if info.get('active') else 'Inactive'}",
            f"[bold]Start Height:[/bold] {info.get('start_height', 0):,}",
            f"[bold]End Height:[/bold] {info.get('end_height', 0):,}",
        ]

        if self.expiration:
            remaining = self.expiration.get("remaining_days", 0)
            if self.expiration.get("is_expired"):
                content_lines.append("[bold]Expiration:[/bold] [red]EXPIRED[/red]")
            else:
                content_lines.append(f"[bold]Expires in:[/bold] {remaining} days")

        alias_type = info.get("alias_type", 0)
        if alias_type == 2:
            alias_addr = info.get("alias_address", "")
            content_lines.append("")
            content_lines.append("[bold]Linked Address:[/bold]")
            content_lines.append(f"  {alias_addr}")
        elif alias_type == 1:
            mosaic_id_hex = info.get("alias_mosaic_id_hex", "")
            content_lines.append("")
            content_lines.append("[bold]Linked Mosaic:[/bold]")
            content_lines.append(f"  {mosaic_id_hex}")
        else:
            content_lines.append("")
            content_lines.append("[italic]No alias linked[/italic]")

        self._content = "\n".join(content_lines)

        yield Horizontal(
            Button("📋 Copy ID", id="copy-id-button"),
            Button("❌ Close", id="close-button"),
        )

    def on_mount(self) -> None:
        content_widget = cast(Static, self.query_one("#namespace-content"))
        content_widget.update(self._content)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-id-button":
            import pyperclip

            ns_id = self.namespace_info.get("namespace_id_hex", "")
            pyperclip.copy(ns_id)
            self.notify(f"Copied: {ns_id}", severity="information")
        elif event.button.id == "close-button":
            self.app.pop_screen()


class ResolveNamespaceScreen(BaseModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("🔍 Resolve Namespace")
        yield Label("Enter namespace name to resolve:")
        yield Input(
            placeholder="symbol.xym",
            id="namespace-input",
        )
        yield Label("", id="result-label")
        yield Horizontal(
            Button("🔍 Resolve", id="resolve-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "resolve-button":
            namespace_input = cast(Input, self.query_one("#namespace-input"))
            namespace = namespace_input.value.strip().lower()

            if namespace:
                self.post_message(ResolveNamespaceSubmitted(namespace_name=namespace))
        elif event.button.id == "cancel-button":
            self.app.pop_screen()


class ResolveNamespaceSubmitted(Message):
    def __init__(self, namespace_name: str):
        super().__init__()
        self.namespace_name = namespace_name
