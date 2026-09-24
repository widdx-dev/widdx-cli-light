# WIDDX Nexus — Load Testing Baseline Report (Task 4.1)

> **Status:** ✅ Baseline established
> **Date:** 2026-07-23
> **Tool:** `scripts/benchmark_baseline.py` (in-process ASGI) + `locustfile.py` (over-the-wire)
> **App version:** 3.3.0

---

## 1. Purpose

This document fixes a **reproducible performance baseline** for the WIDDX
Nexus web API so that future changes can be compared against a known-good
reference and performance regressions can be caught early (including in CI).

Two complementary approaches are provided:

| Tool | Type | Best for |
|------|------|----------|
| `scripts/benchmark_baseline.py` | In-process ASGI (no network) | Stable, comparable regression baseline |
| `locustfile.py` | Distributed, over-the-wire | Capacity planning, real network behavior |

The baseline numbers below come from the in-process tool because it removes
network variance and is therefore **stable and comparable across runs and
machines**.

---

## 2. Methodology

* The real FastAPI app (`scripts/web/server.py`) is driven through an ASGI
  test transport — the full middleware stack runs (CORS, security headers,
  tenant resolution, telemetry), but no socket/network is involved.
* Each scenario does a small warm-up (10% of iterations, unmeasured) to prime
  import/DB/connection caches, then measures every request.
* Latency percentiles (p50/p95/p99) are computed from the measured samples;
  RPS = successful iterations / wall time.
* Telemetry is disabled during the run (`WIDDX_TELEMETRY_DISABLED=1`) so the
  benchmark does not pollute analytics and results stay deterministic.
* Write-heavy scenarios (Session/Memory CRUD) run at 1/5 the iteration count
  of read scenarios.

Reproduce:

```bash
python scripts/benchmark_baseline.py --iterations 400
# emit machine-readable + markdown:
python scripts/benchmark_baseline.py --iterations 400 \
    --json baseline.json --markdown baseline.md
```

Over-the-wire (against a running server):

```bash
export WIDDX_API_KEY="your-key"
locust -f locustfile.py --host=http://127.0.0.1:8000 \
    --headless --users 50 --spawn-rate 5 --run-time 60s
```

---

## 3. Baseline Results

**Environment:** Python 3.11.2 · Linux · in-process ASGI · SQLite (WAL) · 400 iterations/read scenario

| Scenario | iters | RPS | p50 (ms) | p95 (ms) | p99 (ms) | err % |
|----------|------:|----:|---------:|---------:|---------:|------:|
| `GET /api/health` | 400 | 416.0 | 2.2 | 3.5 | 4.2 | 0.0 |
| `GET /api/livez` | 400 | 480.5 | 2.0 | 2.5 | 2.8 | 0.0 |
| `GET /api/ready` | 400 | 487.1 | 2.0 | 2.3 | 2.5 | 0.0 |
| `GET /api/tenant` | 400 | 479.1 | 2.0 | 2.6 | 2.9 | 0.0 |
| `GET /api/telemetry` | 400 | 445.2 | 2.1 | 2.9 | 3.1 | 0.0 |
| Session CRUD (POST+2GET+DEL) | 80 | 87.4 | 11.6 | 12.5 | 15.3 | 0.0 |
| Memory CRUD (POST+GET+DEL) | 80 | 195.9 | 5.0 | 5.8 | 7.0 | 0.0 |

**Zero errors across all scenarios.** Read endpoints sustain **~400–490 RPS**
single-process with sub-5 ms p99; transactional writes sustain **~90–195 RPS**.

---

## 4. Service Level Objectives (SLOs)

Targets derived from the baseline (single process, in-process). Treat a
regression beyond these bands as a performance bug to investigate.

| Metric | Baseline | SLO target | Regress if worse than |
|--------|---------:|-----------:|----------------------:|
| `GET /api/health` p95 | 3.5 ms | ≤ 10 ms | 15 ms |
| `GET /api/ready` p95 | 2.3 ms | ≤ 10 ms | 15 ms |
| Read endpoint RPS | ~450 | ≥ 300 | < 250 |
| Session CRUD p95 | 12.5 ms | ≤ 40 ms | 60 ms |
| Memory CRUD p95 | 5.8 ms | ≤ 25 ms | 40 ms |
| Error rate | 0% | ≤ 0.1% | > 1% |

The benchmark script exits **non-zero** if any scenario records errors, so it
can gate CI directly:

```bash
python scripts/benchmark_baseline.py --iterations 200 || echo "PERF REGRESSION"
```

---

## 5. Interpretation & scaling notes

* These are **single-process, no-network** numbers. Real deployments behind
  Nginx/ingress with TLS and network hops will show higher absolute latency
  but the same relative profile. Use `locustfile.py` for that measurement.
* SQLite with WAL handles the read/write mix well for a single writer. For
  horizontally scaled writes, see the storage notes in
  `deploy/k8s/README.md` (RWX storage or StatefulSet).
* Telemetry and tenant middleware add negligible overhead (a few hundred µs);
  the `/api/tenant` and `/api/telemetry` endpoints match the raw health
  endpoint within noise.

---

## 6. Regression workflow

1. Before a change: `python scripts/benchmark_baseline.py --json before.json`
2. After the change: `python scripts/benchmark_baseline.py --json after.json`
3. Compare p95/p99/RPS per scenario. Any read p95 moving from ~3 ms toward the
   15 ms regress band, or any new errors, should be reviewed before merge.

---

*Baseline generated with `scripts/benchmark_baseline.py`. Re-run on any
hardware/driver change and update Section 3.*
