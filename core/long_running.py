"""Cancellable long-running task management."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class RunStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LongTask:
    title: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: RunStatus = RunStatus.QUEUED
    progress: float = 0.0
    result: Any = None
    error: str = ""
    created_at: float = field(default_factory=time.time)


class LongTaskManager:
    def __init__(self):
        self._tasks: dict[str, LongTask] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._pause: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self, title: str, fn: Callable[[LongTask, threading.Event, threading.Event], Any]) -> LongTask:
        task = LongTask(title)
        cancel = threading.Event()
        pause = threading.Event()
        with self._lock:
            self._tasks[task.id] = task
            self._cancel[task.id] = cancel
            self._pause[task.id] = pause

        def run() -> None:
            task.status = RunStatus.RUNNING
            try:
                task.result = fn(task, cancel, pause)
                task.status = RunStatus.CANCELLED if cancel.is_set() else RunStatus.COMPLETED
            except Exception as exc:
                task.error = str(exc)
                task.status = RunStatus.FAILED

        thread = threading.Thread(target=run, daemon=True)
        self._threads[task.id] = thread
        thread.start()
        return task

    def pause(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status != RunStatus.RUNNING:
            return False
        self._pause[task_id].set()
        task.status = RunStatus.PAUSED
        return True

    def resume(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status != RunStatus.PAUSED:
            return False
        self._pause[task_id].clear()
        task.status = RunStatus.RUNNING
        return True

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
            return False
        self._cancel[task_id].set()
        return True

    def status(self, task_id: str) -> LongTask | None:
        return self._tasks.get(task_id)

    def all(self) -> list[LongTask]:
        return list(self._tasks.values())
