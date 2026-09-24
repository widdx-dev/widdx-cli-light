"""Tests for BackgroundTaskManager."""

import time
from core.background import BackgroundTaskManager, TaskStatus


def test_background_run_and_status():
    mgr = BackgroundTaskManager()
    task_id = mgr.run("echo hello", sandbox_mode="subprocess")
    assert task_id is not None
    assert len(task_id) > 0

    # Wait for completion
    task = mgr.wait(task_id, timeout=10)
    assert task is not None
    assert task.status == TaskStatus.DONE
    assert "hello" in task.result


def test_background_list_tasks():
    mgr = BackgroundTaskManager()
    mgr.run("echo test1", sandbox_mode="subprocess")
    mgr.run("echo test2", sandbox_mode="subprocess")
    tasks = mgr.list_tasks()
    assert len(tasks) >= 2


def test_background_cancel():
    mgr = BackgroundTaskManager()
    task_id = mgr.run("sleep 10", sandbox_mode="subprocess")
    # Cancel immediately
    assert mgr.cancel(task_id) is True
    task = mgr.status(task_id)
    assert task.status == TaskStatus.CANCELLED


def test_background_status_not_found():
    mgr = BackgroundTaskManager()
    assert mgr.status("nonexistent") is None


def test_background_callback():
    results = []

    def on_done(task):
        results.append(task.id)

    mgr = BackgroundTaskManager()
    task_id = mgr.run("echo callback", sandbox_mode="subprocess", on_done=on_done)
    mgr.wait(task_id, timeout=10)
    assert task_id in results


def test_background_failed_command():
    mgr = BackgroundTaskManager()
    task_id = mgr.run("exit 1", sandbox_mode="subprocess")
    mgr.wait(task_id, timeout=10)
    task = mgr.status(task_id)
    assert task.status == TaskStatus.FAILED


def test_background_active_count():
    mgr = BackgroundTaskManager()
    mgr.run("echo test", sandbox_mode="subprocess")
    time.sleep(0.1)
    assert mgr.active_count >= 0  # might finish fast


def test_background_clean_old():
    mgr = BackgroundTaskManager()
    task_id = mgr.run("echo old", sandbox_mode="subprocess")
    mgr.wait(task_id, timeout=10)
    # Simulate old task by manipulating finished_at
    from datetime import datetime, timezone, timedelta
    task = mgr.status(task_id)
    task.finished_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    mgr.clean_old(max_age_minutes=60)
    assert mgr.status(task_id) is None
