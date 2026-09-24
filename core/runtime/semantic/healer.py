"""Self-Healing Cognitive Monitor — detect, snapshot, restore.

Orchestrates the full self-healing cycle:
  1. Take cognitive snapshots when stable
  2. Detect drift via semantic stability measurement
  3. Compare current state to last stable snapshot
  4. Compute and execute rollback operations
  5. Verify recovery
"""

from __future__ import annotations

import logging

from .monitor import get_semantic_monitor
from .state_snapshot import get_snapshot_manager
from .rollback import get_semantic_rollback
from .invariance import get_cognitive_invariance

logger = logging.getLogger("widdx.semantic.healer")


class SelfHealingMonitor:
    """Orchestrates cognitive self-healing.

    Detects instability, captures stable states, computes recovery
    operations, and verifies restoration.
    """

    HEALING_COOLDOWN_STEPS = 5
    CRITICAL_DRIFT_THRESHOLD = 0.7

    def __init__(self):
        self.semantic = get_semantic_monitor()
        self.snapshot = get_snapshot_manager()
        self.rollback = get_semantic_rollback()
        self.invariance = get_cognitive_invariance()
        self._healing_cooldown: int = 0
        self._healing_count: int = 0
        self._last_recovery_step: int = 0
        self._recovery_history: list[dict] = []
        self._pre_healing_stability: float = 0.0
        self._pre_healing_warnings: int = 0

    def start_task(self, goal: str = "", plan_steps: list[str] | None = None):
        self.semantic.start_task(goal, plan_steps)
        self.snapshot.start_task()
        self.rollback.start_task()
        self.invariance.start_task()
        self._healing_cooldown = 0
        self._healing_count = 0
        self._last_recovery_step = 0
        self._recovery_history.clear()
        self._pre_healing_stability = 0.0
        self._pre_healing_warnings = 0

    def tick(
        self,
        step: int,
        tools_used: list[str],
        plan_adherence: float = 1.0,
        current_messages: list | None = None,
        decision_pattern: list[str] | None = None,
        context_size: int = 0,
        policy_state: dict | None = None,
    ) -> dict:
        """Main self-healing tick — called periodically by the agent loop.

        Returns a dict with:
          - needs_healing: bool
          - operations: list of healing operations
          - stability: current overall stability
          - snapshot_taken: whether a new snapshot was captured
        """

        if self._healing_cooldown > 0:
            self._healing_cooldown -= 1

        # Step 1: Measure current stability
        report = self.semantic.measure(step, tools_used, plan_adherence)

        # Step 2: Take snapshot if stable (capture identity)
        snapshot = self.snapshot.maybe_snapshot(
            step=step,
            stability_score=report.overall_stability,
            tools_used=tools_used,
            plan_steps=[],
            decision_pattern=decision_pattern or [],
            context_size=context_size,
            policy_state=policy_state or {},
        )

        # Step 3: Check if healing is needed
        if not report.is_stable and self._healing_cooldown == 0:
            # Compare against last stable snapshot
            delta = self.snapshot.compare_to_last_stable(
                current_tools=tools_used,
                current_context_size=context_size,
            )

            # Compute rollback
            healing = self.rollback.compute_rollback(
                drift_snapshot=report.drift,
                divergence_report=report.divergence,
                contamination_report=report.contamination,
                current_messages=current_messages,
                stable_snapshot=self.snapshot.last_stable_snapshot,
            )

            if healing["needs_rollback"]:
                self._healing_cooldown = self.HEALING_COOLDOWN_STEPS
                self._healing_count += 1
                self._last_recovery_step = step

                # ── Pre-healing: capture state ──
                pre_stability = report.overall_stability
                pre_warnings = len(report.warnings)

                # ── Execute each healing operation with contract enforcement ──
                executed_ops = []
                failed_ops = []
                for op in healing["operations"]:
                    context = {
                        "stability": pre_stability,
                        "warning_count": pre_warnings,
                        "drift_score": report.drift.drift_score if report.drift else 0,
                        "divergence": report.divergence.divergence_ratio if report.divergence else 0,
                        "contamination": report.contamination.contamination_score if report.contamination else 0,
                        "has_snapshot": self.snapshot.last_stable_snapshot is not None,
                        "has_baseline": self.snapshot.last_stable_snapshot is not None,
                        "goal_anchor": self.snapshot.last_stable_snapshot.goal_anchor if self.snapshot.last_stable_snapshot else "",
                        "messages": current_messages or [],
                        "drifted_tools": delta.get("drift_delta", {}).get("tools_changed", {}).get("added", []),
                        "current_tools": tools_used,
                        "stable_tool_set": self.snapshot.last_stable_snapshot.tool_set if self.snapshot.last_stable_snapshot else [],
                        "policy_state": {},
                        "in_safe_mode": getattr(self, '_in_safe_mode', False),
                    }
                    validation = self.invariance.execute_healing(
                        operation_type=op["type"],
                        **context,
                    )
                    if validation.passed:
                        executed_ops.append(op["type"])
                    else:
                        failed_ops.append((op["type"], validation.failures))

                # ── Check system-wide invariants ──
                self.invariance.check_invariants(
                    stability=pre_stability,
                    healing_count=self._healing_count,
                    tool_set_size=len(tools_used),
                    oscillation_warnings=getattr(self.semantic, '_oscillation_warning_count', 0) if hasattr(self.semantic, '_oscillation_warning_count') else 0,
                    context_size=context_size,
                )

                self._pre_healing_stability = pre_stability
                self._pre_healing_warnings = pre_warnings
                self._recovery_history.append({
                    "step": step,
                    "stability_before": report.overall_stability,
                    "severity": healing["severity"],
                    "operations": [op["type"] for op in healing["operations"]],
                    "executed": executed_ops,
                    "failed": failed_ops,
                    "delta": delta,
                })

                logger.warning(
                    "SELF-HEALING #%d at step %d: stability=%.2f, severity=%s, ops=%s, executed=%s, failed=%s",
                    self._healing_count, step, report.overall_stability,
                    healing["severity"],
                    [op["type"] for op in healing["operations"]],
                    executed_ops, failed_ops,
                )

                return {
                    "needs_healing": True,
                    "stability": report.overall_stability,
                    "severity": healing["severity"],
                    "operations": healing["operations"],
                    "executed_operations": executed_ops,
                    "failed_operations": failed_ops,
                    "snapshot_taken": snapshot is not None,
                    "warnings": report.warnings,
                    "healing_count": self._healing_count,
                    "delta": delta,
                }

        return {
            "needs_healing": False,
            "stability": report.overall_stability,
            "operations": [],
            "snapshot_taken": snapshot is not None,
            "warnings": report.warnings,
            "healing_count": self._healing_count,
            "is_stable": report.is_stable,
        }

    @property
    def stats(self) -> dict:
        return {
            "total_healings": self._healing_count,
            "last_recovery_step": self._last_recovery_step,
            "healing_cooldown": self._healing_cooldown,
            "snapshots": self.snapshot.snapshot_count,
            "rollback_stats": self.rollback.stats,
            "invariance_guarantees": self.invariance.get_guarantees(),
            "recovery_history": self._recovery_history[-3:],
        }


_healer: SelfHealingMonitor | None = None


def get_self_healing_monitor() -> SelfHealingMonitor:
    global _healer
    if _healer is None:
        _healer = SelfHealingMonitor()
    return _healer
