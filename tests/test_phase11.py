"""PHASE 11 tests — autonomy + recovery. Mocks only, no real env changes."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_rollback_register_and_apply():
    from core.autonomy import RollbackManager
    rb = RollbackManager()
    rb.register("step1", "undo step1")
    rb.register("step2", "undo step2")
    r = rb.rollback("step1")
    assert r["ok"] is True and "step1" in r.get("detail", "")
    r2 = rb.rollback("step2")
    assert r2["ok"] is True
    assert rb.rollback("ghost")["ok"] is False


def test_error_recovery_retry_success():
    from core.autonomy import ErrorRecovery
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("transient")
        return "ok"

    er = ErrorRecovery(max_retries=2, base_delay_s=0.01)
    result = er.run_with_retry(flaky, "flaky op")
    assert result.ok is True and len(calls) == 2


def test_error_recovery_exhausted():
    from core.autonomy import ErrorRecovery
    er = ErrorRecovery(max_retries=1, base_delay_s=0.01)
    result = er.run_with_retry(lambda: 1 / 0, "doomed")
    assert result.ok is False and "exhausted" in result.error.lower()


def test_circuit_breaker_open():
    from core.autonomy import CircuitBreaker
    cb = CircuitBreaker(threshold=2, window_s=10, cooldown_s=60)
    for _ in range(2):
        cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    cb.record_success()
    assert cb.state == "half_open" or cb.state == "closed"


def test_task_checkpoint_and_resume():
    from core.autonomy import TaskCheckpointManager
    import tempfile, json
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ckpt.jsonl"
        mgr = TaskCheckpointManager(p)
        ckpt = mgr.checkpoint(task_id="T-1", status="RUNNING", step="init",
                               progress=25.0, notes="started")
        loaded = mgr.load_latest("T-1")
        assert loaded is not None and loaded["status"] == "RUNNING"
        loaded2 = mgr.load_latest("T-2")
        assert loaded2 is None
        mgr.prune()
        assert mgr.load_latest("T-1") is not None
