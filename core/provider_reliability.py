"""Provider Reliability Layer — Production-grade execution backbone.

Implements:
  1. Provider Pool with automatic failover
  2. Retry with exponential backoff
  3. Checkpoint on failure for task resume
  4. Unified tool calling across all providers
  5. Failures trigger recovery, not termination

Usage:
    from core.provider_reliability import ReliableProvider
    rp = ReliableProvider()
    result = rp.chat_with_retry(messages, tools, task_state=ts)
"""

from __future__ import annotations

import inspect
import logging
import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import httpx
from core.providers.base import Provider

logger = logging.getLogger("widdx.reliability")


# ═══════════════════════════════════════════════════════════════
# Reliability Result
# ═══════════════════════════════════════════════════════════════

@dataclass
class ReliabilityResult:
    content: str = ""
    tool_calls: list = field(default_factory=list)
    provider_used: str = ""
    attempts: int = 0
    total_time: float = 0.0
    errors: list[str] = field(default_factory=list)
    recovered: bool = False
    failure: Exception | None = None


# ═══════════════════════════════════════════════════════════════
# Provider Pool
# ═══════════════════════════════════════════════════════════════

class ProviderPool:
    """Manages multiple providers with priority-based failover."""

    def __init__(self, cfg: dict | None = None, primary: Provider | None = None):
        self._providers: list[dict] = []
        self._health: dict[str, dict] = {}  # name → {failures, last_fail, cooldown_until}
        self._init_pool(cfg, primary)

    def _init_pool(self, cfg: dict | None = None, primary: Provider | None = None):
        """Initialize the provider pool from config."""
        try:
            if cfg is None:
                from core.config.settings import load as load_cfg
                cfg = load_cfg()
            from core.providers.factory import create_provider

            # Primary provider from config
            try:
                if primary is None:
                    primary = create_provider(cfg, raw=True)
                self._providers.append({
                    "provider": primary,
                    "priority": 1,
                    "name": getattr(primary, "name", "primary"),
                })
            except Exception as e:
                logger.warning("Primary provider unavailable: %s", e)

            # Fallback providers
            fallbacks = [
                ("opencode-zen", "deepseek-v4-flash-free"),
                ("ollama", "deepseek-v4-flash-free"),
            ]
            for name, model in fallbacks:
                if name not in [p["name"] for p in self._providers]:
                    try:
                        fb_cfg = dict(cfg)
                        fb_cfg["provider"] = {"name": name, "model": model}
                        fb = create_provider(fb_cfg, raw=True)
                        self._providers.append({"provider": fb, "priority": len(self._providers) + 1, "name": name})
                    except Exception:
                        logger.debug("Exception suppressed (line 91)")

            logger.info("ProviderPool: %d providers available", len(self._providers))
        except Exception as e:
            logger.error("ProviderPool init failed: %s", e)

    def get_provider(self, skip_unhealthy: bool = True) -> Any | None:
        """Get the best available provider, skipping unhealthy ones."""
        now = time.time()
        for entry in sorted(self._providers, key=lambda x: x["priority"]):
            name = entry["name"]
            health = self._health.get(name, {})
            if skip_unhealthy and health.get("cooldown_until", 0) > now:
                logger.debug("Provider %s in cooldown until %s", name, health.get("cooldown_until"))
                continue
            return entry["provider"]

        # If all are unhealthy and skip_unhealthy was True, fallback to the one with the minimum cooldown_until
        if skip_unhealthy and self._providers:
            entries_with_cooldown = []
            for entry in self._providers:
                name = entry["name"]
                cooldown = self._health.get(name, {}).get("cooldown_until", 0)
                entries_with_cooldown.append((cooldown, entry))
            entries_with_cooldown.sort(key=lambda x: x[0])
            best_entry = entries_with_cooldown[0][1]
            logger.info("All providers are in cooldown. Selected least unhealthy provider: %s", best_entry["name"])
            return best_entry["provider"]

        return None

    def mark_failure(self, name: str, error: str):
        """Mark a provider as failed, putting it in cooldown."""
        now = time.time()
        if name not in self._health:
            self._health[name] = {"failures": 0, "last_fail": 0, "cooldown_until": 0}
        h = self._health[name]
        h["failures"] += 1
        h["last_fail"] = now
        # Exponential cooldown: 2s, 4s, 8s, 16s, max 60s
        cooldown = min(2 ** h["failures"], 60)
        h["cooldown_until"] = now + cooldown
        logger.warning("Provider %s failed (x%d), cooldown %ds: %s", name, h["failures"], cooldown, error[:100])

    def mark_success(self, name: str):
        """Reset failure count on success."""
        if name in self._health:
            self._health[name]["failures"] = 0
            self._health[name]["cooldown_until"] = 0

    @property
    def available_count(self) -> int:
        return len([p for p in self._providers if self._health.get(p["name"], {}).get("cooldown_until", 0) <= time.time()])

    @property
    def total_count(self) -> int:
        return len(self._providers)

    def route_by_complexity(self, complexity: float) -> dict:
        """Select provider settings based on task complexity.

        Low-complexity tasks (quick lookups, simple chat) use faster/cheaper
        providers with higher temperature for creativity.
        High-complexity tasks (code generation, multi-step reasoning) use
        more capable providers with lower temperature for precision.

        Args:
            complexity: Task complexity score from 0.0 (trivial) to 1.0 (very complex).

        Returns:
            dict with keys: provider_name, temperature, max_tokens.
        """
        if not self._providers:
            return {
                "provider_name": "unknown",
                "temperature": 0.7,
                "max_tokens": 4096,
            }

        if complexity < 0.3:
            entry = self._providers[0]
            return {
                "provider_name": entry["name"],
                "temperature": 0.8,
                "max_tokens": 2048,
            }
        elif complexity < 0.6:
            entry = self._providers[0]
            return {
                "provider_name": entry["name"],
                "temperature": 0.6,
                "max_tokens": 4096,
            }
        else:
            entry = self._providers[0]
            return {
                "provider_name": entry["name"],
                "temperature": 0.3,
                "max_tokens": 8192,
            }


# ═══════════════════════════════════════════════════════════════
# Unified Tool Protocol
# ═══════════════════════════════════════════════════════════════

class UnifiedToolCall:
    """Normalized tool call across all providers."""

    def __init__(self, name: str, arguments: dict, call_id: str = ""):
        self.id = call_id or f"call_{name}_{id(arguments)}"
        self.name = name
        self.arguments = arguments

    @staticmethod
    def from_provider(provider_name: str, raw_call: Any) -> "UnifiedToolCall":
        """Parse a provider-specific tool call into unified format."""
        if isinstance(raw_call, UnifiedToolCall):
            return raw_call
        if isinstance(raw_call, dict):
            fn = raw_call.get("function", raw_call)
            return UnifiedToolCall(
                name=fn.get("name", ""),
                arguments=(fn.get("arguments", fn.get("args", {}))
                           if isinstance(fn.get("arguments", fn.get("args", {})), dict)
                           else json.loads(fn.get("arguments", "{}"))),
                call_id=raw_call.get("id", ""),
            )
        if hasattr(raw_call, "name") and hasattr(raw_call, "args"):
            return UnifiedToolCall(name=raw_call.name, arguments=raw_call.args or {}, call_id=getattr(raw_call, "id", ""))
        return UnifiedToolCall(name="unknown", arguments={})

    def to_openai_format(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments, ensure_ascii=False)},
        }

    def to_dict(self) -> dict:
        return {"name": self.name, "args": self.arguments, "id": self.id}


def normalize_tool_result(raw_result: str, provider_name: str) -> str:
    """Normalize tool execution results across providers."""
    if not raw_result:
        return ""
    # DeepSeek sometimes wraps results in extra formatting
    if provider_name in ("deepseek", "opencode-zen"):
        # Strip thinking tags
        import re
        raw_result = re.sub(r'\[thinking\].*?\[/thinking\]', '', raw_result, flags=re.DOTALL)
    return raw_result.strip()


# ═══════════════════════════════════════════════════════════════
# Checkpoint Manager
# ═══════════════════════════════════════════════════════════════

class CheckpointManager:
    """Saves agent state on provider failure for later resume."""

    def __init__(self):
        self._dir = Path.cwd() / ".widdx" / "checkpoints"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, task_id: str, steps: list, messages: list, goal: str):
        """Save current execution state."""
        data = {
            "task_id": task_id,
            "goal": goal,
            "steps": [s.to_dict() for s in steps],
            "messages": messages[-20:],  # last 20 messages
            "timestamp": time.time(),
        }
        fpath = self._dir / f"{task_id}.json"
        fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info("Checkpoint saved: %d steps, %d messages → %s", len(steps), len(messages), fpath.name)

    def load(self, task_id: str) -> dict | None:
        """Load a saved checkpoint."""
        fpath = self._dir / f"{task_id}.json"
        if fpath.exists():
            return json.loads(fpath.read_text())
        return None

    def clear(self, task_id: str):
        (self._dir / f"{task_id}.json").unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
# Reliable Provider — Main API
# ═══════════════════════════════════════════════════════════════

def classify_exception(e: Exception) -> Exception:
    """Classify exception as RateLimitError, ProviderAuthError, transient network error, or general error."""
    if isinstance(e, (RateLimitError, ProviderAuthError, PartialProviderError)):
        return e
    if isinstance(e, httpx.TransportError):
        return TimeoutError(str(e))
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 429:
            return RateLimitError(f"HTTP 429: Rate limited by provider: {e.response.text[:200]}")
        if status in (401, 403):
            return ProviderAuthError(f"HTTP {status}: Auth error: {e.response.text[:200]}")
        if status >= 500:
            return TimeoutError(f"HTTP {status}: Server error: {e.response.text[:200]}")
    err_str = str(e).lower()
    if "rate limit" in err_str or "too many requests" in err_str or "429" in err_str:
        return RateLimitError(str(e))
    if "auth" in err_str or "api key" in err_str or "unauthorized" in err_str or "401" in err_str or "403" in err_str:
        return ProviderAuthError(str(e))
    if "timeout" in err_str or "timed out" in err_str or "connect" in err_str or "network" in err_str or "connection" in err_str or "httpstatuserror" in err_str:
        return TimeoutError(str(e))
    return e


def invoke_provider(method, messages, tool_defs, temperature):
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return method(messages, tool_defs, temperature)
    try:
        signature.bind(messages, tool_defs, temperature)
    except TypeError:
        try:
            signature.bind(messages, tool_defs, temperature=temperature)
        except TypeError:
            signature.bind(messages, tool_defs)
            return method(messages, tool_defs)
        return method(messages, tool_defs, temperature=temperature)
    return method(messages, tool_defs, temperature)


def provider_events(provider, messages, tool_defs, temperature=0.7):
    from core.providers.base import ToolCall

    content_parts: list[str] = []
    tool_calls: list = []
    partial = False
    stream = None
    try:
        stream = invoke_provider(provider.stream, messages, tool_defs or [], temperature)
        for event in stream:
            if isinstance(event, tuple):
                event = {"type": "done", "data": event}
            if not isinstance(event, dict):
                raise ProviderStreamError("Invalid provider stream event")
            kind = event.get("type")
            data = event.get("data")
            if kind == "error":
                error = data if isinstance(data, Exception) else ProviderStreamError(str(data or "Provider stream failed"))
                raise classify_exception(error)
            if kind in ("content", "text", "reasoning"):
                if not isinstance(data, str):
                    raise ProviderStreamError("Invalid provider text event")
                partial = partial or bool(data)
                if kind != "reasoning":
                    content_parts.append(data)
                    event = {"type": "content", "data": data}
            elif kind in ("tool_call", "tool"):
                partial = True
                tool_calls.append(data)
            elif kind == "done":
                if isinstance(data, tuple) and len(data) == 2:
                    content, calls = data
                elif isinstance(data, list):
                    content, calls = "".join(content_parts), data
                elif data is None:
                    content, calls = "".join(content_parts), tool_calls
                else:
                    raise ProviderStreamError("Invalid provider completion payload")
                if content is not None and not isinstance(content, str):
                    raise ProviderStreamError("Invalid provider completion content")
                if calls is not None and not isinstance(calls, list):
                    raise ProviderStreamError("Invalid provider completion tool calls")
                normalized = [UnifiedToolCall.from_provider(provider.name, tc) for tc in (calls or [])]
                yield {"type": "done", "data": (content or "", [
                    ToolCall(tc.name, tc.arguments, tc.id) for tc in normalized
                ])}
                return
            yield event
        raise ProviderStreamError("Provider stream ended without completion")
    except Exception as raw_error:
        error = classify_exception(raw_error)
        if partial and not isinstance(error, PartialProviderError):
            raise PartialProviderError(str(error)) from error
        raise error
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()


def _extract_provider_identity(provider) -> tuple[str, str, str, str]:
    """Safely read (name, model, base_url, api_key) from any provider-like object.

    Test doubles and lightweight wrappers may not define every attribute, so
    every access is guarded with a default instead of raising AttributeError.
    """
    return (
        getattr(provider, "name", "primary"),
        getattr(provider, "model", ""),
        getattr(provider, "base_url", ""),
        getattr(provider, "api_key", ""),
    )


class ReliableProvider(Provider):
    """Production-grade provider with pool, retry, backoff, and checkpointing."""
    def __init__(self, name: str = "", model: str = "", base_url: str = "", api_key: str = "",
                 *, cfg: dict | None = None, primary: Provider | None = None):
        if cfg is not None:
            from core.providers.factory import create_provider
            if primary is None:
                primary = create_provider(cfg, raw=True)
            name, model, base_url, api_key = _extract_provider_identity(primary)
        elif primary is not None:
            name, model, base_url, api_key = _extract_provider_identity(primary)
            cfg = {"provider": {"name": name, "model": model, "base_url": base_url, "api_key": api_key}}
        elif name or model or base_url or api_key:
            cfg = {"provider": {"name": name, "model": model, "base_url": base_url, "api_key": api_key}}
        # Use caller-provided values first; only fall back to config file
        else:
            from core.config.settings import load as _load_cfg
            cfg = _load_cfg()
            p_cfg = cfg.get("provider", {})
            name = p_cfg.get("name", "opencode-zen")
            model = p_cfg.get("model", "deepseek-v4-flash-free")
            base_url = p_cfg.get("base_url", "")
            api_key = p_cfg.get("api_key", "")
        _default_urls = {
            "opencode-zen": "https://opencode.ai/zen/v1",
            "opencode": "https://opencode.ai/zen/v1",
            "ollama": "http://localhost:11434",
            "deepseek": "https://api.deepseek.com",
            "openai": "https://api.openai.com/v1",
        }
        super().__init__(
            name=name,
            model=model or "deepseek-v4-flash-free",
            base_url=base_url or _default_urls.get(name, "https://opencode.ai/zen/v1"),
            api_key=api_key or "",
        )
        self._active_name = self.name
        self._active_model = self.model
        self._pool = ProviderPool(cfg, primary)
        self._checkpoint = CheckpointManager()
        self._max_retries = 3
        self._base_delay = 1.0

    def chat(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Call provider with full reliability: failover + retry + backoff."""
        res = self.chat_with_retry(messages, tool_defs, temperature=temperature)
        if res.failure is not None:
            raise res.failure
        from core.providers.base import ToolCall
        tcs = []
        for tc in res.tool_calls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "arguments", getattr(tc, "args", {}))
            cid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")
            tcs.append(ToolCall(name or "", args or {}, cid or ""))
        return res.content, tcs

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Streaming generator that supports failover and retry transparently."""
        attempt = 0
        while attempt < self._max_retries:
            provider = self._pool.get_provider()
            if provider is None:
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2 ** attempt)
                    logger.warning("All providers in cooldown, retrying in %.1fs", delay)
                    time.sleep(delay)
                    attempt += 1
                    continue
                break

            try:
                for chunk in provider_events(provider, messages, tool_defs, temperature):
                    if chunk["type"] == "done":
                        self._pool.mark_success(provider.name)
                        self._active_name = self.name = provider.name
                        self._active_model = self.model = getattr(provider, "model", self.model)
                    yield chunk
                return

            except Exception as raw_e:
                e = classify_exception(raw_e)
                if isinstance(e, PartialProviderError):
                    self._pool.mark_failure(provider.name, str(e))
                    raise e
                if isinstance(e, RateLimitError):
                    delay = self._base_delay * (2 ** attempt)
                    logger.warning("Rate limited by %s during stream, retry in %.1fs", provider.name, delay)
                    self._pool.mark_failure(provider.name, "rate_limit")
                    time.sleep(delay)
                elif isinstance(e, ProviderAuthError):
                    logger.error("Auth error with %s during stream: %s", provider.name, e)
                    self._pool.mark_failure(provider.name, "auth_error")
                    self._pool._health[provider.name]["cooldown_until"] = time.time() + 3600
                elif isinstance(e, (TimeoutError, ConnectionError, OSError)):
                    logger.warning("Network error with %s during stream: %s", provider.name, e)
                    self._pool.mark_failure(provider.name, str(e)[:100])
                    time.sleep(self._base_delay)
                else:
                    logger.error("Unexpected error with %s during stream: %s", provider.name, e)
                    self._pool.mark_failure(provider.name, str(e)[:100])
                    time.sleep(self._base_delay)
                attempt += 1

        raise ProviderStreamError("All providers failed during execution.")

    def chat_with_retry(
        self,
        messages: list[dict],
        tool_defs: list[dict] | None = None,
        task_state: Any = None,
        task_id: str = "",
        temperature: float = 0.7,
    ) -> ReliabilityResult:
        """Call provider with full reliability: failover + retry + checkpoint."""
        t0 = time.perf_counter()
        result = ReliabilityResult()

        for attempt in range(self._max_retries):
            result.attempts = attempt + 1
            provider = self._pool.get_provider()
            if provider is None:
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2 ** attempt)
                    logger.warning("All providers in cooldown, retrying in %.1fs", delay)
                    time.sleep(delay)
                    continue
                result.errors.append("All providers unavailable")
                result.failure = ProviderStreamError(result.errors[-1])
                break

            try:
                content, tool_calls = self._call_provider(provider, messages, tool_defs, temperature)
                result.content = content or ""
                result.tool_calls = [UnifiedToolCall.from_provider(provider.name, tc).to_dict() for tc in (tool_calls or [])]
                result.provider_used = provider.name
                result.attempts = attempt + 1
                result.recovered = attempt > 0
                result.failure = None
                self._pool.mark_success(provider.name)
                # Update identity to reflect active provider
                self._active_name = provider.name
                self._active_model = getattr(provider, "model", self.model)
                self.name = provider.name
                self.model = getattr(provider, "model", self.model)
                break

            except Exception as raw_e:
                e = classify_exception(raw_e)
                result.errors.append(str(e))
                result.failure = e
                if isinstance(e, PartialProviderError):
                    self._pool.mark_failure(provider.name, str(e))
                    if task_state and task_id:
                        self._checkpoint.save(task_id, [], messages, "")
                    break
                if isinstance(e, RateLimitError):
                    delay = self._base_delay * (2 ** attempt)
                    logger.warning("Rate limited by %s, retry in %.1fs (attempt %d/%d)", provider.name, delay, attempt + 1, self._max_retries)
                    self._pool.mark_failure(provider.name, "rate_limit")
                    if task_state and task_id:
                        self._checkpoint.save(task_id, [], messages, "")
                    time.sleep(delay)
                elif isinstance(e, ProviderAuthError):
                    logger.error("Auth error with %s — disabling", provider.name)
                    self._pool.mark_failure(provider.name, "auth_error")
                    self._pool._health[provider.name]["cooldown_until"] = time.time() + 3600
                elif isinstance(e, (TimeoutError, ConnectionError, OSError)):
                    logger.warning("Network error with %s: %s", provider.name, e)
                    self._pool.mark_failure(provider.name, str(e)[:100])
                    if task_state and task_id:
                        self._checkpoint.save(task_id, [], messages, "")
                    if attempt < self._max_retries - 1:
                        time.sleep(self._base_delay)
                else:
                    logger.error("Unexpected error with %s: %s", provider.name, e)
                    self._pool.mark_failure(provider.name, str(e)[:100])
                    if task_state and task_id:
                        self._checkpoint.save(task_id, [], messages, "")

        result.total_time = round(time.perf_counter() - t0, 3)
        return result

    def _call_provider(self, provider, messages, tool_defs, temperature: float = 0.7):
        """Call a provider, normalizing input/output."""
        if callable(getattr(provider, "stream", None)):
            for event in provider_events(provider, messages, tool_defs, temperature):
                if event["type"] == "done":
                    data = event.get("data")
                    if isinstance(data, tuple) and len(data) == 2:
                        return data
                    if isinstance(data, list):
                        content = "".join(str(c) for c in data if isinstance(c, str))
                        return content, data
            raise ProviderStreamError("Provider stream ended without completion")
        return invoke_provider(provider.chat, messages, tool_defs or [], temperature)

    @property
    def pool_status(self) -> dict:
        return {
            "total": self._pool.total_count,
            "available": self._pool.available_count,
            "health": dict(self._pool._health),
        }


# ═══════════════════════════════════════════════════════════════
# Custom Exceptions
# ═══════════════════════════════════════════════════════════════

class ProviderStreamError(RuntimeError):
    pass


class PartialProviderError(ProviderStreamError):
    pass


class RateLimitError(Exception):
    pass


class ProviderAuthError(Exception):
    pass


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

_reliable: ReliableProvider | None = None


def get_reliable_provider() -> ReliableProvider:
    global _reliable
    if _reliable is None:
        _reliable = ReliableProvider()
    return _reliable


def reset_reliable_provider() -> None:
    """Reset the cached ReliableProvider singleton.

    Call this after config changes (e.g. model/provider switch)
    so the next get_reliable_provider() call creates a fresh provider
    with the updated configuration.
    """
    global _reliable
    _reliable = None
