"""
core/planner.py — task planner with decomposition, dependency, priority, replanning (PHASE 15).

Provides a Plan with ordered steps, dependency-aware ordering,
priority-based scheduling, and replanning on failure.
"""
from __future__ import annotations

import uuid
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class Priority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class DependencyType(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


@dataclass
class PlanStep:
    id: str
    title: str
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    priority: Priority = Priority.NORMAL
    depends_on: list[str] = field(default_factory=list)
    condition: str = ""
    condition_met: bool = True
    tool_hint: str = ""
    args_hint: dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    max_retries: int = 3
    result: Any = None
    error: str = ""


@dataclass
class Plan:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    created_at: float = field(default_factory=float)
    updated_at: float = field(default_factory=float)
    status: str = "PLANNED"
    replan_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(self, title: str, description: str = "", priority: Priority = Priority.NORMAL, depends_on: list[str] | None = None, tool_hint: str = "", args_hint: dict[str, Any] | None = None, condition: str = "", condition_met: bool = True) -> PlanStep:
        step = PlanStep(
            id=str(uuid.uuid4())[:8], title=title, description=description,
            priority=priority, depends_on=depends_on or [], tool_hint=tool_hint,
            args_hint=args_hint or {}, condition=condition, condition_met=condition_met
        )
        self.steps.append(step)
        self.updated_at = __import__("time").monotonic()
        return step

    def topological_order(self) -> list[PlanStep]:
        by_id = {s.id: s for s in self.steps}
        visited: set[str] = set()
        order: list[PlanStep] = []

        def visit(sid: str) -> None:
            if sid in visited:
                return
            visited.add(sid)
            step = by_id.get(sid)
            if step is None:
                return
            for dep in step.depends_on:
                visit(dep)
            order.append(step)

        for s in self.steps:
            visit(s.id)
        return order

    def ready_steps(self) -> list[PlanStep]:
        ordered = self.topological_order()
        completed_ids = {s.id for s in self.steps if s.status == StepStatus.COMPLETED}
        ready: list[PlanStep] = []
        for step in ordered:
            if step.status == StepStatus.SKIPPED:
                continue
            if step.status != StepStatus.PENDING and step.status != StepStatus.FAILED:
                continue
            if step.status == StepStatus.FAILED and step.retries >= step.max_retries:
                step.status = StepStatus.SKIPPED
                continue
            deps_met = all(dep in completed_ids for dep in step.depends_on)
            if not deps_met:
                step.status = StepStatus.BLOCKED
                continue
            if step.condition and not step.condition_met:
                step.status = StepStatus.SKIPPED
                continue
            ready.append(step)
        ready.sort(key=lambda s: s.priority.value, reverse=True)
        return ready

    def mark_running(self, step_id: str) -> bool:
        for s in self.steps:
            if s.id == step_id and s.status == StepStatus.PENDING:
                s.status = StepStatus.RUNNING
                self.updated_at = __import__("time").monotonic()
                return True
        return False

    def mark_completed(self, step_id: str, result: Any = None) -> bool:
        for s in self.steps:
            if s.id == step_id and s.status in (StepStatus.RUNNING, StepStatus.PENDING):
                s.status = StepStatus.COMPLETED
                s.result = result
                self.updated_at = __import__("time").monotonic()
                return True
        return False

    def mark_failed(self, step_id: str, error: str = "") -> bool:
        for s in self.steps:
            if s.id == step_id and s.status in (StepStatus.RUNNING, StepStatus.PENDING):
                s.status = StepStatus.FAILED
                s.error = error
                self.updated_at = __import__("time").monotonic()
                return True
        return False

    def can_replan(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def replan(self) -> Plan:
        self.replan_count += 1
        self.status = "REPLANNING"
        failed = [s for s in self.steps if s.status == StepStatus.FAILED]
        for s in failed:
            s.status = StepStatus.PENDING
            s.retries += 1
            s.error = ""
            if s.retries > s.max_retries:
                s.status = StepStatus.SKIPPED
        self.status = "PLANNED"
        self.updated_at = __import__("time").monotonic()
        return self

    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED))
        return done / len(self.steps)

    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "steps_total": len(self.steps),
            "steps_completed": sum(1 for s in self.steps if s.status == StepStatus.COMPLETED),
            "steps_failed": sum(1 for s in self.steps if s.status == StepStatus.FAILED),
            "steps_blocked": sum(1 for s in self.steps if s.status == StepStatus.BLOCKED),
            "replan_count": self.replan_count,
            "progress": self.progress(),
            "is_complete": self.is_complete(),
        }


class Planner:
    def __init__(self):
        self._lock = threading.Lock()
        self._plans: dict[str, Plan] = {}

    def create_plan(self, goal: str, steps: list[dict[str, Any]] | None = None) -> Plan:
        plan = Plan(goal=goal)
        if steps:
            for sd in steps:
                plan.add_step(
                    title=sd.get("title", ""), description=sd.get("description", ""),
                    priority=Priority(sd.get("priority", 1)),
                    depends_on=sd.get("depends_on", []),
                    tool_hint=sd.get("tool_hint", ""),
                    args_hint=sd.get("args_hint", {}),
                    condition=sd.get("condition", "")
                )
        with self._lock:
            self._plans[plan.id] = plan
        return plan

    def get_plan(self, plan_id: str) -> Plan | None:
        with self._lock:
            return self._plans.get(plan_id)

    def get_active(self) -> list[Plan]:
        with self._lock:
            return [p for p in self._plans.values() if not p.is_complete()]

    def mark_step(self, plan_id: str, step_id: str, status: StepStatus, result: Any = None, error: str = "") -> bool:
        plan = self.get_plan(plan_id)
        if plan is None:
            return False
        if status == StepStatus.COMPLETED:
            return plan.mark_completed(step_id, result)
        elif status == StepStatus.FAILED:
            return plan.mark_failed(step_id, error)
        elif status == StepStatus.RUNNING:
            return plan.mark_running(step_id)
        return False

    def replan(self, plan_id: str) -> Plan | None:
        plan = self.get_plan(plan_id)
        if plan is None:
            return None
        with self._lock:
            return plan.replan()

    def remove_plan(self, plan_id: str) -> None:
        with self._lock:
            self._plans.pop(plan_id, None)
