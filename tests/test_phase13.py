"""Phase 13: dashboard + logging."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile, json, time, threading
import pytest


def test_dashboard_import():
    from core.dashboard import Dashboard, DashboardSnapshot
    assert Dashboard is not None
    assert DashboardSnapshot is not None


def test_dashboard_snapshot_fields():
    from core.dashboard import Dashboard
    d = Dashboard()
    s = d.snapshot()
    assert s.assistant_name == "JARVIS-X"
    assert s.cpu == "N/A" or isinstance(s.cpu, str)
    assert s.at > 0


def test_logging_configure(tmp_path):
    from core.logging import configure, _ensure_file
    p = configure(tmp_path)
    assert p.parent == tmp_path
    assert _ensure_file() == p


def test_logging_roundtrip(tmp_path):
    from core.logging import configure, log_request, log_plan, log_tool_selected, get_trace, clear_trace
    configure(tmp_path)
    clear_trace()
    log_request("open browser")
    log_plan(["step1"])
    log_tool_selected("browser_navigate", {"url": "https://example.com"})
    trace = get_trace()
    assert len(trace) == 3
    assert trace[0]["event"] == "request"
    assert trace[1]["event"] == "plan"
    assert trace[2]["event"] == "tool_select"


def test_logging_redaction(tmp_path):
    from core.logging import configure, log_request, get_trace, clear_trace
    configure(tmp_path)
    clear_trace()
    log_request("token=abc123 password=hunter2")
    trace = get_trace()
    payload = json.dumps(trace[0])
    assert "abc123" not in payload
    assert "hunter2" not in payload


def test_logging_file_write(tmp_path):
    from core.logging import configure, log_request, _ensure_file
    configure(tmp_path)
    log_request("test")
    f = _ensure_file()
    assert f.exists()
    lines = f.read_text().splitlines()
    assert len(lines) >= 1
    data = json.loads(lines[-1])
    assert data["event"] == "request"


def test_logging_result(tmp_path):
    from core.logging import configure, log_result, get_trace, clear_trace
    configure(tmp_path)
    clear_trace()
    log_result("done", True)
    trace = get_trace()
    assert trace[-1]["event"] == "result"
    assert trace[-1]["success"] is True


def test_logging_dump_json(tmp_path):
    from core.logging import configure, log_request, dump_json, clear_trace
    configure(tmp_path)
    clear_trace()
    log_request("x")
    dump_json()
    assert isinstance(dump_json(), str)
    assert "[" in dump_json()


def test_dashboard_task_center(tmp_path):
    from core.task_center import TaskCenter
    from core.dashboard import Dashboard
    center = TaskCenter()
    task = center.create(title="test")
    d = Dashboard(center=center)
    s = d.snapshot()
    assert s.active_task == "test"
    assert s.task_status == task.status


def test_dashboard_concurrent_access(tmp_path):
    from core.dashboard import Dashboard
    d = Dashboard()
    results = []
    def worker():
        for _ in range(20):
            results.append(d.snapshot())
    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 80
    for r in results:
        assert isinstance(r.at, float)
