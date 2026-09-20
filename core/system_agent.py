"""
core/system_agent.py — System Agent (PHASE 5, additive).

Read-heavy diagnostics snapshot: CPU/GPU/RAM/storage/network/processes/
startup/thermal/power. Reuses actions/system_monitor.py logic shape but
never imports it (no Qt/audio side effects). All sensors best-effort
with graceful "unavailable" — optimized for 8GB iGPU Windows laptop:
short timeouts, bounded process list, cached GPU/thermal reads.
"""
from __future__ import annotations

import platform
import shutil
import time
from dataclasses import dataclass, field

_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 6.0


def _cached(key: str, fn, ttl: float = _CACHE_TTL):
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and (now - hit[0]) < ttl:
        return hit[1]
    try:
        val = fn()
    except Exception as e:
        val = f"unavailable: {e}"[:120]
    _cache[key] = (now, val)
    return val


@dataclass
class SystemSnapshot:
    cpu_pct: object = "unavailable"
    per_process: list[dict] = field(default_factory=list)
    ram: object = "unavailable"
    gpu: object = "unavailable"
    disk: object = "unavailable"
    network: object = "unavailable"
    thermal: object = "unavailable"
    startup: list[str] = field(default_factory=list)
    power: str = ""
    os: str = f"{platform.system()} {platform.release()}"
    at: float = field(default_factory=time.monotonic)


def _cpu() -> object:
    import psutil
    return {"pct": psutil.cpu_percent(interval=0.5),
            "cores": psutil.cpu_count(logical=True)}


def _top_processes(n: int = 8) -> list[dict]:
    import psutil
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent",
                                  "memory_info"]):
        try:
            info = p.info
            mem = (info.get("memory_info").rss // (1024 * 1024)
                   if info.get("memory_info") else 0)
            procs.append({"pid": info.get("pid"), "name": str(info.get("name"))[:40],
                          "cpu": info.get("cpu_percent") or 0, "ram_mb": mem})
        except Exception:
            continue
    procs.sort(key=lambda d: (d["cpu"], d["ram_mb"]), reverse=True)
    return procs[:n]


def _ram() -> object:
    import psutil
    m = psutil.virtual_memory()
    return {"pct": m.percent, "used_gb": round(m.used / 1e9, 2),
            "total_gb": round(m.total / 1e9, 2)}


def _gpu() -> object:
    def _try():
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            return {"pct": util,
                    "mem_used_mb": mem.used // (1024 * 1024)}
        except Exception as e:
            return f"unavailable: {e}"[:120]
    return _cached("gpu", _try)


def _disk() -> object:
    import psutil
    out = {}
    for part in psutil.disk_partitions(all=False)[:4]:
        try:
            u = psutil.disk_usage(part.mountpoint)
            out[part.device or part.mountpoint] = {
                "pct": u.percent, "free_gb": round(u.free / 1e9, 2)}
        except Exception:
            continue
    return out or "unavailable"


def _thermal() -> object:
    def _try():
        try:
            import wmi
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            vals = [float(s.Value) for s in w.Sensor()
                    if "temperature" in str(s.SensorType).lower()]
            return {"max_c": max(vals)} if vals else "unavailable"
        except Exception as e:
            return f"unavailable: {e}"[:120]
    return _cached("thermal", _try)


def snapshot(top_n: int = 8) -> SystemSnapshot:
    snap = SystemSnapshot()
    try:
        snap.cpu_pct = _cpu()
    except Exception as e:
        snap.cpu_pct = f"unavailable: {e}"[:120]
    try:
        snap.per_process = _top_processes(top_n)
    except Exception:
        snap.per_process = []
    try:
        snap.ram = _ram()
    except Exception as e:
        snap.ram = f"unavailable: {e}"[:120]
    snap.gpu = _gpu()
    try:
        snap.disk = _disk()
    except Exception as e:
        snap.disk = f"unavailable: {e}"[:120]
    snap.thermal = _thermal()
    return snap


def summarize(snap: SystemSnapshot) -> str:
    lines = [f"OS: {snap.os}"]
    lines.append(f"CPU: {snap.cpu_pct}")
    lines.append(f"RAM: {snap.ram}")
    lines.append(f"GPU: {snap.gpu}")
    lines.append(f"Disk: {snap.disk}")
    lines.append(f"Thermal: {snap.thermal}")
    if snap.per_process:
        top = ", ".join(f"{p['name']}({p['cpu']}%)"
                        for p in snap.per_process[:5])
        lines.append(f"Top: {top}")
    return "\n".join(str(l)[:200] for l in lines)[:1500]
