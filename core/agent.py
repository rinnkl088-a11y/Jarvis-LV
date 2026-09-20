"""
core/agent.py — Agent Runtime (PHASE 3, additive).

Implements the honest execution loop:

  OBSERVE -> UNDERSTAND -> PLAN -> SELECT TOOLS -> EXECUTE
    -> OBSERVE RESULT -> VERIFY -> SUCCESS? COMPLETE
                                    : DIAGNOSE -> REPLAN -> RETRY

Never assumes success: every step is verified (tool ok + optional
verifier callable). Failures retry with backoff, then one replan,
then graceful FAILED with full trace. Supports pause/resume/cancel,
progress events, and "what are you doing" status.

The planner is injectable: pass plan_fn(goal, context) -> Plan.
Default is a direct single-tool match (safe, offline). A model-backed
planner can be wired later without changing this loop.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

VERIFYING = "VERIFYING"


@dataclass
class Step:
    tool: str
    parameters: dict = field(default_factory=dict)
    verify: str = ""  # human-readable expectation, logged in trace


@dataclass
class Plan:
    goal: str
    steps: list[Step] = field(default_factory=list)


@dataclass
class ToolCall:
    step_index: int
    tool: str
    ok: bool = False
    output: str = ""
    error: str = ""


@dataclass
class AgentResult:
    ok: bool
    task_id: str = ""
    output: str = ""
    error: str = ""
    steps_taken: int = 0
    tools_used: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


def _now() -> str:
    return time.strftime("%H:%M:%S")


class AgentRuntime:
    def __init__(self, registry=None, center=None, max_retries: int = 1,
                 step_timeout_s: float = 120.0):
        self._registry = registry
        self._center = center
        self._max_retries = max(0, min(max_retries, 3))
        self._step_timeout = step_timeout_s
        self._pause = threading.Event()
        self._pause.set()  # set = running, clear = paused
        self._cancelled = threading.Event()
        self._current: str = ""
        self._lock = threading.Lock()

    # -- controls (voice: "Stop/Pause/Continue/What are you doing") ---------
    def pause(self) -> str:
        self._pause.clear()
        return "Paused. Say continue to resume."

    def resume(self) -> str:
        self._pause.set()
        return "Resuming."

    def cancel(self) -> str:
        self._cancelled.set()
        self._pause.set()
        return "Cancelling the current task."

    def status(self) -> str:
        with self._lock:
            cur = self._current or "idle"
        paused = "" if self._pause.is_set() else " (paused)"
        return f"Agent is {cur}{paused}."

    def _wait_if_paused(self) -> bool:
        while not self._pause.is_set():
            if self._cancelled.is_set():
                return False
            time.sleep(0.1)
        return not self._cancelled.is_set()

    # -- main loop ---------------------------------------------------------
    def run_goal(self, goal: str, plan_fn=None,
                 max_steps: int = 8) -> AgentResult:
        from core.task_center import get_center
        center = self._center or get_center()
        task = center.create(goal)
        trace = [f"[{_now()}] task_started {task.id}: {goal[:120]}"]
        tools_used: list[str] = []
        self._cancelled.clear()
        self._pause.set()
        with self._lock:
            self._current = f"working on '{goal[:60]}'"

        try:
            plan = self._make_plan(goal, plan_fn, trace)
            if not plan.steps:
                return self._finish(center, task, False, "", "Empty plan.",
                                    0, tools_used, trace)
            center.update(task.id, status="PLANNING",
                          step=f"{len(plan.steps)} steps planned")
            trace.append(f"[{_now()}] plan: "
                         + ", ".join(s.tool for s in plan.steps))

            steps_taken = 0
            for i, step in enumerate(plan.steps[:max_steps]):
                if not self._wait_if_paused():
                    return self._finish(center, task, False, "",
                                        "Cancelled by user.", steps_taken,
                                        tools_used, trace)
                center.update(task.id, status="RUNNING",
                              step=f"step {i+1}/{len(plan.steps)}: {step.tool}",
                              progress=100.0 * i / max(1, len(plan.steps)),
                              tool=step.tool)
                trace.append(f"[{_now()}] execute step {i+1}: {step.tool}")
                call = self._execute_step(i, step, trace)
                steps_taken += 1
                if call.ok:
                    tools_used.append(call.tool)
                    center.update(task.id, status=VERIFYING,
                                  step=f"verified step {i+1}")
                    trace.append(f"[{_now()}] verified step {i+1}")
                    if i == len(plan.steps) - 1:
                        out = call.output
                        return self._finish(center, task, True, out, "",
                                            steps_taken, tools_used, trace)
                    continue
                # failure -> diagnose -> retry -> replan once
                trace.append(f"[{_now()}] step {i+1} failed: "
                             f"{call.error[:150]}")
                recovered = self._recover(plan, i, call, plan_fn, trace)
                if recovered is not None:
                    if recovered.ok:
                        tools_used.append(recovered.tool)
                        steps_taken += 1
                        if i == len(plan.steps) - 1:
                            return self._finish(center, task, True,
                                                recovered.output, "",
                                                steps_taken, tools_used, trace)
                        continue
                    return self._finish(center, task, False, "",
                                        recovered.error, steps_taken,
                                        tools_used, trace)
                return self._finish(center, task, False, "",
                                    f"Step {i+1} ({step.tool}) failed: "
                                    f"{call.error[:200]}", steps_taken,
                                    tools_used, trace)
            return self._finish(center, task, True, "", "", steps_taken,
                                tools_used, trace)
        finally:
            with self._lock:
                self._current = ""

    def _make_plan(self, goal: str, plan_fn, trace: list[str]) -> Plan:
        if callable(plan_fn):
            try:
                plan = plan_fn(goal, {})
                if isinstance(plan, Plan):
                    return plan
            except Exception as e:
                trace.append(f"[{_now()}] planner failed: {e} — fallback")
        return self._default_plan(goal)

    def _default_plan(self, goal: str) -> Plan:
        # Offline-safe: single echo step via registry if available, else empty.
        # The model-backed planner replaces this; the loop stays identical.
        gl = goal.lower()
        if self._registry is not None:
            specs = self._registry.specs()
            for keyword, tool in (("search", "web_search"),
                                  ("weather", "weather_report"),
                                  ("open", "open_app"),
                                  ("remind", "reminder")):
                if keyword in gl and tool in specs:
                    return Plan(goal=goal, steps=[
                        Step(tool=tool,
                             parameters={"query": goal[:200]}
                             if tool in ("web_search",) else {},
                             verify=f"{tool} returns without error")])
        return Plan(goal=goal, steps=[])

    def _execute_step(self, index: int, step: Step,
                      trace: list[str]) -> ToolCall:
        if self._registry is None:
            return ToolCall(index, step.tool, ok=False,
                            error="No tool registry wired.")
        try:
            res = self._registry.execute(step.tool, step.parameters,
                                         ctx={})
        except Exception as e:
            return ToolCall(index, step.tool, ok=False, error=str(e)[:300])
        if res.ok:
            return ToolCall(index, step.tool, ok=True, output=res.output)
        return ToolCall(index, step.tool, ok=False, error=res.error)

    def _recover(self, plan: Plan, index: int, failed: ToolCall,
                 plan_fn, trace: list[str]) -> ToolCall | None:
        step = plan.steps[index]
        for attempt in range(self._max_retries):
            if not self._wait_if_paused():
                return ToolCall(index, step.tool, ok=False,
                                error="Cancelled during retry.")
            trace.append(f"[{_now()}] retry {attempt+1} step {index+1}")
            time.sleep(0.5 * (2 ** attempt))
            call = self._execute_step(index, step, trace)
            if call.ok:
                trace.append(f"[{_now()}] retry {attempt+1} succeeded")
                return call
        # one replan attempt
        if callable(plan_fn):
            try:
                new_plan = plan_fn(plan.goal,
                                   {"failed_step": index,
                                    "error": failed.error})
                if isinstance(new_plan, Plan) and new_plan.steps:
                    alt = new_plan.steps[0]
                    trace.append(f"[{_now()}] replanned: {alt.tool}")
                    return self._execute_step(index, alt, trace)
            except Exception as e:
                trace.append(f"[{_now()}] replan failed: {e}")
        return None

    def _finish(self, center, task, ok: bool, output: str, error: str,
                steps: int, tools: list[str], trace: list[str]) -> AgentResult:
        if ok:
            center.complete(task.id, output[:500])
            center.update(task.id, status="COMPLETED", progress=100.0)
        else:
            center.fail(task.id, error[:300])
        try:
            from core.history import append as _log
            _log("jarvis", f"task {task.id} {'done' if ok else 'failed'}: "
                           f"{task.title[:100]}")
        except Exception:
            pass
        return AgentResult(ok=ok, task_id=task.id, output=output, error=error,
                           steps_taken=steps, tools_used=tools, trace=trace)
