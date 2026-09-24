# Changelog

## 3.4.0 (2026-07-23)

### 🏁 Production Readiness — Phase 4 (Final Enhancements)

#### Kubernetes Manifests (New — Task 4.4)
- **`deploy/k8s/`** — production Kubernetes bundle with Kustomize
  - `deployment.yaml` — 2-replica Deployment with startup/liveness/readiness probes, resource limits, non-root security context
  - `service.yaml` — ClusterIP service (80 → 8000)
  - `ingress.yaml` — nginx ingress + cert-manager TLS + WebSocket timeouts + edge rate limiting
  - `hpa.yaml` — HorizontalPodAutoscaler (2–10 replicas, CPU 70% / memory 80%)
  - `pvc.yaml`, `configmap.yaml`, `namespace.yaml`, `secret.example.yaml`, `kustomization.yaml`, `README.md`
- Web server now exposes unauthenticated `GET /api/livez` and `GET /api/ready` probes for orchestrators

#### Multi-Tenant Isolation (New — Task 4.2)
- **`core/tenancy.py`** — physical data isolation per tenant
  - Each tenant gets its own SQLite database under `.widdx/data/tenants/<id>/widdx.db`
  - Resolution modes: `keymap` (`WIDDX_TENANT_KEYS="acme:key-1,globex:key-2"` + Bearer key) or `header` (`X-Tenant-ID`)
  - Strict tenant-id sanitization (blocks path traversal), constant-time key comparison
  - Session & memory REST routes are tenant-scoped when tenancy is enabled; legacy single-tenant behavior preserved when off
  - `GET /api/tenant` + `X-Tenant-ID` response header for client-side verification

#### Admin Dashboard (New — Task 4.3)
- **`scripts/web/admin.py`** + **`scripts/static/admin.html`** — key-protected ops panel at `/admin/`
  - System overview, tenant registry, telemetry summary, telemetry reset
  - Guarded by `WIDDX_ADMIN_KEY` (timing-safe); fully disabled (403) when unset

#### Telemetry / Usage Analytics (New — Task 4.5)
- **`core/telemetry.py`** — anonymous, opt-out usage analytics
  - Opt out with `WIDDX_TELEMETRY_DISABLED=1`; stores only aggregates + safe labels
  - Sensitive-key scrubber (never stores content, IPs, tokens, paths); pseudonymous instance fingerprint
  - ASGI middleware counts requests by route template; `GET /api/telemetry` public summary

#### Load Testing Baseline (New — Task 4.1)
- **`scripts/benchmark_baseline.py`** — reproducible in-process latency/RPS baseline (CI-gateable)
- **`docs/reports/LOAD-TEST-BASELINE.md`** — measured baseline (~450 RPS reads, p99 < 5ms), SLOs, regression workflow

### 🐛 Critical Fixes
- `scripts/web/server.py` failed to import (`NameError: os`) — added missing `import os`
- `core/database.py` — the entire `Database` class body was accidentally nested inside `_PoolConnection`, so `Database()` always crashed; restructured so all methods live on `Database`
- `core/database.py` — connection pools are now keyed per database file (fixes multi-tenant isolation) and `_PoolConnection.__exit__` releases the correct connection
- `core/database.py` — added `count_sessions` / `count_all_messages` / `count_memories` aggregate helpers

## 3.3.0 (2026-07-23)

### 🚀 Production Readiness — Core Infrastructure

#### Performance Monitoring (New)
- **`core/monitoring.py`** — comprehensive metrics system with p50/p95/p99 latency tracking
- Request tracking per endpoint with automatic error rate calculation
- Tool execution profiling (per-tool latency, error rates)
- System resource monitoring (memory RSS/VMS via `/proc/self/status`, CPU)
- Performance alerts on slow execution (>10s warning, >30s critical)
- New middleware auto-tracks every request in API server
- New endpoint: `GET /api/monitoring` for detailed performance data
- Health endpoint now includes system metrics and performance data

#### Safety & Timeouts (Enhanced)
- **`core/tools/safety.py`** — complete safety overhaul
  - Per-tool timeouts (bash: 30s, write: 10s, docker: 120s, spawn_agent: 300s)
  - `execute_safely()` wrapper with timeout + resource limits
  - `TimeoutError` custom exception with tool context
  - Command whitelist (60+ always-allowed commands, 15 restricted)
  - `ResourceLimits` — max concurrent executions (default: 10), memory threshold (1GB)
  - `check_command_whitelist()` for unknown command logging

#### Tool Dispatch (Enhanced)
- **`core/tools/dispatch.py`** — timeout wrapping + retry logic
  - Automatic retry on transient errors (timeout, connection errors) with exponential backoff
  - Performance monitoring integration via `metrics_collector`
  - All tool executions now have guaranteed timeout enforcement
  - MCP tool calls also wrapped with timeout

#### Chat Provider Timeout (Enhanced)
- **`core/chat.py`** — 60-second timeout guard on all provider calls
  - Threading-based timeout (doesn't block event loop)
  - Records performance alert on timeout
  - Graceful error message for users

#### Memory Learner Limits (Enhanced)
- **`core/memory_learner.py`** — bounded memory storage
  - `MAX_MEMORIES=500` hard cap
  - `MAX_MEMORY_AGE_DAYS=180` auto-cleanup
  - `MAX_CONTENT_LENGTH=200` content truncation
  - Periodic cleanup every 10 saves

#### Production Deployment Infrastructure
- **`.env.example`** — complete environment configuration template
- **`Dockerfile`** — HEALTHCHECK with curl probe (30s interval, 3 retries)
- **`docker-compose.yml`** — health checks, named volumes, custom network
- **CORS production mode** — `WIDDX_CORS_ORIGINS` env var replaces `*`
- **Graceful shutdown** — `timeout_graceful_shutdown=30s` via uvicorn
- **`docs/PRODUCTION-PLAN.md`** — full production readiness roadmap (23 tasks, 4 phases)
- **`TASKS.md`** — daily task tracker for production readiness

#### Testing
- **54 new stress/complex tests** — total 592 tests
- **`tests/test_stress_load.py`** — 24 tests (concurrent load, rate limiting, auth, input validation)
- **`tests/test_stress_complex.py`** — 30 tests (safety, monitoring, memory, dispatch, timeouts)
- **`locustfile.py`** — Locust load testing with 4 user profiles
- **`scripts/run_stress_tests.sh`** — unified stress test runner

### Test Results
- **82 stress tests: 82/82 passed** ✅
- **All existing tests continue to pass**

## 3.2.0 (2026-07-01)

### Quality & Tooling
- **mypy: 253 → 0 errors** across 171 source files (core/ + scripts/ + cli/ + tui/)
- **ruff: 347 → 0 lint warnings** (E401, E402, E501, E701, E741, F401, F821, F841, F811 fixed)
- **Makefile** with 15 commands (install, test, lint, typecheck, build, clean, run-*)
- **pyproject.toml** configured for mypy + ruff
- `callable` → `Callable` type hint fix (15 occurrences)
- `any` → `Any` type hint fix (5 occurrences)
- Implicit `Optional` (PEP 484) fixed across 24 parameters in 12 files
- `CREATE_NO_WINDOW` cross-platform support for non-Windows

### Config & Validation
- `validate_config()` — checks provider, max_turns, temperature, MCP servers with warnings + defaults
- `_resolve_placeholders()` — `{PROJECT_ROOT}`, `{CWD}`, `{USER_HOME}` resolved at load
- `ReliableProvider` now has proper `_default_urls` mapping for all 5 provider types + fallback
- Config default provider changed from `nonexistent-xyz` to `opencode-zen`

### Logging
- New `core/log_setup.py` with `setup_logging()` — unified format across CLI, TUI, Web, API
- CLI app now has proper logging (was silent)
- Web UI now has proper logging (was silent)

### Architecture
- **Parallel ExpertTeam** — Researcher + Coder run in parallel via ThreadPoolExecutor (saves response time)
- Project root cleanup — `api_server.py`, `run_textual.py` removed from root; `run-web.bat` moved to `scripts/`
- Duplicate installation scripts removed (`scripts/install.bat`, `scripts/install.ps1`, etc.)

### Test Stability
- **538 passed, 0 failed** (was 530 passed, 8 failed)
- Provider tests now use `raw=True` to verify actual factory classes
- `test_decision_path` updated for new `PreDecisionForce` decision step
- `ReliableProvider.base_url` now has proper fallback URLs
- All provider tests (opencode-zen, ollama, openai, deepseek) pass reliably

## 3.1.0 (2026-06-27)

### Level 5.0 — Autonomy Platform
- TaskState persistence engine (survives restarts)
- Global StateManager (7 sources → unified context)
- AutonomyLoop (execute→verify→fix→continue without human)
- True SelfCorrection (7 classified fix strategies)
- DecisionLayer (ADR + Memory + KG + Plan weighted decisions)
- Recursive Agent Spawning (agent → sub-agent → sub-sub-agent, max depth 3)

### Level 4.0 — Advanced Capabilities
- Memory Versioning (version, confidence, status, deprecation lifecycle)
- Architecture Decision Records (ADR)
- KnowledgeGraph (BFS, nodes, edges, project structure)
- VerifyLoop (verify→fix→retest cycle)
- DocSync (code-documentation drift detection)

### Provider Reliability Layer
- ProviderPool with automatic failover (priority + cooldown)
- Retry with exponential backoff (2s, 4s, 8s)
- Checkpoint on failure for task resume
- UnifiedToolCall across all 7 providers
- Code extraction fallback (for models without tool support)
- ReliableProvider wired into AutonomousAgent

### Agent System
- Checkpoint/resume in AutonomousAgent (Step Lock idempotency)
- ExpertTeam + KG language detection
- spawn_agent tool for recursive agent trees
- Provider failover within agent loop (3 retries, never dies on first error)
- Code extraction fallback (text → files when LLM won't use tools)

### Web UI
- Project Docs viewer (PLAN/DESIGN/TASKS/ROADMAP with templates)
- Session search across all conversations
- Voice input (Web Speech API, Arabic/English)
- Image/file upload with preview badges
- Autonomous Mode toggle button
- Terminal with command history (Arrow keys)
- Safe JS stubs prevent ReferenceError before scripts load
- All scripts moved to `<head>` for reliable loading

### Security
- API auth bypass fix (empty token → 503 rejection)
- Default permission NORMAL (was PERMISSIVE)
- Request body size limit (1MB, configurable)
- SQLite-backed rate limiter
- Command guard integration in sandbox
- Skill sandbox with safe builtins + blocked modules

### Architecture
- Database migration system (schema_version + ordered migrations)
- Graceful shutdown (SIGINT/SIGTERM handlers)
- Global user config (~/.widdx/config.json) as fallback
- Config resolution: project → CWD → global → bundled
- Wrapper layer reduction (4 layers → 2)
- 17 dead imports removed across 5 files

### Quality
- 523→539 tests, 0 failures
- 15 new test files for Level 4.0/5.0
- Type hints for all public APIs
- Monkey-patch replaced with logging in debug scripts
- Complete architecture documentation (7 docs)

## 3.0.0 (2026-06-26)

### Core Systems
- UIL Brain Pipeline (Analyze → Route → Plan → Execute → Verify → Learn)
- AutonomousAgent with tool-calling loop
- ExpertTeam (5 sequential expert agents)
- 7 LLM providers with unified interface
- 18 built-in skills (React, Vue, Django, Flutter, etc.)
- Sandbox executor (Windows/Linux/macOS)
- Command guard (block dangerous commands)
- SQLite session persistence
- Memory system (markdown + frontmatter)
- MCP Protocol client
- Cron scheduler + background tasks
- Delegation (parallel sub-agents)
- WebSocket + REST API

### Interfaces
- Web UI (FastAPI + WebSocket, 40+ endpoints)
- CLI (Rich terminal interface)
- TUI (Textual terminal UI)
- REST API (Bear token auth)
