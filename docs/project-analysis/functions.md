# WIDDX Nexus — Complete Function Inventory

> Generated: 2026-06-25 | Source: Full forensic scan — 1,521 functions analyzed

## Function Counts

| Directory | Sync | Async | Total |
|-----------|------|-------|-------|
| `core/` | 1,044 | 11 | 1,055 |
| `cli/` | 59 | 0 | 59 |
| `tui/` | 197 | 7 | 204 |
| `scripts/` | 107 | 87 | 194 |
| Root-level | 9 | 0 | 9 |
| **Total** | **1,416** | **105** | **~1,521** |

Async functions concentrated in `scripts/` (87) — FastAPI routes. `core/` has only 11 async.

---

## Docstring Coverage: 67%

| Directory | With | Without | % |
|-----------|------|---------|---|
| `core/` | 699 | 356 | 66% |
| `cli/` | 42 | 17 | 71% |
| `tui/` | 145 | 59 | 71% |
| `scripts/` | 135 | 59 | 70% |

---

## Type Hint Coverage: 74% have return types

| Directory | With | Without | % |
|-----------|------|---------|---|
| `core/` | 763 | 292 | 72% |
| `cli/` | 48 | 11 | 81% |
| `tui/` | 167 | 37 | 82% |
| `scripts/` | 148 | 46 | 76% |

---

## Decorators

| Count | Decorator |
|-------|-----------|
| 55 | `@property` |
| 46 | `@dataclass` |
| 43 | `@staticmethod` |
| 5 | `@classmethod` |

---

## Singleton Pattern: 47 `get_X()` functions

| Function | Returns | Module |
|----------|---------|--------|
| get_db() | Database | core/database.py |
| get_store() | ActivityStore | core/activity.py |
| get_mcp_manager() | MCPClientManager | core/mcp/client.py |
| get_arbiter() | EngineArbiter | core/engine_arbiter.py |
| get_budget() | TokenBudget | core/token_budget.py |
| get_verifier() | Verifier | core/uil/verifier.py |
| get_runner() | CodeRunner | core/validation/runner.py |
| get_reporter() | ValidationReporter | core/validation/reporter.py |
| get_project_context() | ProjectContextManager | core/project_context.py |
| get_key() | str (API key) | core/config/keychain.py |
| get_available_models() | list[str] | core/providers/factory.py |
| get_chat() | ChatHandler | scripts/web/server.py |
| get_dashboard() | Dashboard | scripts/web/server.py |
| (33 more) | — | — |

---

## Duplicate Function Names (>3 occurrences)

| Name | Count | Context |
|------|-------|---------|
| run | 8 | BackgroundTaskManager, DelegationManager, AutonomousAgent, ExpertTeam, WorkflowEngine... |
| save | 7 | CheckpointManager, SessionDB, MemoryStore, SessionV2, JobStore, EmbeddingStore... |
| search | 6 | MemoryStore, RAGStore, SessionSearcher, SessionV2, VectorMemoryStore, TFIDFEmbedder |
| load | 6 | SessionDB, config.settings, JobStore |
| chat | 6 | Provider + all 5 subclasses (polymorphism) |
| start | 5 | SubAgent, PluginWatcher, SkillHotReloader, CronScheduler, MCPClientManager |
| stream | 5 | Provider + all streaming subclasses |
| verify | 4 | Verifier + 3 subclasses (HtmlVerifier, CodeVerifier, BashVerifier) |
| stop | 4 | PluginWatcher, SkillHotReloader, CronScheduler, MCPClientManager |
| summarize | 4 | ClassificationResult, RoutingDecision, VerificationReport, ValidationReport |

---

## Largest Functions (>80 lines)

| Lines | Function | Module | Purpose |
|-------|----------|--------|---------|
| 310 | _execute_subprocess | core/sandbox.py | Subprocess execution with limits |
| 195 | stream | core/providers/opencode_zen.py | SSE streaming with proxy rotation |
| 150 | process | core/uil/brain.py | UIL 7-stage pipeline |
| 145 | run | core/agents/agent.py | Autonomous agent tool loop |
| 130 | _chat_text_tools | core/providers/ollama.py | Text-based tool calling |
| 110 | stream | core/providers/openai_compatible.py | OpenAI-compatible SSE stream |
| 95 | verify | core/uil/verifier.py | HTML verification |
| 85 | _init_systems | dashboard/_mixin_core.py | Dashboard init |
