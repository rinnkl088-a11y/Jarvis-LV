"""
Email plugin (LV, local-first) — drafts only, no auto-send.

Real Gmail sending stays in actions/send_message.py (gated).
Here: compose a local draft, list drafts. Nothing leaves the machine.
"""
import json
import threading
import time
from pathlib import Path
import sys

PLUGIN = {
    "name": "email_inbox",
    "description": (
        "Email drafts — compose a local draft or list drafts. "
        "Use when the user says draft an email, write an email. "
        "Does NOT send; sending stays a confirmed action elsewhere."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "compose | list"},
            "to": {"type": "STRING", "description": "Recipient (compose)"},
            "subject": {"type": "STRING", "description": "Subject (compose)"},
            "body": {"type": "STRING", "description": "Body (compose)"},
        },
        "required": ["action"],
    },
}


def _file() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "memory" / "email_drafts.json"


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
        if action == "compose":
            to = str(params.get("to", "")).strip()[:120]
            subject = str(params.get("subject", "")).strip()[:120]
            body = str(params.get("body", "")).strip()[:2000]
            if not to or not subject:
                return "Give recipient and subject to compose a draft."
            items.append({"ts": time.time(), "to": to,
                          "subject": subject, "body": body})
            try:
                _file().parent.mkdir(parents=True, exist_ok=True)
                _file().write_text(json.dumps(items[-50:], indent=2),
                                   encoding="utf-8")
            except OSError as e:
                return f"Could not save draft: {e}"
            result = f"Draft saved to {to} — '{subject}'. Not sent."
        else:
            if not items:
                result = "No drafts."
            else:
                result = "\n".join(
                    f"{i+1}. to {e.get('to','')} — {e.get('subject','')}"
                    for i, e in enumerate(items[-10:]))
    if player:
        try:
            player.write_log("JARVIS: email draft updated.")
        except Exception:
            pass
    return result
