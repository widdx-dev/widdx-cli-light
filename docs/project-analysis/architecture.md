# WIDDX Nexus — Architecture

## System Overview

WIDDX Nexus is an **orchestration framework** for LLM-powered coding assistance. It wraps multiple LLM providers behind a unified interface, adds tool-calling capabilities, and provides three UIs (CLI, TUI, Web).

**Core Architecture Pattern**: Pipeline-based with a central "Brain" orchestrator.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                     PRESENTATION                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Web UI   │  │ CLI      │  │ TUI      │  │Gateway │  │
│  │ (FastAPI)│  │ (Rich)   │  │(Textual) │  │(TG/DC) │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘  │
│       │              │              │             │       │
├───────┼──────────────┼──────────────┼─────────────┼──────┤
│       └──────────────┼──────────────┘             │       │
│                      ▼                            │       │
│              ┌──────────────┐                     │       │
│              │  core/chat.py│◄────────────────────┘       │
│              │  (Conv Loop) │                             │
│              └──────┬───────┘                             │
├─────────────────────┼─────────────────────────────────────┤
│                     ▼           INTELLIGENCE              │
│              ┌──────────────┐                             │
│              │  core/uil/   │◄── Core pipeline            │
│              │  brain.py    │                             │
│              │ Analyze→Route│                             │
│              │ →Plan→Execute│                             │
│              │ →Verify      │                             │
│              └──────┬───────┘                             │
│                     │                                     │
│     ┌───────────────┼───────────────────┐                │
│     ▼               ▼                   ▼                │
│ ┌─────────┐  ┌────────────┐  ┌──────────────┐           │
│ │core/int │  │core/validat│  │core/isolation│           │
│ │elligence│  │ion/        │  │/             │           │
│ │(v4.0)   │  │(v4.0)      │  │(v4.0)        │           │
│ └─────────┘  └────────────┘  └──────────────┘           │
├──────────────────────────────────────────────────────────┤
│                     INFRASTRUCTURE                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │providers │ │tools     │ │memory    │ │mcp       │   │
│  │(7 types) │ │(12 built)│ │(markdown)│ │(protocol)│   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │session   │ │skills    │ │sandbox   │ │cron      │   │
│  │(SQLite)  │ │(markdown)│ │(subproc) │ │(JSON)    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
└──────────────────────────────────────────────────────────┘
```

## UIL Brain Pipeline (core/uil/brain.py)

The central orchestration pipeline. Every user message flows through:

```
User Input
    │
    ▼
┌─────────────────┐
│ 1. ANALYZE      │  → TaskType (13 types) + confidence + features
│   analyzer.py   │  → LLM classification with keyword fallback
│                 │  → Project-aware: adjusts classification based on project context
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. ROUTE        │  → ExecutionMode (SIMPLE_CHAT/AUTONOMOUS/EXPERT_TEAM/DIRECT_TOOL)
│   router.py     │  → Static mapping: TaskType → ExecutionMode
│                 │  → Feature flag: intelligence engine can override
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. PLAN         │  → Ordered steps with tool hints and file suggestions
│   planner.py    │  → 3 decomposers (CODE_WRITE, CODE_MODIFY, COMPLEX)
│                 │  → All others get minimal single-step plan
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. EXECUTE      │  → ExecutionResult with summary, tools_used, success
│   brain.py      │  → Routes to executor based on ExecutionMode
│                 │  → SIMPLE_CHAT: core.chat.run_stream_turn()
│                 │  → AUTONOMOUS: agent.AutonomousAgent.run()
│                 │  → EXPERT_TEAM: expert.ExpertTeam.run()
│                 │  → DIRECT_TOOL: executors.run_direct_tool()
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4.5 VERIFY      │  → VerificationReport with findings
│   verifier.py   │  → HtmlVerifier / CodeVerifier / BashVerifier / GenericVerifier
│                 │  → CRITICAL findings flip success=False
│                 │  → Auto-retry on CRITICAL (1 attempt)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. FEEDBACK     │  → ExecutionResult updated with verification, telemetry
│   brain.py      │  → Cost tracking, tool usage tracking
└────────┬────────┘
         ▼
┌─────────────────┐
│ 6. KNOWLEDGE    │  → Learn from execution for future routing decisions
│   knowledge.py  │  → JSON-based persistent knowledge store
└─────────────────┘
```

## Three UIs

### CLI (cli/)
- **Entry**: `main.py` → `cli/app.py:run()` → `CLIApp.run()`
- **Loop**: Read input → check commands → process message via UIL → display → repeat
- **Input**: prompt_toolkit with history, autocomplete, styled prompt
- **Display**: Rich library panels, tables, markdown
- **Features**: 30+ slash commands, auto-skill suggestion, auto-commit, self-reflection, memory learning

### TUI (tui/)
- **Entry**: `run_textual.py` → `tui/app.py:run_tui()`
- **Framework**: Textual (modern Python TUI framework)
- **Architecture**: MainScreen → ChatEngine (background thread) + CommandHandler
- **Features**: Streaming chat, side panels (tools, skills, history, memories), settings screens, Ubuntu-style grid launcher
- **State**: `TUIState` centralizes all state; provider, messages, tool_defs, cost

### Web UI (scripts/web/)
- **Entry**: `scripts/web_app.py` → `scripts/web/server.py` (FastAPI)
- **Backend**: FastAPI REST API + WebSocket for streaming
- **Frontend**: Vanilla JS SPA with i18n (English/Arabic), dark/light themes
- **Chat**: WebSocket `/ws/chat` for real-time streaming
- **Dashboard**: 50+ REST endpoints covering all subsystems via Dashboard mixin pattern
- **Features**: Full system management — sessions, memory, cron, gateway, settings, git, plugins, workflows, GGUF, permissions, proxy, MCP, checkpoints, token budget, auto-commit

## Engine Architecture (v4.0)

Three new engines added alongside the original UIL pipeline:

### Intelligence Engine (`core/intelligence/`)
- **Classifier**: TF-IDF embedding + keyword matching, 200+ labeled examples
- **Decision Engine**: Learned routing tree from execution history
- **Patterns**: 25+ software project patterns with concrete steps
- **Planner**: Pattern-aware decomposition (replaces 3-decomposer planner)
- **Learner**: Extracts new patterns from successful executions
- **Embeddings**: Pure Python TF-IDF (zero dependencies)

### Validation Engine (`core/validation/`)
- **Runner**: Actually executes Python/bash code in temp workspace
- **Reporter**: Multi-signal quality scoring (syntax + runtime + quality)
- Catches runtime errors old verifier missed

### Isolation Engine (`core/isolation/`)
- **Profiles**: 5 security profiles (python/bash/browser/mcp/trusted)
- **Container**: Docker/podman execution with graceful subprocess fallback
- **Policy**: Permission-level-based command filtering

### Adapters (`core/engine_adapters.py`)
- Bridges between engine-specific types and UIL contract types
- Single file that needs updating when either side evolves

## Data Flow Patterns

### Session Persistence
```
CLI/TUI/Web → project.state.save_session() → JSON file (.widdx/session.json)
         ↕
CLI/TUI/Web → SessionV2 → SQLite database (.widdx/sessions.db)
         ↕
SessionCompat handles JSON→SQLite migration
```

### Memory System
```
MemoryStore (markdown files in .widdx/memory/)
    ├── Global: ~/.widdx/memory/
    └── Project: .widdx/memory/

MemoryLearner extracts facts every 2 turns via LLM
RAGStore provides semantic search (sentence-transformers or TF-IDF fallback)
VectorMemory provides vector-based similarity search
```

### Provider System
```
create_provider(cfg) → factory pattern
    ├── OpenCodeZenProvider (free tier, proxy rotation)
    ├── DeepSeekProvider (deepseek-v4-flash/pro)
    ├── OpenAICompatibleProvider (any OpenAI-compatible API)
    ├── OllamaProvider (local models)
    ├── GGUFProvider (imported GGUF models via Ollama)
    └── FreeModelsProvider (auto-discover free models)

All providers implement: chat(messages, tools, temperature) → (content, tool_calls)
                        stream(messages, tools, temperature) → generator of events
```

### Tool System
```
core.tools.TOOL_DEFINITIONS (12 built-in tools)
    ├── read, write, edit, bash, glob, grep
    ├── list_files, web_fetch, validate
    └── update_project_doc, use_skill

+ MCP tools (dynamic, from mcp.client)
+ Skill tools (active skill's custom tools)
+ Workflow tools (create_agent, run_parallel)

execute_with_skills(tool_name, args) → result string
    → Skills can intercept and augment tool execution
```

### Gateway System
```
GatewayCore
    ├── TelegramAdapter (python-telegram-bot, polling)
    ├── DiscordAdapter (discord.py, gateway)
    └── Message handler → WIDDX engine → Reply

Multi-platform: same message format across all channels
```

## Design Patterns Used

1. **Singleton Pattern**: Most subsystems use module-level singletons (proxy_manager, skill_manager, error_collector, etc.)
2. **Mixin Pattern**: Dashboard uses 6 mixins for composability
3. **Factory Pattern**: Provider creation, tool definitions
4. **Strategy Pattern**: Multiple executors for different execution modes
5. **Observer Pattern**: Activity store with subscribers for live events
6. **Pipeline Pattern**: UIL Brain (Analyze → Route → Plan → Execute → Verify → Knowledge)
7. **Adapter Pattern**: engine_adapters.py bridges engine types to UIL types
8. **Decorator Pattern**: `@catch_silent` for error collection
9. **Command Pattern**: All slash commands as separate handler methods

## Key Configuration Files

| File | Format | Purpose |
|------|--------|---------|
| `config.json` | JSON | Main config (provider, model, settings) |
| `.widdx/session.json` | JSON | Current session state |
| `.widdx/sessions.db` | SQLite | All sessions (multi-branch) |
| `.widdx/memory/` | Markdown | Persistent facts |
| `.widdx/knowledge.json` | JSON | UIL knowledge base |
| `.widdx/decisions.json` | JSON | Decision engine learnings |
| `.widdx/engine_trust.json` | JSON | Engine trust metrics |
| `.widdx/patterns.json` | JSON | Learned software patterns |
| `.widdx/permissions.json` | JSON | Tool permission state |
| `.widdx/repo_map.json` | JSON | Repository dependency graph |
| `.widdx/self_improve/` | JSON | Error patterns + fix tracker |
| `.widdx/cron_jobs.json` | JSON | Scheduled jobs |
| `.widdx/manifest.json` | JSON | Project manifest |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `WIDDX_API_KEY` | API authentication for REST server |
| `OPENAI_API_KEY` | OpenAI provider key |
| `DEEPSEEK_API_KEY` | DeepSeek provider key |
| `ANTHROPIC_API_KEY` | Anthropic provider key |
| `TELEGRAM_BOT_TOKEN` | Telegram gateway |
| `DISCORD_BOT_TOKEN` | Discord gateway |
| `WIDDX_CORS_ORIGINS` | Allowed CORS origins |
