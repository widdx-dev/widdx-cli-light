"""Autonomy Level Metric — quantitative measurement of system self-governance.

Computes a real autonomy score (0.0-10.0+) from measurable system capabilities:
  - Self-monitoring: does the system detect its own drift/errors?
  - Self-correction: does it heal without human intervention?
  - Self-optimization: does it learn from experience?
  - Self-verification: does it validate its own output?

The score is computed, NOT invented. Each component contributes based on
actual measured behavior, not aspirational claims.

Scale:
  0-2.0: Reactive (responds to commands, no self-monitoring)
  2-4.0: Adaptive (detects issues, suggests fixes)
  4-6.0: Self-correcting (auto-heals, learns from errors)
  6-8.0: Self-governing (full loop: detect→heal→verify→learn)
  8-10+: Autonomous (creative problem-solving, counterfactual reasoning)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("widdx.autonomy")


@dataclass
class AutonomyComponent:
    """A measurable autonomy capability."""
    name: str
    weight: float  # contribution to total score (0-1)
    is_active: bool = False
    measured_value: float = 0.0  # 0.0-1.0 actual performance
    description: str = ""


@dataclass
class AutonomyReport:
    """Complete autonomy assessment."""
    total_score: float  # 0.0-10.0+
    level: str  # descriptive label
    components: dict[str, AutonomyComponent]
    timestamp: float = field(default_factory=time.time)
    evidence: dict[str, Any] = field(default_factory=dict)


class AutonomyMetric:
    """Quantitative autonomy measurement from real system behavior.

    The score is computed from 8 measurable dimensions:
      1. Goal drift detection (semantic stability)
      2. Self-healing execution (invariance contracts)
      3. Decision stability (ECP control plane)
      4. Learning velocity (meta-learning KPIs)
      5. Error recovery (self-correction rate)
      6. Product verification (output validation)
      7. Counterfactual reasoning (experiment wins)
      8. Creative problem-solving (novel strategy generation)
    """

    def __init__(self):
        self._components: dict[str, AutonomyComponent] = {
            "drift_detection": AutonomyComponent(
                name="drift_detection",
                weight=0.15,
                description="Detects semantic drift from original goal",
            ),
            "self_healing": AutonomyComponent(
                name="self_healing",
                weight=0.20,
                description="Executes healing operations with contract enforcement",
            ),
            "decision_stability": AutonomyComponent(
                name="decision_stability",
                weight=0.15,
                description="Maintains stable control decisions (ECP)",
            ),
            "learning_velocity": AutonomyComponent(
                name="learning_velocity",
                weight=0.10,
                description="Adapts parameters from experience",
            ),
            "error_recovery": AutonomyComponent(
                name="error_recovery",
                weight=0.15,
                description="Recovers from tool/runtime failures",
            ),
            "product_verification": AutonomyComponent(
                name="product_verification",
                weight=0.10,
                description="Validates output quality before delivery",
            ),
            "counterfactual_reasoning": AutonomyComponent(
                name="counterfactual_reasoning",
                weight=0.10,
                description="Runs A/B experiments and learns from outcomes",
            ),
            "creative_problem_solving": AutonomyComponent(
                name="creative_problem_solving",
                weight=0.05,
                description="Generates novel strategies when patterns fail",
            ),
        }

    def measure(self, **subsystem_reports: dict) -> AutonomyReport:
        """Compute autonomy score from actual subsystem measurements.

        Args:
            drift_detection: dict with 'current_drift' (0-1, lower=better)
            self_healing: dict with 'total_healings', 'success_rate'
            decision_stability: dict with 'failure_rate', 'oscillation_warnings'
            learning_velocity: dict with 'velocity', 'accept_rate'
            error_recovery: dict with 'recovery_rate', 'total_errors'
            product_verification: dict with 'verification_rate', 'issues_found'
            counterfactual: dict with 'win_rate', 'total_experiments'
            creative: dict with 'novel_strategies_used'
        """
        now = time.time()

        # 1. Drift detection (0-1, inverted: lower drift = higher score)
        drift_data = subsystem_reports.get("drift_detection", {})
        drift_score = 1.0 - drift_data.get("current_drift", 0.0)
        self._components["drift_detection"].measured_value = max(0.0, drift_score)
        self._components["drift_detection"].is_active = drift_data.get("is_active", False)

        # 2. Self-healing (success rate of healing operations)
        healing_data = subsystem_reports.get("self_healing", {})
        healing_success = healing_data.get("success_rate", 0.0)
        healing_active = healing_data.get("total_healings", 0) > 0
        self._components["self_healing"].measured_value = healing_success
        self._components["self_healing"].is_active = healing_active

        # 3. Decision stability (1 - failure_rate, penalize oscillations)
        decision_data = subsystem_reports.get("decision_stability", {})
        failure_rate = decision_data.get("failure_rate", 0.0)
        oscillations = decision_data.get("oscillation_warnings", 0)
        decision_score = max(0.0, 1.0 - failure_rate - oscillations * 0.1)
        self._components["decision_stability"].measured_value = decision_score
        self._components["decision_stability"].is_active = decision_data.get("is_active", False)

        # 4. Learning velocity (normalized: velocity * accept_rate)
        learning_data = subsystem_reports.get("learning_velocity", {})
        velocity = learning_data.get("velocity", 0.0)
        accept_rate = learning_data.get("accept_rate", 0.0)
        learning_score = min(1.0, velocity * accept_rate)
        self._components["learning_velocity"].measured_value = learning_score
        self._components["learning_velocity"].is_active = learning_data.get("is_active", False)

        # 5. Error recovery (recovery_rate)
        error_data = subsystem_reports.get("error_recovery", {})
        recovery_rate = error_data.get("recovery_rate", 0.0)
        self._components["error_recovery"].measured_value = recovery_rate
        self._components["error_recovery"].is_active = error_data.get("total_errors", 0) > 0

        # 6. Product verification (verification_rate * (1 - issue_rate))
        verify_data = subsystem_reports.get("product_verification", {})
        verification_rate = verify_data.get("verification_rate", 0.0)
        issue_rate = verify_data.get("issue_rate", 0.0)
        verify_score = verification_rate * (1.0 - issue_rate)
        self._components["product_verification"].measured_value = verify_score
        self._components["product_verification"].is_active = verify_data.get("is_active", False)

        # 7. Counterfactual reasoning (win_rate of experiments)
        counterfactual_data = subsystem_reports.get("counterfactual", {})
        win_rate = counterfactual_data.get("win_rate", 0.0)
        total_experiments = counterfactual_data.get("total_experiments", 0)
        confidence_factor = min(1.0, total_experiments / 3.0)
        counterfactual_score = win_rate * confidence_factor
        self._components["counterfactual_reasoning"].measured_value = counterfactual_score
        self._components["counterfactual_reasoning"].is_active = total_experiments > 0

        # 8. Creative problem-solving (binary: used or not, scaled by success)
        creative_data = subsystem_reports.get("creative", {})
        novel_used = creative_data.get("novel_strategies_used", 0)
        creative_success = creative_data.get("success_rate", 0.0)
        creative_score = min(1.0, novel_used * 0.2) * creative_success
        self._components["creative_problem_solving"].measured_value = creative_score
        self._components["creative_problem_solving"].is_active = novel_used > 0

        # Compute weighted total (scale to 0-10)
        total = sum(c.weight * c.measured_value for c in self._components.values())
        total_score = round(total * 10.0, 2)

        # Determine level label
        level = self._level_label(total_score)

        # Collect evidence
        evidence = {
            name: {
                "value": c.measured_value,
                "weight": c.weight,
                "weighted_contribution": round(c.weight * c.measured_value * 10, 2),
                "is_active": c.is_active,
            }
            for name, c in self._components.items()
        }

        return AutonomyReport(
            total_score=total_score,
            level=level,
            components=dict(self._components),
            timestamp=now,
            evidence=evidence,
        )

    def _level_label(self, score: float) -> str:
        """Convert numeric score to descriptive label."""
        if score >= 8.0:
            return "AUTONOMOUS (self-governing, creative, verified)"
        elif score >= 6.0:
            return "SELF-GOVERNING (detect-heal-verify-learn loop)"
        elif score >= 4.0:
            return "SELF-CORRECTING (auto-heals, learns from errors)"
        elif score >= 2.0:
            return "ADAPTIVE (detects issues, suggests fixes)"
        elif score >= 0.5:
            return "REACTIVE (responds to commands, basic monitoring)"
        else:
            return "PASSIVE (no self-monitoring)"


_autonomy_metric: AutonomyMetric | None = None


def get_autonomy_metric() -> AutonomyMetric:
    global _autonomy_metric
    if _autonomy_metric is None:
        _autonomy_metric = AutonomyMetric()
    return _autonomy_metric


def compute_autonomy_level(**subsystem_reports: dict) -> AutonomyReport:
    """Convenience function: compute autonomy level from current system state."""
    metric = get_autonomy_metric()
    return metric.measure(**subsystem_reports)
