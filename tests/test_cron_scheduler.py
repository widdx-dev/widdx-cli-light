"""Tests for CronScheduler background thread."""

import tempfile
from pathlib import Path
from datetime import datetime, timezone

from core.cron.scheduler import CronScheduler
from core.cron.job import CronJob, JobStatus
from core.cron.store import JobStore


def test_scheduler_create_job():
    sched = CronScheduler()
    job_id = sched.create_job("*/1 * * * *", "test")
    assert job_id is not None
    assert len(job_id) > 0
    sched.remove_job(job_id)


def test_scheduler_list_jobs():
    sched = CronScheduler()
    sched.create_job("0 9 * * *", "job1")
    sched.create_job("*/30 * * * *", "job2")
    jobs = sched.list_jobs()
    assert len(jobs) >= 2


def test_scheduler_remove_job():
    sched = CronScheduler()
    job_id = sched.create_job("0 9 * * *", "test")
    assert sched.remove_job(job_id) is True
    assert sched.get_job(job_id) is None


def test_scheduler_pause_resume():
    sched = CronScheduler()
    job_id = sched.create_job("0 9 * * *", "test")
    assert sched.pause_job(job_id) is True
    job = sched.get_job(job_id)
    assert job.status == JobStatus.PAUSED
    assert sched.resume_job(job_id) is True
    job = sched.get_job(job_id)
    assert job.status == JobStatus.ACTIVE
    # Cleanup
    sched.remove_job(job_id)


def test_scheduler_start_stop():
    sched = CronScheduler()
    assert sched.running is False
    sched.start()
    assert sched.running is True
    sched.stop()
    assert sched.running is False


def test_scheduler_executor():
    """RED: Executor is called when job is due."""
    _results = []

    def executor(job: CronJob) -> str:
        _results.append(job.prompt)
        return f"Executed: {job.prompt}"

    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(db_path=Path(tmp) / "test.db")
        sched = CronScheduler(store=store)
        sched.set_executor(executor)

        job_id = sched.create_job("*/1 * * * *", "test-exec")
        job = sched.get_job(job_id)
        # Force next_run to now for immediate execution
        job.next_run = datetime.now(timezone.utc).isoformat()
        store.save(job)

        sched._check_due_jobs()
        job = sched.get_job(job_id)
        assert job.last_result is not None
        assert job.run_count == 1
        sched.remove_job(job_id)


def test_scheduler_max_runs():
    """RED: Job with max_runs=1 should complete after one execution."""
    def executor(job: CronJob) -> str:
        return f"Done: {job.prompt}"

    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(db_path=Path(tmp) / "test.db")
        sched = CronScheduler(store=store)
        sched.set_executor(executor)

        job_id = sched.create_job("*/1 * * * *", "max-run-test", max_runs=1)
        job = sched.get_job(job_id)
        job.next_run = datetime.now(timezone.utc).isoformat()
        store.save(job)

        sched._check_due_jobs()
        job = sched.get_job(job_id)
        assert job.run_count == 1
        assert job.status == JobStatus.COMPLETED
        sched.remove_job(job_id)
