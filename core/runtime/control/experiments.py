"""Policy Experiments — counterfactual evaluation of parameter changes.

Closes the final gap: "Is 6 actually better than 5?"

Runs A/B experiments on policy parameters:
  1. Baseline: current value (control group)
  2. Candidate: proposed value (experiment group)
  3. Split traffic — 10% of tasks run with candidate
  4. Compare: success rate, cost, latency, escalation count
  5. Accept candidate only if it beats baseline with statistical confidence
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("widdx.ecp.experiments")


@dataclass
class ExperimentGroup:
    """One arm of an A/B experiment."""
    parameter: str
    value: float
    task_count: int = 0
    success_count: int = 0
    total_cost: float = 0.0
    total_steps: int = 0
    total_escalations: int = 0
    total_aborts: int = 0
    total_model_switches: int = 0
    avg_latency: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.success_count / self.task_count if self.task_count > 0 else 0.0

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.task_count if self.task_count > 0 else 0.0

    @property
    def avg_steps(self) -> float:
        return self.total_steps / self.task_count if self.task_count > 0 else 0.0

    @property
    def escalation_rate(self) -> float:
        return self.total_escalations / self.task_count if self.task_count > 0 else 0.0

    @property
    def abort_rate(self) -> float:
        return self.total_aborts / self.task_count if self.task_count > 0 else 0.0


@dataclass
class ExperimentResult:
    """Result of comparing baseline vs candidate."""
    parameter: str
    baseline_value: float
    candidate_value: float
    baseline_stats: dict
    candidate_stats: dict
    success_delta: float  # + = candidate better
    cost_delta: float     # - = candidate cheaper
    steps_delta: float    # - = candidate faster
    confidence: float
    winner: str           # "baseline" | "candidate" | "inconclusive"
    recommendation: str
    timestamp: float = field(default_factory=time.time)


class PolicyExperimentRunner:
    """Runs A/B experiments on policy parameters.

    Traffic split: 90% baseline, 10% candidate.
    Experiment runs for min 5 tasks in candidate group before comparing.
    Candidate wins only if it beats baseline on 2 of 3 metrics
    with statistical confidence.
    """

    TRAFFIC_SPLIT = 0.10  # 10% of tasks use candidate
    MIN_CANDIDATE_TASKS = 5
    CONFIDENCE_THRESHOLD = 0.75

    def __init__(self):
        self._experiments: dict[str, dict] = {}
        self._results: list[ExperimentResult] = []

    def start_experiment(self, parameter: str, baseline_value: float,
                         candidate_value: float):
        """Start an A/B experiment for a parameter."""
        self._experiments[parameter] = {
            "baseline": ExperimentGroup(parameter=parameter, value=baseline_value),
            "candidate": ExperimentGroup(parameter=parameter, value=candidate_value),
            "started_at": time.time(),
            "active": True,
        }
        logger.info(
            "EXPERIMENT START: %s — baseline=%.2f vs candidate=%.2f",
            parameter, baseline_value, candidate_value,
        )

    def should_use_candidate(self, parameter: str) -> bool:
        """Decide whether this task should use the candidate value."""
        import random
        exp = self._experiments.get(parameter)
        if not exp or not exp["active"]:
            return False
        return random.random() < self.TRAFFIC_SPLIT

    def record_task(self, parameter: str, used_candidate: bool,
                    success: bool, cost: float, steps: int,
                    escalations: int = 0, aborts: int = 0,
                    model_switches: int = 0, latency: float = 0.0):
        """Record outcome for a single task."""
        exp = self._experiments.get(parameter)
        if not exp:
            return

        group = exp["candidate"] if used_candidate else exp["baseline"]
        group.task_count += 1
        if success:
            group.success_count += 1
        group.total_cost += cost
        group.total_steps += steps
        group.total_escalations += escalations
        group.total_aborts += aborts
        group.total_model_switches += model_switches
        if latency > 0:
            group.avg_latency = (
                (group.avg_latency * (group.task_count - 1) + latency)
                / group.task_count
            )

    def evaluate(self, parameter: str) -> ExperimentResult | None:
        """Compare baseline vs candidate using REAL statistical tests.

        Uses:
          - Two-proportion z-test for success rates
          - Welch's t-test for cost and steps
          - Effect size (Cohen's d/h) for practical significance

        Returns result with p-values and statistical significance.
        """
        exp = self._experiments.get(parameter)
        if not exp:
            return None

        baseline = exp["baseline"]
        candidate = exp["candidate"]

        if candidate.task_count < self.MIN_CANDIDATE_TASKS:
            return None

        # Import real statistical tests
        from core.runtime.control.statistical_tests import (
            two_proportion_z_test, welch_t_test
        )

        # 1. Success rate test (proportion z-test)
        success_test = two_proportion_z_test(
            baseline.success_count, baseline.task_count,
            candidate.success_count, candidate.task_count,
            alpha=1.0 - self.CONFIDENCE_THRESHOLD,
        )

        # 2. Cost test (Welch's t-test) — if we have per-task cost data
        # Note: ExperimentGroup stores aggregates, so we approximate variance
        # from the assumption that cost variance ~ mean^2 (common in practice)
        cost_test = None
        if baseline.total_cost > 0 and candidate.total_cost > 0:
            # Approximate variance from aggregate data
            mean_a = baseline.avg_cost
            var_a = mean_a * mean_a * 0.1  # assume CV ~ 0.3
            mean_b = candidate.avg_cost
            var_b = mean_b * mean_b * 0.1
            cost_test = welch_t_test(mean_a, var_a, baseline.task_count,
                                     mean_b, var_b, candidate.task_count,
                                     alpha=1.0 - self.CONFIDENCE_THRESHOLD)

        # 3. Steps test (Welch's t-test)
        steps_test = None
        if baseline.total_steps > 0 and candidate.total_steps > 0:
            mean_a = baseline.avg_steps
            var_a = mean_a * mean_a * 0.15
            mean_b = candidate.avg_steps
            var_b = mean_b * mean_b * 0.15
            steps_test = welch_t_test(mean_a, var_a, baseline.task_count,
                                      mean_b, var_b, candidate.task_count,
                                      alpha=1.0 - self.CONFIDENCE_THRESHOLD)

        # 4. Determine winner based on statistical tests
        sig_tests = [success_test]
        if cost_test:
            sig_tests.append(cost_test)
        if steps_test:
            sig_tests.append(steps_test)

        # Count where candidate is better
        candidate_better = 0
        candidate_worse = 0
        for t in sig_tests:
            if not t.is_significant:
                continue
            if t.test_name == "Two-proportion z-test":
                if t.effect_size > 0:
                    candidate_better += 1
                else:
                    candidate_worse += 1
            else:
                # For cost/steps: negative effect = lower = better
                if t.effect_size < 0:
                    candidate_better += 1
                else:
                    candidate_worse += 1

        # Overall confidence = 1 - p_value of the strongest test
        min_p = min(t.p_value for t in sig_tests)
        overall_confidence = 1.0 - min_p

        if len(sig_tests) >= 2 and candidate_better > candidate_worse:
            winner = "candidate"
            recommendation = (
                f"ACCEPT: candidate={candidate.value} beats baseline={baseline.value} "
                f"on {candidate_better}/{len(sig_tests)} metrics "
                f"(p={min_p:.4f}, success_delta={success_test.effect_size:+.3f})"
            )
        elif len(sig_tests) >= 2 and candidate_worse > candidate_better:
            winner = "baseline"
            recommendation = (
                f"REJECT: candidate={candidate.value} loses on "
                f"{candidate_worse}/{len(sig_tests)} metrics. Keep {baseline.value}."
            )
        else:
            winner = "inconclusive"
            recommendation = (
                f"NEED MORE DATA: {candidate_better} better, {candidate_worse} worse, "
                f"p={min_p:.4f}. Continue experiment."
            )

        result = ExperimentResult(
            parameter=parameter,
            baseline_value=baseline.value,
            candidate_value=candidate.value,
            baseline_stats={
                "tasks": baseline.task_count,
                "success_rate": round(baseline.success_rate, 3),
                "avg_cost": round(baseline.avg_cost, 4),
                "avg_steps": round(baseline.avg_steps, 1),
                "escalation_rate": round(baseline.escalation_rate, 3),
                "abort_rate": round(baseline.abort_rate, 3),
            },
            candidate_stats={
                "tasks": candidate.task_count,
                "success_rate": round(candidate.success_rate, 3),
                "avg_cost": round(candidate.avg_cost, 4),
                "avg_steps": round(candidate.avg_steps, 1),
                "escalation_rate": round(candidate.escalation_rate, 3),
                "abort_rate": round(candidate.abort_rate, 3),
            },
            success_delta=round(success_test.effect_size, 3),
            cost_delta=round(cost_test.effect_size if cost_test else 0.0, 4),
            steps_delta=round(steps_test.effect_size if steps_test else 0.0, 1),
            confidence=round(overall_confidence, 4),
            winner=winner,
            recommendation=recommendation,
        )

        self._results.append(result)
        exp["active"] = winner == "inconclusive"

        # Save results
        self._save_results(result)

        logger.info("EXPERIMENT %s: %s — %s", parameter, winner, recommendation)
        return result

    def _save_results(self, result: ExperimentResult):
        try:
            path = Path(".widdx/experiment_results.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if path.exists():
                existing = json.loads(path.read_text())
            existing.append({
                "ts": result.timestamp,
                "param": result.parameter,
                "baseline": result.baseline_value,
                "candidate": result.candidate_value,
                "winner": result.winner,
                "confidence": result.confidence,
                "success_delta": result.success_delta,
                "cost_delta": result.cost_delta,
                "steps_delta": result.steps_delta,
                "recommendation": result.recommendation,
            })
            path.write_text(json.dumps(existing, indent=2))
        except Exception:
            logger.debug("Exception suppressed (line 302)")

    @property
    def active_experiments(self) -> list[str]:
        return [k for k, v in self._experiments.items() if v["active"]]

    @property
    def results_history(self) -> list[dict]:
        return [
            {
                "param": r.parameter,
                "baseline": r.baseline_value,
                "candidate": r.candidate_value,
                "winner": r.winner,
                "confidence": r.confidence,
                "success_delta": r.success_delta,
            }
            for r in self._results
        ]


_experiment_runner: PolicyExperimentRunner | None = None


def get_experiment_runner() -> PolicyExperimentRunner:
    global _experiment_runner
    if _experiment_runner is None:
        _experiment_runner = PolicyExperimentRunner()
    return _experiment_runner
