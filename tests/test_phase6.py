"""PHASE 6 tests — optimizer. Mocks only, no real system changes."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _snap(cpu=95, ram=50):
    from core.system_agent import SystemSnapshot
    s = SystemSnapshot()
    s.cpu_pct = {"pct": cpu, "cores": 8}
    s.ram = {"pct": ram, "used_gb": 4, "total_gb": 8}
    s.per_process = [{"pid": 1, "name": "Game.exe", "cpu": 60, "ram_mb": 500}]
    s.disk = {"C:": {"pct": 50, "free_gb": 100}}
    return s


def test_diagnose_finds_cpu():
    from core.optimizer import diagnose
    bl = diagnose(_snap())
    assert any(b.kind == "cpu" for b in bl)


def test_plan_separates_risk():
    from core.optimizer import diagnose, plan
    p = plan(diagnose(_snap()))
    assert p.risky_steps  # heavy app close needs confirmation
    assert "confirmation" in __import__("core.optimizer",
                                        fromlist=["preview"]).preview(p).lower()


def test_apply_safe_only_without_confirm():
    from core.optimizer import plan, diagnose, apply
    p = plan(diagnose(_snap()))
    ran = []
    out = apply(p, executor=lambda s: ran.append(s.label) or "did it",
                confirmed=False)
    assert out["pending_confirmation"]  # risky held back
    # safe noop-style steps may run; risky never auto-ran
    assert all("Game.exe" not in d for d in out["done"])


def test_apply_risky_with_confirm_mock():
    from core.optimizer import plan, diagnose, apply
    p = plan(diagnose(_snap()))
    out = apply(p, executor=lambda s: f"closed {s.target}", confirmed=True)
    assert any("Game.exe" in d for d in out["done"])
    assert out["pending_confirmation"] == []


def test_benchmark_reports():
    from core.optimizer import benchmark
    assert "CPU" in benchmark(_snap(90), _snap(40))
    assert "inconclusive" in benchmark(object(), object()).lower()


def test_healthy_system_noop():
    from core.optimizer import diagnose, plan, apply
    s = _snap(cpu=20, ram=30)
    s.per_process = []
    p = plan(diagnose(s))
    out = apply(p, executor=lambda s: "x")
    assert any("nothing to do" in d for d in out["done"])
