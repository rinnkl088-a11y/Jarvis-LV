"""Configurable proactive system notifications."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Alert:
    category: str
    message: str
    severity: str = "info"


class ProactiveMonitor:
    def __init__(self, enabled: bool = False, notify: Callable[[Alert], None] | None = None):
        self.enabled = enabled
        self.notify = notify
        self.history: list[Alert] = []

    def emit(self, alert: Alert) -> bool:
        if not self.enabled:
            return False
        self.history.append(alert)
        if self.notify:
            self.notify(alert)
        return True

    def inspect(self, *, disk_pct: float | None = None, cpu_temp: float | None = None) -> list[Alert]:
        alerts: list[Alert] = []
        if disk_pct is not None and disk_pct >= 90:
            alerts.append(Alert("disk", "Disk space is almost full.", "warning"))
        if cpu_temp is not None and cpu_temp >= 85:
            alerts.append(Alert("temperature", "CPU temperature is unusually high.", "warning"))
        for alert in alerts:
            self.emit(alert)
        return alerts
