# Development Guide

## Project Structure
```
widdx-nexus/
├── core/               ← Engine (55 modules)
│   ├── uil/            ← Brain pipeline
│   ├── agents/         ← AutonomousAgent, ExpertTeam
│   ├── providers/      ← 7 LLM providers
│   ├── config/         ← Settings, keychain
│   ├── tools/          ← Tool definitions + handlers
│   ├── intelligence/   ← v4.0 classifier, planner
│   ├── validation/     ← CodeRunner, reporter
│   ├── isolation/      ← Sandbox policies
│   ├── verification/   ← VerifyLoop
│   └── project/        ← Scanner, git, tracker
├── scripts/            ← Web server + static
│   ├── web/            ← FastAPI server, ChatHandler
│   └── static/         ← HTML, CSS, JS
├── cli/                ← CLI interface
├── tui/                ← Textual TUI
└── tests/              ← 523 tests
```

## Build Rules

1. **No breakage:** 523 tests must stay green
2. **Reuse existing:** Use existing modules before creating new ones
3. **Clean code:** type hints, docstrings, no bare except
4. **Test everything:** Every new capability gets a test
5. **Backend first:** core/ → scripts/web/ → static/js/

## Key Patterns

### Singleton Access
```python
from core.memory import MemoryStore
mem = MemoryStore()  # auto-creates if needed
```

### Lazy Import (avoid circular deps)
```python
def my_func():
    from core.heavy_module import HeavyClass  # import inside function
    return HeavyClass().do_work()
```

### Dataclass + JSON
```python
@dataclass
class MyResult:
    success: bool = False
    summary: str = ""
    def to_dict(self) -> dict:
        return {"success": self.success, "summary": self.summary}
```

### Logging
```python
import logging
logger = logging.getLogger("widdx.module_name")
logger.info("Something happened: %s", detail)
```

## Running
```bash
# Development
cd &lt;project-dir&gt;
pip install -e .
widdx-web                    # → http://127.0.0.1:8000

# Tests
python -m pytest tests/ -q   # 523 tests

# Specific test
python -m pytest tests/test_memory.py -v
```

## Provider Setup
```bash
# DeepSeek (API key required)
python -c "from core.config.keychain import prompt_key; prompt_key('deepseek')"

# OpenCode Zen (free, no key)
# Set in Settings → Provider → opencode-zen

# Ollama (local)
ollama pull deepseek-v4-flash-free
```

## Adding a New Provider
1. Create `core/providers/myprovider.py`
2. Extend `Provider` base class
3. Implement `chat(messages, tool_defs, temperature) → tuple[str, list]`
4. Add to `factory.py` → `create_provider()`
5. Test: `python -m pytest tests/test_providers.py`

## Adding a New Tool
```python
# In core/tools/__init__.py:
def _handle_my_tool(arg1: str = "") -> str:
    return f"Result: {arg1}"

register(
    "my_tool",
    "Description of what this tool does",
    {"type": "object", "properties": {
        "arg1": {"type": "string", "description": "First argument"},
    }, "required": ["arg1"]},
    _handle_my_tool,
)
```

## Common Commands
```bash
git log --oneline -10         # Recent commits
python -m pytest tests/ -q    # Full test suite
widdx-web                     # Start server
pip install -e .              # Reinstall after changes
```
