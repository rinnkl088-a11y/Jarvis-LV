"""
core/tool_metadata.py — permission/risk/timeout overlay for existing tools.

Lets PHASE 2 classify the 16 shipped actions + 8 inline tools WITHOUT
rewriting their files. Explicit TOOL['permission'] wins when present;
otherwise this overlay, otherwise permissions.classify() fallback.
"""
from __future__ import annotations

from core.tool_schema import (READ_ONLY, SAFE, CONFIRM, PRIVILEGED,
                              DESTRUCTIVE, BLOCKED)

# name -> {permission, timeout_s, verify, rollback}
OVERLAY: dict[str, dict] = {
    "system_status": {"permission": READ_ONLY, "timeout_s": 10,
                      "verify": "metrics dict returned"},
    "web_search": {"permission": SAFE, "timeout_s": 60,
                   "verify": "results list non-empty or graceful empty"},
    "weather_report": {"permission": READ_ONLY, "timeout_s": 30},
    "open_app": {"permission": SAFE, "timeout_s": 20,
                 "verify": "process or window appears"},
    "screen_process": {"permission": SAFE, "timeout_s": 30,
                       "verify": "image frame injected that turn"},
    "close_camera": {"permission": SAFE, "timeout_s": 10},
    "save_memory": {"permission": SAFE, "timeout_s": 10,
                    "verify": "key present via recall_memory"},
    "recall_memory": {"permission": READ_ONLY, "timeout_s": 10},
    "undo": {"permission": SAFE, "timeout_s": 15,
             "verify": "undo_last() names the reversed action",
             "rollback": "not applicable (is itself the rollback)"},
    "reminder": {"permission": SAFE, "timeout_s": 30,
                 "verify": "OS scheduler entry exists"},
    "file_controller": {"permission": CONFIRM, "timeout_s": 30,
                        "verify": "file at expected path after op",
                        "rollback": "undo stack when reversible; delete not guaranteed"},
    "file_processor": {"permission": SAFE, "timeout_s": 60},
    "browser_control": {"permission": SAFE, "timeout_s": 60,
                        "verify": "page state re-observed after nav"},
    "computer_control": {"permission": CONFIRM, "timeout_s": 30,
                         "verify": "window/focus state re-observed"},
    "computer_settings": {"permission": CONFIRM, "timeout_s": 30,
                          "verify": "setting re-read after change",
                          "rollback": "undo stack for volume/brightness/dark mode"},
    "youtube_video": {"permission": SAFE, "timeout_s": 30},
    "flight_finder": {"permission": SAFE, "timeout_s": 60},
    "game_updater": {"permission": CONFIRM, "timeout_s": 120,
                     "verify": "launcher reports up to date"},
    "send_message": {"permission": DESTRUCTIVE, "timeout_s": 30,
                     "verify": "provider confirms queued/sent",
                     "rollback": "not guaranteed once sent"},
    "code_helper": {"permission": SAFE, "timeout_s": 60},
    "dev_agent": {"permission": CONFIRM, "timeout_s": 120,
                  "verify": "tests pass after modify",
                  "rollback": "git checkout / undo when available"},
    "desktop_control": {"permission": SAFE, "timeout_s": 30},
    "shutdown_jarvis": {"permission": DESTRUCTIVE, "timeout_s": 10,
                        "rollback": "restart required"},
    "manage_monitor": {"permission": SAFE, "timeout_s": 15},
    "system_monitor": {"permission": READ_ONLY, "timeout_s": 15},
}


def lookup(name: str) -> dict:
    return OVERLAY.get(name, {})
