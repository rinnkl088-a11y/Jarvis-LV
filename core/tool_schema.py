"""
core/tool_schema.py — standardized tool interface (PHASE 2, additive).

Every tool exposes: name, description, input schema, output schema,
permission level, risk, timeout, verification + rollback strategy.
Old TOOL/PLUGIN dicts without these keys keep loading (defaults).
"""
from __future__ import annotations

from dataclasses import dataclass, field

READ_ONLY = "READ_ONLY"
SAFE = "SAFE"
CONFIRM = "CONFIRM"
PRIVILEGED = "PRIVILEGED"
DESTRUCTIVE = "DESTRUCTIVE"
BLOCKED = "BLOCKED"

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
CRITICAL = "CRITICAL"

PERMISSIONS = (READ_ONLY, SAFE, CONFIRM, PRIVILEGED, DESTRUCTIVE, BLOCKED)
RISKS = (LOW, MEDIUM, HIGH, CRITICAL)

DEFAULT_TIMEOUT_S = 30.0


@dataclass
class ToolSpec:
    name: str
    description: str = ""
    parameters: dict = field(default_factory=lambda: {"type": "OBJECT",
                                                      "properties": {}})
    permission: str = "SENSITIVE"
    risk: str = MEDIUM
    timeout_s: float = DEFAULT_TIMEOUT_S
    verify: str = ""
    rollback: str = ""
    source: str = "action"  # action | plugin | inline

    def validated(self) -> "ToolSpec":
        if self.permission not in PERMISSIONS and self.permission != "SENSITIVE":
            self.permission = "SENSITIVE"
        if self.risk not in RISKS:
            self.risk = MEDIUM
        try:
            self.timeout_s = max(1.0, min(300.0, float(self.timeout_s)))
        except (TypeError, ValueError):
            self.timeout_s = DEFAULT_TIMEOUT_S
        if not isinstance(self.parameters, dict) or \
                self.parameters.get("type") != "OBJECT":
            self.parameters = {"type": "OBJECT", "properties": {}}
        return self


def risk_for_permission(permission: str) -> str:
    return {
        READ_ONLY: LOW,
        SAFE: LOW,
        CONFIRM: HIGH,
        PRIVILEGED: HIGH,
        DESTRUCTIVE: HIGH,
        BLOCKED: CRITICAL,
    }.get(permission, MEDIUM)
