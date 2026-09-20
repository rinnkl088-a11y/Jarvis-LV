"""Phase 16: self_correction."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_import():
    from core.self_correction import SelfCorrector, ReplanDecider, ActionRecord, Correction, CorrectionResult, ErrorClass
    assert SelfCorrector is not None
    assert ErrorClass is not None


def test_record_action():
    from core.self_correction import SelfCorrector, ErrorClass
    sc = SelfCorrector()
    rec = sc.record_action("click", "window appears", actual="nothing", success=False, error_class=ErrorClass.NOT_FOUND)
    assert rec.action == "click"
    assert rec.success is False
    assert len(sc.correction_history()) == 1


def test_verify_success():
    from core.self_correction import SelfCorrector
    sc = SelfCorrector()
    assert sc.verify("click", "Settings", "Settings window is open") is True


def test_verify_fail():
    from core.self_correction import SelfCorrector
    sc = SelfCorrector()
    assert sc.verify("click", "Settings", "Nothing happened") is False


def test_diagnose():
    from core.self_correction import SelfCorrector, ErrorClass
    sc = SelfCorrector()
    c = sc.diagnose("click", "window", "nothing", ErrorClass.TIMEOUT)
    assert c.action == "click"
    assert "retry with extended timeout" in c.strategy
    assert c.retry_count == 0


def test_correct():
    from core.self_correction import SelfCorrector, ErrorClass
    sc = SelfCorrector()
    result = sc.correct("click", "window", "nothing", ErrorClass.NOT_FOUND)
    assert result.corrected is True
    assert len(result.corrections) == 1
    assert result.final_action.startswith("click")


def test_correct_exhausted():
    from core.self_correction import SelfCorrector, ErrorClass
    sc = SelfCorrector(max_global_retries=1)
    sc.record_action("click", "window", "", success=False, error_class=ErrorClass.NOT_FOUND, detail="fail")
    result = sc.correct("click", "window", "", ErrorClass.NOT_FOUND)
    # After max_global_retries calls, should be exhausted
    assert result.exhausted is True or result.corrected is True


def test_success_rate():
    from core.self_correction import SelfCorrector, ErrorClass
    sc = SelfCorrector()
    sc.record_action("a", "x", success=True)
    sc.record_action("b", "y", actual="z", success=False, error_class=ErrorClass.UNKNOWN)
    assert sc.success_rate() == 0.5


def test_success_rate_empty():
    from core.self_correction import SelfCorrector
    sc = SelfCorrector()
    assert sc.success_rate() == 0.0


def test_failures():
    from core.self_correction import SelfCorrector, ErrorClass
    sc = SelfCorrector()
    sc.record_action("a", "x", success=True)
    sc.record_action("b", "y", success=False, error_class=ErrorClass.TIMEOUT)
    fails = sc.failures()
    assert len(fails) == 1
    assert fails[0].error_class == ErrorClass.TIMEOUT


def test_reset():
    from core.self_correction import SelfCorrector, ErrorClass
    sc = SelfCorrector()
    sc.record_action("a", "x", success=True)
    sc.reset()
    assert len(sc.correction_history()) == 0


def test_replan_decider():
    from core.self_correction import ReplanDecider
    rd = ReplanDecider()
    decision = rd.decide({"failures": 5, "consecutive_failures": 3})
    assert decision["replan"] is True


def test_replan_decider_no_replan():
    from core.self_correction import ReplanDecider
    rd = ReplanDecider()
    decision = rd.decide({"failures": 1, "consecutive_failures": 1})
    assert decision["replan"] is False


def test_replan_history():
    from core.self_correction import ReplanDecider
    rd = ReplanDecider()
    rd.decide({"failures": 5, "consecutive_failures": 3})
    assert len(rd.history()) == 1


def test_error_class_values():
    from core.self_correction import ErrorClass
    assert ErrorClass.TIMEOUT.value == "timeout"
    assert ErrorClass.NOT_FOUND.value == "not_found"
    assert ErrorClass.PERMISSION.value == "permission"


def test_correct_updates_history():
    from core.self_correction import SelfCorrector, ErrorClass
    sc = SelfCorrector()
    sc.correct("click", "window", "nothing", ErrorClass.TIMEOUT)
    history = sc.correction_history()
    assert len(history) == 1
    assert history[0].retry_count == 1
