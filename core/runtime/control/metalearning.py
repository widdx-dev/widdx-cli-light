"""Meta-Learning Monitor — evaluates the learning process itself.

Tracks whether the LEARNING POLICY (confidence, half-life, sample ratio)
is working correctly. Does NOT auto-adjust — only measures and reports.

Learning KPIs tracked:
  - proposal accept/reject ratio
  - experiment win/lose/inconclusive ratio
  - average time to reach decision
  - false accept estimate (accepted proposals that degraded performance)
  - learning velocity (how fast parameters converge)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("widdx.ecp.metalearning")


@dataclass
class LearningKPI:
    """Snapshot of learning process health."""
    total_proposals: int = 0
    proposals_accepted: int = 0
    proposals_rejected: int = 0
    total_experiments: int = 0
    experiments_won: int = 0       # candidate beat baseline
    experiments_lost: int = 0      # baseline beat candidate
    experiments_inconclusive: int = 0
    avg_time_to_decision: float = 0.0  # seconds from proposal to verdict
    learning_velocity: float = 0.0     # params changed per hour
    estimated_false_accepts: int = 0   # accept + subsequent degradation

    @property
    def accept_rate(self) -> float:
        return self.proposals_accepted / max(self.total_proposals, 1)

    @property
    def win_rate(self) -> float:
        done = self.experiments_won + self.experiments_lost
        return self.experiments_won / max(done, 1) if done > 0 else 0

    @property
    def decisiveness(self) -> float:
        done = self.experiments_won + self.experiments_lost
        total = done + self.experiments_inconclusive
        return done / max(total, 1) if total > 0 else 0

    @property
    def is_overconfident(self) -> bool:
        """High accept rate + high false accepts → overconfident"""
        return (self.accept_rate > 0.6 and
                self.estimated_false_accepts > max(1, self.proposals_accepted * 0.2))

    @property
    def is_underconfident(self) -> bool:
        """Low accept rate + high inconclusive → underconfident"""
        return (self.accept_rate < 0.1 and
                self.total_proposals >= 5 and
                self.decisiveness < 0.4)

    @property
    def is_stale(self) -> bool:
        """Very low learning velocity → parameters not adapting"""
        return (self.total_proposals >= 5 and
                self.learning_velocity < 0.05)


@dataclass
class MetaLearningReport:
    """Complete meta-learning health report."""
    kpi: LearningKPI
    recommendations: list[str]
    parameter_health: dict[str, dict]
    timestamp: float = field(default_factory=time.time)


class MetaLearningMonitor:
    """Measures and reports on the learning process itself.

    Does NOT auto-adjust learning parameters — only provides
    KPIs and recommendations for human review.
    """

    def __init__(self):
        self._proposals: list[dict] = []
        self._experiments: list[dict] = []
        self._parameter_timeline: dict[str, list[tuple[float, float]]] = {}
        self._start_time: float = 0.0

    def start(self):
        self._start_time = time.time()

    def record_proposal(self, parameter: str, accepted: bool,
                        confidence: float, reasoning: str = ""):
        self._proposals.append({
            "t": time.time(),
            "param": parameter,
            "accepted": accepted,
            "confidence": confidence,
            "reasoning": reasoning,
        })

    def record_experiment(self, parameter: str, winner: str,
                          confidence: float, success_delta: float):
        self._experiments.append({
            "t": time.time(),
            "param": parameter,
            "winner": winner,
            "confidence": confidence,
            "success_delta": success_delta,
        })

    def record_parameter_value(self, parameter: str, value: float):
        if parameter not in self._parameter_timeline:
            self._parameter_timeline[parameter] = []
        self._parameter_timeline[parameter].append((time.time(), value))

    def evaluate(self) -> MetaLearningReport:
        """Compute current learning KPIs and recommendations."""
        kpi = LearningKPI(
            total_proposals=len(self._proposals),
            proposals_accepted=sum(1 for p in self._proposals if p["accepted"]),
            proposals_rejected=sum(1 for p in self._proposals if not p["accepted"]),
            total_experiments=len(self._experiments),
            experiments_won=sum(1 for e in self._experiments if e["winner"] == "candidate"),
            experiments_lost=sum(1 for e in self._experiments if e["winner"] == "baseline"),
            experiments_inconclusive=sum(1 for e in self._experiments if e["winner"] == "inconclusive"),
        )

        # Time to decision
        if self._experiments:
            times = [e["t"] - self._start_time for e in self._experiments if e["winner"] != "inconclusive"]
            if times:
                kpi.avg_time_to_decision = sum(times) / len(times)

        # Learning velocity: parameter changes per hour
        total_changes = sum(len(vals) - 1 for vals in self._parameter_timeline.values() if len(vals) > 1)
        elapsed_hours = max(0.01, (time.time() - self._start_time) / 3600)
        kpi.learning_velocity = round(total_changes / elapsed_hours, 3)

        # False accept estimate: accepted + subsequent experiment lost
        accepted_params = set(p["param"] for p in self._proposals if p["accepted"])
        for exp in self._experiments:
            if exp["param"] in accepted_params and exp["winner"] == "baseline":
                kpi.estimated_false_accepts += 1

        # Recommendations
        recs: list[str] = []
        if kpi.is_overconfident:
            recs.append("LEARNING_OVERCONFIDENT: accept_rate={:.0%} + false_accepts={}. "
                       "Consider raising MIN_CONFIDENCE.".format(
                           kpi.accept_rate, kpi.estimated_false_accepts))
        if kpi.is_underconfident:
            recs.append("LEARNING_UNDERCONFIDENT: accept_rate={:.0%} with {} proposals. "
                       "Consider lowering MIN_CONFIDENCE.".format(
                           kpi.accept_rate, kpi.total_proposals))
        if kpi.is_stale:
            recs.append("LEARNING_STALE: velocity={:.3f}/h. "
                       "Consider reducing half-life or increasing sample rate.".format(
                           kpi.learning_velocity))

        # Per-parameter health
        param_health: dict[str, dict] = {}
        for param, timeline in self._parameter_timeline.items():
            if len(timeline) >= 2:
                values = [v for _, v in timeline]
                param_health[param] = {
                    "current": values[-1],
                    "initial": values[0],
                    "changes": len(values) - 1,
                    "range": (min(values), max(values)),
                    "is_converging": abs(values[-1] - values[-2]) < 0.05 if len(values) >= 3 else None,
                    "drift_direction": "increasing" if values[-1] > values[0] else "decreasing" if values[-1] < values[0] else "stable",
                }

        return MetaLearningReport(
            kpi=kpi,
            recommendations=recs,
            parameter_health=param_health,
        )


_metalearning: MetaLearningMonitor | None = None


def get_metalearning_monitor() -> MetaLearningMonitor:
    global _metalearning
    if _metalearning is None:
        _metalearning = MetaLearningMonitor()
    return _metalearning
