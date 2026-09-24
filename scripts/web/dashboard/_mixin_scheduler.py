"""Dashboard mixin — scheduler."""
from __future__ import annotations
import logging

logger = logging.getLogger("widdx.web.dashboard")



class SchedulerMixin:
    def cron_jobs(self) -> list[dict]:
        try:
            from core.cron.store import JobStore
            store = JobStore()
            return store.list_jobs()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Cron list: %s", e)
            return []


    def cron_create(self, schedule: str, prompt: str) -> dict:
        try:
            from core.cron.scheduler import CronScheduler
            sched = CronScheduler()
            job_id = sched.create_job(schedule, prompt)
            return {"id": job_id, "status": "created"}
        except Exception as e:
            return {"error": str(e)}


    def cron_delete(self, job_id: str) -> dict:
        try:
            from core.cron.store import JobStore
            store = JobStore()
            store.delete_job(job_id)  # type: ignore[attr-defined]
            return {"status": "deleted"}
        except Exception as e:
            return {"error": str(e)}


    def cron_toggle(self, job_id: str) -> dict:
        """Toggle a cron job on/off."""
        try:
            from core.cron.store import JobStore
            from core.cron.job import JobStatus
            store = JobStore()
            jobs = store.list_jobs()  # type: ignore[attr-defined]
            for j in jobs:
                if j.get("id") == job_id:
                    current = j.get("status", "active")
                    new_status = JobStatus.PAUSED if current == "active" else JobStatus.ACTIVE
                    store.update_status(job_id, new_status)
                    return {"status": "toggled", "new_status": new_status.value}
            return {"error": "Job not found"}
        except Exception as e:
            return {"error": str(e)}

    # ── Background Tasks ──


    def background_tasks(self) -> list[dict]:
        try:
            from core.background import background
            return [
                {"id": t.id, "status": t.status.value, "summary": (t.result or "")[:100]}
                for t in background.list_tasks()
            ]
        except Exception:
            return []

    # ── Sub-Agents ──


    def sub_agents(self) -> list[dict]:
        try:
            from core.delegation import delegation
            return [
                {"id": a.id, "status": a.status.value, "goal": a.goal[:60]}  # type: ignore[attr-defined]
                for a in delegation.list_agents()
            ]
        except Exception:
            return []

    # ── Memory ──


