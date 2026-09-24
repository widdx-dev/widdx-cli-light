"""Provider factory — create providers, discover models."""
from __future__ import annotations

from pathlib import Path

from .base import Provider
from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider
from .opencode_zen import OpenCodeZenProvider
from .deepseek import DeepSeekProvider
from .atria import AtriaProvider
from .gguf_provider import GGUFDirectProvider, _DEFAULT_BASE_URLS, _DEFAULT_MODELS
from .free_models import fetch_free_models, fetch_free_models_cli, fetch_ollama_models, set_fallback_model
from ..config.keychain import get_key

import logging as _logging
logger = _logging.getLogger("widdx.providers")

def create_provider(cfg: dict, raw: bool = False) -> Provider:
    """Create a provider instance from configuration dict.

    Reads provider name, model, base_url from cfg. API keys resolved via
    keychain (env vars) with config fallback. Supports ollama, gguf,
    opencode-zen, deepseek, and openai-compatible providers.
    """
    if not raw:
        from core.provider_reliability import ReliableProvider
        return ReliableProvider(cfg=cfg)

    p = cfg.get("provider", {})

    p = cfg.get("provider", {})
    if isinstance(p, str):
        p = {"name": p}
    # Load from config with dynamic fallbacks
    name = p.get("name") or cfg.get("default_provider", "opencode-zen")
    model = p.get("model") or cfg.get("default_model", "")
    # Use provider-specific default base_url, fall back to config, then opencode
    base_url = (
        p.get("base_url")
        or cfg.get("default_base_url")
        or _DEFAULT_BASE_URLS.get(name, "https://opencode.ai/zen/v1")
    )
    # Resolve model dynamically — never use a stale hardcoded name
    resolved = resolve_model(name, preferred=model or None, base_url=base_url)
    if resolved:
        model = resolved
    elif not model:
        # Absolute last resort
        model = "deepseek-v4-flash-free"
    # Update the fallback model for proxy & cache (dynamic)
    set_fallback_model(model)

    # Prefer key from env / keychain; fall back to config (for legacy compat)
    # Only opencode-zen uses "public" as default; other providers need real keys
    if name in ("opencode-zen", "opencode"):
        api_key = get_key(name) or p.get("api_key", "public")
    else:
        api_key = get_key(name) or p.get("api_key", "")
    if name == "ollama":
        return OllamaProvider(name, model, base_url, api_key)
    if name == "gguf":
        # If model is a .gguf file path → use direct provider, else fallback to Ollama
        if model and (model.endswith(".gguf") or Path(model).exists()):
            try:
                return GGUFDirectProvider(name, model, base_url, api_key)
            except Exception:
                logger.debug("Exception suppressed (line 66)")  # fall through to Ollama if llama-cpp not available
        return OllamaProvider(name, model, base_url, api_key)
    if name in ("opencode-zen", "opencode"):
        # Use OpenCode CLI provider for "opencode" (free, no API key)
        if name == "opencode":
            from .opencode_provider import OpenCodeProvider
            return OpenCodeProvider(name, model, base_url, api_key, cfg=cfg)
        return OpenCodeZenProvider(name, model, base_url, api_key)
    if name == "deepseek":
        return DeepSeekProvider(name, model, base_url, api_key, cfg=cfg)
    if name == "atria":
        return AtriaProvider(name, model, base_url, api_key, cfg=cfg)
    return OpenAICompatibleProvider(name, model, base_url, api_key)


def fetch_gguf_models() -> list[str]:
    """Return only GGUF-imported Ollama models (not all Ollama models)."""
    try:
        from .gguf import list_imports
        imports = list_imports()
        return [e["model_name"] for e in imports if e.get("model_name")]
    except Exception:
        return []


def get_available_models(provider_name: str, base_url: str | None = None, force_refresh: bool = False) -> list[str]:
    """Get available models for a given provider (fetching dynamically where possible)."""
    if provider_name == "opencode":
        return fetch_free_models_cli(force_refresh=force_refresh)
    if provider_name == "opencode-zen":
        return fetch_free_models(force_refresh=force_refresh)
    elif provider_name == "ollama":
        installed = fetch_ollama_models(base_url=base_url, force_refresh=force_refresh)
        return [m["name"] for m in installed] if installed else []
    elif provider_name == "gguf":
        return fetch_gguf_models()
    else:  # deepseek, openai: use static default lists
        return list(_DEFAULT_MODELS.get(provider_name, []))


def resolve_model(provider_name: str, preferred: str | None = None,
                  base_url: str | None = None) -> str:
    """Return a valid model name for *provider_name*.

    1. If *preferred* is given → return it (user explicitly selected it).
    2. Otherwise fetch the dynamic list and return the first entry.
    3. Fall back to a hardcoded safe default if everything fails.
    """
    if preferred:
        return preferred
    available = get_available_models(provider_name, base_url, force_refresh=False)
    if available:
        return available[0]

    # Ultimate fallback — one known-good model per provider
    _FALLBACK = {
        "opencode-zen": "deepseek-v4-flash-free",
        "opencode": "opencode/mimo-v2.5-free",
        "ollama": "",
        "gguf": "",
        "deepseek": "deepseek-v4-flash",
        "openai": "gpt-4o-mini",
        "atria": "Atria-Dawn-Preview",
    }
    return _FALLBACK.get(provider_name, preferred or "")
