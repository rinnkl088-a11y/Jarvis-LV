"""
3D-printer plugin (LV, local queue only).

Real MQTT printers stay optional (paho-mqtt). Default is a local
print queue in memory/printer_queue.json: queue | list | clear.
Never starts a physical print without on-screen CONFIRM.
"""
import json
import threading
import time
from pathlib import Path
import sys

PLUGIN = {
    "name": "printer_3d",
    "description": (
        "3D-printer queue — queue a file, list queued jobs, or clear the "
        "queue. Use when the user mentions 3D print. Local queue only; "
        "a physical print always needs on-screen confirmation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "queue | list | clear"},
            "file": {"type": "STRING",
                     "description": "Model file (.stl/.3mf/.gcode) for queue"},
        },
        "required": ["action"],
    },
}


def _file() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "memory" / "printer_queue.json"


_lock = threading.Lock()


def _load() -> list[dict]:
    try:
        return json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "list")).strip().lower()
    with _lock:
        items = _load()
        if action == "queue":
            f = str(params.get("file", "")).strip()[:260]
            if not f or not f.lower().endswith((".stl", ".3mf", ".gcode")):
                return "Give a model file (.stl/.3mf/.gcode) to queue."
            items.append({"ts": time.time(), "file": f, "status": "queued"})
            try:
                _file().parent.mkdir(parents=True, exist_ok=True)
                _file().write_text(json.dumps(items[-50:], indent=2),
                                   encoding="utf-8")
            except OSError as e:
                return f"Could not queue: {e}"
            result = (f"Queued {f} locally. Starting a physical print "
                      f"needs on-screen CONFIRM — nothing started.")
        elif action == "clear":
            items = []
            try:
                _file().parent.mkdir(parents=True, exist_ok=True)
                _file().write_text("[]", encoding="utf-8")
            except OSError as e:
                return f"Could not clear: {e}"
            result = "Print queue cleared."
        else:
            if not items:
                result = "Print queue is empty."
            else:
                result = "\n".join(
                    f"{i+1}. {e.get('file','')} [{e.get('status','queued')}]"
                    for i, e in enumerate(items[-10:]))
    if player:
        try:
            player.write_log("JARVIS: printer queue updated.")
        except Exception:
            pass
    return result
