"""Free model discovery and cost tracking."""
from __future__ import annotations

import time
import threading
from typing import Any
import httpx

from ..proxy import ZEN_BASE

import logging as _logging
logger = _logging.getLogger("widdx.providers")

# ---------------------------------------------------------------------------
# Default fallback model (used when API calls fail — loaded from config first)
# ---------------------------------------------------------------------------

_DEFAULT_FALLBACK_MODEL: str | None = None

def set_fallback_model(model: str) -> None:
    """Set the fallback model from config (called at startup)."""
    global _DEFAULT_FALLBACK_MODEL
    _DEFAULT_FALLBACK_MODEL = model


def _get_fallback_model() -> str:
    """Return the configured fallback, or a safe hardcoded last resort."""
    return _DEFAULT_FALLBACK_MODEL or "deepseek-v4-flash-free"


# ---------------------------------------------------------------------------
# Free Models Cache
# ---------------------------------------------------------------------------

FREE_MODELS_CACHE: dict[str, Any] = {"models": [], "timestamp": 0}
_FREE_MODELS_LOCK = threading.Lock()

def fetch_free_models(force_refresh: bool = False) -> list[str]:
    """Fetch free model IDs from OpenCode Zen API.

    Model IDs from the API are bare (e.g. "nemotron-3-ultra-free").
    The OpenCode CLI requires the "opencode/" prefix.
    The OpenCode Zen provider (direct HTTP) uses bare IDs.
    """
    with _FREE_MODELS_LOCK:
        now = time.time()
        if (not force_refresh
                and FREE_MODELS_CACHE["models"]
                and (now - FREE_MODELS_CACHE["timestamp"]) < 3600):
            return FREE_MODELS_CACHE["models"]
    fallback = _get_fallback_model()
    try:
        r = httpx.get(f"{ZEN_BASE}/models", timeout=10)
        if r.status_code != 200:
            with _FREE_MODELS_LOCK:
                return FREE_MODELS_CACHE["models"] or [fallback]
        all_models = r.json().get("data", [])
        free = [m["id"] for m in all_models if "free" in m.get("id", "").lower()]
        if free:
            with _FREE_MODELS_LOCK:
                FREE_MODELS_CACHE["models"] = free
                FREE_MODELS_CACHE["timestamp"] = now
                return FREE_MODELS_CACHE["models"] or [fallback]
        with _FREE_MODELS_LOCK:
            return FREE_MODELS_CACHE["models"] or [fallback]
    except Exception:
        with _FREE_MODELS_LOCK:
            return FREE_MODELS_CACHE["models"] or [fallback]


def fetch_free_models_cli(force_refresh: bool = False) -> list[str]:
    """Return free model IDs with opencode/ prefix for CLI usage.

    The OpenCode CLI requires the full model name like:
      opencode/nemotron-3-ultra-free
    while the Zen API returns bare IDs like:
      nemotron-3-ultra-free
    """
    raw = fetch_free_models(force_refresh=force_refresh)
    # Add opencode/ prefix if not already present
    return [
        m if m.startswith("opencode/") else f"opencode/{m}"
        for m in raw
    ]


# ── Ollama local model discovery ─────────────────────────────

_OLLAMA_MODELS_CACHE: dict = {"models": [], "timestamp": 0}
OLLAMA_DEFAULT_URL = "http://localhost:11434"


def fetch_ollama_models(base_url: str | None = None,
                        force_refresh: bool = False) -> list[dict]:
    """Discover installed models from a local Ollama instance.

    Queries ``GET /api/tags`` on the Ollama server.  Returns a list of
    dicts with keys ``name``, ``size``, ``modified_at`` so callers can
    display rich information.

    Results are cached for 300 seconds (5 min) — models don't change
    often on a local machine.  Pass *force_refresh=True* to bypass.
    """
    url_base = (base_url or OLLAMA_DEFAULT_URL).rstrip("/")

    now = time.time()
    if (not force_refresh
            and _OLLAMA_MODELS_CACHE["models"]
            and (now - _OLLAMA_MODELS_CACHE["timestamp"]) < 300):
        return _OLLAMA_MODELS_CACHE["models"]

    try:
        r = httpx.get(f"{url_base}/api/tags", timeout=5)
        if r.status_code != 200:
            return _OLLAMA_MODELS_CACHE["models"]
        data = r.json()
        models = data.get("models", [])
        # Normalise: keep only the fields we care about
        result = [{
            "name": m.get("name", m.get("model", "unknown")),
            "size": m.get("size", 0),           # bytes
            "modified_at": m.get("modified_at", ""),
        } for m in models]
        # Sort by name
        result.sort(key=lambda m: m["name"])
        _OLLAMA_MODELS_CACHE["models"] = result
        _OLLAMA_MODELS_CACHE["timestamp"] = now
        return result
    except Exception as e:
        logger.debug("Ollama models fetch failed: %s", e)
        return _OLLAMA_MODELS_CACHE["models"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Cost tracking — map model names to per-token pricing
# ---------------------------------------------------------------------------

_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_1M, output_per_1M) in USD
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-3.5": (0.80, 4.00),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "deepseek-v4-flash": (0.35, 1.40),
    "deepseek-v4-pro": (1.50, 6.00),
}

# Fallback pricing for unknown models
_DEFAULT_INPUT_PRICE = 1.0  # $1/M tokens
_DEFAULT_OUTPUT_PRICE = 4.0  # $4/M tokens


def get_model_pricing(model: str) -> tuple[float, float]:
    """Return (input_price_per_1M, output_price_per_1M) for a model.

    Falls back to sensible defaults for unknown models.
    Returns (0, 0) for free models (opencode-zen, etc.).
    """
    if not model or "free" in model.lower() or "opencode" in model.lower():
        return (0.0, 0.0)
    model_lower = model.lower()
    if model_lower in _MODEL_PRICING:
        return _MODEL_PRICING[model_lower]
    # Check partial match
    for key, pricing in _MODEL_PRICING.items():
        if key in model_lower:
            return pricing
    return (_DEFAULT_INPUT_PRICE, _DEFAULT_OUTPUT_PRICE)


def estimate_turn_cost(model: str, input_tokens: int = 500,
                       output_tokens: int = 1000) -> float:
    """Estimate cost of a single LLM turn.

    Uses model pricing lookup. Returns 0 for free models.
    """
    inp_price, out_price = get_model_pricing(model)
    if inp_price == 0 and out_price == 0:
        return 0.0
    return (input_tokens / 1_000_000 * inp_price +
            output_tokens / 1_000_000 * out_price)

