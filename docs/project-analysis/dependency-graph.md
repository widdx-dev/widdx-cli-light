# WIDDX Nexus — Dependency Graph

> Generated: 2026-06-25 | Full dependency analysis

## Dependency Layers (bottom-up)

```
┌────────────────────────────────────────────────┐
│ Layer 5: Frontends                             │
│   cli/  tui/  scripts/web/  vscode-extension/  │
│   github-app/  scripts/api_server.py           │
└───────────────────┬────────────────────────────┘
                    │ depends on
┌───────────────────▼────────────────────────────┐
│ Layer 4: Orchestrators                         │
│   core/chat.py  core/commands.py               │
│   scripts/web/chat.py  tui/chat_engine.py      │
│   core/agents/executor_adapter.py              │
└───────────────────┬────────────────────────────┘
                    │ depends on
┌───────────────────▼────────────────────────────┐
│ Layer 3: UIL Cognitive Pipeline                │
│   core/uil/brain.py (UnifiedIntelligenceLayer) │
│   core/uil/analyzer.py  core/uil/router.py     │
│   core/uil/planner.py  core/uil/verifier.py    │
│   core/uil/knowledge.py                        │
│   core/agents/ (AutonomousAgent, ExpertTeam)   │
└───────────────────┬────────────────────────────┘
                    │ depends on
┌───────────────────▼────────────────────────────┐
│ Layer 2: Services                              │
│   core/providers/ (6 LLM providers)            │
│   core/tools/ (20 built-in tools)              │
│   core/mcp/ (MCP client)                       │
│   core/memory.py  core/database.py             │
│   core/sandbox.py  core/guard.py               │
│   core/cron/  core/gateway/                    │
│   core/project/  core/config/                  │
└───────────────────┬────────────────────────────┘
                    │ depends on
┌───────────────────▼────────────────────────────┐
│ Layer 1: Foundation                            │
│   core/config/settings.py (JSON config)        │
│   core/config/keychain.py (API keys)           │
│   core/_path.py (sys.path resolver)            │
│   core/utils.py (shared helpers)               │
└────────────────────────────────────────────────┘
```

---

## Module Dependency Graph

### core/__init__.py — Central Hub
```
core/__init__
├── core.config.settings (load, get, save)
├── core.proxy (proxy_manager, ProxyManager)
├── core.providers.providers (all providers + factory)
├── core.memory (MemoryStore)
├── core.activity (ActivityStore)
├── core.background (BackgroundTaskManager)
├── core.delegation (DelegationManager)
├── core.voice (TTSEngine)
├── core.cron.scheduler (CronScheduler)
├── core.gateway (GatewayCore, Platform, Message, Reply)
├── core.vision (describe_image, VisionMode)
└── core.tools (TOOL_DEFINITIONS, execute, execute_with_skills)
```

### core/providers/providers.py — Provider Hub
```
providers.py (compatibility layer)
├── base.py        → Provider, ToolCall, _clean_surrogates
├── ollama.py      → OllamaProvider
├── openai_compatible.py → OpenAICompatibleProvider
├── opencode_zen.py → OpenCodeZenProvider (extends OpenAICompatible)
├── deepseek.py    → DeepSeekProvider (extends OpenAICompatible)
├── gguf_provider.py → GGUFDirectProvider + config
├── free_models.py → fetch_free_models, pricing
├── factory.py     → create_provider, resolve_model
└── gguf.py        → GGUF file utilities (separate)
```

### scripts/web/ — Web UI
```
server.py (FastAPI + 68 endpoints)
├── chat.py        → ChatHandler (UIL Brain wrapper)
├── sandbox.py     → SandboxHandler
└── dashboard/__init__.py → Dashboard (6 mixins)
    ├── _mixin_core.py
    ├── _mixin_scheduler.py
    ├── _mixin_storage.py
    ├── _mixin_gateway.py
    ├── _mixin_settings.py
    └── _mixin_devops.py
```

### core/agents/ — Agent System
```
executor_adapter.py (maps ExecutionMode → function)
├── agent.py       → AutonomousAgent (tool-calling loop)
└── expert.py      → ExpertTeam (multi-agent pipeline)
```

---

## External Dependency Tree

```
widdx-nexus
├── rich (CLI/TUI rendering)
│   ├── Console, Panel, Table, Text, Rule, Syntax, Markdown
│   └── Live, Progress
├── httpx (HTTP client)
│   └── Used by: all providers, web_fetch, proxy
├── textual (TUI framework)
│   └── Used by: tui/ (all screens and widgets)
├── prompt_toolkit (CLI input)
│   └── Used by: cli/input.py
├── pygments (Syntax highlighting)
│   └── Used by: cli/display.py, core/ui_visual.py
├── python-bidi (RTL text)
│   └── Used by: cli/display.py
├── fastapi + uvicorn (optional, API server)
│   └── Used by: scripts/api_server.py, scripts/web/server.py
├── llama-cpp-python (optional, GGUF)
│   └── Used by: core/providers/gguf_provider.py
├── edge-tts (optional, voice)
│   └── Used by: core/voice.py
├── python-telegram-bot (optional, gateway)
│   └── Used by: core/gateway/telegram.py
└── discord.py (optional, gateway)
    └── Used by: core/gateway/discord.py
```

---

## Key Integration Points

| Interface | Consumer | Provider | Pattern |
|-----------|----------|----------|---------|
| Provider.chat() | UIL, agents, chat handlers | All 6 providers | Strategy |
| TOOL_DEFINITIONS | UIL, agents | core/tools/ | Registry |
| skill_manager | Chat handlers, CLI, TUI | core/skills.py | Singleton |
| get_mcp_manager() | Tools, chat | core/mcp/client.py | Lazy singleton |
| MemoryStore | CLI, TUI, web | core/memory.py | Instance |
| SandboxExecutor | Tools, background | core/sandbox.py | Instance |
