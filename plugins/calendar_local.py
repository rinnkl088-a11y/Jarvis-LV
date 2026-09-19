"""
Local calendar plugin (LV) — no OAuth, no network.

Stores events in memory/calendar.json: {date YYYY-MM-DD, time HH:MM, title}.
Actions: add | list | today | remove. All local, undo-friendly message.
"""
import json
import threading
from datetime import date
from pathlib import Path
import sys

PLUGIN = {
    "name": "calendar_local",
    "description": (
        "Local calendar — add, list, show today's events, or remove an event. "
        "Use when the user says add to calendar, my schedule, what is today, "
        "remind me on a date. Fully offline."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "add | list | today | remove"},
            "date": {"type": "STRING",
                     "description": "YYYY-MM-DD (add/list)"},
            "time": {"type": "STRING",
                     "description": "HH:MM 24h (add)"},
            "title": {"type": "STRING",
                      "description": "Event title (add/remove matches substring)"},
        },
        "required": ["action"],
    },
}


def _base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_FILE = _base() / "memory" / "calendar.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def _save(items: list[dict]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(items[-200:], indent=2), encoding="utf-8")


def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "today")).strip().lower()
    with _lock:
        items = _load()
        if action == "add":
            d = str(params.get("date", "")).strip()
            t = str(params.get("time", "")).strip()
            title = str(params.get("title", "")).strip()[:120]
            if not d or not title:
                return "Give date YYYY-MM-DD and title to add."
            items.append({"date": d, "time": t, "title": title})
            items.sort(key=lambda e: (e.get("date", ""), e.get("time", "")))
            try:
                _save(items)
            except OSError as e:
                return f"Could not save calendar: {e}"
            result = f"Added: {d} {t} — {title}."
        elif action == "list":
            d = str(params.get("date", "")).strip()
            sel = [e for e in items if not d or e.get("date") == d] if d else items
            if not sel:
                result = "Calendar is empty." if not d else f"Nothing on {d}."
            else:
                result = "\n".join(
                    f"{e.get('date','')} {e.get('time','')}".strip()
                    + f" — {e.get('title','')}" for e in sel[-20:])
        elif action == "remove":
            title = str(params.get("title", "")).strip().lower()
            if not title:
                return "Give a title substring to remove."
            before = len(items)
            items = [e for e in items
                     if title not in str(e.get("title", "")).lower()]
            removed = before - len(items)
            try:
                _save(items)
            except OSError as e:
                return f"Could not save calendar: {e}"
            result = f"Removed {removed} event(s)." if removed else "No matching event."
        else:  # today
            today = date.today().isoformat()
            sel = [e for e in items if e.get("date") == today]
            if not sel:
                result = f"Nothing scheduled today ({today})."
            else:
                result = f"Today ({today}):\n" + "\n".join(
                    f"{e.get('time','')}".strip() + f" — {e.get('title','')}"
                    for e in sel)
    if player:
        try:
            player.write_log(f"JARVIS: calendar {action} done.")
        except Exception:
            pass
    return result
