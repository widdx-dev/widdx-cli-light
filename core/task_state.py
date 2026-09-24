"""Task Persistence Engine — Level 5.1.

Persists project state across sessions so the agent can resume
exactly where it left off after a restart.

Metric: شغّل مهمة → أوقف → أعد → تكمل من نفس النقطة

Usage:
    from core.task_state import TaskState
    ts = TaskState()
    ts.set_goal("Build a REST API")
    ts.update_step(1, "done")
    # ... restart server ...
    ts2 = TaskState()
    print(ts2.get_goal())  # "Build a REST API"
    print(ts2.get_progress())  # {"step": 1, "status": "done", ...}
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("widdx.task_state")

STATE_FILE = "task_state.json"


@dataclass
class StepState:
    order: int = 0
    description: str = ""
    status: str = "pending"  # pending | running | done | failed
    tool_used: str = ""
    result_summary: str = ""
    started_at: str = ""
    finished_at: str = ""


class TaskState:
    """Persistent project task state in .widdx/task_state.json."""

    def __init__(self, project_dir: str | Path | None = None):
        root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        self._widdx = root / ".widdx"
        self._widdx.mkdir(parents=True, exist_ok=True)
        self._path = self._widdx / STATE_FILE
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return self._default()

    def _default(self) -> dict:
        return {
            "goal": "",
            "created_at": "",
            "updated_at": "",
            "iterations": 0,
            "tools_used": 0,
            "progress_pct": 0,
            "steps": [],
            "messages": [],
            "agent_steps": [],
        }

    def _save(self):
        import os
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
        tmp_path = self._path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(str(tmp_path), str(self._path))
        except Exception as e:
            logger.error("Atomic write failed for TaskState: %s", e)

    def get_messages(self) -> list:
        return self._data.get("messages", [])

    def set_messages(self, messages: list):
        self._data["messages"] = messages
        self._save()

    def get_agent_steps(self) -> list:
        return self._data.get("agent_steps", [])

    def set_agent_steps(self, steps: list):
        self._data["agent_steps"] = steps
        self._save()

    # ── Public API ──────────────────────────────────────

    def set_goal(self, goal: str):
        self._data["goal"] = goal
        self._data["created_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        logger.info("TaskState: goal set — %s", goal[:80])

    def get_goal(self) -> str:
        return self._data.get("goal", "")

    def add_step(self, description: str, order: int | None = None):
        order = order if order is not None else len(self._data["steps"]) + 1
        step = StepState(order=order, description=description).__dict__
        self._data["steps"].append(step)
        self._data["iterations"] = len(self._data["steps"])
        self._save()

    def update_step(self, order: int, status: str, result: str = ""):
        for s in self._data["steps"]:
            if s["order"] == order:
                s["status"] = status
                if result:
                    s["result_summary"] = result
                if status == "running" and not s["started_at"]:
                    s["started_at"] = datetime.now(timezone.utc).isoformat()
                if status in ("done", "failed"):
                    s["finished_at"] = datetime.now(timezone.utc).isoformat()
                break
        self._recalc_progress()
        self._save()

    def increment_tools(self):
        self._data["tools_used"] = self._data.get("tools_used", 0) + 1
        self._save()

    def get_progress(self) -> dict:
        return {
            "goal": self._data["goal"],
            "progress_pct": self._data["progress_pct"],
            "iterations": self._data["iterations"],
            "tools_used": self._data["tools_used"],
            "steps": [
                {"order": s["order"], "description": s["description"], "status": s["status"]}
                for s in self._data["steps"]
            ],
        }

    def is_active(self) -> bool:
        """Return True if there is an active or resumable task.

        A task is considered active if:
        - There are StepState entries still pending/running, OR
        - A checkpoint exists (goal + messages saved) meaning the agent
          crashed mid-execution and can be resumed.
        """
        has_goal = bool(self._data.get("goal"))
        has_pending_steps = any(
            s["status"] in ("pending", "running") for s in self._data.get("steps", [])
        )
        has_checkpoint = bool(self._data.get("messages"))
        return has_goal and (has_pending_steps or has_checkpoint)

    def get_active_step(self) -> dict | None:
        for s in self._data["steps"]:
            if s["status"] in ("pending", "running"):
                return s
        return None

    def get_context_for_prompt(self) -> str:
        if not self._data["goal"]:
            return ""
        lines = [
            "<task_state>",
            f"Goal: {self._data['goal']}",
            f"Progress: {self._data['progress_pct']}%",
            f"Iterations: {self._data['iterations']}",
        ]
        for s in self._data["steps"]:
            icon = {"done": "✅", "failed": "❌", "running": "🔄", "pending": "⏳"}.get(s["status"], "❓")
            lines.append(f"  {icon} Step {s['order']}: {s['description']} [{s['status']}]")
        lines.append("</task_state>")
        return "\n".join(lines)

    def clear(self):
        self._data = self._default()
        self._path.unlink(missing_ok=True)

    def _recalc_progress(self):
        steps = self._data["steps"]
        if not steps:
            self._data["progress_pct"] = 0
            return
        done = sum(1 for s in steps if s["status"] == "done")
        self._data["progress_pct"] = round(done / len(steps) * 100)


# Singleton
_task_state: TaskState | None = None


def get_task_state() -> TaskState:
    global _task_state
    if _task_state is None:
        _task_state = TaskState()
    return _task_state
