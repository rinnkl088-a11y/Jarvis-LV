"""
core/autonomy.py — autonomy + recovery (PHASE 11, additive).

RollbackManager, ErrorRecovery, CircuitBreaker,
TaskCheckpointManager. All stdlib, thread-safe,
best-effort (never crashes the caller).
"""
from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
import tempfile


# ── Rollback ─────────────────────────────────────────────────────────
@dataclass
class _RollbackEntry:
    label: str
    undo_detail: str
    at: float = field(default_factory=time.monotonic)


class RollbackManager:
    def __init__(self):
        self._stack: list[_RollbackEntry] = []
        self._lock = threading.Lock()

    def register(self, label: str, undo_detail: str = "") -> None:
        with self._lock:
            self._stack.append(_RollbackEntry(label, undo_detail))

    def rollback(self, label: str) -> dict:
        with self._lock:
            entry = next((e for e in self._stack if e.label == label), None)
            if entry is None:
                return {"ok": False, "error": "not found"}
            detail = entry.undo_detail or f"Rolled back '{label}'"
            self._stack.remove(entry)
            return {"ok": True, "detail": detail}


# ── Error recovery ───────────────────────────────────────────────────
@dataclass
class RecoveryResult:
    ok: bool
    attempts: int = 0
    error: str = ""


class ErrorRecovery:
    def __init__(self, max_retries: int = 3, base_delay_s: float = 0.1):
        self.max = max(0, min(max_retries, 5))
        self.delay = max(0.01, base_delay_s)

    def run_with_retry(self, fn, label: str = "op") -> RecoveryResult:
        last = ""
        for attempt in range(self.max):
            try:
                out = fn()
                return RecoveryResult(ok=True, attempts=attempt + 1)
            except Exception as e:
                last = str(e)[:200]
                if attempt < self.max - 1:
                    time.sleep(self.delay * (2 ** attempt))
        return RecoveryResult(ok=False, attempts=self.max,
                               error=f"{label} exhausted: {last}")


# ── Circuit breaker ──────────────────────────────────────────────────
class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, threshold: int = 3, window_s: float = 60.0,
                 cooldown_s: float = 30.0):
        self.threshold = max(1, threshold)
        self.window = max(1.0, window_s)
        self.cooldown = max(1.0, cooldown_s)
        self._failures: deque[float] = deque()
        self._state = self.CLOSED
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _prune(self) -> None:
        now = time.monotonic()
        cutoff = now - self.window
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    def record_failure(self) -> None:
        with self._lock:
            self._prune()
            self._failures.append(time.monotonic())
            if len(self._failures) >= self.threshold:
                self._state = self.OPEN

    def record_success(self) -> None:
        with self._lock:
            self._prune()
            self._state = self.CLOSED

    def allow(self) -> bool:
        with self._lock:
            if self._state == self.CLOSED:
                return True
            if self._state == self.OPEN:
                # Half-open probe after cooldown.
                self._prune()
                oldest = (self._failures[0] if self._failures else 0)
                if time.monotonic() - oldest >= self.cooldown:
                    self._state = self.HALF_OPEN
                    return True
                return False
            return True  # half_open: allow one probe


# ── Task checkpoints ─────────────────────────────────────────────────
@dataclass
class Checkpoint:
    task_id: str
    status: str
    step: str = ""
    progress: float = 0.0
    notes: str = ""
    at: float = field(default_factory=time.monotonic)


class TaskCheckpointManager:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    def checkpoint(self, task_id: str, status: str, step: str = "",
                   progress: float = 0.0, notes: str = "") -> dict:
        ckpt = {"task_id": task_id, "status": status, "step": step,
                "progress": progress, "notes": notes}
        line = json.dumps(ckpt)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return ckpt

    def load_latest(self, task_id: str) -> dict | None:
        lines = []
        try:
            with open(self._path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            return None
        matches = []
        for line in lines:
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if rec.get("task_id") == task_id:
                matches.append(rec)
        return matches[-1] if matches else None

    def prune(self) -> int:
        seen: set[str] = set()
        kept: list[str] = []
        removed = 0
        try:
            with open(self._path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            return 0
        for line in reversed(lines):
            try:
                rec = json.loads(line)
                tid = rec.get("task_id", "")
                if tid in seen:
                    removed += 1
                    continue
                seen.add(tid)
                kept.append(line)
            except (json.JSONDecodeError, ValueError):
                kept.append(line)
        kept.reverse()
        try:
            self._path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        except OSError:
            pass
        return removed
