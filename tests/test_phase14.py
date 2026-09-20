"""Phase 14: pc_doctor diagnostics."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_pc_doctor_import():
    from core.pc_doctor import diagnose, quick_status, HealthReport, Severity, RootCause, MaintenanceItem
    assert diagnose is not None
    assert quick_status is not None
    assert HealthReport is not None
    assert Severity is not None


def test_quick_status_keys():
    from core.pc_doctor import quick_status
    status = quick_status()
    for k in ("cpu", "gpu", "ram", "thermal", "disk", "network"):
        assert k in status


def test_quick_status_values_are_str():
    from core.pc_doctor import quick_status
    status = quick_status()
    for v in status.values():
        assert isinstance(v, str)


def test_diagnosis_has_summary():
    from core.pc_doctor import diagnose
    report = diagnose()
    assert isinstance(report.summary, str) and len(report.summary) > 0


def test_diagnosis_has_metrics():
    from core.pc_doctor import diagnose
    report = diagnose()
    assert report.cpu is not None
    assert report.ram is not None
    assert report.gpu is not None
    assert report.disk is not None
    assert report.thermal is not None


def test_diagnosis_metrics_are_strings():
    from core.pc_doctor import diagnose
    report = diagnose()
    for m in (report.cpu, report.ram, report.gpu, report.disk, report.thermal, report.network):
        assert isinstance(m.value, str)
        assert isinstance(m.status.value, str)


def test_diagnosis_no_invented_values():
    from core.pc_doctor import diagnose
    report = diagnose()
    for m in (report.cpu, report.ram, report.gpu, report.disk, report.thermal, report.network):
        assert m.value != ""


def test_root_causes_are_observations_not_guesses():
    from core.pc_doctor import diagnose
    report = diagnose()
    for rc in report.root_causes:
        assert isinstance(rc.metric, str)
        assert isinstance(rc.observed, str)
        assert isinstance(rc.possible_cause, str)
        assert isinstance(rc.recommended_action, str)
        assert rc.confidence in ("low", "medium", "high")


def test_maintenance_items_have_category():
    from core.pc_doctor import diagnose, Severity
    report = diagnose()
    for item in report.maintenance_items:
        assert isinstance(item.category, str)
        assert isinstance(item.item, str)
        assert isinstance(item.suggestion, str)
        assert item.risk in (Severity.OK, Severity.WARN, Severity.CRITICAL, Severity.UNAVAILABLE)


def test_diagnosis_timestamp():
    from core.pc_doctor import diagnose
    report = diagnose()
    import time
    assert report.timestamp > 0
    assert isinstance(report.timestamp, float)


def test_report_serialization():
    from core.pc_doctor import diagnose
    report = diagnose()
    import json
    data = json.dumps({
        "summary": report.summary,
        "cpu": report.cpu.value,
        "ram": report.ram.value,
        "root_causes": [rc.metric for rc in report.root_causes],
    }, default=str)
    assert isinstance(data, str)
    assert "summary" in data
