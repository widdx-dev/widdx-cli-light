"""Performance Benchmark System — measures agent improvement over time.

Creates real tasks, measures success rate, and tracks improvement.
Compares performance with and without the neural control systems.

Metrics tracked:
  - Success rate: % of tasks completed successfully
  - Efficiency: steps per task (fewer = better)
  - Quality: output quality score
  - Recovery: number of self-healing interventions needed
  - Time: wall-clock time per task
"""

from __future__ import annotations

import json
import logging
import time

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("widdx.benchmark")


@dataclass
class TaskResult:
    """Result of a single task execution."""
    task_id: str
    task_description: str
    success: bool
    steps_taken: int
    quality_score: float  # 0-1
    healing_interventions: int
    time_seconds: float
    error_count: int
    output_files: list[str]
    signals_generated: dict[str, int]
    decisions_made: dict[str, int]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_description": self.task_description[:100],
            "success": self.success,
            "steps_taken": self.steps_taken,
            "quality_score": self.quality_score,
            "healing_interventions": self.healing_interventions,
            "time_seconds": round(self.time_seconds, 2),
            "error_count": self.error_count,
            "output_files": len(self.output_files),
            "signals_generated": self.signals_generated,
            "decisions_made": self.decisions_made,
            "timestamp": self.timestamp,
        }


@dataclass
class BenchmarkSuite:
    """A collection of tasks to measure performance."""
    name: str
    description: str
    tasks: list[dict[str, Any]]
    success_criteria: dict[str, Any]


class PerformanceTracker:
    """Tracks performance over time and measures improvement."""

    def __init__(self, storage_path: str = ".widdx/performance_history.json"):
        self._storage_path = Path(storage_path)
        self._history: list[dict[str, Any]] = []
        self._load_history()

    def _load_history(self):
        if self._storage_path.exists():
            try:
                self._history = json.loads(self._storage_path.read_text())
            except Exception:
                self._history = []

    def _save_history(self):
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(self._history, indent=2, default=str))

    def record_result(self, result: TaskResult):
        """Record a task result."""
        self._history.append(result.to_dict())
        self._save_history()

    def get_summary(self, last_n: int = 50) -> dict[str, Any]:
        """Get performance summary for last N tasks."""
        recent = self._history[-last_n:] if len(self._history) > last_n else self._history
        if not recent:
            return {"total_tasks": 0}

        successes = sum(1 for r in recent if r.get("success"))
        total = len(recent)

        return {
            "total_tasks": total,
            "success_rate": round(successes / total, 3) if total > 0 else 0,
            "avg_steps": round(sum(r.get("steps_taken", 0) for r in recent) / total, 1) if total > 0 else 0,
            "avg_quality": round(sum(r.get("quality_score", 0) for r in recent) / total, 3) if total > 0 else 0,
            "avg_healing": round(sum(r.get("healing_interventions", 0) for r in recent) / total, 2) if total > 0 else 0,
            "avg_time": round(sum(r.get("time_seconds", 0) for r in recent) / total, 1) if total > 0 else 0,
            "total_errors": sum(r.get("error_count", 0) for r in recent),
        }

    def compare_periods(self, period1_size: int = 25, period2_size: int = 25) -> dict[str, Any]:
        """Compare two time periods to measure improvement."""
        if len(self._history) < period1_size + period2_size:
            return {"insufficient_data": True, "total_records": len(self._history)}

        period1 = self._history[-(period1_size + period2_size):-period2_size]
        period2 = self._history[-period2_size:]

        def calc_stats(tasks):
            if not tasks:
                return {}
            successes = sum(1 for t in tasks if t.get("success"))
            return {
                "success_rate": round(successes / len(tasks), 3),
                "avg_steps": round(sum(t.get("steps_taken", 0) for t in tasks) / len(tasks), 1),
                "avg_quality": round(sum(t.get("quality_score", 0) for t in tasks) / len(tasks), 3),
                "avg_time": round(sum(t.get("time_seconds", 0) for t in tasks) / len(tasks), 1),
            }

        stats1 = calc_stats(period1)
        stats2 = calc_stats(period2)

        improvement = {}
        for key in stats1:
            if stats1[key] != 0:
                improvement[f"{key}_change"] = round((stats2[key] - stats1[key]) / abs(stats1[key]) * 100, 1)
            else:
                improvement[f"{key}_change"] = 0

        return {
            "period1": stats1,
            "period2": stats2,
            "improvement_pct": improvement,
            "is_improving": improvement.get("success_rate_change", 0) > 0,
        }

    def get_trend(self, window: int = 10) -> list[dict[str, Any]]:
        """Get performance trend over time."""
        if len(self._history) < window:
            return self._history

        trends = []
        for i in range(0, len(self._history) - window + 1, window):
            chunk = self._history[i:i + window]
            successes = sum(1 for t in chunk if t.get("success"))
            trends.append({
                "window": i // window,
                "success_rate": round(successes / len(chunk), 3),
                "avg_quality": round(sum(t.get("quality_score", 0) for t in chunk) / len(chunk), 3),
            })
        return trends


class TaskGenerator:
    """Generates benchmark tasks for testing agent performance."""

    @staticmethod
    def get_standard_tasks() -> list[dict[str, Any]]:
        """Get a set of standard benchmark tasks."""
        return [
            {
                "id": "create_file",
                "description": "Create a Python file hello.py that prints 'Hello, World!'",
                "type": "file_creation",
                "success_criteria": {
                    "file_exists": "hello.py",
                    "content_contains": "Hello, World",
                },
                "difficulty": "easy",
            },
            {
                "id": "fix_syntax_error",
                "description": "Fix the syntax error in the provided code: def foo( print('hi')",
                "type": "bug_fix",
                "success_criteria": {
                    "syntax_valid": True,
                    "runs_without_error": True,
                },
                "difficulty": "easy",
            },
            {
                "id": "refactor_code",
                "description": "Refactor the following code to use a function: x = 1\\ny = 2\\nprint(x + y)",
                "type": "refactoring",
                "success_criteria": {
                    "has_function": True,
                    "runs_correctly": True,
                },
                "difficulty": "medium",
            },
            {
                "id": "add_error_handling",
                "description": "Add try/except error handling to: result = 10 / 0",
                "type": "enhancement",
                "success_criteria": {
                    "has_try_except": True,
                    "handles_zero_division": True,
                },
                "difficulty": "medium",
            },
            {
                "id": "create_class",
                "description": "Create a Python class Calculator with add, subtract, multiply, divide methods",
                "type": "class_creation",
                "success_criteria": {
                    "has_class": True,
                    "has_methods": ["add", "subtract", "multiply", "divide"],
                },
                "difficulty": "medium",
            },
            {
                "id": "debug_logic_error",
                "description": "Debug: this code should return 15 but returns 0. def sum_list(lst): total = 0\\nfor i in range(len(lst)): total = lst[i]\\nreturn total",
                "type": "debugging",
                "success_criteria": {
                    "returns_correct": True,
                    "test_passes": True,
                },
                "difficulty": "hard",
            },
        ]

    @staticmethod
    def get_stress_tasks() -> list[dict[str, Any]]:
        """Get stress-test tasks that trigger self-healing."""
        return [
            {
                "id": "infinite_loop_risk",
                "description": "Write a while loop that prints numbers 1 to 10",
                "type": "loop_writing",
                "success_criteria": {
                    "no_infinite_loop": True,
                    "prints_1_to_10": True,
                },
                "difficulty": "medium",
                "triggers": ["LOOP_DETECTED"],
            },
            {
                "id": "memory_heavy",
                "description": "Create a list of 1 million numbers and find the sum",
                "type": "memory_intensive",
                "success_criteria": {
                    "completes": True,
                    "correct_sum": True,
                },
                "difficulty": "medium",
                "triggers": ["MEMORY_PRESSURE"],
            },
            {
                "id": "repeated_failures",
                "description": "Read a non-existent file, handle the error gracefully",
                "type": "error_handling",
                "success_criteria": {
                    "handles_error": True,
                    "no_crash": True,
                },
                "difficulty": "easy",
                "triggers": ["TOOL_FAILURE_RATE"],
            },
        ]


class BenchmarkRunner:
    """Runs benchmarks and measures performance."""

    def __init__(self):
        self.tracker = PerformanceTracker()
        self.task_generator = TaskGenerator()

    def run_benchmark(
        self,
        agent_runner: Any,
        tasks: list[dict[str, Any]] | None = None,
        verbose: bool = True,
    ) -> dict[str, Any]:
        """Run a benchmark suite and return results."""
        if tasks is None:
            tasks = self.task_generator.get_standard_tasks()

        results = []
        start_time = time.time()

        for task in tasks:
            if verbose:
                print(f"  Running: {task['id']} ({task.get('difficulty', 'unknown')})")

            task_start = time.time()
            try:
                # Run the task through the agent
                success, details = agent_runner(task)
                task_time = time.time() - task_start

                result = TaskResult(
                    task_id=task["id"],
                    task_description=task["description"],
                    success=success,
                    steps_taken=details.get("steps", 0),
                    quality_score=details.get("quality", 0.5),
                    healing_interventions=details.get("healing", 0),
                    time_seconds=task_time,
                    error_count=details.get("errors", 0),
                    output_files=details.get("output_files", []),
                    signals_generated=details.get("signals", {}),
                    decisions_made=details.get("decisions", {}),
                )
                results.append(result)
                self.tracker.record_result(result)

                if verbose:
                    status = "✅" if success else "❌"
                    print(f"    {status} steps={result.steps_taken}, quality={result.quality_score:.2f}")

            except Exception as e:
                logger.error(f"Task {task['id']} failed: {e}")
                if verbose:
                    print(f"    ❌ ERROR: {e}")

        total_time = time.time() - start_time
        successes = sum(1 for r in results if r.success)

        return {
            "total_tasks": len(tasks),
            "completed": successes,
            "success_rate": round(successes / len(tasks), 3) if tasks else 0,
            "total_time": round(total_time, 1),
            "results": [r.to_dict() for r in results],
        }

    def get_performance_report(self) -> dict[str, Any]:
        """Get comprehensive performance report."""
        return {
            "summary": self.tracker.get_summary(),
            "comparison": self.tracker.compare_periods(),
            "trend": self.tracker.get_trend(),
        }


# Singleton
_performance_tracker: PerformanceTracker | None = None


def get_performance_tracker() -> PerformanceTracker:
    global _performance_tracker
    if _performance_tracker is None:
        _performance_tracker = PerformanceTracker()
    return _performance_tracker
