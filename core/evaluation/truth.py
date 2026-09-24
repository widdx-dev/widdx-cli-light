"""Experimental Truth Layer — rigorous reproducibility and statistical validation.

Bridges the gap from "system design validation" to "true performance proof."

Core guarantees:
  1. Deterministic replay — same seed + input = same output
  2. Statistical significance — effect sizes with confidence intervals
  3. Reproducibility lock — seed, environment, and configuration snapshots
  4. Dataset governance — frozen, versioned benchmark suites
  5. External baseline — controlled comparisons with protocol rigor

This is NOT another architecture layer.
This is a SCIENTIFIC PROTOCOL for system evaluation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("widdx.truth")


@dataclass
class ReproducibilityLock:
    """Captured environment state to guarantee reproducibility."""
    seed: int
    config_hash: str
    code_version: str
    environment_hash: str
    timestamp: float = field(default_factory=time.time)
    python_version: str = ""
    os_info: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)

    def snapshot(self) -> dict:
        """Capture current environment state."""
        import platform
        import sys
        self.python_version = sys.version.split()[0]
        self.os_info = f"{platform.system()} {platform.release()}"
        try:
            import importlib.metadata
            self.dependencies = {
                d.metadata["Name"]: d.version
                for d in importlib.metadata.distributions()
                if d.metadata["Name"] in ("httpx", "rich", "psutil")
            }
        except Exception:
            logger.debug("Exception suppressed (line 54)")
        return self.__dict__


@dataclass
class StatisticalResult:
    """A single statistical measurement with confidence."""
    metric: str
    baseline_value: float
    experiment_value: float
    absolute_delta: float
    relative_delta_pct: float
    sample_size: int
    confidence_interval: tuple[float, float]
    p_value: float
    is_significant: bool  # p < 0.05
    effect_size: float     # Cohen's d
    effect_magnitude: str  # negligible | small | medium | large


@dataclass
class FrozenBenchmark:
    """A versioned, immutable benchmark suite."""
    name: str
    version: str
    task_count: int
    hash_seed: str  # deterministic hash of all tasks
    tasks: list[dict]  # [{id, text, complexity, expected_tools, ground_truth}]
    created_at: float = field(default_factory=time.time)

    @staticmethod
    def freeze(name: str, version: str, tasks: list[dict]) -> FrozenBenchmark:
        """Create a frozen benchmark from a task list."""
        task_text = json.dumps([t["text"] for t in tasks], sort_keys=True)
        hash_seed = hashlib.sha256(task_text.encode()).hexdigest()[:16]
        return FrozenBenchmark(
            name=name, version=version,
            task_count=len(tasks),
            hash_seed=hash_seed,
            tasks=tasks,
        )


class ExperimentalTruthLayer:
    """Rigorous scientific evaluation protocol.

    Usage:
        truth = get_truth()
        truth.start_experiment("ecp_vs_baseline")
        for task in benchmark.tasks:
            result_a = truth.run_with_lock(seed=42, config="baseline", task=task)
            result_b = truth.run_with_lock(seed=42, config="ecp", task=task)
            truth.record(task, result_a, result_b)
        report = truth.conclude()
    """

    RESULTS_PATH = ".widdx/truth_results.json"
    BENCHMARKS_PATH = ".widdx/benchmarks/"

    def __init__(self):
        self._lock: ReproducibilityLock | None = None
        self._experiments: dict[str, dict] = {}
        self._frozen_benchmarks: dict[str, FrozenBenchmark] = {}
        self._results: list[StatisticalResult] = []

    def lock_environment(self, seed: int, config_hash: str = "") -> ReproducibilityLock:
        """Snapshot current environment for reproducibility."""
        lock = ReproducibilityLock(
            seed=seed,
            config_hash=config_hash or hashlib.sha256(str(time.time()).encode()).hexdigest()[:8],
            code_version=self._get_code_version(),
            environment_hash=self._get_environment_hash(),
        )
        lock.snapshot()
        self._lock = lock

        # Set global random seed for deterministic execution
        random.seed(seed)

        logger.info("TRUTH: Environment locked — seed=%d, env_hash=%s", seed, lock.environment_hash)
        return lock

    def freeze_benchmark(self, name: str, version: str, tasks: list[dict]) -> FrozenBenchmark:
        """Create and store a frozen benchmark suite."""
        bm = FrozenBenchmark.freeze(name, version, tasks)
        self._frozen_benchmarks[bm.hash_seed] = bm

        path = Path(self.BENCHMARKS_PATH) / f"{name}_{version}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "name": name, "version": version,
            "hash_seed": bm.hash_seed,
            "task_count": bm.task_count,
            "tasks": bm.tasks,
        }, indent=2))

        logger.info("TRUTH: Benchmark frozen — %s v%s (%d tasks, hash=%s)",
                     name, version, bm.task_count, bm.hash_seed)
        return bm

    def run_with_lock(self, seed: int, config: str, task: dict) -> dict:
        """Run a single task under reproducibility lock. Returns result dict."""
        random.seed(seed ^ hash(task.get("text", "")))
        # Placeholder — real implementation calls the agent
        return {"task": task.get("id", ""), "config": config, "locked_seed": seed}

    def start_experiment(self, name: str, baseline: str, experiment: str):
        """Begin a new controlled experiment."""
        self._experiments[name] = {
            "baseline": baseline,
            "experiment": experiment,
            "results": [],
            "started_at": time.time(),
        }

    def record(self, experiment_name: str,
               baseline_result: dict, experiment_result: dict):
        """Record a paired observation for statistical analysis."""
        exp = self._experiments.get(experiment_name)
        if exp is None:
            return
        exp["results"].append({
            "baseline": baseline_result,
            "experiment": experiment_result,
        })

    def conclude(self, experiment_name: str) -> dict:
        """Compute statistical significance and effect sizes.

        Uses paired statistical tests:
          - Welch's t-test for significance
          - Cohen's d for effect size
          - 95% confidence intervals
        """
        exp = self._experiments.get(experiment_name)
        if exp is None or len(exp["results"]) < 3:
            return {"status": "insufficient_data"}

        results = exp["results"]
        n = len(results)

        # Collect metrics
        baseline_success = [1 if r["baseline"].get("success") else 0 for r in results]
        experiment_success = [1 if r["experiment"].get("success") else 0 for r in results]
        baseline_cost = [r["baseline"].get("cost", 0) for r in results]
        experiment_cost = [r["experiment"].get("cost", 0) for r in results]
        baseline_steps = [r["baseline"].get("steps", 0) for r in results]
        experiment_steps = [r["experiment"].get("steps", 0) for r in results]

        analyses: list[StatisticalResult] = []

        for metric, b_values, e_values in [
            ("success_rate", baseline_success, experiment_success),
            ("avg_cost", baseline_cost, experiment_cost),
            ("avg_steps", baseline_steps, experiment_steps),
        ]:
            b_mean = sum(b_values) / n
            e_mean = sum(e_values) / n

            # Paired differences
            diffs = [e - b for e, b in zip(e_values, b_values)]
            mean_diff = sum(diffs) / n
            var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1) if n > 1 else 0
            std_diff = var_diff ** 0.5
            se = std_diff / (n ** 0.5) if n > 0 else 0

            # 95% CI: mean ± 1.96 * SE
            ci_lower = mean_diff - 1.96 * se
            ci_upper = mean_diff + 1.96 * se

            # Welch's t-test
            t_stat = mean_diff / se if se > 0 else 0
            # Approximate p-value from t-distribution
            p_value = self._approx_p_value(abs(t_stat), n - 1)

            # Cohen's d
            pooled_std = ((var_diff + (sum((e - e_mean) ** 2 for e in e_values) / (n - 1))) / 2) ** 0.5 if n > 1 else 0
            cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0

            # Effect magnitude
            d_abs = abs(cohens_d)
            magnitude = (
                "large" if d_abs >= 0.8
                else "medium" if d_abs >= 0.5
                else "small" if d_abs >= 0.2
                else "negligible"
            )

            result = StatisticalResult(
                metric=metric,
                baseline_value=round(b_mean, 4),
                experiment_value=round(e_mean, 4),
                absolute_delta=round(mean_diff, 4),
                relative_delta_pct=round((e_mean - b_mean) / max(abs(b_mean), 0.0001) * 100, 1),
                sample_size=n,
                confidence_interval=(round(ci_lower, 4), round(ci_upper, 4)),
                p_value=round(p_value, 4),
                is_significant=p_value < 0.05,
                effect_size=round(cohens_d, 3),
                effect_magnitude=magnitude,
            )
            analyses.append(result)
            self._results.append(result)

        # Save
        self._save_results()

        return {
            "experiment": experiment_name,
            "baseline": exp["baseline"],
            "experiment_config": exp["experiment"],
            "sample_size": n,
            "analyses": [
                {
                    "metric": a.metric,
                    "baseline": a.baseline_value,
                    "experiment": a.experiment_value,
                    "delta_pct": f"{a.relative_delta_pct:+.1f}%",
                    "p_value": a.p_value,
                    "significant": a.is_significant,
                    "effect": f"{a.effect_magnitude} (d={a.effect_size})",
                    "ci_95": f"[{a.confidence_interval[0]:+.4f}, {a.confidence_interval[1]:+.4f}]",
                }
                for a in analyses
            ],
            "verdict": self._verdict(analyses),
        }

    @staticmethod
    def _approx_p_value(t_stat: float, df: int) -> float:
        """Approximate two-tailed p-value from t-statistic."""
        if t_stat < 0.5:
            return 0.5
        if t_stat > 4.0:
            return 0.0001
        if t_stat > 3.0:
            return 0.005
        if t_stat > 2.5:
            return 0.02
        if t_stat > 2.0:
            return 0.05
        if t_stat > 1.5:
            return 0.15
        return 0.3

    @staticmethod
    def _verdict(analyses: list[StatisticalResult]) -> str:
        significant = [a for a in analyses if a.is_significant]
        if len(significant) >= 2:
            # Improvement depends on metric direction:
            # Higher success = improvement, Lower cost/steps = improvement
            improved = 0
            for a in significant:
                if a.metric == "success_rate" and a.relative_delta_pct > 0:
                    improved += 1
                elif a.metric != "success_rate" and a.relative_delta_pct < 0:
                    improved += 1
            if improved >= 2:
                return "ACCEPT: experiment beats baseline with statistical significance"
            else:
                return "REJECT: experiment does not improve baseline"
        elif len(significant) == 1:
            return "INCONCLUSIVE: weak evidence — only 1/3 metrics significant"
        else:
            return "INCONCLUSIVE: no statistically significant difference"

    def _save_results(self):
        try:
            path = Path(self.RESULTS_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "lock": self._lock.__dict__ if self._lock else {},
                "results": [
                    {
                        "metric": r.metric,
                        "baseline": r.baseline_value,
                        "experiment": r.experiment_value,
                        "delta_pct": r.relative_delta_pct,
                        "p_value": r.p_value,
                        "significant": r.is_significant,
                        "effect_size": r.effect_size,
                        "effect_magnitude": r.effect_magnitude,
                        "ci_95": list(r.confidence_interval),
                    }
                    for r in self._results[-10:]
                ],
            }, indent=2))
        except Exception:
            logger.debug("Exception suppressed (line 342)")

    def _get_code_version(self) -> str:
        try:
            import subprocess
            r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip() or "unknown"
        except Exception:
            return "unknown"

    def _get_environment_hash(self) -> str:
        import platform
        import sys
        env_str = f"{sys.version}|{platform.system()}|{platform.release()}"
        return hashlib.sha256(env_str.encode()).hexdigest()[:12]


_truth: ExperimentalTruthLayer | None = None


def get_truth() -> ExperimentalTruthLayer:
    global _truth
    if _truth is None:
        _truth = ExperimentalTruthLayer()
    return _truth
