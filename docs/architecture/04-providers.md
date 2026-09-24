# Provider Layer

## 7 Providers — 1 Interface

```python
def chat(self, messages: list[dict], tool_defs: list[dict], temperature: float) -> tuple[str, list]
```

| Provider | Auth | Tools | Stream | Best For |
|----------|------|-------|--------|----------|
| **OpenCode Zen** | Public (free) | ✅ | ✅ | Zero-config quick start |
| **DeepSeek** | API Key | ✅ | ✅ | Best tool-use behavior |
| **OpenAI Compatible** | API Key | ✅ | ✅ | Any OpenAI-API model |
| **Ollama** | None (local) | ✅ | ❌ | Privacy, offline |
| **GGUF Direct** | None | ✅ | ✅ | Local quantized models |
| **GGUF Legacy** | None | ❌ | ❌ | Legacy support |
| **Free Models** | None | ❌ | ❌ | Discovery only |

## Provider Resolution

Config priority (first found wins):
1. `.widdx/config.json` (project-local)
2. `config.json` (CWD)
3. `~/.widdx/config.json` (global user)
4. `<install>/config.json` (bundled default)

## Reliability Layer

`core/provider_reliability.py` — production-grade execution backbone.

### ProviderPool
- Priority-based selection
- Health tracking: failures, cooldown, last error
- Exponential cooldown: 2s, 4s, 8s, 16s, max 60s
- Falls back to least-unhealthy when all are down

### ReliableProvider
- `chat_with_retry(messages, tools)` — full reliability
- 3 retries with exponential backoff
- Auth errors → permanent disable (24h)
- Rate limits → backoff + retry
- Checkpoint save before each attempt

### Wired in AutonomousAgent
- `_call_provider_with_retry()` handles all provider interaction
- Primary provider + auto-detected fallbacks
- Agent never dies on first provider error

## Model-Agnostic Design

All layers above providers are completely provider-independent:
- Brain (analyze/route/plan/execute/verify)
- Memory, KnowledgeGraph, ADR, DocSync
- TaskState, StateManager, DecisionLayer
- Sandbox, Guard, Permissions

**Code Extraction Fallback** handles models without tool support:
- Extracts ```python, ```html, ```js blocks from text
- Auto-detects filenames from comments
- Writes files to disk automatically
