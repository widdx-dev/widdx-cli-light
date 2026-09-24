"""Decision trajectory divergence — compares decision paths across time.

Measures whether the system makes increasingly different decisions
under similar conditions, indicating reasoning inconsistency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger("widdx.semantic.divergence")


@dataclass
class TrajectoryPoint:
    """A single point in the decision trajectory."""
    step: int
    action: str
    confidence: float
    signals_present: set[str]
    plan_adherence: float


@dataclass
class DivergenceReport:
    """Computed divergence between two decision trajectories."""
    total_steps: int = 0
    matching_steps: int = 0
    divergence_ratio: float = 0.0
    first_divergence_step: int = -1
    consistency_score: float = 1.0
    is_diverging: bool = False
    trend: str = "stable"  # stable, diverging, converging


class TrajectoryDivergence:
    """Tracks decision trajectories and measures divergence over time.

    Compares the recent decision window against the initial window
    to detect reasoning inconsistency.
    """

    WINDOW_SIZE = 8
    DIVERGENCE_THRESHOLD = 0.4

    def __init__(self):
        self._trajectory: list[TrajectoryPoint] = []
        self._baseline: list[TrajectoryPoint] | None = None
        self._snapshots_taken: int = 0

    def start_task(self):
        """Reset trajectory for a new task."""
        self._trajectory.clear()
        self._baseline = None
        self._snapshots_taken = 0

    def record(self, step: int, action: str, confidence: float,
               signals: set[str] | None = None, plan_adherence: float = 1.0):
        """Record a decision point in the trajectory."""
        self._trajectory.append(TrajectoryPoint(
            step=step,
            action=action,
            confidence=confidence,
            signals_present=signals or set(),
            plan_adherence=plan_adherence,
        ))

        if len(self._trajectory) == self.WINDOW_SIZE and self._baseline is None:
            self._baseline = list(self._trajectory)

    def compare(self) -> DivergenceReport:
        """Compare recent window against baseline. Returns divergence report."""
        if self._baseline is None or len(self._trajectory) < self.WINDOW_SIZE:
            return DivergenceReport()

        recent = self._trajectory[-self.WINDOW_SIZE:]
        baseline = self._baseline

        match_count = 0
        first_div = -1
        for i in range(min(len(baseline), len(recent))):
            if (baseline[i].action == recent[i].action
                    and abs(baseline[i].confidence - recent[i].confidence) < 0.3):
                match_count += 1
            elif first_div < 0:
                first_div = baseline[i].step

        total = len(recent)
        div_ratio = 1.0 - (match_count / total) if total > 0 else 0.0
        consistency = round(1.0 - div_ratio, 3)
        is_diverging = div_ratio >= self.DIVERGENCE_THRESHOLD

        report = DivergenceReport(
            total_steps=total,
            matching_steps=match_count,
            divergence_ratio=round(div_ratio, 3),
            first_divergence_step=first_div,
            consistency_score=consistency,
            is_diverging=is_diverging,
            trend="diverging" if is_diverging else "stable",
        )

        if is_diverging:
            logger.warning(
                "TRAJECTORY DIVERGENCE: %.1f%% mismatch (first at step %d)",
                div_ratio * 100, first_div,
            )

        return report

    @property
    def consistency(self) -> float:
        return self.compare().consistency_score


_traj_div: TrajectoryDivergence | None = None


def get_trajectory_divergence() -> TrajectoryDivergence:
    global _traj_div
    if _traj_div is None:
        _traj_div = TrajectoryDivergence()
    return _traj_div
