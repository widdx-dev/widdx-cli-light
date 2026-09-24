"""Delegation — spawn isolated sub-agents for parallel/independent tasks.

Architecture:
  DelegationManager
  ├── spawn(task, tools, provider) → SubAgent (background thread)
  ├── run_parallel([tasks]) → [results]
  ├── status(agent_id) → State
  └── collect() → جميع النتائج

  SubAgent
  ├── جلسة محادثة مستقلة (messages خاصة به)
  ├── أدواته الخاصة (يمكن تصفيتها)
  ├── Thread خلفي
  └── يرجع StructuredResult عند الانتهاء

Usage:
    from core.delegation import delegation

    # Single task
    result = delegation.run("Search latest Python news")

    # Parallel tasks
    results = delegation.run_parallel([
      "Search prices",
      "Write calculator code",
    ])
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from core import tools as core_tools

logger = logging.getLogger("widdx.delegation")


class SubAgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubAgentResult:
    """Result from a sub-agent execution."""
    task_id: str
    task: str
    status: SubAgentStatus
    summary: str = ""
    steps: int = 0
    tools_used: list[str] = field(default_factory=list)
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    elapsed_seconds: float = 0.0


class SubAgent:
    """An isolated sub-agent that runs a task in its own context.

    Each SubAgent gets:
    - Fresh conversation messages
    - Its own tool list
    - Runs in a daemon thread
    - Reports progress via status callback
    """

    def __init__(
        self,
        task: str,
        task_id: str,
        provider: Any,
        tool_defs: list[dict],
        cfg: dict | None = None,
        on_progress: Callable[[str], None] | None = None,
    ):
        self.task = task
        self.task_id = task_id
        self._provider = provider
        self._tool_defs = tool_defs
        self._cfg = cfg or {}
        self._on_progress = on_progress
        self._messages: list[dict] = [{"role": "user", "content": task}]
        self._status = SubAgentStatus.PENDING
        self._result: SubAgentResult | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        """Start the sub-agent in a background thread."""
        self._status = SubAgentStatus.RUNNING
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"subagent-{self.task_id[:8]}",
        )
        self._thread.start()

    def _run(self):
        """Execute the task in the background."""
        t0 = time.perf_counter()
        steps = 0
        tools_used = []
        summary = ""

        try:
            max_turns = self._cfg.get("max_turns", 10)
            temperature = self._cfg.get("temperature", 0.7)

            for turn in range(max_turns):
                content, tool_calls = self._provider.chat(
                    self._messages, self._tool_defs, temperature
                )

                if not tool_calls:
                    summary = content or "[done]"
                    self._messages.append({"role": "assistant", "content": content or "[done]"})
                    break

                # Execute tools
                tc_list = []
                for tc in tool_calls:
                    tc_list.append({
                        "id": tc.id or f"call_{uuid.uuid4().hex[:12]}",
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                    })
                    if tc.name not in tools_used:
                        tools_used.append(tc.name)

                self._messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": tc_list,
                })

                for tc in tool_calls:
                    steps += 1
                    if self._on_progress:
                        self._on_progress(f"  🔧 Step {steps}: {tc.name}")
                    try:
                        result = core_tools.execute_with_skills(tc.name, tc.args)
                    except Exception as e:
                        result = f"[Tool error: {e}]"
                    self._messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id or f"call_{uuid.uuid4().hex[:12]}",
                        "name": tc.name,
                        "content": result,
                    })
            else:
                summary = "[Max turns reached]"

            self._status = SubAgentStatus.DONE

        except Exception as e:
            self._status = SubAgentStatus.FAILED
            summary = f"Error: {e}"
            logger.error("SubAgent %s error: %s", self.task_id, e, exc_info=True)

        elapsed = time.perf_counter() - t0
        self._result = SubAgentResult(
            task_id=self.task_id,
            task=self.task[:100],
            status=self._status,
            summary=summary[:500],
            steps=steps,
            tools_used=tools_used,
            error="" if self._status == SubAgentStatus.DONE else summary,
            finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=elapsed,
        )
        logger.info(
            "SubAgent %s: %s (%d steps, %.1fs)",
            self.task_id, self._status.value, steps, elapsed,
        )

    @property
    def result(self) -> SubAgentResult | None:
        return self._result

    @property
    def status(self) -> SubAgentStatus:
        return self._status

    @property
    def is_done(self) -> bool:
        return self._status in (SubAgentStatus.DONE, SubAgentStatus.FAILED, SubAgentStatus.CANCELLED)


class DelegationManager:
    """Manages sub-agent lifecycle — spawn, monitor, collect."""

    def __init__(self):
        self._agents: dict[str, SubAgent] = {}
        self._lock = threading.Lock()

    def run(
        self,
        task: str,
        provider: Any = None,
        tool_defs: list[dict] | None = None,
        cfg: dict | None = None,
    ) -> str:
        """Run a task in a sub-agent.

        Args:
            task: The task description.
            provider: LLM provider (uses default if None).
            tool_defs: Tool list (uses all tools if None).
            cfg: Config dict.

        Returns:
            Task ID for tracking.
        """
        task_id = f"agent_{uuid.uuid4().hex[:8]}"
        if tool_defs is None:
            tool_defs = list(core_tools.TOOL_DEFINITIONS)
        if cfg is None:
            cfg = {}

        agent = SubAgent(
            task=task,
            task_id=task_id,
            provider=provider,
            tool_defs=tool_defs,
            cfg=cfg,
        )

        with self._lock:
            self._agents[task_id] = agent

        agent.start()
        logger.info("Delegation: spawned %s — %s", task_id, task[:80])
        return task_id

    def run_parallel(
        self,
        tasks: list[str],
        provider: Any = None,
        tool_defs: list[dict] | None = None,
        cfg: dict | None = None,
    ) -> list[SubAgentResult]:
        """Run multiple tasks in parallel sub-agents.

        Args:
            tasks: List of task descriptions.
            provider: LLM provider.
            tool_defs: Tool list.
            cfg: Config dict.

        Returns:
            List of SubAgentResult in the same order as tasks.
        """
        task_ids = []
        for task in tasks:
            tid = self.run(task, provider, tool_defs, cfg)
            task_ids.append(tid)

        # Wait for all to complete
        results: list[SubAgentResult] = []
        for tid in task_ids:
            result = self.wait(tid, timeout=120)
            if result is not None:
                results.append(result)
        return results

    def status(self, task_id: str) -> SubAgentResult | None:
        """Get current status of a sub-agent."""
        with self._lock:
            agent = self._agents.get(task_id)
        if agent is None:
            return None
        if agent.result:
            return agent.result
        return SubAgentResult(
            task_id=task_id,
            task="",
            status=agent.status,
        )

    def wait(self, task_id: str, timeout: float = 60.0) -> SubAgentResult | None:
        """Wait for a sub-agent to complete."""
        with self._lock:
            agent = self._agents.get(task_id)
        if agent is None:
            return None
        if agent.is_done:
            return agent.result
        if agent._thread and agent._thread.is_alive():
            agent._thread.join(timeout=timeout)
        return agent.result

    def list_agents(self) -> list[SubAgentResult]:
        """Return all sub-agents, newest first."""
        with self._lock:
            results = []
            for agent in self._agents.values():
                if agent.result:
                    results.append(agent.result)
                else:
                    results.append(SubAgentResult(
                        task_id=agent.task_id,
                        task=agent.task[:100],
                        status=agent.status,
                    ))
            results.sort(key=lambda r: r.created_at, reverse=True)
            return results

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for a in self._agents.values() if not a.is_done)


# Global singleton
delegation = DelegationManager()
