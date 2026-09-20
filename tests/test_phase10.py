"""PHASE 10 tests — gaming. Mocks only, no real Steam/Epic files."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_cheats_refused():
    from core.gaming import check_allowed
    assert "Refused" in check_allowed("aimbot bypass")
    assert check_allowed("launch a game") == ""


def test_session_and_perf():
    from core.gaming import GameSession, perf_tick
    s = GameSession(title="test game")
    tick = perf_tick(s)
    assert "at" in tick and len(s.perf_ticks) == 1
    # cap at 20
    s.perf_ticks = [{"at": 0}] * 30
    s.cap()
    assert len(s.perf_ticks) == 20


def test_launch_not_found():
    from core.gaming import launch
    r = launch("not a real game", known_games=[])
    assert r["ok"] is False and "not found" in r["error"].lower()


def test_launch_dry_run():
    from core.gaming import launch
    games = [{"title": "My Game", "source": "steam"}]
    r = launch("my game", known_games=games)
    assert r["ok"] is True and r.get("dry_run") is True


def test_launch_refuses_on_call():
    from core.gaming import launch, GameSession
    calls = []
    def bad_launcher(g):
        calls.append(g)
        raise RuntimeError("blocked")
    games = [{"title": "My Game", "source": "steam"}]
    r = launch("my game", launcher_fn=bad_launcher, known_games=games)
    assert r["ok"] is False and "blocked" in r["error"].lower()
