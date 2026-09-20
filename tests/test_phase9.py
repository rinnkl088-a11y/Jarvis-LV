"""PHASE 9 tests — layered memory. Sandbox history, no secrets stored."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_secret_refused():
    from core.memory2 import store
    r = store("semantic", "my api_key = ABC123")
    assert r["ok"] is False and "secret" in r["error"].lower()
    r2 = store("nope", "hello")
    assert r2["ok"] is False


def test_short_term_search_and_forget():
    from core import memory2
    memory2._short.clear()
    assert store_ok("preferences", "likes dark HUD theme")
    hits = memory2.search("dark HUD", layers=["preferences"])
    assert hits and "dark" in hits[0]["text"].lower()
    n = memory2.forget("dark hud")
    assert n >= 1
    assert memory2.search("dark HUD", layers=["preferences"]) == []


def store_ok(layer, text):
    from core.memory2 import store
    return store(layer, text)["ok"]


def test_episodic_sandbox(tmp_path, monkeypatch):
    import core.history as h
    from core import memory2
    monkeypatch.setattr(h, "_HISTORY", tmp_path / "h.jsonl")
    memory2._short.clear()
    h.append("episodic", "edited Roblox obby project yesterday")
    hits = memory2.search("obby", layers=["episodic"])
    assert any("obby" in x["text"].lower() for x in hits)
