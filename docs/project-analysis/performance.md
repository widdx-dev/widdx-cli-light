# WIDDX Nexus — Performance Analysis

> Generated: 2026-06-25

## Current Characteristics

### Startup Time
- CLI startup: ~2-4 seconds (provider init, MCP discovery, project scan)
- Web UI startup: ~1-2 seconds (lazy loading of handlers)
- TUI startup: ~3-5 seconds (Textual framework + all subsystems)

### Request/Response Latency
- Simple chat (no tools): Provider-dependent (200ms-2000ms)
- With classification: +500-2000ms (LLMClassifier)
- Autonomous agent loop: 5-60s (up to 25 tool iterations)
- ExpertTeam pipeline: 15-120s (3-6 agents sequentially)

### Memory
- Idle: ~50MB Python process
- With LLM providers: +200MB (llama-cpp for GGUF)
- MCP servers (Node.js): ~300MB total (6 servers)
- Peak with agents: ~100-200MB Python

---

## Known Bottlenecks

### 1. LLM Classification on Every Message (MED-010)
- **Impact:** +500-2000ms per message
- **Root Cause:** LLMClassifier calls Provider.chat() for every user input
- **Suggestion:** Use LocalClassifier as primary; LLM as fallback

### 2. ExpertTeam Sequential Execution (MED-008)
- **Impact:** 3-6x slower than possible
- **Root Cause:** Experts run one at a time with string concatenation
- **Suggestion:** Use threading for independent expert tasks

### 3. Knowledge Save on Every Execution (MED-007)
- **Impact:** Disk I/O after every UIL process()
- **Root Cause:** _save() writes entire JSON file each time
- **Suggestion:** Batch writes every N records or timer-based flush

### 4. No Connection Pooling for SQLite (MED-005)
- **Impact:** ~1ms overhead per DB operation
- **Root Cause:** New connection per operation
- **Status:** Mitigated by WAL mode (FIXED P1-5)

### 5. Tool Cache Over-Invalidation (MED-009)
- **Impact:** Cache hit rate degradation during editing
- **Root Cause:** Clears ALL read caches on any write
- **Suggestion:** Invalidation by file path pattern

### 6. In-Memory Rate Limiter (MED-006)
- **Impact:** Rate limit state lost on restart
- **Root Cause:** No persistent/ditributed storage
- **Suggestion:** Redis or DB-backed for production

---

## Optimizations Applied (P1 Sprint)

| Fix | Impact |
|-----|--------|
| SQLite WAL mode | Concurrent reads without locking |
| SQLite timeout=5 | Prevent hangs |
| SQLite foreign_keys=ON | Referential integrity |
| ProjectScanner throttling | 30s cache between scans |
| Lazy imports (80+ sites) | Reduced startup memory/time |

---

## Benchmark Data (test_benchmark.py)

| Metric | Value |
|--------|-------|
| Tool execution (echo) | <100ms |
| File read (100 lines) | <50ms |
| File write (small) | <100ms |
| Grep (100 files) | <500ms |
| Provider chat (DeepSeek) | 500-2000ms |
| Provider stream (DeepSeek) | 200-500ms TTFB |
