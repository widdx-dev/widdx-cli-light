# WIDDX Nexus — Import/Export Analysis

> Generated: 2026-06-25 | 125+ Python files analyzed

## External Dependencies

### Required (pyproject.toml)
| Package | Version | Purpose |
|---------|---------|---------|
| rich | >=13.0 | Terminal formatting |
| httpx | >=0.25 | HTTP client |
| textual | >=1.0 | TUI framework |
| prompt_toolkit | >=3.0 | CLI input |
| pygments | >=2.15 | Syntax highlighting |
| python-bidi | >=0.6.0 | RTL text support |

### Optional (ImportError-guarded)
| Group | Packages |
|-------|----------|
| api | fastapi, uvicorn |
| gguf | llama-cpp-python |
| voice | edge-tts |
| gateway | python-telegram-bot, discord.py |
| dev | pytest, pytest-asyncio, build, twine |

### NPM (MCP servers)
- @modelcontextprotocol/server-filesystem
- @modelcontextprotocol/server-memory
- @modelcontextprotocol/server-sequential-thinking
- @playwright/mcp

---

## Top 20 Most-Imported Modules

| Rank | Module | Count | Used By |
|------|--------|-------|---------|
| 1 | pathlib.Path | 40+ | Every file |
| 2 | json | 30+ | Config, state, serialization |
| 3 | logging | 30+ | All subsystems |
| 4 | typing | 20+ | Type annotations |
| 5 | os | 18+ | Paths, env vars |
| 6 | sys | 16+ | Path setup |
| 7 | re | 16+ | Pattern matching |
| 8 | time | 14+ | Timing, delays |
| 9 | datetime | 14+ | Timestamps |
| 10 | threading | 12+ | Concurrency |
| 11 | core.skills | 12+ | Chat, CLI, TUI |
| 12 | core.memory | 10+ | Memory system |
| 13 | core.tools | 10+ | Tool definitions |
| 14 | core.providers.providers | 10+ | Provider creation |
| 15 | core.mcp.client | 9+ | MCP integration |
| 16 | core.config.settings | 8+ | Configuration |
| 17 | core.project.state | 8+ | Session persistence |
| 18 | dataclasses | 8+ | Data models |
| 19 | rich (aggregate) | 30+ | UI rendering |
| 20 | core.sandbox | 6+ | Sandbox execution |

---

## Import Patterns

### Absolute imports (dominant)
```python
from core.tools import TOOL_DEFINITIONS, execute
from core.skills import skill_manager
from core.providers.providers import create_provider
```

### Relative imports (within subpackages)
```python
from .display import show_system_msg    # cli/
from ..tools import execute             # core/agents/
from ..config.keychain import get_key   # core/providers/
```

### Lazy imports (80+ sites)
Used to avoid circular imports and handle optional deps:
```python
def _bash(command):
    from core.sandbox import SandboxExecutor  # lazy
    ...
```

---

## Wildcard Imports: ZERO

Confirmed by `test_no_wildcard_imports_in_cli` (tests/test_e2e.py).

---

## Circular Import Risk: NONE

The project uses disciplined lazy imports (80+ sites) to break every potential cycle. Key examples:

| File | Lazy imports | Reason |
|------|-------------|--------|
| core/tools/__init__.py | 15+ lazy imports | Avoids circular deps with sandbox, linter, skills, permissions |
| core/uil/brain.py | 4 lazy imports | Avoids circular deps with engines, classifier |
| tui/chat_engine.py | 12+ lazy imports | Avoids circular deps with core |
| core/agents/agent.py | 5 lazy imports | Avoids circular deps with cache, tools |
| core/commands.py | 20+ lazy imports | Avoids circular deps with CLI app |

---

## Re-Export Chains

```
core/__init__.py → core.providers.providers → 8 sub-modules
core/providers/__init__.py → core.providers.providers
core/uil/__init__.py → 6 sub-modules (contract, analyzer, router, planner, brain, knowledge)
core/intelligence/__init__.py → 6 sub-modules
scripts/web/dashboard/__init__.py → 6 mixin files
```

---

## __import__ Anti-Pattern: FIXED

All 8 provider files previously used `logger = __import__("logging").getLogger(...)`. Fixed to standard `import logging as _logging` pattern as of 2026-06-25.
