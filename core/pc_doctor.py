"""
core/pc_doctor.py — PC Doctor diagnostics (PHASE 14, additive).

Extends core/system_agent with root-cause analysis, maintenance
recommendations, and structured health reports. Never invents metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.system_agent import snapshot as _snapshot


class Severity(Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"


@dataclass
class Metric:
    name: str
    value: str
    status: Severity
    unit: str = ""
    detail: str = ""


@dataclass
class RootCause:
    metric: str
    observed: str
    possible_cause: str
    recommended_action: str
    confidence: str = "low"


@dataclass
class MaintenanceItem:
    category: str
    item: str
    size_or_value: str
    risk: Severity
    suggestion: str


@dataclass
class HealthReport:
    timestamp: float = 0.0
    cpu: Metric = field(default_factory=lambda: Metric("CPU", "N/A", Severity.UNAVAILABLE))
    gpu: Metric = field(default_factory=lambda: Metric("GPU", "N/A", Severity.UNAVAILABLE))
    ram: Metric = field(default_factory=lambda: Metric("RAM", "N/A", Severity.UNAVAILABLE))
    disk: Metric = field(default_factory=lambda: Metric("DISK", "N/A", Severity.UNAVAILABLE))
    thermal: Metric = field(default_factory=lambda: Metric("TEMP", "N/A", Severity.UNAVAILABLE))
    network: Metric = field(default_factory=lambda: Metric("NETWORK", "N/A", Severity.UNAVAILABLE))
    root_causes: list[RootCause] = field(default_factory=list)
    maintenance_items: list[MaintenanceItem] = field(default_factory=list)
    summary: str = ""


def _s(val: Any, fallback: str = "N/A") -> str:
    if val is None:
        return fallback
    return str(val)


def diagnose() -> HealthReport:
    s = _snapshot(top_n=0)
    report = HealthReport(timestamp=s.at)

    cpu_val = s.cpu_pct
    if isinstance(cpu_val, dict):
        cpu_pct = cpu_val.get("pct")
    else:
        cpu_pct = cpu_val
    if cpu_pct is not None:
        cp = float(cpu_pct)
        report.cpu = Metric("CPU", _s(cpu_pct), Severity.OK if cp < 80 else (Severity.WARN if cp < 95 else Severity.CRITICAL), "%")
    else:
        report.cpu = Metric("CPU", "N/A", Severity.UNAVAILABLE)

    ram = s.ram
    if ram is not None and "%" in str(ram):
        pct_str = str(ram).replace("%", "").strip()
        pct = int(pct_str) if pct_str.isdigit() else None
        if pct is not None:
            report.ram = Metric("RAM", _s(ram), Severity.OK if pct < 80 else (Severity.WARN if pct < 95 else Severity.CRITICAL), "%")
        else:
            report.ram = Metric("RAM", _s(ram), Severity.OK)
    else:
        report.ram = Metric("RAM", _s(ram), Severity.UNAVAILABLE if ram is None else Severity.OK)

    gpu = s.gpu
    if gpu is not None:
        report.gpu = Metric("GPU", _s(gpu), Severity.OK, "%")
    else:
        report.gpu = Metric("GPU", "N/A", Severity.UNAVAILABLE)

    thermal = s.thermal
    if thermal is not None:
        t_val = str(thermal).replace("°C", "").strip()
        report.thermal = Metric("TEMP", _s(thermal), Severity.OK if str(thermal).startswith("N/A") or (t_val.isdigit() and float(t_val) < 80) else (Severity.WARN if t_val.isdigit() and float(t_val) < 90 else Severity.CRITICAL), "°C")
    else:
        report.thermal = Metric("TEMP", "N/A", Severity.UNAVAILABLE)

    disk = s.disk
    if disk is not None:
        report.disk = Metric("DISK", _s(disk), Severity.OK, "%")
    else:
        report.disk = Metric("DISK", "N/A", Severity.UNAVAILABLE)

    network = s.network
    report.network = Metric("NETWORK", _s(network), Severity.UNAVAILABLE if network is None else Severity.OK)

    # Root causes
    if cpu_pct is not None and float(cpu_pct) > 80:
        high_proc = [p for p in s.per_process if p.get("cpu_pct", 0) > float(cpu_pct) * 0.5] if s.per_process else []
        top = high_proc[:3] if high_proc else []
        top_names = ", ".join(p.get("name", "?") for p in top) if top else "N/A"
        report.root_causes.append(RootCause(
            metric="CPU", observed=f"CPU at {cpu_pct}%",
            possible_cause=f"Top consumers: {top_names}",
            recommended_action="Identify high-CPU process; consider closing or optimizing.",
            confidence="medium" if top else "low"
        ))

    if ram is not None and "%" in str(ram):
        pct_str = str(ram).replace("%", "").strip()
        pct = int(pct_str) if pct_str.isdigit() else None
        if pct is not None and pct > 80:
            high_mem = [p for p in s.per_process if p.get("mem_pct", 0) > pct * 0.3] if s.per_process else []
            top = high_mem[:3] if high_mem else []
            top_names = ", ".join(p.get("name", "?") for p in top) if top else "N/A"
            report.root_causes.append(RootCause(
                metric="RAM", observed=f"RAM at {pct}%",
                possible_cause=f"Top consumers: {top_names}",
                recommended_action="Close unused applications or increase RAM.",
                confidence="medium" if top else "low"
            ))

    if thermal is not None and "°C" in str(thermal):
        t_val = str(thermal).replace("°C", "").strip()
        if t_val.isdigit() and float(t_val) > 85:
            report.root_causes.append(RootCause(
                metric="TEMP", observed=f"Thermal at {thermal}",
                possible_cause="Sustained high temperature likely from CPU/GPU load.",
                recommended_action="Improve airflow; check fans; reduce workload.",
                confidence="medium"
            ))

    if disk is not None and "%" in str(disk):
        d_val = int(str(disk).replace("%", "").strip()) if str(disk).replace("%", "").strip().isdigit() else None
        if d_val is not None and d_val > 90:
            report.root_causes.append(RootCause(
                metric="DISK", observed=f"Disk at {d_val}%",
                possible_cause="Low storage.",
                recommended_action="Free space or expand storage.",
                confidence="high"
            ))

    # Maintenance items
    report.maintenance_items = _maintenance_items(s)

    # Summary
    issues = [rc.metric for rc in report.root_causes]
    if issues:
        report.summary = f"Attention needed: {', '.join(issues)}."
    elif all(m.status == Severity.OK for m in [report.cpu, report.ram, report.gpu, report.disk]):
        report.summary = "System healthy. No issues detected."
    else:
        report.summary = "Partial telemetry available; some metrics unavailable."

    return report


def _maintenance_items(s) -> list[MaintenanceItem]:
    items: list[MaintenanceItem] = []
    # Temporary files hint (generic)
    items.append(MaintenanceItem("Storage", "Temporary files", "varies", Severity.WARN, "Run disk cleanup or manually clear temp folders."))
    if s.per_process:
        top_cpu = sorted(s.per_process, key=lambda p: p.get("cpu_pct", 0), reverse=True)[:3]
        for p in top_cpu:
            if p.get("cpu_pct", 0) > 20:
                items.append(MaintenanceItem("Process", f"High CPU: {p.get('name', '?')}", _s(p.get("cpu_pct")) + "%", Severity.WARN, "Review if this process is needed."))
    return items


def quick_status() -> dict[str, str]:
    s = _snapshot(top_n=0)
    return {
        "cpu": _s(s.cpu_pct, "N/A") + "%",
        "gpu": _s(s.gpu, "N/A") + "%",
        "ram": _s(s.ram, "N/A"),
        "thermal": _s(s.thermal, "N/A"),
        "disk": _s(s.disk, "N/A"),
        "network": _s(s.network, "N/A"),
    }
