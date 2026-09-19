"""
core/event_bus.py — lightweight publish/subscribe for JARVIS OS.

UI subscribes instead of every module holding a direct reference.
Thread-safe, bounded history, stdlib only. Importing this must never
pull Qt, audio, or network packages.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable

# Canonical event names (PHASE 15)
AI_STARTED = "AI_STARTED"
AI_COMPLETED = "AI_COMPLETED"
VOICE_STARTED = "VOICE_STARTED"
VOICE_STOPPED = "VOICE_STOPPED"
TASK_STARTED = "TASK_STARTED"
TASK_PROGRESS = "TASK_PROGRESS"
TASK_COMPLETED = "TASK_COMPLETED"
TOOL_STARTED = "TOOL_STARTED"
TOOL_COMPLETED = "TOOL_COMPLETED"
ERROR = "ERROR"
SYSTEM_WARNING = "SYSTEM_WARNING"
PLUGIN_LOADED = "PLUGIN_LOADED"

_MAX_HISTORY = 100


@dataclass
class Event:
    name: str
    payload: dict = field(default_factory=dict)
    at: float = field(default_factory=time.monotonic)


class EventBus:
    def __init__(self, max_history: int = _MAX_HISTORY):
        self._subs: dict[str, list[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._history: deque[Event] = deque(maxlen=max_history)

    def subscribe(self, name: str, fn: Callable[[Event], None]) -> None:
        if not callable(fn):
            return
        with self._lock:
            if fn not in self._subs[name]:
                self._subs[name].append(fn)

    def unsubscribe(self, name: str, fn: Callable[[Event], None]) -> None:
        with self._lock:
            try:
                self._subs[name].remove(fn)
            except ValueError:
                pass

    def publish(self, name: str, payload: dict | None = None) -> Event:
        ev = Event(name=name, payload=dict(payload or {}))
        with self._lock:
            subs = list(self._subs.get(name, []))
            self._history.append(ev)
        for fn in subs:
            try:
                fn(ev)
            except Exception as e:
                print(f"[EventBus] subscriber failed for {name}: {e}")
        return ev

    def history(self, name: str | None = None, limit: int = 20) -> list[Event]:
        with self._lock:
            items = list(self._history)
        if name:
            items = [e for e in items if e.name == name]
        return items[-limit:]


# Process-wide default bus. Modules use `get_bus()` so tests can
# construct their own EventBus() without touching global state.
_default_bus: EventBus | None = None
_bus_lock = threading.Lock()


def get_bus() -> EventBus:
    global _default_bus
    with _bus_lock:
        if _default_bus is None:
            _default_bus = EventBus()
        return _default_bus
