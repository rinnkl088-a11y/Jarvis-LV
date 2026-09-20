"""
core/dashboard.py — real-time JARVIS-X dashboard (PHASE 13, additive).

Provides a structured snapshot of the assistant + system state for the
PyQt HUD (ui.py) and the existing FastAPI dashboard (dashboard/server.py).
Reads telemetry best-effort via system_agent; never invents numbers.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class DashboardSnapshot:
    assistant_name: str = "JARVIS-X"
    assistant_online: bool = True
    brain: str = "ONLINE"
    planner: str = "ONLINE"
    vision: str = "ONLINE"
    memory: str = "ONLINE"
    computer: str = "ONLINE"
    browser: str = "ONLINE"
    system: str = "ONLINE"
    active_task: str = ""
    task_status: str = ""
    task_progress: float = 0.0
    cpu: str = "N/A"
    gpu: str = "N/A"
    ram: str = "N/A"
    cpu_temp: str = "N/A"
    gpu_temp: str = "N/A"
    disk: str = "N/A"
    network: str = "N/A"
    at: float = field(default_factory=time.monotonic)


class Dashboard:
    def __init__(self, center=None):
        self._center = center
        self._lock = threading.Lock()
        self._last: DashboardSnapshot = DashboardSnapshot()

    def snapshot(self) -> DashboardSnapshot:
        snap = DashboardSnapshot()
        try:
            from core.task_center import get_center
            c = self._center or get_center()
            acts = c.active()
            if acts:
                t = acts[-1]
                snap.active_task = t.title[:80]
                snap.task_status = t.status
                snap.task_progress = t.progress
        except Exception:
            pass
        try:
            from core.system_agent import snapshot as _sys
            s = _sys(top_n=0)
            snap.cpu = str(s.cpu_pct)
            snap.ram = str(s.ram)
            snap.gpu = str(s.gpu)
            snap.thermal = str(s.thermal)
            snap.disk = str(s.disk)
            snap.cpu_temp = str(s.thermal)
        except Exception:
            pass
        with self._lock:
            self._last = snap
        return snap

    def last(self) -> DashboardSnapshot:
        with self._lock:
            return self._last
