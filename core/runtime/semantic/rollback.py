"""Semantic rollback — restores cognitive state when drift exceeds threshold.

Operations:
  - Context pruning (compress message history)
  - Goal re-anchoring (reset goal drift detector)
  - Tool restriction (remove drifted tools)
  - Policy injection (force ECP to stabilize)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("widdx.semantic.rollback")


class SemanticRollback:
    """Orchestrates cognitive state restoration when drift is critical.

    Does not directly modify execution — produces a RollbackAction
    that the agent loop or ECP can apply.
    """

    def __init__(self):
        self._rollback_count: int = 0
        self._prune_count: int = 0
        self._reanchor_count: int = 0

    def start_task(self):
        self._rollback_count = 0
        self._prune_count = 0
        self._reanchor_count = 0

    def compute_rollback(
        self,
        drift_snapshot: Any,
        divergence_report: Any,
        contamination_report: Any,
        current_messages: list | None = None,
        stable_snapshot: Any = None,
    ) -> dict:
        """Compute the rollback operations needed to restore stability.

        Returns a dict with:
          - needs_rollback: bool
          - operations: list of dicts (each with 'type' and 'params')
          - severity: 'none' | 'mild' | 'critical'
        """
        operations = []
        severity = "none"

        # Determine if rollback is needed
        drift = drift_snapshot.drift_score if hasattr(drift_snapshot, 'drift_score') else 0
        divergence = divergence_report.divergence_ratio if hasattr(divergence_report, 'divergence_ratio') else 0
        contamination = contamination_report.contamination_score if hasattr(contamination_report, 'contamination_score') else 0

        needs_rollback = (
            drift >= 0.7 or divergence >= 0.7 or contamination >= 0.6
        )
        if not needs_rollback:
            return {"needs_rollback": False, "operations": [], "severity": "none"}

        severity = "critical" if (drift >= 0.8 or contamination >= 0.7) else "mild"

        # Operation 1: Context pruning
        if contamination >= 0.5 and current_messages and len(current_messages) > 20:
            operations.append({
                "type": "PRUNE_CONTEXT",
                "params": {
                    "keep_last": 10,
                    "keep_system": True,
                    "current_message_count": len(current_messages),
                },
            })

        # Operation 2: Goal re-anchoring
        if drift >= 0.6:
            operations.append({
                "type": "REANCHOR_GOAL",
                "params": {
                    "drift_score": drift,
                    "reanchor_instruction": (
                        "[SYSTEM: Cognitive stability recovered. "
                        "Returning to original task goal. "
                        "Ignore tangential work and refocus on the core objective.]"
                    ),
                },
            })

        # Operation 3: Tool restriction
        if stable_snapshot and hasattr(stable_snapshot, 'tool_set'):
            drifted_tools = set(getattr(drift_snapshot, 'current_tool_set', set())) - set(stable_snapshot.tool_set)
            if drifted_tools:
                operations.append({
                    "type": "RESTRICT_TOOLS",
                    "params": {
                        "allowed_tools": list(stable_snapshot.tool_set),
                        "blocked_tools": list(drifted_tools),
                    },
                })

        # Operation 4: Decision pattern reset
        if divergence >= 0.7:
            operations.append({
                "type": "RESET_DECISION_PATTERN",
                "params": {
                    "reason": f"Decision trajectory diverged {divergence:.0%} from baseline",
                },
            })

        # Operation 5: Safe-mode reinitialization (critical only)
        if severity == "critical":
            operations.append({
                "type": "SAFE_MODE",
                "params": {
                    "reason": "Critical cognitive instability detected",
                    "ecp_action": "REPLAN",
                },
            })

        self._rollback_count += 1
        logger.warning(
            "SEMANTIC ROLLBACK #%d: severity=%s, operations=%s",
            self._rollback_count, severity,
            [op["type"] for op in operations],
        )

        return {
            "needs_rollback": True,
            "operations": operations,
            "severity": severity,
            "rollback_count": self._rollback_count,
        }

    @property
    def stats(self) -> dict:
        return {
            "total_rollbacks": self._rollback_count,
            "prune_operations": self._prune_count,
            "reanchor_operations": self._reanchor_count,
        }


_rollback: SemanticRollback | None = None


def get_semantic_rollback() -> SemanticRollback:
    global _rollback
    if _rollback is None:
        _rollback = SemanticRollback()
    return _rollback
