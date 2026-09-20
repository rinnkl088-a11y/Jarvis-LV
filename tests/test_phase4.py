"""PHASE 4 tests — vision cache + verification. Mocks only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_cache_and_change_detection(monkeypatch):
    import core.vision as v
    frames = [b"frame-one-bytes", b"frame-one-bytes", b"frame-two-bytes"]
    monkeypatch.setattr(v, "_capture_uncached",
                        lambda kind, region: frames.pop(0))
    monkeypatch.setattr(v, "_downscale", lambda raw: raw)
    v.clear_cache()
    img1, changed1 = v.capture(v.SCREEN, force=True)
    assert changed1 is True
    img2, changed2 = v.capture(v.SCREEN)  # TTL cache -> same, unchanged
    assert img2 == img1 and changed2 is False
    img3, changed3 = v.capture(v.SCREEN, force=True)
    assert changed3 is False  # same bytes as cached frame-one
    img4, changed4 = v.capture(v.SCREEN, force=True)
    assert changed4 is True  # frame-two differs


def test_analyze_mock_and_local_fallback(monkeypatch):
    import core.vision as v
    monkeypatch.setattr(v, "_local_context", lambda: {"applications": []})
    obs = v.analyze(b"img", v.SCREEN,
                    analyze_fn=lambda img, kind: {
                        "visible_text": ["Error 404"],
                        "ui_elements": ["OK button"]})
    assert obs.visible_text == ["Error 404"]
    assert obs.ui_elements == ["OK button"]
    plain = v.analyze(b"img", v.SCREEN)
    assert any("Local-only" in o for o in plain.observations)
    assert plain.ui_elements == []  # never fabricated


def test_act_and_verify_success_and_failure():
    from core.computer_use import act_and_verify
    state = {"on": False}
    ok = act_and_verify("turn on", lambda: state.update(on=True),
                        lambda: state["on"], timeout_s=2)
    assert ok.ok and ok.verified
    bad = act_and_verify("never", lambda: None, lambda: False, timeout_s=1)
    assert bad.ok is False and bad.verified is False
    err = act_and_verify("boom", lambda: 1 / 0, lambda: True)
    assert err.ok is False


def test_focus_empty_title():
    from core.computer_use import focus_window_verified
    res = focus_window_verified("")
    assert res.ok is False


def test_observe_end_to_end(monkeypatch):
    import core.vision as v
    monkeypatch.setattr(v, "capture", lambda *a, **k: (b"img", True))
    monkeypatch.setattr(v, "_local_context", lambda: {"applications": ["App"]})
    obs = v.observe(v.SCREEN)
    assert obs.changed_since_last is True
    assert obs.applications == ["App"]
