"""Job data model for Cron Scheduler."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class JobStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CronJob:
    """A single scheduled job."""

    schedule: str
    prompt: str
    id: str = field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    status: JobStatus = JobStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_result: Optional[str] = None
    last_error: Optional[str] = None
    run_count: int = 0
    max_runs: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> CronJob:
        data = dict(data)
        data["status"] = JobStatus(data.get("status", "active"))
        return cls(**data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> CronJob:
        return cls.from_dict(json.loads(text))
