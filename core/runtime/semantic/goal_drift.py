"""Goal drift detector — tracks whether execution stays aligned with original intent.

Measures: plan deviation rate, tool diversity, response entropy,
and semantic distance from the original goal over extended execution.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("widdx.semantic.drift")


@dataclass
class GoalAnchor:
    """Immutable reference point for the original task goal."""
    goal_hash: str
    goal_text: str
    initial_step_count: int = 0
    initial_tool_set: set[str] = field(default_factory=set)


@dataclass
class DriftSnapshot:
    """One measurement of semantic drift at a point in time."""
    step: int
    current_tool_set: set[str]
    tool_diversity: float
    response_entropy: float
    plan_adherence: float
    drift_score: float  # 0.0 = perfect alignment, 1.0 = completely drifted
    is_drifting: bool


class GoalDriftDetector:
    """Tracks semantic drift from the original task goal during long execution.

    Computes drift as a composite score from:
      - Tool diversity change (new tools = possible drift)
      - Response length volatility (inconsistent output = drift)
      - Step trajectory deviation from initial plan
    """

    DRIFT_WARNING_THRESHOLD = 0.4
    DRIFT_CRITICAL_THRESHOLD = 0.7

    def __init__(self):
        self._anchor: GoalAnchor | None = None
        self._snapshots: list[DriftSnapshot] = []
        self._response_lengths: list[int] = []
        self._initial_tool_sequence: list[str] = []
        self._step_count: int = 0

    def start_task(self, goal: str, plan_steps: list[str] | None = None):
        """Anchor the original goal at task start."""
        self._anchor = GoalAnchor(
            goal_hash=hashlib.sha256(goal.encode()).hexdigest()[:16],
            goal_text=goal[:200],
        )
        self._snapshots.clear()
        self._response_lengths.clear()
        self._initial_tool_sequence.clear()
        self._step_count = 0
        logger.info("Drift detector anchored: %s", self._anchor.goal_hash)

    def note_step(self, step: int, tool_used: str, tool_args: dict | None = None,
                  response: str = "", plan_adherence: float = 1.0):
        """Record a step for drift analysis."""
        self._step_count = max(self._step_count, step)
        if step < 10:
            self._initial_tool_sequence.append(tool_used)

        self._response_lengths.append(len(response))
        if len(self._response_lengths) > 20:
            self._response_lengths.pop(0)

    def measure(self, step: int, tools_used: list[str],
                plan_adherence: float = 1.0) -> DriftSnapshot:
        """Compute current drift score."""
        if self._anchor is None:
            return DriftSnapshot(step=step, current_tool_set=set(),
                                 tool_diversity=0, response_entropy=0,
                                 plan_adherence=1.0, drift_score=0,
                                 is_drifting=False)

        current = set(tools_used)

        # Tool diversity: ratio of tools NOT in initial set
        initial_set = set(self._initial_tool_sequence)
        if initial_set:
            new_tools = len(current - initial_set)
            tool_diversity = new_tools / max(len(current), 1)
        else:
            tool_diversity = 0.0

        # Response entropy: coefficient of variation of response lengths
        if len(self._response_lengths) >= 3:
            mean_len = sum(self._response_lengths) / len(self._response_lengths)
            if mean_len > 0:
                variance = sum((rl - mean_len) ** 2 for rl in self._response_lengths) / len(self._response_lengths)
                response_entropy = min(1.0, (variance ** 0.5) / mean_len)
            else:
                response_entropy = 0.0
        else:
            response_entropy = 0.0

        # Plan deviation
        deviation = 1.0 - plan_adherence

        # Composite drift score (weighted)
        drift_score = round(
            tool_diversity * 0.35
            + response_entropy * 0.25
            + deviation * 0.40,
            3
        )

        is_drifting = drift_score >= self.DRIFT_WARNING_THRESHOLD

        snapshot = DriftSnapshot(
            step=step,
            current_tool_set=current,
            tool_diversity=round(tool_diversity, 3),
            response_entropy=round(response_entropy, 3),
            plan_adherence=round(plan_adherence, 3),
            drift_score=drift_score,
            is_drifting=is_drifting,
        )
        self._snapshots.append(snapshot)

        if is_drifting:
            level = "CRITICAL" if drift_score >= self.DRIFT_CRITICAL_THRESHOLD else "WARNING"
            logger.warning(
                "DRIFT %s at step %d: score=%.3f (tool_div=%.3f, resp_ent=%.3f, plan_dev=%.3f)",
                level, step, drift_score, tool_diversity, response_entropy, deviation,
            )

        return snapshot

    def should_reanchor(self) -> bool:
        """Return True if drift is critical enough to warrant re-anchoring the goal."""
        if not self._snapshots:
            return False
        recent = self._snapshots[-3:]
        return all(s.drift_score >= self.DRIFT_CRITICAL_THRESHOLD for s in recent)

    @property
    def current_drift(self) -> float:
        if not self._snapshots:
            return 0.0
        return self._snapshots[-1].drift_score

    @property
    def drift_trend(self) -> str:
        """Return 'increasing', 'stable', or 'decreasing' based on last 3 snapshots."""
        if len(self._snapshots) < 3:
            return "insufficient_data"
        recent = self._snapshots[-3:]
        scores = [s.drift_score for s in recent]
        if scores[-1] > scores[0] + 0.1:
            return "increasing"
        elif scores[-1] < scores[0] - 0.1:
            return "decreasing"
        return "stable"


_goaldrift: GoalDriftDetector | None = None


def get_goal_drift_detector() -> GoalDriftDetector:
    global _goaldrift
    if _goaldrift is None:
        _goaldrift = GoalDriftDetector()
    return _goaldrift
