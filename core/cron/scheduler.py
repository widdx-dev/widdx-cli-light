"""Background cron scheduler — checks and executes due jobs."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Callable

from core.cron.job import CronJob, JobStatus
from core.cron.parser import next_run, parse_schedule
from core.cron.store import JobStore

logger = logging.getLogger("widdx.cron.scheduler")

CHECK_INTERVAL = 15  # seconds between checks


class CronScheduler:
    """Background cron scheduler.

    Usage:
        scheduler = CronScheduler()
        scheduler.start()   # starts background thread
        scheduler.stop()    # stops background thread
        scheduler.create_job("0 9 * * *", "check email")
    """

    def __init__(self, store: Optional[JobStore] = None):
        self._store = store or JobStore()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._executor: Optional[Callable[[CronJob], str]] = None

    def set_executor(self, fn: Callable[[CronJob], str]):
        """Set the function that executes a job's prompt."""
        self._executor = fn

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            logger.debug("Cron scheduler already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="cron-scheduler")
        self._thread.start()
        logger.info("Cron scheduler started")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("Cron scheduler stopped")

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def create_job(
        self,
        schedule: str,
        prompt: str,
        max_runs: Optional[int] = None,
    ) -> str:
        """Create a new cron job.

        Args:
            schedule: Cron expression or duration string
            prompt: What to execute
            max_runs: Max executions (None = infinite)

        Returns:
            Job ID
        """
        cron_expr, one_shot_dt = parse_schedule(schedule)
        job = CronJob(
            schedule=cron_expr,
            prompt=prompt,
            max_runs=max_runs,
        )
        job.next_run = next_run(cron_expr, one_shot_dt)
        self._store.save(job)
        logger.info("Cron job created: %s (%s)", job.id, schedule)
        return job.id

    def list_jobs(self) -> list[CronJob]:
        return self._store.load_all()

    def get_job(self, job_id: str) -> Optional[CronJob]:
        return self._store.load(job_id)

    def remove_job(self, job_id: str) -> bool:
        return self._store.delete(job_id)

    def pause_job(self, job_id: str) -> bool:
        return self._store.update_status(job_id, JobStatus.PAUSED)

    def resume_job(self, job_id: str) -> bool:
        job = self._store.load(job_id)
        if job is None:
            return False
        try:
            cron_expr, one_shot_dt = parse_schedule(job.schedule)
            job.next_run = next_run(cron_expr, one_shot_dt)
        except Exception:
            job.next_run = None
        job.status = JobStatus.ACTIVE
        self._store.save(job)
        return True

    def _run_loop(self):
        """Main scheduler loop — runs in background thread."""
        while not self._stop_event.is_set():
            try:
                self._check_due_jobs()
            except Exception as e:
                logger.error("Cron check error: %s", e, exc_info=True)
            self._stop_event.wait(CHECK_INTERVAL)

    def _check_due_jobs(self):
        """Find and execute due jobs."""
        now = datetime.now(timezone.utc)
        jobs = self._store.load_all(status=JobStatus.ACTIVE)

        for job in jobs:
            if self._stop_event.is_set():
                break

            if job.next_run is None:
                continue

            try:
                due_time = datetime.fromisoformat(job.next_run)
            except (ValueError, TypeError):
                continue

            if now < due_time:
                continue

            # Execute job
            logger.info("Executing cron job: %s", job.id)
            job.run_count += 1
            job.last_run = now.isoformat()

            if self._executor:
                try:
                    result = self._executor(job)
                    job.last_result = result[:1000]
                    job.last_error = None
                except Exception as e:
                    logger.error("Cron job %s failed: %s", job.id, e, exc_info=True)
                    job.last_error = str(e)[:500]
                    job.last_result = None
            else:
                job.last_result = "[No executor configured]"

            # Calculate next run
            if job.max_runs is not None and job.run_count >= job.max_runs:
                job.status = JobStatus.COMPLETED
                job.next_run = None
            else:
                try:
                    cron_expr, one_shot_dt = parse_schedule(job.schedule)
                    job.next_run = next_run(cron_expr, one_shot_dt)
                except Exception as e:
                    logger.debug("Job %s next_run calc error: %s", job.id, e)
                    job.next_run = None

            self._store.save(job)
