"""AI Provider implementations — backward compatibility layer.

This module re-exports everything from the split provider modules.
All existing code importing from ``core.providers.providers`` continues to work.

Each provider now lives in its own module:
  - base.py              — Provider base class + ToolCall + utilities
  - ollama.py            — OllamaProvider
  - openai_compatible.py — OpenAICompatibleProvider
  - opencode_zen.py      — OpenCodeZenProvider
  - deepseek.py          — DeepSeekProvider
  - atria.py             — AtriaProvider
  - free_models.py       — Free model discovery + cost tracking
  - gguf_provider.py     — GGUFDirectProvider + config constants
  - factory.py           — create_provider + model resolution
"""

# ── Base ────────────────────────────────────────────────────
from core.providers.base import (
    Provider, ToolCall,
    _clean_surrogates, _DEFAULT_MAX_TOKENS,
    _TOOL_CAPABLE_PATTERNS, _REASONING_PATTERNS,
)

# ── Provider implementations ────────────────────────────────
from core.providers.ollama import OllamaProvider
from core.providers.openai_compatible import OpenAICompatibleProvider
from core.providers.opencode_zen import OpenCodeZenProvider
from core.providers.deepseek import DeepSeekProvider
from core.providers.atria import AtriaProvider
from core.providers.gguf_provider import (
    GGUFDirectProvider,
    _auto_install_llama_cpp,
    _DEFAULT_BASE_URLS,
    _DEFAULT_MODELS,
)

# ── Free models + pricing ───────────────────────────────────
from core.providers.free_models import (
    fetch_free_models, fetch_free_models_cli, fetch_ollama_models,  # noqa: F401
    get_model_pricing, estimate_turn_cost,
    set_fallback_model, _get_fallback_model,
    FREE_MODELS_CACHE,
)

# ── Factory ─────────────────────────────────────────────────
from core.providers.factory import (
    create_provider,
    fetch_gguf_models,
    get_available_models,
    resolve_model,
)

# ── Keep gguf imports available (used via providers.py) ─────
from core.providers.gguf import (  # noqa: F401 — existing gguf utilities
    scan_gguf_files, import_gguf, list_imports,
    read_gguf_metadata, suggest_model_name, log_import,
)

__all__ = [
    # Base
    "Provider", "ToolCall", "_clean_surrogates", "_DEFAULT_MAX_TOKENS",
    "_TOOL_CAPABLE_PATTERNS", "_REASONING_PATTERNS",
    # Providers
    "OllamaProvider", "OpenAICompatibleProvider", "OpenCodeZenProvider",
    "DeepSeekProvider", "GGUFDirectProvider", "AtriaProvider",
    # Config
    "_DEFAULT_BASE_URLS", "_DEFAULT_MODELS", "FREE_MODELS_CACHE",
    # Factory
    "create_provider", "fetch_gguf_models", "get_available_models", "resolve_model",
    # Free models
    "fetch_free_models", "fetch_free_models_cli", "fetch_ollama_models",
    "get_model_pricing", "estimate_turn_cost",
    "set_fallback_model", "_get_fallback_model",
    # GGUF
    "scan_gguf_files", "import_gguf", "list_imports",
    "read_gguf_metadata", "suggest_model_name", "log_import",
    "_auto_install_llama_cpp",
]
