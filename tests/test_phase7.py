"""PHASE 7 tests — coding agent. Temp dirs only, no real env changes."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_blocked_commands():
    from core.coding_agent import is_blocked_command
    assert is_blocked_command("rm -rf / tmp") is True
    assert is_blocked_command("python -m pytest -q") is False


def test_analyze_temp_project(tmp_path):
    from core.coding_agent import analyze_project
    (tmp_path / "a.py").write_text("x=1")
    (tmp_path / "test_a.py").write_text("def test_x(): assert 1==1")
    out = analyze_project(tmp_path)
    assert any("a.py" in s for s in out)
    assert any("__summary__" in s for s in out)


def test_run_tests_pass_and_fail(tmp_path):
    from core.coding_agent import run_tests
    (tmp_path / "test_ok.py").write_text("def test_ok(): assert 1 == 1")
    rep = run_tests(tmp_path, "python -m pytest -q", timeout_s=60)
    assert rep.passed is True and "passed" in rep.output.lower()
    (tmp_path / "test_bad.py").write_text("def test_bad(): assert 1 == 2")
    rep2 = run_tests(tmp_path, "python -m pytest -q", timeout_s=60)
    assert rep2.passed is False


def test_run_tests_blocked_and_bad_dir(tmp_path):
    from core.coding_agent import run_tests, analyze_project
    rep = run_tests(tmp_path, "rm -rf /", timeout_s=10)
    assert rep.passed is False and "BLOCKED" in rep.output
    rep2 = analyze_project(tmp_path / "nope")
    assert "Not a directory" in rep2[0]


def test_explain_diff():
    from core.coding_agent import explain_diff
    d = explain_diff("a=1\n", "a=2\n")
    assert "before" in d and "after" in d
