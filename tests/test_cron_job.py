"""Tests for CronJob data model."""

from core.cron.job import CronJob, JobStatus


def test_cron_job_defaults():
    """RED: Job should have sensible defaults."""
    job = CronJob(schedule="0 9 * * *", prompt="test")
    assert job.schedule == "0 9 * * *"
    assert job.prompt == "test"
    assert job.status == JobStatus.ACTIVE
    assert job.run_count == 0
    assert job.id.startswith("job_")


def test_cron_job_to_from_dict():
    """RED: to_dict() → from_dict() should preserve all fields."""
    original = CronJob(schedule="0 9 * * *", prompt="hello", run_count=5)
    d = original.to_dict()
    restored = CronJob.from_dict(d)
    assert restored.id == original.id
    assert restored.schedule == original.schedule
    assert restored.prompt == original.prompt
    assert restored.run_count == original.run_count
    assert restored.status == original.status


def test_cron_job_status_enum():
    """RED: Status enum values should be correct."""
    assert JobStatus.ACTIVE.value == "active"
    assert JobStatus.PAUSED.value == "paused"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"


def test_cron_job_to_from_json():
    """RED: JSON serialization round-trip."""
    original = CronJob(schedule="every 30m", prompt="check email")
    json_str = original.to_json()
    restored = CronJob.from_json(json_str)
    assert restored.schedule == "every 30m"
    assert restored.prompt == "check email"
