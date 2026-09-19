"""
Home assistant plugin (LV, safe stub).

Lists Tuya/Smart Life devices only when tinytuya + config are present.
Never toggles power without the on-screen CONFIRM gate (core.confirm).
Without configuration it explains setup instead of failing.
"""
from pathlib import Path
import sys

PLUGIN = {
    "name": "home_assistant",
    "description": (
        "Smart home status — list configured Tuya lights/switches. "
        "Use when the user asks about smart lights, home devices. "
        "Power changes always need on-screen confirmation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "status (only read action in this version)"},
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        import tinytuya  # noqa: F401
    except ImportError:
        return ("Smart home is not set up: pip install tinytuya and add "
                "device config. Nothing was changed.")
    # Config lives beside api_keys.json, never committed (see .gitignore).
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    cfg = base / "config" / "tuya.json"
    if not cfg.exists():
        return ("tinytuya is installed but config/tuya.json is missing. "
                "Create it locally (git-ignored). Nothing was changed.")
    return ("Tuya config found. Power toggles need on-screen CONFIRM — "
            "say which device to control and I will ask for confirmation.")
