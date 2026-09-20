"""Phase 17: computer_control."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_import():
    from core.computer_control import ComputerController, MouseButton, KeyCode, Point, MouseAction, KeyboardAction
    assert ComputerController is not None
    assert MouseButton.LEFT.value == "left"
    assert KeyCode.ENTER.value == "enter"


def test_move_mouse():
    from core.computer_control import ComputerController
    cc = ComputerController()
    r = cc.move_mouse(100, 200)
    assert r["op"] == "move_mouse"
    assert r["params"]["x"] == 100


def test_click():
    from core.computer_control import ComputerController, MouseButton
    cc = ComputerController()
    r = cc.click(100, 200, MouseButton.RIGHT)
    assert r["op"] == "click"
    assert r["params"]["button"] == "right"


def test_dblclick():
    from core.computer_control import ComputerController, MouseButton
    cc = ComputerController()
    r = cc.click(100, 200, MouseButton.LEFT, dbl=True)
    assert r["params"]["double"] is True


def test_scroll():
    from core.computer_control import ComputerController
    cc = ComputerController()
    r = cc.scroll(0, 0, -3)
    assert r["op"] == "scroll"
    assert r["params"]["delta"] == -3


def test_drag():
    from core.computer_control import ComputerController
    cc = ComputerController()
    r = cc.drag(10, 20, 100, 200)
    assert r["op"] == "drag"
    assert r["params"]["from_x"] == 10


def test_type_text():
    from core.computer_control import ComputerController
    cc = ComputerController()
    r = cc.type_text("hello")
    assert r["op"] == "type_text"
    assert r["params"]["text"] == "hello"


def test_press_key():
    from core.computer_control import ComputerController, KeyCode
    cc = ComputerController()
    r = cc.press_key(KeyCode.ENTER, hold_ms=50)
    assert r["op"] == "press_key"
    assert r["params"]["key"] == "enter"


def test_key_combo():
    from core.computer_control import ComputerController
    cc = ComputerController()
    r = cc.key_combo(["ctrl", "c"])
    assert r["op"] == "key_combo"
    assert r["params"]["keys"] == ["ctrl", "c"]


def test_focus_window():
    from core.computer_control import ComputerController
    cc = ComputerController()
    r = cc.focus_window(title="Notepad")
    assert r["op"] == "focus_window"


def test_minimize_maximize_close():
    from core.computer_control import ComputerController
    cc = ComputerController()
    assert cc.minimize_window("app")["op"] == "minimize_window"
    assert cc.maximize_window("app")["op"] == "maximize_window"
    assert cc.close_window("app")["op"] == "close_window"


def test_list_windows():
    from core.computer_control import ComputerController
    cc = ComputerController()
    assert cc.list_windows()["op"] == "list_windows"


def test_clipboard():
    from core.computer_control import ComputerController
    cc = ComputerController()
    assert cc.copy("text")["op"] == "copy"
    assert cc.paste()["op"] == "paste"
    assert cc.cut()["op"] == "cut"
    assert cc.clipboard_get()["op"] == "clipboard_get"


def test_desktop_ops():
    from core.computer_control import ComputerController
    cc = ComputerController()
    assert cc.lock_screen()["op"] == "lock_screen"
    assert cc.shutdown()["op"] == "shutdown"
    assert cc.restart()["op"] == "restart"


def test_launch():
    from core.computer_control import ComputerController
    cc = ComputerController()
    r = cc.launch("notepad")
    assert r["op"] == "launch"


def test_locate_on_screen():
    from core.computer_control import ComputerController
    cc = ComputerController()
    r = cc.locate_on_screen("Settings button")
    assert r["op"] == "locate_on_screen"


def test_log():
    from core.computer_control import ComputerController
    cc = ComputerController()
    cc.click(10, 20)
    cc.type_text("hi")
    log = cc.get_log()
    assert len(log) == 2
    assert log[0]["op"] == "click"
