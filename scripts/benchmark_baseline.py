#!/usr/bin/env python3
"""WIDDX Nexus — Load Testing Baseline Benchmark (Task 4.1).

Reproducible, in-process latency/RPS baseline for the web API. It runs
the real FastAPI app through an ASGI test transport (no network), so
results are stable and comparable across machines — a fixed baseline to
detect performance regressions in CI.

This complements ``locustfile.py`` (distributed, over-the-wire load
testing). Use this for quick regression baselines; use Locust for
capacity planning under real network conditions.

Usage:
    python scripts/benchmark_baseline.py                 # run all scenarios
    python scripts/benchmark_baseline.py --iterations 500
    python scripts/benchmark_baseline.py --json out.json # also emit raw JSON
    python scripts/benchmark_baseline.py --markdown report.md

Requirements:
    pip install fastapi httpx            # (already in the [api] extra)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

# Ensure repo root is importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Keep the benchmark self-contained and anonymous.
os.environ.setdefault("WIDDX_TELEMETRY_DISABLED", "1")


# ── Percentile helper (no numpy dependency) ───────────────────
def percentile(data: list[float], pct: float) -> float:
    if not data:
        return 0.0
    ordered = sorted(data)
    k = (len(ordered) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


class Scenario:
    """One named benchmark scenario."""

    def __init__(self, name: str, runner, iterations: int):
        self.name = name
        self.runner = runner          # callable(client) -> None (one request/transaction)
        self.iterations = iterations

    def run(self, client) -> dict:
        latencies: list[float] = []
        errors = 0
        # Warm-up (JIT/import caches, connection setup) — not measured.
        for _ in range(min(10, max(1, self.iterations // 10))):
            try:
                self.runner(client)
            except Exception:
                pass
        start = time.perf_counter()
        for _ in range(self.iterations):
            t0 = time.perf_counter()
            try:
                self.runner(client)
                latencies.append((time.perf_counter() - t0) * 1000.0)
            except Exception:
                errors += 1
        elapsed = time.perf_counter() - start
        ok = len(latencies)
        return {
            "scenario": self.name,
            "iterations": self.iterations,
            "ok": ok,
            "errors": errors,
            "elapsed_s": round(elapsed, 3),
            "rps": round(ok / elapsed, 1) if elapsed else 0.0,
            "p50_ms": round(percentile(latencies, 50), 2),
            "p95_ms": round(percentile(latencies, 95), 2),
            "p99_ms": round(percentile(latencies, 99), 2),
            "avg_ms": round(statistics.fmean(latencies), 2) if latencies else 0.0,
            "max_ms": round(max(latencies), 2) if latencies else 0.0,
            "error_rate_pct": round(100.0 * errors / self.iterations, 2),
        }


def build_scenarios(iterations: int) -> list[Scenario]:
    """Define the standard baseline workload."""
    import uuid

    def s_health(client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def s_livez(client):
        assert client.get("/api/livez").status_code == 200

    def s_ready(client):
        assert client.get("/api/ready").status_code == 200

    def s_tenant(client):
        assert client.get("/api/tenant").status_code == 200

    def s_telemetry(client):
        assert client.get("/api/telemetry").status_code == 200

    def s_session_crud(client):
        name = f"bench-{uuid.uuid4().hex[:8]}"
        r = client.post("/api/sessions", json={
            "name": name,
            "messages": [{"role": "user", "content": "hello"},
                         {"role": "assistant", "content": "hi"}],
        })
        data = r.json()
        sid = data.get("id")
        assert sid, data
        client.get("/api/sessions")
        client.get(f"/api/sessions/{sid}")
        client.delete(f"/api/sessions/{sid}")

    def s_memory_crud(client):
        r = client.post("/api/memories", json={
            "content": f"bench memory {uuid.uuid4().hex[:8]}",
            "tags": "bench,load",
        })
        data = r.json()
        mid = data.get("id")
        client.get("/api/memories/search?q=bench")
        if mid:
            client.delete(f"/api/memories/{mid}")

    return [
        Scenario("GET /api/health", s_health, iterations),
        Scenario("GET /api/livez", s_livez, iterations),
        Scenario("GET /api/ready", s_ready, iterations),
        Scenario("GET /api/tenant", s_tenant, iterations),
        Scenario("GET /api/telemetry", s_telemetry, iterations),
        # Fewer iterations for the write-heavy transactional scenarios.
        Scenario("Session CRUD (POST+2GET+DEL)", s_session_crud, max(50, iterations // 5)),
        Scenario("Memory CRUD (POST+GET+DEL)", s_memory_crud, max(50, iterations // 5)),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="WIDDX load-testing baseline benchmark")
    parser.add_argument("--iterations", type=int, default=300,
                        help="iterations per read scenario (default 300)")
    parser.add_argument("--json", metavar="PATH", help="write raw results JSON")
    parser.add_argument("--markdown", metavar="PATH", help="write a markdown table")
    args = parser.parse_args()

    from fastapi.testclient import TestClient
    import scripts.web.server as server

    client = TestClient(server.app)
    scenarios = build_scenarios(args.iterations)

    print(f"WIDDX Nexus — Baseline Benchmark  (Python {platform.python_version()}, "
          f"{platform.system()})")
    print("=" * 96)
    header = f"{'Scenario':<34}{'iters':>7}{'RPS':>9}{'p50':>9}{'p95':>9}{'p99':>9}{'err%':>7}"
    print(header)
    print("-" * 96)

    results = []
    for sc in scenarios:
        res = sc.run(client)
        results.append(res)
        print(f"{res['scenario']:<34}{res['iterations']:>7}{res['rps']:>9}"
              f"{res['p50_ms']:>8.1f}m{res['p95_ms']:>8.1f}m{res['p99_ms']:>8.1f}m"
              f"{res['error_rate_pct']:>6.1f}%")

    print("-" * 96)

    report = {
        "tool": "scripts/benchmark_baseline.py",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "iterations": args.iterations,
        "generated_at": int(time.time()),
        "results": results,
    }

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nRaw JSON written to {args.json}")

    if args.markdown:
        lines = [
            "# WIDDX Nexus — Baseline Benchmark Results",
            "",
            f"- Python: {report['python']}  |  Platform: {report['platform']}  |  CPUs: {report['cpu_count']}",
            f"- Iterations (read scenarios): {report['iterations']}",
            "",
            "| Scenario | iters | RPS | p50 (ms) | p95 (ms) | p99 (ms) | err % |",
            "|----------|------:|----:|---------:|---------:|---------:|------:|",
        ]
        for r in results:
            lines.append(
                f"| {r['scenario']} | {r['iterations']} | {r['rps']} | "
                f"{r['p50_ms']} | {r['p95_ms']} | {r['p99_ms']} | {r['error_rate_pct']} |"
            )
        Path(args.markdown).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Markdown written to {args.markdown}")

    # Non-zero exit if any scenario had errors — useful for CI gating.
    failed = [r for r in results if r["error_rate_pct"] > 0]
    if failed:
        print("\n⚠ Scenarios with errors: " + ", ".join(r["scenario"] for r in failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
