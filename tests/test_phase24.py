"""Phase 24: main.py integration — new agent-layer tools wired and callable."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest


@pytest.fixture(scope="module")
def decls():
    import main
    return {d["name"] for d in main.TOOL_DECLARATIONS}


def test_new_tools_declared(decls):
    for name in ("run_agent_task", "pc_health", "file_op", "computer_op",
                 "browser_op", "long_task", "memory_layer"):
        assert name in decls, f"missing tool declaration: {name}"


def test_legacy_tools_preserved(decls):
    for name in ("system_status", "screen_process", "close_camera",
                 "manage_monitor", "shutdown_jarvis", "save_memory",
                 "recall_memory", "undo"):
        assert name in decls, f"legacy tool removed: {name}"


def test_agent_modules_importable():
    import main
    assert main._pc_doctor is not None
    assert main._planner is not None
    assert main._selfcorr is not None
    assert main._memory2 is not None


def test_agent_singletons():
    import main
    assert main._long_mgr is not None
    assert main._file_mgr is not None
    assert main._comp_mgr is not None
    assert main._brws_mgr is not None


def test_plan_for_goal_gaming():
    import main
    steps = main._plan_for_goal("prepare my PC for gaming")
    assert any("hardware" in s for s in steps)
    assert any("temperature" in s for s in steps)
    assert len(steps) >= 5


def test_plan_for_goal_cleanup():
    import main
    steps = main._plan_for_goal("clean up disk space")
    assert any("storage" in s for s in steps)


def test_plan_for_goal_health():
    import main
    steps = main._plan_for_goal("check my PC health")
    assert any("root cause" in s for s in steps)


def test_plan_for_goal_generic():
    import main
    steps = main._plan_for_goal("do something unrelated")
    assert len(steps) >= 2


def test_run_agent_task_dry_run():
    import main
    out = main._run_agent_task("check PC health", dry_run=True)
    assert out.startswith("DRY RUN")
    assert "diagnose" in out


def test_run_agent_task_empty_goal():
    import main
    assert main._run_agent_task("", dry_run=True) == "No goal given."


def test_format_health_report():
    import main
    from core.pc_doctor import diagnose
    rep = diagnose()
    text = main._format_health_report(rep)
    assert "Summary:" in text
    assert "Metrics:" in text


def test_file_op_unknown():
    import main
    assert "Unknown file op" in main._run_file_op(main._file_mgr, {"op": "bogus"})


def test_file_op_info_missing():
    import main
    out = main._run_file_op(main._file_mgr, {"op": "info", "path": "C:\\nope.txt"})
    assert "exists=False" in out


def test_computer_op_unknown():
    import main
    assert "Unknown computer op" in main._run_computer_op(main._comp_mgr, {"op": "bogus"})


def test_computer_op_click():
    import main
    out = main._run_computer_op(main._comp_mgr, {"op": "click", "x": 5, "y": 5})
    assert "click recorded" in out


def test_browser_op_navigate():
    import main
    out = main._run_browser_op(main._brws_mgr, {"op": "navigate", "url": "https://example.com"})
    assert "navigated" in out


def test_browser_op_unknown():
    import main
    assert "Unknown browser op" in main._run_browser_op(main._brws_mgr, {"op": "bogus"})


def test_long_task_lifecycle():
    import main
    started = main._run_long_task(main._long_mgr, {"op": "start", "title": "t"})
    assert "started" in started
    tid = started.split("id=")[1].split()[0]
    assert "[" in main._run_long_task(main._long_mgr, {"op": "status", "task_id": tid})


def test_long_task_unknown():
    import main
    assert "Unknown long_task op" in main._run_long_task(main._long_mgr, {"op": "bogus"})


def test_memory_layer_search():
    import main
    out = main._run_memory_layer(main._memory2, {"op": "search", "query": "test"})
    assert "memories" in out


def test_memory_layer_unknown():
    import main
    assert "Unknown memory op" in main._run_memory_layer(main._memory2, {"op": "bogus"})
