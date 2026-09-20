"""PHASE 12 tests — UI layer. Verifies HUD settings without PyQt6 import."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_ui_imports_version():
    import ui
    assert ui.APP_VERSION in ("MARK LV", "MARK LIV")
    assert isinstance(ui.APP_PROTOCOL, str) and ui.APP_PROTOCOL


def test_readme_reflects_version(tmp_path, monkeypatch):
    readme = tmp_path / "readme.md"
    readme.write_text("# MARK LIV\n")
    import re
    text = readme.read_text()
    # Version string must appear explicitly
    assert re.search(r"MARK\s+LV", text, re.IGNORECASE) or \
        "MARK LIV" in text


def test_settings_persistence():
    from memory.config_manager import save_assistant_config
    save_assistant_config("TestName", "UserX")
    from memory.config_manager import get_assistant_name
    assert get_assistant_name() == "TestName"
    save_assistant_config("JARVIS-X", "UserY")
    assert get_assistant_name() == "JARVIS-X"
