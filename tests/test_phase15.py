"""Phase 15: planner — decomposition, dependency, priority, replanning."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_planner_import():
    from core.planner import Planner, Plan, PlanStep, Priority, StepStatus, DependencyType
    assert Planner is not None
    assert Plan is not None
    assert Priority is not None


def test_planner_create_plan():
    from core.planner import Planner
    p = Planner()
    plan = p.create_plan("test goal")
    assert plan.goal == "test goal"
    assert plan.id is not None
    assert plan.is_complete()


def test_planner_add_steps():
    from core.planner import Planner, Priority
    p = Planner()
    plan = p.create_plan("multi-step")
    s1 = plan.add_step("step1", priority=Priority.HIGH)
    s2 = plan.add_step("step2", depends_on=[s1.id], priority=Priority.NORMAL)
    assert len(plan.steps) == 2
    assert s2.depends_on == [s1.id]


def test_topological_order():
    from core.planner import Planner, Priority
    p = Planner()
    plan = p.create_plan("ordered")
    s1 = plan.add_step("first", priority=Priority.NORMAL)
    s2 = plan.add_step("second", depends_on=[s1.id], priority=Priority.NORMAL)
    s3 = plan.add_step("third", depends_on=[s2.id], priority=Priority.NORMAL)
    ordered = plan.topological_order()
    ids = [s.id for s in ordered]
    assert ids.index(s1.id) < ids.index(s2.id)
    assert ids.index(s2.id) < ids.index(s3.id)


def test_ready_steps_respects_dependency():
    from core.planner import Planner, Priority, StepStatus
    p = Planner()
    plan = p.create_plan("deps")
    s1 = plan.add_step("s1", priority=Priority.HIGH)
    s2 = plan.add_step("s2", depends_on=[s1.id], priority=Priority.NORMAL)
    plan.mark_completed(s1.id)
    ready = plan.ready_steps()
    assert any(s.id == s2.id for s in ready)
    assert not any(s.id == s1.id for s in ready)


def test_priority_sorting():
    from core.planner import Planner, Priority
    p = Planner()
    plan = p.create_plan("priority")
    s1 = plan.add_step("low", priority=Priority.LOW)
    s2 = plan.add_step("urgent", priority=Priority.URGENT)
    s3 = plan.add_step("normal", priority=Priority.NORMAL)
    plan.mark_completed(s1.id)
    ready = plan.ready_steps()
    assert ready[0].priority == Priority.URGENT
    assert ready[-1].priority == Priority.NORMAL


def test_mark_running_completed_failed():
    from core.planner import Planner, StepStatus
    p = Planner()
    plan = p.create_plan("lifecycle")
    step = plan.add_step("do something")
    assert plan.mark_running(step.id) is True
    assert step.status == StepStatus.RUNNING
    assert plan.mark_completed(step.id, result="ok") is True
    assert step.status == StepStatus.COMPLETED
    assert step.result == "ok"


def test_mark_failed():
    from core.planner import Planner, StepStatus
    p = Planner()
    plan = p.create_plan("fail")
    step = plan.add_step("may fail")
    plan.mark_running(step.id)
    assert plan.mark_failed(step.id, "oops") is True
    assert step.status == StepStatus.FAILED
    assert step.error == "oops"


def test_replan_resets_failed():
    from core.planner import Planner, StepStatus
    p = Planner()
    plan = p.create_plan("replan")
    step = plan.add_step("retry")
    plan.mark_running(step.id)
    plan.mark_failed(step.id, "error")
    assert plan.can_replan() is True
    assert plan.replan_count == 0
    replanned = plan.replan()
    assert replanned.replan_count == 1
    assert step.status == StepStatus.PENDING
    assert step.retries == 1


def test_replan_max_retries():
    from core.planner import Planner, StepStatus
    p = Planner()
    plan = p.create_plan("max")
    step = plan.add_step("limited")
    step.max_retries = 2
    for _ in range(5):
        plan.mark_running(step.id)
        plan.mark_failed(step.id, "fail")
        plan.replan()
    assert step.retries >= 2
    assert step.status == StepStatus.SKIPPED


def test_progress():
    from core.planner import Planner, StepStatus
    p = Planner()
    plan = p.create_plan("progress")
    s1 = plan.add_step("s1")
    s2 = plan.add_step("s2")
    plan.mark_completed(s1.id)
    assert plan.progress() == 0.5
    plan.mark_completed(s2.id)
    assert plan.progress() == 1.0


def test_is_complete():
    from core.planner import Planner, StepStatus
    p = Planner()
    plan = p.create_plan("complete")
    s1 = plan.add_step("s1")
    s2 = plan.add_step("s2")
    assert plan.is_complete() is False
    plan.mark_completed(s1.id)
    plan.mark_completed(s2.id)
    assert plan.is_complete() is True


def test_plan_summary():
    from core.planner import Planner, StepStatus
    p = Planner()
    plan = p.create_plan("summary")
    s1 = plan.add_step("s1")
    s2 = plan.add_step("s2")
    plan.mark_completed(s1.id)
    summary = plan.summary()
    assert summary["goal"] == "summary"
    assert summary["steps_completed"] == 1
    assert summary["steps_failed"] == 0
    assert summary["progress"] == 0.5
    assert summary["is_complete"] is False


def test_planner_get_active():
    from core.planner import Planner, StepStatus
    p = Planner()
    plan1 = p.create_plan("active1")
    plan1.add_step("s1")
    active = p.get_active()
    assert plan1 in active

    plan2 = p.create_plan("complete")
    s2 = plan2.add_step("s2")
    plan2.mark_completed(s2.id)
    active = p.get_active()
    assert plan2 not in active


def test_planner_remove():
    from core.planner import Planner
    p = Planner()
    plan = p.create_plan("remove me")
    assert p.get_plan(plan.id) is not None
    p.remove_plan(plan.id)
    assert p.get_plan(plan.id) is None


def test_conditional_step_skipped():
    from core.planner import Planner, StepStatus, Priority
    p = Planner()
    plan = p.create_plan("conditional")
    s1 = plan.add_step("conditional step", condition="feature_flag", condition_met=False)
    ready = plan.ready_steps()
    assert not any(s.id == s1.id for s in ready)
    assert s1.status == StepStatus.SKIPPED


def test_plan_topological_order_is_deterministic():
    from core.planner import Planner, Priority
    p = Planner()
    plan = p.create_plan("deterministic")
    s1 = plan.add_step("a")
    s2 = plan.add_step("b", depends_on=[s1.id])
    s3 = plan.add_step("c", depends_on=[s1.id])
    order1 = plan.topological_order()
    order2 = plan.topological_order()
    ids1 = [s.id for s in order1]
    ids2 = [s.id for s in order2]
    assert ids1 == ids2
    assert ids1.index(s1.id) < ids1.index(s2.id)
    assert ids1.index(s1.id) < ids1.index(s3.id)


def test_blocked_steps_not_ready():
    from core.planner import Planner, Priority, StepStatus
    p = Planner()
    plan = p.create_plan("blocked")
    s1 = plan.add_step("s1", priority=Priority.HIGH)
    s2 = plan.add_step("s2", depends_on=["nonexistent"], priority=Priority.NORMAL)
    ready = plan.ready_steps()
    assert any(s.id == s1.id for s in ready)
    assert s2.status == StepStatus.BLOCKED
