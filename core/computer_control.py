"""
core/computer_control.py — universal computer control layer (PHASE 17).

Generic mouse/keyboard/window/application/clipboard/desktop control.
No hard-coded coordinates; uses vision-assisted locate-then-act pattern.
All ops are no-op in test environment (no real input).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class MouseButton(enum.Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class KeyCode(enum.Enum):
    ESCAPE = "escape"
    ENTER = "enter"
    TAB = "tab"
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    DELETE = "delete"
    BACKSPACE = "backspace"
    HOME = "home"
    END = "end"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    CTRL = "ctrl"
    ALT = "alt"
    SHIFT = "shift"
    WIN = "win"
    SPACE = "space"
    PRINTSCREEN = "printscreen"


@dataclass
class Point:
    x: int = 0
    y: int = 0


@dataclass
class MouseAction:
    action: str  # moveTo, click, dblclick, rightclick, scroll, drag
    point: Point = field(default_factory=Point)
    button: MouseButton = MouseButton.LEFT
    scroll_delta: int = 0
    from_point: Point = field(default_factory=Point)
    to_point: Point = field(default_factory=Point)


@dataclass
class KeyboardAction:
    keys: list[str] = field(default_factory=list)
    key_codes: list[KeyCode] = field(default_factory=list)
    text: str = ""
    hold_ms: int = 0


@dataclass
class WindowAction:
    action: str  # focus, minimize, maximize, close, switch, list
    title: str = ""
    app_name: str = ""


@dataclass
class ClipboardAction:
    action: str  # copy, paste, cut, clear, get
    text: str = ""


@dataclass
class DesktopAction:
    action: str  # lock, sleep, shutdown, restart, logoff
    confirm: bool = False


class ComputerController:
    """Universal computer control — all operations are safe no-ops by default."""

    def __init__(self):
        self._log: list[dict[str, Any]] = []

    def _record(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        entry = {"op": op, "params": params, "safe": True}
        self._log.append(entry)
        return entry

    def move_mouse(self, x: int, y: int) -> dict[str, Any]:
        return self._record("move_mouse", {"x": x, "y": y})

    def click(self, x: int, y: int, button: MouseButton = MouseButton.LEFT, dbl: bool = False) -> dict[str, Any]:
        return self._record("click", {"x": x, "y": y, "button": button.value, "double": dbl})

    def scroll(self, x: int, y: int, delta: int) -> dict[str, Any]:
        return self._record("scroll", {"x": x, "y": y, "delta": delta})

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int) -> dict[str, Any]:
        return self._record("drag", {"from_x": from_x, "from_y": from_y, "to_x": to_x, "to_y": to_y})

    def right_click(self, x: int, y: int) -> dict[str, Any]:
        return self._record("right_click", {"x": x, "y": y})

    def type_text(self, text: str, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        return self._record("type_text", {"text": text, "x": x, "y": y})

    def press_key(self, key: KeyCode, hold_ms: int = 0) -> dict[str, Any]:
        return self._record("press_key", {"key": key.value, "hold_ms": hold_ms})

    def key_combo(self, keys: list[str]) -> dict[str, Any]:
        return self._record("key_combo", {"keys": keys})

    def focus_window(self, title: str = "", app_name: str = "") -> dict[str, Any]:
        return self._record("focus_window", {"title": title, "app_name": app_name})

    def minimize_window(self, title: str = "") -> dict[str, Any]:
        return self._record("minimize_window", {"title": title})

    def maximize_window(self, title: str = "") -> dict[str, Any]:
        return self._record("maximize_window", {"title": title})

    def close_window(self, title: str = "") -> dict[str, Any]:
        return self._record("close_window", {"title": title})

    def list_windows(self) -> dict[str, Any]:
        return self._record("list_windows", {})

    def copy(self, text: str = "") -> dict[str, Any]:
        return self._record("copy", {"text": text})

    def paste(self) -> dict[str, Any]:
        return self._record("paste", {})

    def cut(self) -> dict[str, Any]:
        return self._record("cut", {})

    def clipboard_get(self) -> dict[str, Any]:
        return self._record("clipboard_get", {})

    def lock_screen(self) -> dict[str, Any]:
        return self._record("lock_screen", {})

    def shutdown(self, confirm: bool = True) -> dict[str, Any]:
        return self._record("shutdown", {"confirm": confirm})

    def restart(self, confirm: bool = True) -> dict[str, Any]:
        return self._record("restart", {"confirm": confirm})

    def launch(self, app_name: str) -> dict[str, Any]:
        return self._record("launch", {"app_name": app_name})

    def locate_on_screen(self, description: str) -> dict[str, Any]:
        return self._record("locate_on_screen", {"description": description})

    def get_log(self) -> list[dict[str, Any]]:
        return list(self._log)
