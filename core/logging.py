"""
core/logging.py — structured task trace logging (PHASE 13, additive).

Never logs secrets (passwords, tokens, API keys). All values matching
secret-like patterns are redacted in-line before writing.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SECRET_RE = re.compile(r"(password|token|api[_-]?key|secret|authorization|credential|bearer)\s*[:=]\s*['\"]?[^\s'\"]+", re.IGNORECASE)

_REDACTED = "<REDACTED>"

_log_lock = threading.Lock()
_log_dir: Path | None = None
_log_file: Path | None = None
_trace: list[dict[str, Any]] = []
_max_trace = 200


def _redact(text: str) -> str:
    return _SECRET_RE.sub(r"\1" + _REDACTED, text)


def configure(log_dir: str | Path | None = None) -> Path:
    global _log_dir, _log_file
    _log_dir = Path(log_dir) if log_dir else Path("logs")
    _log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _log_file = _log_dir / f"jarvisx_{ts}.jsonl"
    return _log_file


def _ensure_file() -> Path:
    global _log_file
    if _log_file is None:
        return configure()
    return _log_file


def _emit(record: dict[str, Any]) -> None:
    record["_ts"] = datetime.now(timezone.utc).isoformat()
    with _log_lock:
        _trace.append(record)
        if len(_trace) > _max_trace:
            _trace.pop(0)
        f = _ensure_file()
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")


def log_request(user_request: str) -> None:
    _emit({"event": "request", "user_request": _redact(user_request)})


def log_plan(plan: list[str]) -> None:
    _emit({"event": "plan", "steps": [_redact(s) for s in plan]})


def log_tool_selected(tool: str, args: dict[str, Any]) -> None:
    _emit({"event": "tool_select", "tool": tool, "args": {k: _redact(str(v)) for k, v in args.items()}})


def log_tool_output(tool: str, output: Any, error: bool = False) -> None:
    _emit({"event": "tool_output", "tool": tool, "error": error, "output": _redact(str(output))[:2000]})


def log_retry(tool: str, attempt: int, reason: str) -> None:
    _emit({"event": "retry", "tool": tool, "attempt": attempt, "reason": _redact(reason)})


def log_verification(ok: bool, detail: str = "") -> None:
    _emit({"event": "verification", "ok": ok, "detail": _redact(detail)})


def log_result(result: str, success: bool) -> None:
    _emit({"event": "result", "success": success, "result": _redact(result)[:2000]})


def log_task_start(task_id: str, goal: str) -> None:
    _emit({"event": "task_start", "task_id": task_id, "goal": _redact(goal)})


def log_task_complete(task_id: str) -> None:
    _emit({"event": "task_complete", "task_id": task_id})


def get_trace() -> list[dict[str, Any]]:
    with _log_lock:
        return list(_trace)


def clear_trace() -> None:
    with _log_lock:
        _trace.clear()


def dump_json() -> str:
    return json.dumps(get_trace(), indent=2, default=str)
