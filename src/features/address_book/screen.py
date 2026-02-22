"""Address book-related modal screens for Symbol Quick Wallet."""

import logging
from typing import Any, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

logger = logging.getLogger(__name__)


class BaseModalScreen(ModalScreen):
    """Base modal screen with common key bindings."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("tab", "action_focus_next", "Next"),
        ("shift+tab", "action_focus_previous", "Previous"),
    ]


class AddressBookSelectorScreen(BaseModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def __init__(self, addresses, groups=None):
        super().__init__()
        self.addresses = addresses
        self.groups = groups or {}
        self._address_keys = []
        self._filtered_addresses = {}
        self._selected_group_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("📒 Select Address")
        group_options: list[tuple[str, str | None]] = [
            ("(All)", None),
            ("(No Group)", "none"),
        ]
        for gid, ginfo in self.groups.items():
            group_options.append((ginfo.get("name", gid), gid))
        yield Horizontal(
            Label("Filter:"),
            Select(group_options, id="group-filter", value=None),
        )
        yield DataTable(id="selector-table")
        yield Button("❌ Cancel", id="cancel-button")

    def on_mount(self) -> None:
        self._update_table()

    def _update_table(self) -> None:
        table = cast(DataTable, self.query_one("#selector-table"))
        table.clear()
        table.add_column("Name")
        table.add_column("Address")
        table.add_column("Group")

        filtered = {}
        if self._selected_group_id is None:
            filtered = self.addresses
        elif self._selected_group_id == "none":
            filtered = {
                addr: info
                for addr, info in self.addresses.items()
                if not info.get("group_id")
            }
        else:
            filtered = {
                addr: info
                for addr, info in self.addresses.items()
                if info.get("group_id") == self._selected_group_id
            }

        self._address_keys = list(filtered.keys())
        for addr in self._address_keys:
            info = filtered[addr]
            group_id = info.get("group_id")
            group_name = ""
            if group_id and group_id in self.groups:
                group_name = self.groups[group_id].get("name", "")
            table.add_row(info["name"], addr, group_name, key=addr)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "group-filter":
            val = event.value
            if val is None:
                self._selected_group_id = None
            else:
                self._selected_group_id = str(val) if val else None
            self._update_table()

    def _get_selected_address(self) -> str | None:
        table = cast(DataTable, self.query_one("#address-book-table"))
        cursor_row = table.cursor_row
        if cursor_row is None:
            return None

        try:
            get_row_at = getattr(table, "get_row_at", None)
            if callable(get_row_at):
                selected = get_row_at(cursor_row)
            else:
                if 0 <= cursor_row < len(self._address_keys):
                    selected = table.get_row(self._address_keys[cursor_row])
                else:
                    selected = None
        except Exception:
            selected = None

        if selected and len(selected) >= 2:
            return selected[1]

        if 0 <= cursor_row < len(self._address_keys):
            return self._address_keys[cursor_row]
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-button":
            address = self._get_selected_address()
            if address:
                self.post_message(self.SendToAddress(address=address))
                self.app.pop_screen()
        elif event.button.id == "edit-button":
            address = self._get_selected_address()
            if address:
                info = self.addresses[address]
                self.post_message(
                    self.EditAddress(
                        address=address,
                        name=info["name"],
                        note=info.get("note", ""),
                        group_id=info.get("group_id"),
                    )
                )
        elif event.button.id == "delete-button":
            address = self._get_selected_address()
            if address:
                self.post_message(self.DeleteAddress(address=address))
        elif event.button.id == "groups-button":
            self.post_message(self.ManageGroups())
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class SendToAddress(Message):
        def __init__(self, address):
            super().__init__()
            self.address = address

    class EditAddress(Message):
        def __init__(self, address, name, note, group_id=None):
            super().__init__()
            self.address = address
            self.name = name
            self.note = note
            self.group_id = group_id

    class DeleteAddress(Message):
        def __init__(self, address):
            super().__init__()
            self.address = address

    class ManageGroups(Message):
        def __init__(self):
            super().__init__()


class EditAddressScreen(BaseModalScreen):
    def __init__(self, address, name, note, groups=None, current_group_id=None):
        super().__init__()
        self.address_value = address
        self.name_value = name
        self.note_value = note
        self.groups = groups or {}
        self.current_group_id = current_group_id

    def compose(self) -> ComposeResult:
        yield Label("✏️ Edit Address")
        yield Label(f"Address: {self.address_value}")
        yield Input(placeholder="Name", id="name-input", value=self.name_value)
        yield Input(
            placeholder="Note (optional)", id="note-input", value=self.note_value
        )
        group_options = [("(No Group)", None)]
        for gid, ginfo in self.groups.items():
            group_options.append((ginfo.get("name", gid), gid))
        yield Label("Group:")
        yield Select(group_options, id="group-select", value=self.current_group_id)
        yield Horizontal(
            Button("✓ Save", id="save-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            name_input = cast(Input, self.query_one("#name-input"))
            note_input = cast(Input, self.query_one("#note-input"))
            group_select = cast(Select, self.query_one("#group-select"))
            name = name_input.value
            note = note_input.value
            group_id = group_select.value
            self.post_message(
                self.EditAddressDialogSubmitted(
                    address=self.address_value, name=name, note=note, group_id=group_id
                )
            )
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class EditAddressDialogSubmitted(Message):
        def __init__(self, address, name, note, group_id=None):
            super().__init__()
            self.address = address
            self.name = name
            self.note = note
            self.group_id = group_id


class AddAddressScreen(BaseModalScreen):
    def __init__(self, groups=None):
        super().__init__()
        self.groups = groups or {}

    def compose(self) -> ComposeResult:
        yield Label("➕ Add to Address Book")
        yield Input(placeholder="Name (Label)", id="name-input")
        yield Input(placeholder="Address", id="address-input")
        yield Input(placeholder="Note (optional)", id="note-input")
        group_options = [("(No Group)", None)]
        for gid, ginfo in self.groups.items():
            group_options.append((ginfo.get("name", gid), gid))
        yield Label("Group:")
        yield Select(group_options, id="group-select", value=None)
        yield Horizontal(
            Button("✓ Save", id="save-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            name_input = cast(Input, self.query_one("#name-input"))
            address_input = cast(Input, self.query_one("#address-input"))
            note_input = cast(Input, self.query_one("#note-input"))
            group_select = cast(Select, self.query_one("#group-select"))
            name = name_input.value
            address = address_input.value
            note = note_input.value
            group_id = group_select.value
            self.post_message(
                self.AddAddressDialogSubmitted(
                    name=name, address=address, note=note, group_id=group_id
                )
            )
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class AddAddressDialogSubmitted(Message):
        def __init__(self, name, address, note="", group_id=None):
            super().__init__()
            self.name = name
            self.address = address
            self.note = note
            self.group_id = group_id


class AddressBookScreen(BaseModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def __init__(self, addresses, groups=None):
        super().__init__()
        self.addresses = addresses
        self.groups = groups or {}
        self._address_keys = list(addresses.keys())
        self._selected_group_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("📒 Address Book")
        group_options: list[tuple[str, str | None]] = [
            ("(All)", None),
            ("(No Group)", "none"),
        ]
        for gid, ginfo in self.groups.items():
            group_options.append((ginfo.get("name", gid), gid))
        yield Horizontal(
            Label("Filter:"),
            Select(group_options, id="group-filter", value=None),
        )
        if not self.addresses:
            yield Label("No addresses in address book")
        else:
            yield DataTable(id="address-book-table")
        yield Horizontal(
            Button("➕ Add", id="add-button", variant="primary"),
            Button("✏️ Edit", id="edit-button"),
            Button("🗑️ Delete", id="delete-button"),
            Button("📁 Groups", id="groups-button"),
            Button("❌ Close", id="close-button"),
        )

    def on_mount(self) -> None:
        if self.addresses:
            self._update_table()

    def _update_table(self) -> None:
        if not self.addresses:
            return
        table = cast(DataTable, self.query_one("#address-book-table"))
        table.clear()
        table.add_column("Name")
        table.add_column("Address")
        table.add_column("Group")
        table.add_column("Note")

        filtered = {}
        if self._selected_group_id is None:
            filtered = self.addresses
        elif self._selected_group_id == "none":
            filtered = {
                addr: info
                for addr, info in self.addresses.items()
                if not info.get("group_id")
            }
        else:
            filtered = {
                addr: info
                for addr, info in self.addresses.items()
                if info.get("group_id") == self._selected_group_id
            }

        self._address_keys = list(filtered.keys())
        for addr in self._address_keys:
            info = filtered[addr]
            group_id = info.get("group_id")
            group_name = ""
            if group_id and group_id in self.groups:
                group_name = self.groups[group_id].get("name", "")
            table.add_row(
                info.get("name", ""),
                addr,
                group_name,
                info.get("note", ""),
                key=addr,
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "group-filter":
            val = event.value
            if val is None:
                self._selected_group_id = None
            else:
                self._selected_group_id = str(val) if val else None
            self._update_table()

    def _get_selected_address(self) -> str | None:
        if not self.addresses:
            return None
        table = cast(DataTable, self.query_one("#address-book-table"))
        cursor_row = table.cursor_row
        if cursor_row is None:
            return None
        if 0 <= cursor_row < len(self._address_keys):
            return self._address_keys[cursor_row]
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-button":
            self.post_message(self.AddAddressRequested())
        elif event.button.id == "edit-button":
            address = self._get_selected_address()
            if address:
                info = self.addresses[address]
                self.post_message(
                    self.EditAddress(
                        address=address,
                        name=info.get("name", ""),
                        note=info.get("note", ""),
                        group_id=info.get("group_id"),
                    )
                )
        elif event.button.id == "delete-button":
            address = self._get_selected_address()
            if address:
                self.post_message(self.DeleteAddress(address=address))
        elif event.button.id == "groups-button":
            self.post_message(self.ManageGroups())
        elif event.button.id == "close-button":
            self.app.pop_screen()

    class AddAddressRequested(Message):
        def __init__(self):
            super().__init__()

    class EditAddress(Message):
        def __init__(self, address, name, note, group_id=None):
            super().__init__()
            self.address = address
            self.name = name
            self.note = note
            self.group_id = group_id

    class DeleteAddress(Message):
        def __init__(self, address):
            super().__init__()
            self.address = address

    class ManageGroups(Message):
        def __init__(self):
            super().__init__()


class ContactGroupsScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("escape", "app.pop_screen", "Close")]

    def __init__(self, groups: dict[str, dict[str, str]]):
        super().__init__()
        self.groups = groups
        self._group_ids = list(groups.keys())

    def compose(self) -> ComposeResult:
        yield Label("📁 Contact Groups")
        if not self.groups:
            yield Label("No groups created yet.")
        else:
            yield DataTable(id="groups-table")
        yield Horizontal(
            Button("➕ Create Group", id="create-button", variant="primary"),
            Button("✏️ Edit", id="edit-button"),
            Button("🗑️ Delete", id="delete-button"),
            Button("❌ Close", id="close-button"),
        )

    def on_mount(self) -> None:
        if not self.groups:
            return
        table = cast(DataTable, self.query_one("#groups-table"))
        table.add_column("Name", key="name")
        table.add_column("ID", key="id")
        for group_id, group_info in self.groups.items():
            table.add_row(group_info.get("name", ""), group_id, key=group_id)

    def _get_selected_group_id(self) -> str | None:
        if not self.groups:
            return None
        table = cast(DataTable, self.query_one("#groups-table"))
        cursor_row = table.cursor_row
        if cursor_row is not None and 0 <= cursor_row < len(self._group_ids):
            return self._group_ids[cursor_row]
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-button":
            self.post_message(self.CreateGroupRequested())
        elif event.button.id == "edit-button":
            group_id = self._get_selected_group_id()
            if group_id:
                group_info = self.groups[group_id]
                self.post_message(
                    self.EditGroupRequested(
                        group_id=group_id,
                        name=group_info.get("name", ""),
                        color=group_info.get("color", ""),
                    )
                )
        elif event.button.id == "delete-button":
            group_id = self._get_selected_group_id()
            if group_id:
                self.post_message(self.DeleteGroupRequested(group_id=group_id))
        elif event.button.id == "close-button":
            self.app.pop_screen()

    class CreateGroupRequested(Message):
        def __init__(self):
            super().__init__()

    class EditGroupRequested(Message):
        def __init__(self, group_id: str, name: str, color: str):
            super().__init__()
            self.group_id = group_id
            self.name = name
            self.color = color

    class DeleteGroupRequested(Message):
        def __init__(self, group_id: str):
            super().__init__()
            self.group_id = group_id


class CreateGroupScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("escape", "app.pop_screen", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Label("➕ Create Contact Group")
        yield Input(placeholder="Group Name", id="name-input")
        yield Horizontal(
            Button("✓ Create", id="create-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-button":
            name_input = cast(Input, self.query_one("#name-input"))
            name = name_input.value.strip()
            if name:
                self.post_message(self.CreateGroupSubmitted(name=name))
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class CreateGroupSubmitted(Message):
        def __init__(self, name: str):
            super().__init__()
            self.name = name


class EditGroupScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("escape", "app.pop_screen", "Cancel")]

    def __init__(self, group_id: str, name: str, color: str = ""):
        super().__init__()
        self.group_id = group_id
        self.group_name = name
        self.group_color = color

    def compose(self) -> ComposeResult:
        yield Label("✏️ Edit Contact Group")
        yield Input(placeholder="Group Name", id="name-input", value=self.group_name)
        yield Horizontal(
            Button("✓ Save", id="save-button", variant="primary"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            name_input = cast(Input, self.query_one("#name-input"))
            name = name_input.value.strip()
            if name:
                self.post_message(
                    self.EditGroupSubmitted(group_id=self.group_id, name=name, color="")
                )
                self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class EditGroupSubmitted(Message):
        def __init__(self, group_id: str, name: str, color: str):
            super().__init__()
            self.group_id = group_id
            self.name = name
            self.color = color


class DeleteGroupConfirmScreen(BaseModalScreen):
    BINDINGS = BaseModalScreen.BINDINGS + [("escape", "app.pop_screen", "Cancel")]

    def __init__(self, group_id: str, group_name: str):
        super().__init__()
        self.group_id = group_id
        self.group_name = group_name

    def compose(self) -> ComposeResult:
        yield Label("🗑️ Delete Group?")
        yield Label(f"Are you sure you want to delete '{self.group_name}'?")
        yield Label("Contacts in this group will be moved to 'No Group'.")
        yield Horizontal(
            Button("🗑️ Delete", id="confirm-button", variant="error"),
            Button("✗ Cancel", id="cancel-button"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-button":
            self.post_message(self.DeleteGroupConfirmed(group_id=self.group_id))
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    class DeleteGroupConfirmed(Message):
        def __init__(self, group_id: str):
            super().__init__()
            self.group_id = group_id
