"""Tests for CronJob persistence store."""

import tempfile
from pathlib import Path

from core.cron.job import CronJob, JobStatus
from core.cron.store import JobStore


def test_store_save_and_load():
    """RED: Save a job then load it by ID."""
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(db_path=Path(tmp) / "test.db")
        job = CronJob(schedule="0 9 * * *", prompt="test")
        job_id = store.save(job)
        assert job_id == job.id

        loaded = store.load(job_id)
        assert loaded is not None
        assert loaded.id == job.id
        assert loaded.schedule == "0 9 * * *"
        assert loaded.prompt == "test"


def test_store_load_all():
    """RED: Load all jobs should return all saved jobs."""
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(db_path=Path(tmp) / "test.db")
        store.save(CronJob(schedule="0 9 * * *", prompt="job1"))
        store.save(CronJob(schedule="*/30 * * * *", prompt="job2"))
        all_jobs = store.load_all()
        assert len(all_jobs) == 2


def test_store_delete():
    """RED: Delete should remove job and return True."""
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(db_path=Path(tmp) / "test.db")
        job = CronJob(schedule="0 9 * * *", prompt="test")
        job_id = store.save(job)
        assert store.delete(job_id) is True
        assert store.load(job_id) is None


def test_store_update_status():
    """RED: Update status should persist."""
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(db_path=Path(tmp) / "test.db")
        job = CronJob(schedule="0 9 * * *", prompt="test")
        job_id = store.save(job)
        assert store.update_status(job_id, JobStatus.PAUSED) is True
        loaded = store.load(job_id)
        assert loaded.status == JobStatus.PAUSED


def test_store_count():
    """RED: Count should reflect number of jobs."""
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(db_path=Path(tmp) / "test.db")
        assert store.count() == 0
        store.save(CronJob(schedule="0 9 * * *", prompt="test"))
        assert store.count() == 1


def test_store_load_by_status():
    """RED: Load only active or paused jobs."""
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(db_path=Path(tmp) / "test.db")
        job1 = CronJob(schedule="0 9 * * *", prompt="active job")
        job2 = CronJob(schedule="*/5 * * * *", prompt="paused job")
        store.save(job1)
        store.save(job2)
        store.update_status(job2.id, JobStatus.PAUSED)

        active = store.load_all(status=JobStatus.ACTIVE)
        paused = store.load_all(status=JobStatus.PAUSED)
        assert len(active) == 1
        assert len(paused) == 1
