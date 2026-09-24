"""Semantic Stability Monitor — unified cognitive consistency tracking.

Orchestrates: GoalDriftDetector, TrajectoryDivergence, MemoryContaminationTracker.
Provides a single entry point for semantic stability measurement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .goal_drift import DriftSnapshot, get_goal_drift_detector
from .trajectory import DivergenceReport, get_trajectory_divergence
from .memory_contamination import (
    ContaminationReport,
    get_memory_contamination_tracker,
)

logger = logging.getLogger("widdx.semantic")


@dataclass
class SemanticStabilityReport:
    """Unified report from all three semantic stability subsystems."""
    drift: DriftSnapshot | None = None
    divergence: DivergenceReport | None = None
    contamination: ContaminationReport | None = None
    overall_stability: float = 0.0
    is_stable: bool = True
    warnings: list[str] = field(default_factory=list)


class SemanticStabilityMonitor:
    """Unified orchestrator for semantic stability measurement.

    Tracks whether the system "remains the same system over time"
    by measuring goal drift, trajectory divergence, and memory contamination.
    """

    def __init__(self):
        self.drift = get_goal_drift_detector()
        self.divergence = get_trajectory_divergence()
        self.contamination = get_memory_contamination_tracker()
        self._reports: list[SemanticStabilityReport] = []

    def start_task(self, goal: str = "", plan_steps: list[str] | None = None):
        """Initialize all subsystems for a new task."""
        self.drift.start_task(goal, plan_steps)
        self.divergence.start_task()
        self.contamination.start_task()
        self._reports.clear()

    def note_step(self, step: int, tool_used: str, tool_args: dict | None = None,
                  response: str = ""):
        """Record execution data for all subsystems."""
        self.drift.note_step(step, tool_used, tool_args, response)
        self.contamination.note_tool_args(tool_args)
        if response:
            self.contamination.note_response(response)

    def note_message(self, role: str = "", content: str = ""):
        self.contamination.note_message(role, content)

    def record_decision(self, step: int, action: str, confidence: float,
                        signals: set[str] | None = None, plan_adherence: float = 1.0):
        self.divergence.record(step, action, confidence, signals, plan_adherence)

    def measure(self, step: int, tools_used: list[str],
                plan_adherence: float = 1.0) -> SemanticStabilityReport:
        """Compute unified semantic stability snapshot."""
        drift_snap = self.drift.measure(step, tools_used, plan_adherence)
        div_report = self.divergence.compare()
        contam_report = self.contamination.measure()

        warnings = []
        if drift_snap.is_drifting:
            warnings.append(f"GOAL_DRIFT: {drift_snap.drift_score:.2f}")
        if div_report.is_diverging:
            warnings.append(f"TRAJECTORY_DIVERGENCE: {div_report.divergence_ratio:.2f}")
        if contam_report.contamination_score > 0.4:
            warnings.append(f"MEMORY_CONTAMINATION: {contam_report.contamination_score:.2f}")

        # Overall stability: weighted inverse of all three
        overall = round(1.0 - (
            drift_snap.drift_score * 0.40
            + div_report.divergence_ratio * 0.35
            + contam_report.contamination_score * 0.25
        ), 3)
        overall = max(0.0, min(1.0, overall))

        report = SemanticStabilityReport(
            drift=drift_snap,
            divergence=div_report,
            contamination=contam_report,
            overall_stability=overall,
            is_stable=overall >= 0.6,
            warnings=warnings,
        )
        self._reports.append(report)

        if warnings:
            logger.warning("SEMANTIC INSTABILITY: %s — stability=%.2f",
                           "; ".join(warnings), overall)

        return report

    @property
    def trend(self) -> str:
        if len(self._reports) < 3:
            return "insufficient_data"
        recent = [r.overall_stability for r in self._reports[-3:]]
        if recent[-1] < recent[0] - 0.1:
            return "degrading"
        elif recent[-1] > recent[0] + 0.1:
            return "improving"
        return "stable"


_semantic_monitor: SemanticStabilityMonitor | None = None


def get_semantic_monitor() -> SemanticStabilityMonitor:
    global _semantic_monitor
    if _semantic_monitor is None:
        _semantic_monitor = SemanticStabilityMonitor()
    return _semantic_monitor
