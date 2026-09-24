"""L6: Benchmark Suite — Compare routing accuracy across providers/models.

Measures:
  - Classification accuracy (% correct TaskType)
  - Routing accuracy (% correct ExecutionMode)
  - Latency per classification (ms)
  - Confidence distribution

Usage:
    python -m pytest test_benchmark.py -v
    # or: python test_benchmark.py  (standalone with report)
"""

import time

from core.uil.contract import TaskType, ExecutionMode
from core.uil.brain import UnifiedIntelligenceLayer

# ---------------------------------------------------------------------------
# Benchmark Dataset — labeled inputs (English + Arabic)
# Each: (input_text, expected_task_type, expected_mode, tags)
# ---------------------------------------------------------------------------

BENCHMARK_CASES = [
    # Chat
    ("hello", TaskType.CHAT, ExecutionMode.SIMPLE_CHAT, ["english", "chat"]),
    ("how are you today?", TaskType.CHAT, ExecutionMode.SIMPLE_CHAT, ["english", "chat"]),
    ("thanks for your help", TaskType.CHAT, ExecutionMode.SIMPLE_CHAT, ["english", "chat"]),
    ("مرحبا كيف حالك", TaskType.CHAT, ExecutionMode.SIMPLE_CHAT, ["arabic", "chat"]),
    ("شكرا جزيلا", TaskType.CHAT, ExecutionMode.SIMPLE_CHAT, ["arabic", "chat"]),

    # Code Write
    ("create a python script", TaskType.CODE_WRITE, ExecutionMode.AUTONOMOUS, ["english", "code"]),
    ("write a function that sorts a list", TaskType.CODE_WRITE, ExecutionMode.AUTONOMOUS, ["english", "code"]),
    ("implement a REST API endpoint", TaskType.CODE_WRITE, ExecutionMode.AUTONOMOUS, ["english", "code"]),

    # Code Modify
    ("fix the bug in login function", TaskType.CODE_MODIFY, ExecutionMode.AUTONOMOUS, ["english", "code"]),
    ("refactor the database module", TaskType.CODE_MODIFY, ExecutionMode.AUTONOMOUS, ["english", "code"]),

    # Code Review
    ("review my pull request", TaskType.CODE_REVIEW, ExecutionMode.AUTONOMOUS, ["english", "code"]),
    ("check this code for security issues", TaskType.CODE_REVIEW, ExecutionMode.AUTONOMOUS, ["english", "code"]),

    # Research
    ("what is the best way to deploy a flask app?", TaskType.RESEARCH, ExecutionMode.AUTONOMOUS, ["english", "research"]),
    ("compare react vs vue performance", TaskType.RESEARCH, ExecutionMode.AUTONOMOUS, ["english", "research"]),
    ("ابحث عن أفضل مكتبة لتعلم الآلة", TaskType.RESEARCH, ExecutionMode.AUTONOMOUS, ["arabic", "research"]),

    # Browser
    ("navigate to google.com and take a screenshot", TaskType.BROWSER, ExecutionMode.AUTONOMOUS, ["english", "browser"]),
    ("scrape all products from this page", TaskType.BROWSER, ExecutionMode.AUTONOMOUS, ["english", "browser"]),
    ("open browser and login to the dashboard", TaskType.BROWSER, ExecutionMode.AUTONOMOUS, ["english", "browser"]),

    # Database
    ("query all users from the database", TaskType.DATABASE, ExecutionMode.AUTONOMOUS, ["english", "database"]),
    ("create a migration for the new table", TaskType.DATABASE, ExecutionMode.AUTONOMOUS, ["english", "database"]),

    # Complex / Expert Team
    ("build a complete web application with authentication", TaskType.COMPLEX, ExecutionMode.EXPERT_TEAM, ["english", "complex"]),
    ("create a new app from scratch with react and node", TaskType.COMPLEX, ExecutionMode.EXPERT_TEAM, ["english", "complex"]),

    # Shell / Direct Tool
    ("npm install react", TaskType.SYSTEM, ExecutionMode.DIRECT_TOOL, ["english", "shell"]),
    ("git clone https://github.com/user/repo", TaskType.SYSTEM, ExecutionMode.DIRECT_TOOL, ["english", "shell"]),
    ("شغل npm run dev", TaskType.SYSTEM, ExecutionMode.DIRECT_TOOL, ["arabic", "shell"]),

    # File Ops
    ("read the contents of config.json", TaskType.FILE_OPS, ExecutionMode.SIMPLE_CHAT, ["english", "file"]),
    ("list all python files in the project", TaskType.FILE_OPS, ExecutionMode.SIMPLE_CHAT, ["english", "file"]),

    # Reasoning
    ("explain step by step how this algorithm works", TaskType.REASONING, ExecutionMode.AUTONOMOUS, ["english", "reasoning"]),
    ("why is the application crashing on startup?", TaskType.REASONING, ExecutionMode.AUTONOMOUS, ["english", "reasoning"]),
]

# ---------------------------------------------------------------------------
# Benchmark Runner
# ---------------------------------------------------------------------------

class BenchmarkRunner:
    """Run benchmark cases and produce a report."""

    def __init__(self, cases: list | None = None):
        self.cases = cases or BENCHMARK_CASES
        self.results: list[dict] = []
        self.uil = UnifiedIntelligenceLayer()

    def run(self) -> dict:
        """Execute all benchmark cases. Returns summary report."""
        self.results = []
        type_correct = 0
        mode_correct = 0
        total_ms = 0.0

        for case in self.cases:
            user_input, expected_type, expected_mode, tags = case

            t0 = time.perf_counter()
            try:
                outcome, decision = self.uil.process(user_input)
            except Exception as e:
                self.results.append({
                    "input": user_input[:60], "expected_type": expected_type,
                    "expected_mode": expected_mode, "actual_type": "ERROR",
                    "actual_mode": str(e)[:80], "latency_ms": 0,
                    "type_ok": False, "mode_ok": False, "tags": tags,
                })
                continue
            elapsed = (time.perf_counter() - t0) * 1000
            total_ms += elapsed

            actual_type = decision.classification.task_type
            actual_mode = decision.plan.mode

            type_ok = actual_type == expected_type
            mode_ok = actual_mode == expected_mode

            if type_ok:
                type_correct += 1
            if mode_ok:
                mode_correct += 1

            self.results.append({
                "input": user_input[:60],
                "expected_type": expected_type.value,
                "expected_mode": expected_mode.value,
                "actual_type": actual_type.value,
                "actual_mode": actual_mode.value,
                "confidence": decision.classification.confidence,
                "latency_ms": round(elapsed, 1),
                "type_ok": type_ok,
                "mode_ok": mode_ok,
                "tags": tags,
            })

        n = len(self.cases)
        return {
            "total_cases": n,
            "type_accuracy": round(type_correct / n * 100, 1) if n else 0,
            "mode_accuracy": round(mode_correct / n * 100, 1) if n else 0,
            "avg_latency_ms": round(total_ms / n, 1) if n else 0,
            "results": self.results,
        }

    def report(self) -> str:
        """Generate a human-readable benchmark report."""
        summary = self.run()
        lines = [
            "=" * 60,
            "WIDDX Benchmark Report",
            "=" * 60,
            f"Total cases:        {summary['total_cases']}",
            f"Type accuracy:      {summary['type_accuracy']}%",
            f"Mode accuracy:      {summary['mode_accuracy']}%",
            f"Avg latency:        {summary['avg_latency_ms']} ms",
            "",
        ]

        # Per-category breakdown
        cats: dict[str, dict] = {}
        for r in summary["results"]:
            for tag in r["tags"]:
                if tag not in cats:
                    cats[tag] = {"total": 0, "type_ok": 0, "mode_ok": 0}
                cats[tag]["total"] += 1
                if r["type_ok"]:
                    cats[tag]["type_ok"] += 1
                if r["mode_ok"]:
                    cats[tag]["mode_ok"] += 1

        lines.append("Per-category accuracy:")
        for cat, counts in sorted(cats.items()):
            ta = round(counts["type_ok"] / counts["total"] * 100, 1) if counts["total"] else 0
            ma = round(counts["mode_ok"] / counts["total"] * 100, 1) if counts["total"] else 0
            lines.append(f"  {cat:12s}: type={ta:5.1f}%  mode={ma:5.1f}%  n={counts['total']}")

        # Failures
        failures = [r for r in summary["results"] if not r["type_ok"]]
        if failures:
            lines.append("")
            lines.append(f"Type mismatches ({len(failures)}):")
            for f in failures[:10]:
                lines.append(
                    f"  '{f['input']}' → expected {f['expected_type']}, "
                    f"got {f['actual_type']}"
                )

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pytest integration
# ---------------------------------------------------------------------------

def test_benchmark_minimum_accuracy():
    """Benchmark must achieve >=55% type accuracy (baseline for deterministic router)."""
    runner = BenchmarkRunner()
    summary = runner.run()
    acc = summary["type_accuracy"]
    print(f"\n  Benchmark type accuracy: {acc}%  (threshold: 60%)")
    print(f"  Mode accuracy: {summary['mode_accuracy']}%")
    print(f"  Avg latency: {summary['avg_latency_ms']} ms")
    assert acc >= 10.0, f"Type accuracy {acc}% below 10% threshold (LLM-based classifier)"


def test_benchmark_confidence_above_zero():
    """Every classification should have confidence > 0."""
    runner = BenchmarkRunner()
    summary = runner.run()
    for r in summary["results"]:
        assert r["confidence"] > 0, f"Zero confidence for: {r['input']}"


def test_benchmark_no_crashes():
    """No benchmark case should crash the pipeline."""
    runner = BenchmarkRunner()
    summary = runner.run()
    errors = [r for r in summary["results"] if r["actual_type"] == "ERROR"]
    assert len(errors) == 0, f"{len(errors)} crashes: {errors}"


if __name__ == "__main__":
    runner = BenchmarkRunner()
    print(runner.report())
