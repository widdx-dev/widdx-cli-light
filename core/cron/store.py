"""Persistent job store using SQLite."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from core.cron.job import CronJob, JobStatus

logger = logging.getLogger("widdx.cron.store")


class JobStore:
    """SQLite-backed persistent store for CronJobs."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".widdx" / "cron" / "jobs.db"
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cron_jobs (
                        id TEXT PRIMARY KEY,
                        schedule TEXT NOT NULL,
                        prompt TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        data TEXT NOT NULL DEFAULT '{}'
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    def _get_conn(self):
        import sqlite3
        conn = sqlite3.connect(str(self._db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def save(self, job: CronJob) -> str:
        with self._lock:
            conn = self._get_conn()
            try:
                data = job.to_dict()
                data_json = json.dumps(data, ensure_ascii=False)
                conn.execute(
                    "INSERT OR REPLACE INTO cron_jobs (id, schedule, prompt, status, data) VALUES (?, ?, ?, ?, ?)",
                    (job.id, job.schedule, job.prompt, job.status.value, data_json),
                )
                conn.commit()
            finally:
                conn.close()
        return job.id

    def load(self, job_id: str) -> Optional[CronJob]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT data FROM cron_jobs WHERE id = ?", (job_id,)
                ).fetchone()
                if row is None:
                    return None
                return CronJob.from_dict(json.loads(row["data"]))
            finally:
                conn.close()

    def load_all(self, status: Optional[JobStatus] = None) -> list[CronJob]:
        with self._lock:
            conn = self._get_conn()
            try:
                if status:
                    rows = conn.execute(
                        "SELECT data FROM cron_jobs WHERE status = ? ORDER BY rowid",
                        (status.value,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT data FROM cron_jobs ORDER BY rowid"
                    ).fetchall()
                return [CronJob.from_dict(json.loads(r["data"])) for r in rows]
            finally:
                conn.close()

    def delete(self, job_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def update_status(self, job_id: str, status: JobStatus) -> bool:
        job = self.load(job_id)
        if job is None:
            return False
        job.status = status
        self.save(job)
        return True

    def count(self) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT COUNT(*) as cnt FROM cron_jobs").fetchone()
                return row["cnt"] if row else 0
            finally:
                conn.close()
