"""PHASE 5 tests — system snapshot. Real sensors allowed, all guarded."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_snapshot_never_raises():
    from core.system_agent import snapshot, summarize
    snap = snapshot(top_n=4)
    assert snap.os
    text = summarize(snap)
    assert "CPU" in text and "RAM" in text


def test_snapshot_bounded():
    from core.system_agent import snapshot
    snap = snapshot(top_n=3)
    assert len(snap.per_process) <= 3


def test_gpu_thermal_graceful():
    from core.system_agent import _gpu, _thermal
    # Must return something printable, never raise.
    assert _gpu() is not None
    assert _thermal() is not None
