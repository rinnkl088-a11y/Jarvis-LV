"""
core/history.py — LV conversation history (additive).

Appends {ts, role, text} to memory/history.jsonl (bounded).
Answers: "yesterday what did we do", "which project", without
loading everything. Stdlib only, thread-safe, capped for 8GB RAM.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
import sys

_MAX_LINES = 500
_MAX_TEXT = 1000


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_HISTORY = _base_dir() / "memory" / "history.jsonl"
_lock = threading.Lock()


def _ensure_parent() -> None:
    try:
        _HISTORY.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def append(role: str, text: str) -> None:
    text = (text or "").strip()[:_MAX_TEXT]
    if not text:
        return
    _ensure_parent()
    rec = {"ts": time.time(), "role": role[:16], "text": text}
    try:
        with _lock:
            with open(_HISTORY, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            _trim_locked()
    except OSError:
        pass


def _trim_locked() -> None:
    try:
        lines = _HISTORY.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > _MAX_LINES:
        try:
            _HISTORY.write_text("\n".join(lines[-_MAX_LINES:]) + "\n",
                                encoding="utf-8")
        except OSError:
            pass


def recent(limit: int = 20) -> list[dict]:
    try:
        lines = _HISTORY.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-max(1, min(limit, 100)):]:
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def search(query: str, limit: int = 10) -> list[dict]:
    q = (query or "").lower().strip()
    if not q:
        return recent(limit)
    hits = [r for r in recent(200) if q in str(r.get("text", "")).lower()]
    return hits[-limit:]


def summary_for_prompt(max_chars: int = 800) -> str:
    items = recent(6)
    if not items:
        return ""
    parts = []
    for r in items:
        role = "User" if r.get("role") == "user" else "JARVIS"
        parts.append(f"{role}: {str(r.get('text',''))[:160]}")
    s = "Recent conversation:\n" + "\n".join(parts)
    return s[-max_chars:]
