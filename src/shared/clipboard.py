from __future__ import annotations

import base64
import os
import sys
from typing import Any, TextIO


def _write_control_sequence(sequence: str, stream: TextIO | None = None) -> bool:
    candidates: list[TextIO] = []
    if stream is not None:
        candidates.append(stream)

    # `sys.__stdout__` is closer to the real terminal than `sys.stdout` in TUI apps.
    if hasattr(sys, "__stdout__") and sys.__stdout__ is not None:
        candidates.append(sys.__stdout__)
    candidates.append(sys.stdout)

    for output in candidates:
        try:
            output.write(sequence)
            output.flush()
            return True
        except Exception:
            continue

    # Final fallback: write directly to the controlling terminal.
    try:
        with open("/dev/tty", "w", encoding="utf-8") as tty:
            tty.write(sequence)
            tty.flush()
            return True
    except Exception:
        return False


def copy_with_osc52(text: str, stream: TextIO | None = None) -> bool:
    if not text:
        return False

    try:
        payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
        osc = f"\x1b]52;c;{payload}\x07"

        # tmux requires DCS passthrough for OSC to reach the outer terminal.
        if os.getenv("TMUX"):
            osc = f"\x1bPtmux;\x1b{osc}\x1b\\"

        return _write_control_sequence(osc, stream=stream)
    except Exception:
        return False


def copy_with_pyperclip(text: str) -> bool:
    if not text:
        return False

    try:
        import pyperclip
    except Exception:
        return False

    try:
        pyperclip.copy(text)
    except Exception:
        return False

    try:
        return pyperclip.paste() == text
    except Exception:
        # Some environments allow copy but not paste. Treat copy as success.
        return True


def copy_text(text: str, prefer_osc52: bool = False) -> dict[str, Any]:
    if prefer_osc52:
        methods = (("osc52", copy_with_osc52), ("pyperclip", copy_with_pyperclip))
    else:
        methods = (("pyperclip", copy_with_pyperclip), ("osc52", copy_with_osc52))

    for method_name, method in methods:
        if method(text):
            return {"success": True, "method": method_name}

    return {"success": False, "method": None}
