"""PHASE 1 tests — mocks/sandbox only. No network, no destructive ops."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_event_bus():
    from core.event_bus import EventBus
    bus = EventBus()
    seen = []
    bus.subscribe("TASK_STARTED", lambda e: seen.append(e.name))
    bus.publish("TASK_STARTED", {"id": "T-1"})
    assert seen == ["TASK_STARTED"]
    assert len(bus.history("TASK_STARTED")) == 1


def test_permissions():
    from core.permissions import classify, requires_confirmation, is_blocked
    assert classify("system_status") == "SAFE"
    assert classify("shutdown_jarvis") == "DESTRUCTIVE"
    assert requires_confirmation("shutdown_jarvis") is True
    assert is_blocked("read", {"file": "config/api_keys.json"}) is True
    assert classify("unknown_tool_xyz") == "SENSITIVE"


def test_task_center():
    from core.task_center import TaskCenter
    c = TaskCenter(max_tasks=10)
    t = c.create("smoke")
    assert t.status == "QUEUED"
    c.update(t.id, status="RUNNING", step="verify", progress=50, tool="doctor")
    assert c.get(t.id).progress == 50
    c.complete(t.id, "ok")
    assert c.get(t.id).status == "COMPLETED"
    c2 = c.create("bad")
    c.fail(c2.id, "boom")
    assert c2.status == "FAILED" or c.get(c2.id).status == "FAILED"


def test_ai_router_offline():
    from core.ai_router import ModelRouter, ProviderConfig
    cfg = ProviderConfig(model="m1", fallback_model="m2", max_retries=0)
    r = ModelRouter(cfg).route("hi")  # no call_fn -> graceful offline
    assert r.ok is False and r.attempts >= 1
    ok = ModelRouter(cfg).route("hi", call_fn=lambda m, p, t: f"reply from {m}")
    assert ok.ok is True and ok.model == "m1"


def test_history_sandbox(tmp_path, monkeypatch):
    import core.history as h
    monkeypatch.setattr(h, "_HISTORY", tmp_path / "history.jsonl")
    h.append("user", "prepare PC for gaming tonight")
    assert len(h.recent(5)) == 1
    assert len(h.search("gaming")) == 1
    assert "gaming" in h.summary_for_prompt().lower()


def test_loaders_still_work():
    from core.action_loader import discover_actions
    from core.plugin_loader import discover_plugins
    ar = discover_actions(ROOT / "actions", reserved_names=set(),
                          logger=lambda m: None)
    assert len(ar.names()) >= 10  # LIV ships 16; never drop below 10
    pr = discover_plugins(ROOT / "plugins", core_tool_names=ar.names(),
                          logger=lambda m: None)
    assert isinstance(pr._plugins, dict)  # zero plugins OK on LIV
