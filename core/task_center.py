"""
core/task_center.py — Task management layer (PHASE 4).

Every significant autonomous operation gets: id, title, status,
current step, progress, times, tools used, errors, result.
Bounded (50 tasks) for 8GB RAM targets. Emits EventBus events
best-effort — never crashes the caller if the bus is unavailable.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

QUEUED = "QUEUED"
PLANNING = "PLANNING"
RUNNING = "RUNNING"
WAITING = "WAITING"
RETRYING = "RETRYING"
FAILED = "FAILED"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"

_MAX_TASKS = 50


@dataclass
class Task:
    id: str
    title: str
    status: str = QUEUED
    step: str = ""
    progress: float = 0.0  # 0..100
    started_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)
    tools: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    result: str = ""

    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_at


def _emit(name: str, payload: dict) -> None:
    try:
        from core.event_bus import get_bus
        get_bus().publish(name, payload)
    except Exception:
        pass


class TaskCenter:
    def __init__(self, max_tasks: int = _MAX_TASKS):
        self._tasks: dict[str, Task] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self._max = max(10, max_tasks)

    def create(self, title: str) -> Task:
        t = Task(id=f"T-{uuid.uuid4().hex[:8]}", title=title[:120] or "task")
        with self._lock:
            self._tasks[t.id] = t
            self._order.append(t.id)
            while len(self._order) > self._max:
                old = self._order.pop(0)
                self._tasks.pop(old, None)
        _emit("TASK_STARTED", {"id": t.id, "title": t.title})
        return t

    def update(self, task_id: str, status: str | None = None,
               step: str | None = None, progress: float | None = None,
               tool: str | None = None) -> Task | None:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return None
            if status:
                t.status = status
            if step is not None:
                t.step = step[:200]
            if progress is not None:
                try:
                    t.progress = max(0.0, min(100.0, float(progress)))
                except (TypeError, ValueError):
                    pass
            if tool and tool not in t.tools:
                t.tools.append(tool[:64])
            t.updated_at = time.monotonic()
        _emit("TASK_PROGRESS", {"id": t.id, "status": t.status,
                                "step": t.step, "progress": t.progress})
        return t

    def fail(self, task_id: str, error: str) -> Task | None:
        return self._finish(task_id, FAILED, error=error)

    def complete(self, task_id: str, result: str = "") -> Task | None:
        return self._finish(task_id, COMPLETED, result=result)

    def cancel(self, task_id: str) -> Task | None:
        return self._finish(task_id, CANCELLED)

    def _finish(self, task_id: str, status: str, result: str = "",
                error: str = "") -> Task | None:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return None
            t.status = status
            if result:
                t.result = result[:2000]
            if error:
                t.errors.append(error[:300])
            t.updated_at = time.monotonic()
            if status == COMPLETED:
                t.progress = 100.0
        _emit("TASK_COMPLETED", {"id": t.id, "status": t.status,
                                 "result": t.result[:200]})
        return t

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def active(self) -> list[Task]:
        with self._lock:
            return [t for t in self._tasks.values()
                    if t.status in (QUEUED, PLANNING, RUNNING, WAITING, RETRYING)]

    def recent(self, limit: int = 10) -> list[Task]:
        with self._lock:
            ids = self._order[-limit:]
            return [self._tasks[i] for i in ids if i in self._tasks]


_default_center: TaskCenter | None = None
_center_lock = threading.Lock()


def get_center() -> TaskCenter:
    global _default_center
    with _center_lock:
        if _default_center is None:
            _default_center = TaskCenter()
        return _default_center
