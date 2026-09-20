"""
core/self_correction.py — closed-loop self-correction engine (PHASE 16).

Implements ACTION → OBSERVE → COMPARE → SUCCESS? → DIAGNOSE → REPLAN → RETRY
with bounded retries and structured error classification.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorClass(Enum):
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    PERMISSION = "permission"
    INSTRUCTION = "instruction"
    ENV = "environment"
    UNKNOWN = "unknown"


@dataclass
class ActionRecord:
    action: str
    expected: str
    actual: str = ""
    success: bool = False
    error_class: ErrorClass = ErrorClass.UNKNOWN
    retry_count: int = 0
    max_retries: int = 3
    timestamp: float = field(default_factory=time.monotonic)
    detail: str = ""


@dataclass
class Correction:
    action: str
    strategy: str
    reason: str
    retry_count: int = 0


@dataclass
class CorrectionResult:
    corrected: bool
    corrections: list[Correction] = field(default_factory=list)
    exhausted: bool = False
    final_action: str = ""


class SelfCorrector:
    def __init__(self, max_global_retries: int = 10):
        self._history: list[ActionRecord] = []
        self._max_global = max_global_retries

    def record_action(self, action: str, expected: str, actual: str = "", success: bool = False, error_class: ErrorClass | None = None, detail: str = "") -> ActionRecord:
        rec = ActionRecord(
            action=action, expected=expected, actual=actual,
            success=success,
            error_class=error_class or ErrorClass.UNKNOWN,
            detail=detail
        )
        self._history.append(rec)
        return rec

    def diagnose(self, action: str, expected: str, actual: str, error_class: ErrorClass | None = None) -> Correction:
        ec = error_class or ErrorClass.UNKNOWN
        strategies: dict[ErrorClass, str] = {
            ErrorClass.TIMEOUT: "retry with extended timeout",
            ErrorClass.NOT_FOUND: "search for alternative target or use fallback",
            ErrorClass.PERMISSION: "request user confirmation or use safe alternative",
            ErrorClass.INSTRUCTION: "clarify intent with user",
            ErrorClass.ENV: "check environment and retry",
            ErrorClass.UNKNOWN: "inspect result and replan",
        }
        strategy = strategies.get(ec, "inspect and replan")
        return Correction(
            action=action, strategy=strategy,
            reason=f"Action '{action}' failed: expected '{expected}', got '{actual}'",
            retry_count=0
        )

    def correct(self, action: str, expected: str, actual: str = "", error_class: ErrorClass | None = None) -> CorrectionResult:
        correction = self.diagnose(action, expected, actual, error_class)
        rec = self.record_action(action, expected, actual, success=False, error_class=error_class or ErrorClass.UNKNOWN, detail=correction.reason)
        result = CorrectionResult(corrected=False, corrections=[correction])

        if rec.retry_count < rec.max_retries:
            rec.retry_count += 1
            result.corrected = True
            result.corrections[0].retry_count = rec.retry_count
            result.final_action = f"{action} (retry {rec.retry_count})"
        else:
            result.exhausted = True
            result.final_action = action

        return result

    def verify(self, action: str, expected: str, actual: str) -> bool:
        success = expected.lower() in actual.lower() if actual else False
        self.record_action(action, expected, actual, success=success)
        return success

    def correction_history(self) -> list[ActionRecord]:
        return list(self._history)

    def failures(self) -> list[ActionRecord]:
        return [r for r in self._history if not r.success]

    def success_rate(self) -> float:
        if not self._history:
            return 0.0
        return sum(1 for r in self._history if r.success) / len(self._history)

    def reset(self) -> None:
        self._history.clear()


class ReplanDecider:
    def __init__(self):
        self._replan_history: list[dict[str, Any]] = []

    def should_replan(self, failure_count: int, consecutive_failures: int) -> bool:
        if consecutive_failures >= 3:
            return True
        if failure_count >= 5:
            return True
        return False

    def decide(self, task_result: dict[str, Any]) -> dict[str, Any]:
        failures = task_result.get("failures", 0)
        consecutive = task_result.get("consecutive_failures", 0)
        if self.should_replan(failures, consecutive):
            decision = {"replan": True, "reason": f"failures={failures}, consecutive={consecutive}"}
        else:
            decision = {"replan": False, "reason": "within acceptable limits"}
        self._replan_history.append(decision)
        return decision

    def history(self) -> list[dict[str, Any]]:
        return list(self._replan_history)
