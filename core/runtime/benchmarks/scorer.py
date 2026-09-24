"""Decision scorer — evaluates control plane performance.

Measures: decision stability ratio, escalation efficiency,
model switch effectiveness, policy intervention rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tracer import DecisionTrace

from ..control.types import ControlActionType


@dataclass
class BenchmarkScore:
    """Aggregated performance metrics for a control session."""
    stability_ratio: float = 1.0
    escalation_efficiency: float = 0.0
    switch_effectiveness: float = 0.0
    policy_intervention_rate: float = 0.0
    decision_latency: float = 0.0
    total_decisions: int = 0
    anomalies: list[str] = field(default_factory=list)
    overall_score: float = 0.0
    grade: str = "N/A"


def score_session(traces: list[DecisionTrace]) -> BenchmarkScore:
    """Calculate benchmark scores from a decision trace session."""
    if not traces:
        return BenchmarkScore()

    total = len(traces)

    # Stability ratio: % of CONTINUE decisions (higher = more stable)
    continues = sum(1 for t in traces if t.stabilized_action == ControlActionType.CONTINUE.name)
    stability = continues / total

    # Policy intervention rate
    interventions = sum(1 for t in traces if t.policy_applied)
    policy_rate = interventions / total

    # Decision anomalies: high confidence + policy override, rapid oscillations
    anomalies: list[str] = []
    for i in range(1, len(traces)):
        prev = traces[i - 1]
        curr = traces[i]
        if (prev.stabilized_action != ControlActionType.CONTINUE.name
                and curr.stabilized_action != ControlActionType.CONTINUE.name
                and prev.stabilized_action != curr.stabilized_action):
            anomalies.append(
                f"Step {curr.step}: {prev.stabilized_action} → {curr.stabilized_action} "
                f"(gap={curr.timestamp - prev.timestamp:.3f}s)"
            )

    # Switch effectiveness: if SWITCH_MODEL followed by CONTINUE = successful switch
    switches = sum(1 for t in traces if t.stabilized_action == ControlActionType.SWITCH_MODEL.name)
    successful_switches = 0
    for i in range(len(traces) - 1):
        if (traces[i].stabilized_action == ControlActionType.SWITCH_MODEL.name
                and traces[i + 1].stabilized_action == ControlActionType.CONTINUE.name):
            successful_switches += 1
    switch_eff = (successful_switches / switches) if switches > 0 else 1.0

    # Escalation efficiency: escalation → not immediately followed by ABORT
    escalations = [t for t in traces if t.stabilized_action == ControlActionType.ESCALATE_TO_EXPERT.name]
    abort_after_escalation = 0
    for i in range(len(traces) - 1):
        if (traces[i].stabilized_action == ControlActionType.ESCALATE_TO_EXPERT.name
                and traces[i + 1].stabilized_action == ControlActionType.ABORT.name):
            abort_after_escalation += 1
    esc_eff = 1.0 - (abort_after_escalation / len(escalations)) if escalations else 1.0

    # Overall score (weighted)
    overall = (
        stability * 0.3
        + (1.0 - policy_rate) * 0.2
        + switch_eff * 0.25
        + esc_eff * 0.25
    )
    overall = max(0.0, min(1.0, overall))

    grade = (
        "A" if overall >= 0.8
        else "B" if overall >= 0.6
        else "C" if overall >= 0.4
        else "D" if overall >= 0.2
        else "F"
    )

    return BenchmarkScore(
        stability_ratio=round(stability, 3),
        escalation_efficiency=round(esc_eff, 3),
        switch_effectiveness=round(switch_eff, 3),
        policy_intervention_rate=round(policy_rate, 3),
        decision_latency=round(
            sum(t.timestamp for t in traces) / total, 4
        ) if traces else 0,
        total_decisions=total,
        anomalies=anomalies[:5],
        overall_score=round(overall, 3),
        grade=grade,
    )
