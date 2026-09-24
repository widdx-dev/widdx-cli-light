"""Cognitive state snapshot — captures system identity at a stable moment.

A snapshot records the "cognitive fingerprint" — the set of parameters
that define what the system "is" at a given point in time. Used for
self-healing: when drift is detected, the system can compare against
its last stable snapshot and restore.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("widdx.semantic.snapshot")


@dataclass
class CognitiveSnapshot:
    """Frozen cognitive state at a moment of stability."""
    timestamp: float = 0.0
    step: int = 0
    goal_anchor: str = ""
    tool_set: list[str] = field(default_factory=list)
    plan_steps: list[str] = field(default_factory=list)
    decision_pattern: list[str] = field(default_factory=list)
    context_size: int = 0
    stability_score: float = 0.0
    policy_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        return self.timestamp > 0 and len(self.tool_set) > 0


class StateSnapshotManager:
    """Manages cognitive state snapshots for self-healing.

    Takes snapshots when the system is stable. When drift exceeds
    threshold, compares current state against the last stable snapshot
    to determine what changed and what needs restoration.
    """

    MAX_SNAPSHOTS = 5
    STABILITY_THRESHOLD_FOR_SNAPSHOT = 0.8

    def __init__(self):
        self._snapshots: list[CognitiveSnapshot] = []
        self._last_stable: CognitiveSnapshot | None = None
        self._snapshot_count: int = 0

    def start_task(self):
        self._snapshots.clear()
        self._last_stable = None
        self._snapshot_count = 0

    def maybe_snapshot(
        self,
        step: int,
        stability_score: float,
        goal: str = "",
        tools_used: list[str] | None = None,
        plan_steps: list[str] | None = None,
        decision_pattern: list[str] | None = None,
        context_size: int = 0,
        policy_state: dict[str, Any] | None = None,
    ) -> CognitiveSnapshot | None:
        """Take a snapshot if the system is stable enough.

        Only snapshots above STABILITY_THRESHOLD are kept — unstable
        states are not valid recovery targets.
        """
        if stability_score < self.STABILITY_THRESHOLD_FOR_SNAPSHOT:
            return None

        snapshot = CognitiveSnapshot(
            timestamp=time.time(),
            step=step,
            goal_anchor=goal[:200],
            tool_set=list(tools_used or []),
            plan_steps=list(plan_steps or []),
            decision_pattern=list(decision_pattern or []),
            context_size=context_size,
            stability_score=stability_score,
            policy_state=dict(policy_state or {}),
            metadata={"snapshot_index": self._snapshot_count},
        )

        self._snapshots.append(snapshot)
        if len(self._snapshots) > self.MAX_SNAPSHOTS:
            self._snapshots.pop(0)

        self._last_stable = snapshot
        self._snapshot_count += 1

        logger.info(
            "Cognitive snapshot #%d at step %d: stability=%.2f, tools=%d",
            self._snapshot_count, step, stability_score, len(snapshot.tool_set),
        )
        return snapshot

    def compare_to_last_stable(
        self,
        current_tools: list[str],
        current_context_size: int,
        current_plan_steps: list[str] | None = None,
    ) -> dict:
        """Compare current state to last stable snapshot. Returns a diff."""
        if self._last_stable is None:
            return {"has_stable_reference": False, "drift_delta": {}, "recommendations": []}

        stable = self._last_stable
        diff: dict[str, Any] = {}

        # Tool set drift
        added_tools = set(current_tools) - set(stable.tool_set)
        removed_tools = set(stable.tool_set) - set(current_tools)
        if added_tools or removed_tools:
            diff["tools_changed"] = {
                "added": list(added_tools),
                "removed": list(removed_tools),
                "stable_tools": list(stable.tool_set),
                "current_tools": list(current_tools),
            }

        # Context bloat
        if current_context_size > stable.context_size * 1.5:
            diff["context_bloat"] = {
                "stable_size": stable.context_size,
                "current_size": current_context_size,
                "growth_factor": round(current_context_size / max(stable.context_size, 1), 1),
            }

        # Plan divergence
        if current_plan_steps and stable.plan_steps:
            stable_set = set(stable.plan_steps)
            current_set = set(current_plan_steps)
            new_steps = current_set - stable_set
            if new_steps:
                diff["plan_divergence"] = {
                    "new_steps": list(new_steps),
                    "stable_step_count": len(stable.plan_steps),
                    "current_step_count": len(current_plan_steps),
                }

        recommendations = []
        if "context_bloat" in diff:
            recommendations.append("PRUNE_CONTEXT")
        if "tools_changed" in diff:
            recommendations.append("RESTRICT_TOOLS")
        if "plan_divergence" in diff:
            recommendations.append("REANCHOR_GOAL")

        return {
            "has_stable_reference": True,
            "stable_step": stable.step,
            "stable_stability": stable.stability_score,
            "drift_delta": diff,
            "recommendations": recommendations,
        }

    @property
    def last_stable_snapshot(self) -> CognitiveSnapshot | None:
        return self._last_stable

    @property
    def snapshot_count(self) -> int:
        return self._snapshot_count


_snapshot_mgr: StateSnapshotManager | None = None


def get_snapshot_manager() -> StateSnapshotManager:
    global _snapshot_mgr
    if _snapshot_mgr is None:
        _snapshot_mgr = StateSnapshotManager()
    return _snapshot_mgr
