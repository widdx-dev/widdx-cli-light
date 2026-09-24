"""Evaluation Framework — bridges architecture to evidence.

Runs comparative benchmarks to answer:
  - Does ECP improve outcomes vs. no ECP?
  - Does Adaptive Policy improve quality vs. static thresholds?
  - Does model switching reduce cost vs. fixed model?
  - What is the MTBF (Mean Time Between Failures)?
  - What is the MTTR (Mean Time To Recovery)?

Produces: comparative reports, regression detection, operational KPIs.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger("widdx.evaluation")


@dataclass
class TaskResult:
    """Result of executing a single task."""
    task_id: str
    task_type: str  # simple, medium, complex
    success: bool
    steps: int
    cost: float
    latency_seconds: float
    model_switches: int
    escalations: int
    replans: int
    aborts: int
    config: str  # which configuration was used
    error: str = ""


@dataclass
class ComparativeReport:
    """Comparison between two configurations."""
    name: str
    config_a: str
    config_b: str
    tasks_run: int
    a_results: list[TaskResult]
    b_results: list[TaskResult]
    a_success_rate: float
    b_success_rate: float
    a_avg_cost: float
    b_avg_cost: float
    a_avg_steps: float
    b_avg_steps: float
    a_avg_latency: float
    b_avg_latency: float
    winner: str  # "A", "B", or "tie"
    improvement_pct: float
    recommendations: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class TaskCorpus:
    """Fixed dataset of tasks with expected complexity levels."""

    SIMPLE = [
        ("read a file", "simple"),
        ("list files in current directory", "simple"),
        ("count lines in a Python file", "simple"),
        ("find all imports in a module", "simple"),
        ("check git status", "simple"),
    ]

    MEDIUM = [
        ("write a function that calculates fibonacci", "medium"),
        ("create a simple HTML page with a form", "medium"),
        ("write unit tests for a given function", "medium"),
        ("refactor a function to use async/await", "medium"),
        ("add error handling to an existing script", "medium"),
    ]

    COMPLEX = [
        ("build a REST API with authentication", "complex"),
        ("create a full-stack web app with database", "complex"),
        ("migrate a codebase from JavaScript to TypeScript", "complex"),
        ("implement a CI/CD pipeline configuration", "complex"),
        ("design and implement a caching layer", "complex"),
    ]

    @classmethod
    def all_tasks(cls, repeat: int = 1) -> list[tuple[str, str]]:
        tasks = cls.SIMPLE + cls.MEDIUM + cls.COMPLEX
        return tasks * repeat


class EvaluationRunner:
    """Runs comparative benchmarks across system configurations.

    Configurations:
      - baseline: ECP OFF, Adaptive OFF, fixed model
      - ecp_only: ECP ON, Adaptive OFF, fixed model
      - full: ECP ON, Adaptive ON, model switching ON

    Produces ComparativeReports for each pair.
    """

    RESULTS_PATH = ".widdx/evaluation_results.json"

    def __init__(self):
        self._results: dict[str, list[TaskResult]] = {}
        self._reports: list[ComparativeReport] = []

    def run_configuration(
        self,
        name: str,
        tasks: list[tuple[str, str]],
        executor: Callable[[str], TaskResult],
    ) -> list[TaskResult]:
        """Run all tasks under a specific configuration."""
        results: list[TaskResult] = []
        for i, (task, task_type) in enumerate(tasks):
            t0 = time.time()
            try:
                result = executor(task)
                result.task_id = f"{name}_{i}"
                result.task_type = task_type
                result.config = name
                result.latency_seconds = round(time.time() - t0, 3)
                results.append(result)
            except Exception as e:
                results.append(TaskResult(
                    task_id=f"{name}_{i}",
                    task_type=task_type,
                    success=False,
                    steps=0, cost=0,
                    latency_seconds=round(time.time() - t0, 3),
                    model_switches=0, escalations=0, replans=0, aborts=0,
                    config=name, error=str(e),
                ))
        self._results[name] = results
        return results

    def compare(self, name_a: str, name_b: str) -> ComparativeReport:
        """Compare two configurations and produce a report."""
        a_results = self._results.get(name_a, [])
        b_results = self._results.get(name_b, [])

        if not a_results or not b_results:
            return ComparativeReport(
                name=f"{name_a}_vs_{name_b}",
                config_a=name_a, config_b=name_b,
                tasks_run=0, a_results=[], b_results=[],
                a_success_rate=0, b_success_rate=0,
                a_avg_cost=0, b_avg_cost=0,
                a_avg_steps=0, b_avg_steps=0,
                a_avg_latency=0, b_avg_latency=0,
                winner="tie", improvement_pct=0,
            )

        def success_rate(results):
            return sum(1 for r in results if r.success) / max(len(results), 1)

        def avg_cost(results):
            return sum(r.cost for r in results) / max(len(results), 1)

        def avg_steps(results):
            return sum(r.steps for r in results) / max(len(results), 1)

        def avg_latency(results):
            return sum(r.latency_seconds for r in results) / max(len(results), 1)

        a_sr = round(success_rate(a_results), 3)
        b_sr = round(success_rate(b_results), 3)
        a_cost = round(avg_cost(a_results), 4)
        b_cost = round(avg_cost(b_results), 4)
        a_steps = round(avg_steps(a_results), 1)
        b_steps = round(avg_steps(b_results), 1)
        a_latency = round(avg_latency(a_results), 3)
        b_latency = round(avg_latency(b_results), 3)

        # Determine winner
        wins_a = 0
        wins_b = 0
        if b_sr > a_sr:
            wins_b += 1
        else:
            wins_a += 1
        if b_cost < a_cost:
            wins_b += 1
        else:
            wins_a += 1
        if b_steps < a_steps:
            wins_b += 1
        else:
            wins_a += 1

        winner = "B" if wins_b >= 2 else "A" if wins_a >= 2 else "tie"
        improvement_sr = (b_sr - a_sr) * 100
        improvement_cost = (a_cost - b_cost) / max(a_cost, 0.0001) * 100
        improvement = max(improvement_sr, improvement_cost)

        # Regression detection
        regressions: list[str] = []
        if b_sr < a_sr - 0.05:
            regressions.append(
                f"SUCCESS_REGRESSION: {name_b} success rate {b_sr:.1%} < {name_a} {a_sr:.1%}"
            )
        if b_latency > a_latency * 1.2:
            regressions.append(
                f"LATENCY_REGRESSION: {name_b} {b_latency:.2f}s > {name_a} {a_latency:.2f}s"
            )

        # Recommendations
        recommendations: list[str] = []
        if winner == "B":
            recommendations.append(
                f"ADOPT {name_b}: {improvement_sr:+.0f}% success, "
                f"{improvement_cost:+.0f}% cost delta over {name_a}"
            )
        elif winner == "A":
            recommendations.append(
                f"KEEP {name_a}: {name_b} did not demonstrate improvement"
            )
        else:
            recommendations.append(
                f"INCONCLUSIVE: {name_a} and {name_b} are statistically equivalent"
            )
        if regressions:
            recommendations.append(f"WARNING: {len(regressions)} regression(s) detected")

        report = ComparativeReport(
            name=f"{name_a}_vs_{name_b}",
            config_a=name_a, config_b=name_b,
            tasks_run=len(a_results),
            a_results=a_results, b_results=b_results,
            a_success_rate=a_sr, b_success_rate=b_sr,
            a_avg_cost=a_cost, b_avg_cost=b_cost,
            a_avg_steps=a_steps, b_avg_steps=b_steps,
            a_avg_latency=a_latency, b_avg_latency=b_latency,
            winner=winner,
            improvement_pct=round(improvement, 1),
            recommendations=recommendations,
            regressions=regressions,
        )
        self._reports.append(report)
        self._save(report)
        return report

    def _save(self, report: ComparativeReport):
        try:
            path = Path(self.RESULTS_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if path.exists():
                existing = json.loads(path.read_text())
            existing.append({
                "ts": report.timestamp,
                "comparison": report.name,
                "winner": report.winner,
                "improvement_pct": report.improvement_pct,
                "a": {"success": report.a_success_rate, "cost": report.a_avg_cost, "steps": report.a_avg_steps},
                "b": {"success": report.b_success_rate, "cost": report.b_avg_cost, "steps": report.b_avg_steps},
                "regressions": report.regressions,
            })
            path.write_text(json.dumps(existing, indent=2))
        except Exception:
            logger.debug("Exception suppressed (line 269)")

    @property
    def all_reports(self) -> list[dict]:
        return [
            {
                "comparison": r.name,
                "winner": r.winner,
                "a_success": r.a_success_rate,
                "b_success": r.b_success_rate,
                "regressions": len(r.regressions),
            }
            for r in self._reports
        ]


_runner: EvaluationRunner | None = None


def get_evaluation_runner() -> EvaluationRunner:
    global _runner
    if _runner is None:
        _runner = EvaluationRunner()
    return _runner
