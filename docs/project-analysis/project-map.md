# WIDDX Nexus — Complete Project Map

> Forensic analysis of every file and directory. Version: 3.0.0+
> Author: MUHAMMAD MUSLIH (widdx.com) 🇵🇸

## Root Level

| File | Purpose |
|------|---------|
| `main.py` | Entry point — delegates to `scripts/main.py` → `scripts/web_app.py` |
| `api_server.py` | Standalone entry for API server (delegates to `scripts/api_server.py`) |
| `run_textual.py` | Standalone entry for TUI (delegates to `scripts/run_textual.py`) |
| `pyproject.toml` | Python project metadata, dependencies, build config |
| `package.json` | Node.js package info (for VSCode extension build) |
| `config.json` | Runtime configuration (provider, model, settings) |
| `_debug_brain.py` | Debug script for UIL Brain `_resolve_executor` (monkey-patch) |
| `Dockerfile` | Docker containerization for deployment |
| `.gitignore` | Git ignore patterns |
| `.gitattributes` | Git line-ending normalization rules |
| `install.bat` / `install.ps1` | Windows installation scripts |
| `uninstall.bat` / `uninstall.ps1` | Windows uninstallation scripts |
| `run-web.bat` | Windows quick-launch for Web UI |
| `LICENSE` | MIT License |

## `core/` — Core Engine (the heart of WIDDX)

### Top-Level Modules

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `__init__.py` | Package init, exports key modules | — |
| `__main__.py` | `python -m core` launcher → Web UI | `run()` |
| `_path.py` | Central sys.path management | `ensure_project_root()` |
| `chat.py` | Conversation loop, tool dispatch, streaming | `DisplayManager`, `run_chat_turn()`, `run_stream_turn()`, `run_agent_turn()`, `process_tool_calls()` |
| `commands.py` | Slash command handlers (shared CLI/TUI) | `handle_model()`, `handle_provider()`, `handle_mcp()`, `handle_gguf()`, `handle_doctor()`, `handle_export()`, `handle_version()`, `handle_permissions()` |
| `tools/` | Tool definitions package | See subsection below |
| `memory.py` | Persistent fact storage (markdown files) | `MemoryStore` |
| `memory_learner.py` | Auto-extract facts from conversations via LLM | `MemoryLearner` |
| `session_v2.py` | SQLite session storage (with JSON compat) | `SessionV2`, `create_new_session()`, `load_session()` |
| `database.py` | SQLite database manager | `Database`, `SessionDB` |
| `skills.py` | Skill management (markdown-based plugins) | `SkillManager`, `Skill`, `skill_manager` singleton |
| `workflow.py` | Workflow engine (multi-step pipelines) | `WorkflowEngine` |
| `config/__init__.py` | Config package init | — |
| `config/settings.py` | Load/save config.json | `load()`, `save()`, `get_config_path()` |
| `config/keychain.py` | API key management (env vars) | `prompt_key()`, `get_key()`, `forget_key()`, `has_key()` |
| `sandbox.py` | Command execution (sandboxed subprocess) | `SandboxExecutor`, `SandboxResult` |
| `guard.py` | Command safety checking | `CommandGuard`, `GuardResult` |
| `proxy.py` | Free proxy manager for OpenCode Zen | `ProxyManager`, `proxy_manager` singleton |
| `cache.py` | Response and tool result caching | `CacheStore`, `ResponseCache`, `ToolResultCache` |
| `diagnostics.py` | Silent error collection and auditing | `ErrorCollector`, `error_collector`, `audit_silent_errors()` |
| `delegation.py` | Sub-agent spawning and management | `DelegationManager`, `SubAgent` |
| `background.py` | Background task execution | `BackgroundTaskManager`, `BackgroundTask`, `background` singleton |
| `checkpoint.py` | Session checkpoint/restore | `CheckpointManager` |
| `auto_commit.py` | Auto git-commit after agent success | `AutoCommitManager`, `auto_committer` |
| `auto_setup.py` | Auto-dependency install + project learning | `detect_project_deps()`, `learn_project()`, `setup_project()` |
| `utils.py` | Shared utilities (frontmatter, slugs) | `parse_frontmatter()`, `strip_frontmatter()`, `to_slug()`, `get_last_turn()` |
| `ui_visual.py` | Shared Rich rendering helpers | `Theme`, `render_user_message()`, `render_assistant_message()`, `console`, `header_bar()` |
| `token_budget.py` | Token/cost budget enforcement | `TokenBudget`, `BudgetExceededError`, `get_budget()` |
| `project_tracker.py` | Persistent project plan/docs (.widdx/) | `ensure_docs()`, `build_context_block()`, `update_doc()` |
| `project_context.py` | Project context aggregation (deprecated) | `ProjectContextManager`, `get_project_context()` |
| `project_structure.py` | Project tree analyzer (deprecated → scanner) | `ProjectStructureAnalyzer` |
| `suggester.py` | Proactive project suggestions | `ProjectSuggester`, `Suggestion` |
| `self_reflection.py` | LLM self-reflection on last turn | `reflect_on_last_turn()`, `extract_lessons()` |
| `self_improve.py` | Error pattern learning + prompt optimization | `ErrorPatternLearner`, `get_improver()` |
| `repo_mapper.py` | Repository dependency graph + context selector | `RepoMapper`, `FileNode` |
| `rag.py` | RAG pipeline (sentence-transformers + TF-IDF) | `RAGStore`, `rag_store` |
| `vector_memory.py` | Vector-based memory search | `VectorMemory` |
| `session_search.py` | Session content search | Session search functions |
| `linter.py` | Auto-lint after agent edits | `LinterRunner`, `LintResult`, `linter` |
| `multi_editor.py` | Atomic multi-file edits with rollback | `MultiFileEditor`, `MultiEditResult` |
| `diff_engine.py` | Unified diff generation and application | `DiffEngine`, `DiffResult` |
| `plugin_loader.py` | Skills hot-reload via file watching | `SkillHotReloader`, `PluginWatcher`, `PluginLoader` |
| `permissions.py` | Tool permission system (permissive/strict/silent) | `PermissionManager`, `PermissionLevel`, `get_permission_manager()` |
| `vision.py` | Multi-modal image understanding | `describe_image()`, `VisionMode`, `process_user_input_with_vision()` |
| `voice.py` | Text-to-Speech (edge-tts) | `TTSEngine`, `tts` singleton |
| `web_launcher.py` | Web UI launcher helper | Web launch utilities |
| `activity.py` | Activity event tracking for dashboard | `ActivityStore`, `ActivityEvent` |

### `core/providers/` — LLM Provider System

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `providers.py` | Provider factory + model listing | `create_provider()`, `get_available_models()`, `estimate_turn_cost()`, `fetch_free_models()`, `fetch_ollama_models()` |
| `base.py` | Base provider class | `BaseProvider` |
| `opencode_zen.py` | OpenCode Zen free tier provider | `OpenCodeZenProvider` |
| `deepseek.py` | DeepSeek API provider | `DeepSeekProvider` |
| `openai_compatible.py` | OpenAI-compatible API adapter | `OpenAICompatibleProvider` |
| `ollama.py` | Ollama local model provider | `OllamaProvider` |
| `gguf.py` | GGUF model import/conversion | `import_gguf()`, `list_imports()`, `read_gguf_metadata()` |
| `gguf_provider.py` | GGUF runtime provider | `GGUFProvider` |
| `factory.py` | Provider factory | Factory functions |
| `free_models.py` | Free model discovery | Free model listing |

### `core/uil/` — Unified Intelligence Layer (Brain Pipeline)

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `UnifiedIntelligenceLayer`, `ExecutionMode` |
| `contract.py` | Data contracts — ALL types for the pipeline | `TaskType` (13 types), `ExecutionMode` (4 modes), `Domain`, `ClassificationResult`, `RoutingDecision`, `Plan`, `TaskStep`, `ExecutionResult`, `VerificationReport`, `VerificationFinding`, `VerificationSeverity`, `DecisionStep` |
| `analyzer.py` | Task classification (LLM + keyword fallback) | `TaskAnalyzer`, `LLMClassifier`, `_apply_project_context()` |
| `router.py` | Execution mode routing (static mapping) | `DecisionRouter`, `_MODE_MAP` |
| `planner.py` | Task decomposition (3 decomposers + minimal) | `TaskPlanner`, `_DECOMPOSERS` |
| `executors.py` | Direct tool execution | `run_direct_tool()` |
| `verifier.py` | Output verification (regex-based) | `HtmlVerifier`, `CodeVerifier`, `BashVerifier`, `GenericVerifier`, `get_verifier()` |
| `knowledge.py` | Execution knowledge base (JSON storage) | `KnowledgeBase` |
| `brain.py` | The UIL Brain — orchestrates full pipeline | `UnifiedIntelligenceLayer.process()` — Analyze → Route → Plan → Execute → Verify → Feedback → Knowledge |

### `core/agents/` — Agent System

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `agent.py` | Autonomous agent (LLM→tool loop) | `AutonomousAgent`, `AgentStep` |
| `executor_adapter.py` | Executor bridge: UIL contract → real execution | `EXECUTOR_MAP` (4 executors), `ExecutionContext` |
| `expert.py` | Expert team (multi-expert sequential) | `ExpertTeam`, `ExpertAgent`, `ExpertProfile` |

### `core/intelligence/` — Local Intelligence Engine (v4.0)

| File | Purpose |
|------|---------|
| `__init__.py` | Exports all intelligence components |
| `classifier.py` | LLM-free task classifier (TF-IDF + keywords, 200+ examples) | `LocalClassifier`, `classify_input()`, `ClassificationResult` |
| `decision_engine.py` | Learned routing decision tree | `DecisionEngine`, `DecisionStats`, `DEFAULT_MODE_MAP` |
| `patterns.py` | 25+ software project patterns knowledge base | `SoftwarePattern`, `PatternStep`, `PATTERNS`, `find_patterns()` |
| `planner.py` | Pattern-aware task decomposition | `PatternAwarePlanner`, `Plan`, `PlanStep`, `create_plan()` |
| `learner.py` | Extracts new patterns from execution history | `PatternLearner`, `get_learner()` |
| `embeddings.py` | TF-IDF local embeddings (zero external deps) | `TFIDFEmbedder`, `SentenceEmbedder`, `EmbeddingStore` |

### `core/isolation/` — Process Isolation Engine (v4.0)

| File | Purpose |
|------|---------|
| `__init__.py` | Exports isolation components |
| `profiles.py` | Execution environment profiles (python/bash/browser/mcp/trusted) | `IsolationProfile`, `PROFILES`, `resolve_profile()` |
| `container.py` | Docker/podman container manager with fallback | `ContainerManager`, `ContainerResult` |
| `policy.py` | Permission-level-based execution policy | `IsolationPolicy`, `get_policy()` |

### `core/validation/` — Validation Engine (v4.0)

| File | Purpose |
|------|---------|
| `__init__.py` | Exports validation components |
| `runner.py` | Safe code execution harness (actually runs code) | `CodeRunner`, `RunResult`, `run_code()` |
| `reporter.py` | Multi-signal quality reports | `ValidationReporter`, `ValidationReport`, `Finding`, `validate_result()` |

### `core/project/` — Project Management

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `state.py` | Session save/load, project config, indexing | `save_session()`, `load_session()`, `build_index()` |
| `scanner.py` | Project structure scanner | `ProjectScanner`, `ProjectCard` |
| `git.py` | Git operations (commit, undo, branch) | `is_git_repo()`, `auto_commit()`, `undo_last_commit()` |
| `manifest.py` | MANIFEST.json generation | `generate_manifest()` |

### `core/cron/` — Cron Scheduler

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `job.py` | Cron job data model | `CronJob`, `JobStatus` |
| `parser.py` | Natural language → cron expression | `parse_schedule()`, `next_run()` |
| `scheduler.py` | Job scheduler with background thread | `CronScheduler` |
| `store.py` | Job persistence (JSON) | `JobStore` |

### `core/gateway/` — Multi-Platform Gateway

| File | Purpose |
|------|---------|
| `__init__.py` | Core gateway + Message/Reply types | `GatewayCore`, `Platform`, `Message`, `Reply` |
| `telegram.py` | Telegram bot adapter | `TelegramAdapter` |
| `discord.py` | Discord bot adapter | `DiscordAdapter` |

### `core/tools/` — Tool Definitions

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `__init__.py` | Tool registry and execution | `TOOL_DEFINITIONS`, `execute_with_skills()`, `ToolCall` |
| `browser.py` | Browser automation (Playwright MCP + HTTP fallback) | `_browser_navigate()`, `_browser_screenshot()`, `_browser_click()`, `_browser_type()`, `_browser_press()`, `_browser_snapshot()` |
| `security.py` | Dangerous command pattern detection | `scan_dangerous()`, `_DANGEROUS_PATTERNS`, `_WARN_PATTERNS` |

### `core/mcp/` — Model Context Protocol

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `client.py` | MCP server discovery + tool integration | `MCPManager`, `MCPServerConnection`, `discover_mcp_servers()` |

## `cli/` — Command-Line Interface

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `app.py` | Main CLI app (loop, startup, UIL integration) | `CLIApp`, `run()` |
| `commands.py` | Slash command processing | `CLICommands` — 30+ commands |
| `display.py` | Rich rendering (thin wrapper on ui_visual) | `show_header()`, `show_user_msg()`, `show_ai_msg()`, `show_system_msg()` |
| `input.py` | prompt_toolkit input (history, autocomplete) | `CLIInput` |
| `theme.py` | Theme constants (re-exports from ui_visual) | Color/style constants |

## `tui/` — Terminal User Interface (Textual)

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `__main__.py` | `python -m tui` entry point |
| `app.py` | Main TUI app + MainScreen + event handlers | `WIDDXTUI`, `MainScreen`, `ViewPanel` |
| `app.tcss` | Textual CSS stylesheet | Visual styling |
| `chat_engine.py` | Chat execution engine (streaming, tools, agents) | `ChatEngine`, message types (`ResultMsg`, `ErrorMsg`, `StreamEndMsg`, etc.) |
| `commands.py` | TUI slash command handler | `CommandHandler` — 30+ commands |
| `state.py` | Central TUI state management | `TUIState` |
| `theme_util.py` | Theme utilities | `apply_app_theme()`, `PROVIDER_OPTIONS` |
| `screens/help.py` | Help screen | `HelpScreen` |
| `screens/settings.py` | Settings screen (provider, model, GGUF) | `SettingsScreen`, `ProviderTab`, `GGUFTab` |
| `screens/session_crud.py` | Session management screens | `SessionListScreen`, `SessionPickerScreen`, `SessionRenameScreen`, `SessionDeleteScreen` |
| `screens/memory_crud.py` | Memory management screens | `MemoryListScreen`, `MemoryEditScreen`, `MemoryPickerScreen`, `MemoryDeleteScreen` |
| `screens/detail.py` | Text detail modal | `TextDetailScreen` |
| `screens/tool_detail.py` | Tool detail modal | `ToolDetailScreen` |
| `screens/ubuntu_grid.py` | Ubuntu-style app grid launcher | `UbuntuGrid` |
| `widgets/header.py` | Top header widget (provider, branch, cost) | `HeaderWidget` |
| `widgets/diff_viewer.py` | Diff viewer widget | Diff display |

## `scripts/` — Scripts and Web UI

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `main.py` | Main script entry → web_app.py |
| `web_app.py` | Web UI launcher |
| `api_server.py` | FastAPI REST API server (older version) | `AppState`, `ChatRequest`, `ChatResponse`, `RateLimiter` |
| `run_textual.py` | TUI launcher |
| `install.bat` / `install.ps1` | Installation scripts |

### `scripts/web/` — Web UI Backend

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `server.py` | FastAPI app + WebSocket + all REST endpoints | 50+ API routes |
| `chat.py` | Chat handler (UIL Brain pipeline) | `ChatHandler`, `chat()`, `chat_stream()` |
| `sandbox.py` | Sandbox handler (terminal, browser, files) | `SandboxHandler` |
| `dashboard/__init__.py` | Dashboard aggregator (mixin pattern) | `Dashboard` (composes 6 mixins) |
| `dashboard/_mixin_core.py` | System info, computer operations | `CoreDashboardMixin` |
| `dashboard/_mixin_scheduler.py` | Cron, background tasks, agents | `SchedulerMixin` |
| `dashboard/_mixin_storage.py` | Sessions, memory, activity, skills | `StorageMixin` |
| `dashboard/_mixin_gateway.py` | Gateway, MCP, proxy, permissions | `GatewayMixin` |
| `dashboard/_mixin_settings.py` | Provider settings, models, config | `SettingsMixin` |
| `dashboard/_mixin_devops.py` | Git, checkpoints, plugins, workflows, GGUF | `DevOpsMixin` |
| `.widdx/knowledge.json` | Knowledge base data file | Persisted learning |

### `scripts/static/` — Frontend Assets

| File | Purpose |
|------|---------|
| `index.html` | Main Web UI page (RTL/Arabic i18n) |
| `css/style.css` | Full design system (dark/light, RTL) |
| `js/nexus.js` | Main app logic, WebSocket, all views |
| `js/ui.js` | Theme, sidebar, markdown parser, command palette |
| `js/lang.js` | i18n engine (English/Arabic) |
| `js/views/*.js` | 22 view modules (dashboard, settings, git, etc.) |

## `tests/` — Test Suite

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest config, KnowledgeBase cleanup |
| `test_e2e.py` | End-to-end: import chain, provider, tools, memory, sessions |
| `test_engines_e2e.py` | Engine integration: classifier, planner, validation, isolation, adapters, feature flags, trust |
| `test_benchmark.py` | Routing accuracy benchmark (29 cases) |
| `test_api_server.py` | API server integration (13 tests) |
| `test_executor_adapter.py` | Executor adapter (19 tests) |
| `test_verifier.py` | Verifier tests (33 tests) |
| `test_uil_knowledge.py` | UIL knowledge base (8 tests) |
| `test_uil_p12.py` | UIL Phase 1.2 (11 tests) |
| `test_uil_p13.py` | UIL Phase 1.3 (8 tests) |
| `test_uil_p15.py` | UIL Phase 1.5 (6 tests) |
| `test_uil_planner.py` | Planner tests (12 tests) |
| `test_cache.py` | Cache tests (19 tests) |
| `test_providers.py` | Provider tests (13 tests) |
| `test_sandbox.py` | Sandbox tests |
| `test_guard.py` | Command guard tests |
| `test_tui.py` | TUI headless tests (30 tests) |
| `test_check_cli.py` / `test_cli_all.py` | CLI validation tests |
| `test_cron_*.py` | Cron system tests (4 files) |
| `test_background.py` | Background task tests |
| `test_delegation.py` | Sub-agent tests |
| `test_checkpoint.py` | Checkpoint tests |
| `test_diff_engine.py` | Diff engine tests |
| `test_linter.py` | Linter tests |
| `test_multi_editor.py` | Multi-editor tests |
| `test_plugin_loader.py` | Plugin loader tests |
| `test_project_context.py` / `test_project_validate.py` | Project tests |
| `test_rag.py` / `test_repo_mapper.py` / `test_vector_memory.py` | Memory/search tests |
| `test_session_search.py` | Session search tests |
| `test_token_budget.py` | Token budget tests |
| `test_features.py` | Integration tests (git, config, load, summary, index) |
| `test_auto_commit.py` | Auto-commit tests |
| `run_integration_test.py` | Integration test runner |

## `github-app/` — GitHub App

| File | Purpose |
|------|---------|
| `app.py` | GitHub webhook handler + PR analysis |
| `README.md` | Setup instructions |

## `vscode-extension/` — VSCode Extension

| File | Purpose |
|------|---------|
| `package.json` | Extension manifest (commands, activation events) |
| `src/extension.ts` | Main extension entry |
| `src/client.ts` | WebSocket client |
| `src/panel.ts` | WebView panel provider |
| `out/` | Compiled JavaScript |
| `media/style.css` | WebView styles |
| `tsconfig.json` | TypeScript configuration |
