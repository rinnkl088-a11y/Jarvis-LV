import time


def test_long_task_completion():
    from core.long_running import LongTaskManager, RunStatus
    manager = LongTaskManager()

    def work(task, cancel, pause):
        task.progress = 1.0
        return "done"

    task = manager.start("test", work)
    manager._threads[task.id].join(1)
    assert task.status == RunStatus.COMPLETED
    assert task.result == "done"


def test_long_task_cancel():
    from core.long_running import LongTaskManager, RunStatus
    manager = LongTaskManager()

    def work(task, cancel, pause):
        while not cancel.is_set():
            time.sleep(0.001)

    task = manager.start("cancel", work)
    assert manager.cancel(task.id)
    manager._threads[task.id].join(1)
    assert task.status == RunStatus.CANCELLED


def test_proactive_disabled():
    from core.proactive import ProactiveMonitor
    monitor = ProactiveMonitor()
    assert monitor.inspect(disk_pct=95)
    assert monitor.history == []


def test_proactive_enabled():
    from core.proactive import ProactiveMonitor
    monitor = ProactiveMonitor(enabled=True)
    alerts = monitor.inspect(disk_pct=95, cpu_temp=90)
    assert len(alerts) == 2
    assert len(monitor.history) == 2


def test_personality_reports():
    from core.personality import report, clarification
    assert report(True, "saved") == "Completed: saved"
    assert "couldn't" in report(False, "failed")
    assert clarification("Continue") == "Continue?"
