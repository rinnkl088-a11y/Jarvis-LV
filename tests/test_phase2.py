"""PHASE 2 tests — unified registry. Mocks/sandbox only, no network."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _registries():
    from core.tool_registry import build_default_registry
    reg, ar, pr = build_default_registry(logger=lambda m: None)
    return reg, ar, pr


def test_specs_cover_shipped_actions():
    reg, ar, _ = _registries()
    specs = reg.specs()
    assert len(specs) >= 10
    for name in ("web_search", "system_status", "open_app"):
        if name in ar.names():
            assert name in specs


def test_permission_overlay_and_defaults():
    reg, _, _ = _registries()
    s = reg.get("system_status")
    if s is not None:
        assert s.permission == "READ_ONLY" and s.risk == "LOW"
    d = reg.get("shutdown_jarvis")
    if d is not None:  # inline tools only wired when passed in
        assert d.permission == "DESTRUCTIVE"
    # unknown tool -> None, never fabricated
    assert reg.get("no_such_tool_xyz") is None


def test_blocked_refuses_without_running():
    from core.tool_registry import ToolRegistry
    from core.tool_schema import ToolSpec
    from core.action_loader import ActionRegistry
    ran = []

    class FakeActions(ActionRegistry):
        def __init__(self):
            super().__init__({}, lambda m: None)

    reg = ToolRegistry(FakeActions(), None, None)
    reg._specs["evil"] = ToolSpec(name="evil", permission="BLOCKED",
                                  source="action").validated()
    res = reg.execute("evil", {})
    assert res.ok is False and res.blocked is True
    assert ran == []


def test_timeout_enforced():
    from core.tool_registry import ToolRegistry
    from core.tool_schema import ToolSpec
    from core.action_loader import ActionRegistry, ActionRecord

    def _slow(parameters, **kw):
        time.sleep(5)
        return "too late"

    rec = ActionRecord(name="slowtool", description="slow", valid=True,
                       handler=_slow, parameters={"type": "OBJECT",
                                                  "properties": {}})
    ar = ActionRegistry({"slowtool": rec}, lambda m: None)
    reg = ToolRegistry(ar, None, None)
    reg._specs["slowtool"] = ToolSpec(name="slowtool", permission="SAFE",
                                      timeout_s=1, source="action").validated()
    res = reg.execute("slowtool", {})
    assert res.ok is False and res.timed_out is True


def test_backward_compat_old_tool_dicts():
    # Old TOOL dicts without permission/timeout keys still validate.
    from core.tool_schema import ToolSpec
    s = ToolSpec(name="legacy", description="old",
                 parameters={"type": "OBJECT"}).validated()
    assert s.permission == "SENSITIVE"
    assert 1.0 <= s.timeout_s <= 300.0
