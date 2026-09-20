"""PHASE 3 tests — agent loop. Mocks only, no network, no destructive ops."""
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeResult:
    def __init__(self, ok=True, output="done", error=""):
        self.ok = ok
        self.output = output
        self.error = error


class FakeRegistry:
    def __init__(self, behavior):
        # behavior: tool -> ("ok", output) | ("fail", error) | ("flaky", n)
        self.behavior = behavior
        self.calls = []
        self._flaky = {}

    def specs(self):
        return {t: object() for t in self.behavior}

    def execute(self, name, params=None, ctx=None):
        self.calls.append(name)
        kind = self.behavior.get(name, ("ok", "done"))
        if kind[0] == "ok":
            return FakeResult(True, kind[1])
        if kind[0] == "fail":
            return FakeResult(False, error=kind[1])
        # flaky: fail n times then succeed
        n = self._flaky.get(name, kind[1])
        if n > 0:
            self._flaky[name] = n - 1
            return FakeResult(False, error="transient")
        return FakeResult(True, "recovered")


def _agent(behavior):
    from core.agent import AgentRuntime
    from core.task_center import TaskCenter
    return AgentRuntime(FakeRegistry(behavior), TaskCenter(max_tasks=10))


def _plan(goal, ctx):
    from core.agent import Plan, Step
    if ctx.get("failed_step") is not None:
        return Plan(goal, [Step(tool="backup_tool")])
    return Plan(goal, [Step(tool="step_one"), Step(tool="step_two")])


def test_multistep_success():
    ag = _agent({"step_one": ("ok", "one"), "step_two": ("ok", "two")})
    res = ag.run_goal("do two things", plan_fn=_plan)
    assert res.ok is True and res.steps_taken == 2
    assert res.tools_used == ["step_one", "step_two"]
    assert any("verified" in t for t in res.trace)


def test_retry_then_recover():
    ag = _agent({"step_one": ("flaky", 1), "step_two": ("ok", "two")})
    res = ag.run_goal("flaky task", plan_fn=_plan)
    assert res.ok is True
    assert any("retry" in t for t in res.trace)


def test_graceful_failure():
    ag = _agent({"step_one": ("fail", "broken"), "step_two": ("ok", "two"),
                 "backup_tool": ("fail", "also broken")})
    res = ag.run_goal("doomed", plan_fn=_plan)
    assert res.ok is False and "broken" in res.error or "also broken" in res.error


def test_cancel():
    ag = _agent({"step_one": ("ok", "one"), "step_two": ("ok", "two")})
    t = threading.Thread(target=lambda: ag.run_goal("long", plan_fn=_plan))
    t.start()
    time.sleep(0.1)
    ag.cancel()
    t.join(timeout=10)
    assert ag.status().startswith("Agent is idle")


def test_pause_resume_status():
    ag = _agent({"step_one": ("ok", "one")})
    ag.pause()
    assert "paused" in ag.status()
    ag.resume()
    assert "paused" not in ag.status()
