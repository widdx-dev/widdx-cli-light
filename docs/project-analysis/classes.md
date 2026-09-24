# WIDDX Nexus — Complete Class Catalog

> Generated: 2026-06-25 | ~395 total classes, 149 unique in core/

## Classes per Directory

| Directory | Classes | Key Type |
|-----------|---------|----------|
| `core/` | 149 | Engine logic |
| `cli/` | 5 | Terminal UI |
| `tui/` | 25 | Textual screens/widgets |
| `scripts/` | 15 | Web handlers |
| `tests/` | 35 | Test cases |
| **Total** | **~232 source** (+163 test/build) | |

---

## Inheritance Hierarchy

| Parent | Children | Depth |
|--------|----------|-------|
| `Provider` | OllamaProvider, OpenAICompatibleProvider, GGUFDirectProvider | 1 |
| `OpenAICompatibleProvider` | DeepSeekProvider, OpenCodeZenProvider | 2 |
| `Verifier` | HtmlVerifier, CodeVerifier, BashVerifier | 1 |
| `HTMLParser` | HTMLTagValidator | 1 |
| `Enum` | TaskStatus, SubAgentStatus, PermissionLevel, JobStatus, Platform, TaskType, ExecutionMode, Domain, VerificationSeverity | 1 |
| `Exception` | BudgetExceededError | 1 |
| `Dashboard` | (inherits from 6 mixins) | 1 |

**No formal ABCs** — Provider and Verifier use conventional `NotImplementedError` instead of `abc.ABC`.

---

## Dataclasses: 46 in core/

| Class | Module | Purpose |
|-------|--------|---------|
| BackgroundTask | background.py | Background task state |
| SubAgentResult | delegation.py | Delegated task result |
| SandboxResult | sandbox.py | Sandbox execution output |
| ResourceLimits | sandbox.py | CPU/memory/file limits |
| ClassificationResult | uil/contract.py | Input classification |
| RoutingDecision | uil/contract.py | Execution routing |
| ExecutionResult | uil/contract.py | Task execution output |
| VerificationReport | uil/contract.py | Verification results |
| ExecutionContext | uil/contract.py | Execution context |
| Plan | uil/contract.py | Task plan |
| ExecutionRecord | uil/knowledge.py | Knowledge base record |
| ProjectCard | project/scanner.py | Project scan result |
| CronJob | cron/job.py | Scheduled task |
| Message | gateway/__init__.py | Gateway message |
| Reply | gateway/__init__.py | Gateway reply |
| SoftwarePattern | intelligence/patterns.py | Code pattern |
| Plan (intelligence) | intelligence/planner.py | AI plan |
| IsolationProfile | isolation/profiles.py | Container profile |
| ValidationReport | validation/reporter.py | Validation output |
| RunResult | validation/runner.py | Code execution |
| Plus 26 more | — | — |

---

## Largest Classes (>200 lines)

| Lines | Class | Module | Role |
|-------|-------|--------|------|
| 499 | SandboxExecutor | core/sandbox.py | Multi-platform sandbox |
| 499 | UnifiedIntelligenceLayer | core/uil/brain.py | 7-stage pipeline |
| 447 | AutonomousAgent | core/agents/agent.py | Tool-calling loop |
| 374 | OllamaProvider | core/providers/ollama.py | Local LLM |
| 362 | HtmlVerifier | core/uil/verifier.py | HTML validation |
| 311 | WorkflowEngine | core/workflow.py | Workflow orchestration |
| 304 | Database | core/database.py | SQLite ORM |
| 301 | PatternAwarePlanner | core/intelligence/planner.py | AI planning |
| 300 | RepoMapper | core/repo_mapper.py | Repo structure |
| 289 | SessionSearcher | core/session_search.py | Full-text search |
| 283 | MCPServerConnection | core/mcp/client.py | MCP server |
| 720 | MainScreen | tui/app.py | TUI main screen |
| 413 | DevOpsMixin | dashboard/_mixin_devops.py | DevOps dashboard |
| 357 | CLICommands | cli/commands.py | Slash commands |
| 327 | CLIApp | cli/app.py | CLI main loop |

---

## MVC Separation

| Layer | Classes | Role |
|-------|---------|------|
| Model (core/) | 149 | Business logic, data |
| View (cli/, tui/, scripts/static/) | 30+ | UI rendering |
| Controller (cli/commands, tui/commands, scripts/web/) | 14 | User input handling |
