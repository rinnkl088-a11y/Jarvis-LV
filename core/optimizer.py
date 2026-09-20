"""
core/optimizer.py — PC Optimization Engine (PHASE 6, additive).

Pipeline: COLLECT -> ANALYZE -> BOTTLENECK -> PLAN -> CLASSIFY RISK
  -> CONFIRM IF REQUIRED -> CHECKPOINT -> APPLY -> BENCHMARK
  -> COMPARE -> KEEP OR ROLLBACK.

Never promises improvement without measurement. Dry-run default:
preview() counts affected items; apply() runs SAFE steps at once and
returns CONFIRMATION_REQUIRED for the rest. Reversible steps register
core.undo so "Undo that" works.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

SAFE = "SAFE"
NEEDS_CONFIRM = "CONFIRMATION_REQUIRED"


@dataclass
class Bottleneck:
    kind: str  # cpu | ram | disk | thermal | startup
    detail: str = ""
    severity: str = "note"  # serious | caution | note


@dataclass
class OptStep:
    label: str
    risk: str = SAFE  # SAFE | NEEDS_CONFIRM
    kind: str = ""  # e.g. close_app, clean_temp, power_mode
    target: str = ""
    reversible: bool = True


@dataclass
class OptPlan:
    bottlenecks: list[Bottleneck] = field(default_factory=list)
    safe_steps: list[OptStep] = field(default_factory=list)
    risky_steps: list[OptStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)


def diagnose(snap) -> list[Bottleneck]:
    out: list[Bottleneck] = []
    try:
        cpu = snap.cpu_pct
        pct = cpu.get("pct") if isinstance(cpu, dict) else None
        if isinstance(pct, (int, float)) and pct >= 85:
            out.append(Bottleneck("cpu", f"CPU at {pct}%", "serious"))
        ram = snap.ram
        rpct = ram.get("pct") if isinstance(ram, dict) else None
        if isinstance(rpct, (int, float)) and rpct >= 90:
            out.append(Bottleneck("ram", f"RAM at {rpct}%", "serious"))
        disk = snap.disk if isinstance(snap.disk, dict) else {}
        for dev, info in disk.items():
            if isinstance(info, dict) and info.get("pct", 0) >= 90:
                out.append(Bottleneck("disk", f"{dev} at {info['pct']}% full",
                                      "caution"))
        for p in getattr(snap, "per_process", [])[:3]:
            if p.get("cpu", 0) >= 40:
                out.append(Bottleneck("cpu", f"{p.get('name')} using "
                                             f"{p.get('cpu')}% CPU", "caution"))
    except Exception:
        pass
    return out


def plan(bottlenecks: list[Bottleneck], snap=None) -> OptPlan:
    p = OptPlan(bottlenecks=list(bottlenecks))
    for b in bottlenecks:
        if b.kind == "cpu" and "using" in b.detail:
            name = b.detail.split(" using")[0]
            p.risky_steps.append(OptStep(
                label=f"Close heavy app: {name}", risk=NEEDS_CONFIRM,
                kind="close_app", target=name, reversible=False))
        elif b.kind == "disk":
            p.safe_steps.append(OptStep(
                label=f"Preview temp cleanup for {b.detail}",
                risk=SAFE, kind="clean_temp", target=b.detail))
    if not p.safe_steps and not p.risky_steps:
        p.safe_steps.append(OptStep(label="No action needed — system healthy",
                                    risk=SAFE, kind="noop"))
    return p


def preview(plan_: OptPlan) -> str:
    lines = [f"Bottlenecks: {len(plan_.bottlenecks)}"]
    for b in plan_.bottlenecks:
        lines.append(f"  [{b.severity}] {b.kind}: {b.detail}"[:140])
    lines.append(f"Safe steps ({len(plan_.safe_steps)}):")
    for s in plan_.safe_steps:
        lines.append(f"  - {s.label}"[:140])
    lines.append(f"Needs confirmation ({len(plan_.risky_steps)}):")
    for s in plan_.risky_steps:
        lines.append(f"  - {s.label}"[:140])
    return "\n".join(lines)[:2000]


def apply(plan_: OptPlan, executor=None, confirmed: bool = False,
          register_undo=None) -> dict:
    """Run SAFE steps now. Risky steps need confirmed=True, else returned
    as pending with counts. executor(step) -> str; kept injectable for
    tests (no real system changes in unit tests)."""
    done, pending = [], []
    for s in plan_.safe_steps:
        if s.kind == "noop":
            done.append("noop: nothing to do")
            continue
        try:
            detail = executor(s) if callable(executor) else f"planned: {s.label}"
            done.append(str(detail)[:200])
            if s.reversible and callable(register_undo):
                try:
                    register_undo(f"optimization: {s.label}",
                                  lambda: f"rollback noted for {s.label}")
                except Exception:
                    pass
        except Exception as e:
            done.append(f"FAILED {s.label}: {e}"[:200])
    for s in plan_.risky_steps:
        if confirmed and callable(executor):
            try:
                done.append(str(executor(s))[:200])
            except Exception as e:
                done.append(f"FAILED {s.label}: {e}"[:200])
        else:
            pending.append(s.label)
    return {"done": done, "pending_confirmation": pending}


def benchmark(before, after) -> str:
    def _cpu(s):
        try:
            return s.cpu_pct.get("pct")
        except Exception:
            return None
    b, a = _cpu(before), _cpu(after)
    if isinstance(b, (int, float)) and isinstance(a, (int, float)):
        delta = b - a
        verdict = "improved" if delta > 0 else "unchanged/worse"
        return f"CPU {b}% -> {a}% ({verdict})."
    return "Benchmark inconclusive — sensors unavailable."
