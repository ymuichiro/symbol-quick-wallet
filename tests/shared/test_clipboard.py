import sys
from io import StringIO
from types import SimpleNamespace

import pytest

from src.shared.clipboard import copy_text, copy_with_osc52, copy_with_pyperclip


@pytest.mark.unit
def test_copy_with_osc52_writes_escape_sequence():
    stream = StringIO()
    assert copy_with_osc52("ABC", stream=stream)

    value = stream.getvalue()
    assert value.startswith("\x1b]52;c;")
    assert value.endswith("\x07")


@pytest.mark.unit
def test_copy_with_pyperclip_success(monkeypatch):
    fake_module = SimpleNamespace()
    state = {"value": ""}

    def fake_copy(text):
        state["value"] = text

    def fake_paste():
        return state["value"]

    fake_module.copy = fake_copy
    fake_module.paste = fake_paste
    monkeypatch.setitem(sys.modules, "pyperclip", fake_module)

    assert copy_with_pyperclip("TBGPWGP56HIAUYLNCPEKLSY6FLG3Y7YQZA43NZQ")


@pytest.mark.unit
def test_copy_text_falls_back_to_osc52(monkeypatch):
    monkeypatch.setattr("src.shared.clipboard.copy_with_pyperclip", lambda text: False)
    monkeypatch.setattr("src.shared.clipboard.copy_with_osc52", lambda text: True)

    result = copy_text("ABC")

    assert result["success"] is True
    assert result["method"] == "osc52"


@pytest.mark.unit
def test_copy_text_reports_failure(monkeypatch):
    monkeypatch.setattr("src.shared.clipboard.copy_with_pyperclip", lambda text: False)
    monkeypatch.setattr("src.shared.clipboard.copy_with_osc52", lambda text: False)

    result = copy_text("ABC")

    assert result == {"success": False, "method": None}
