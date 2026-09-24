"""Cache Layer — Response + Tool-Result Caching.

Eliminates redundant API calls and speeds up repeated operations.
Zero external dependencies. Pure Python stdlib + hashlib.

Architecture:
  ResponseCache   — caches LLM responses by (provider, model, messages_hash)
  ToolResultCache — caches tool outputs by (tool_name, args_hash)
  CacheStore      — shared TTL + LRU + disk persistence engine

Integration:
  - Check cache BEFORE provider API call → skip if hit
  - Store result AFTER successful call
  - Auto-invalidate tool cache on file writes
  - Skip response cache when temperature > 0 (non-deterministic)

Usage:
    from core.cache import response_cache, tool_cache

    # Response caching
    key = response_cache.make_key(provider, model, messages)
    cached = response_cache.get(key)
    if cached:
        return cached
    result = provider.chat(...)
    response_cache.set(key, result)

    # Tool caching
    key = tool_cache.make_key("bash", {"command": "ls"})
    tool_cache.get(key)  # → str | None
"""

from __future__ import annotations
import logging

import hashlib
import json
import os
import time
import threading
from pathlib import Path
from typing import Any
logger = logging.getLogger("widdx.cache")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CACHE_DIR = Path.home() / ".widdx" / "cache"
DEFAULT_MAX_SIZE = 500         # max entries before LRU eviction
DEFAULT_RESPONSE_TTL = 300     # 5 minutes for LLM responses
DEFAULT_BASH_TTL = 30          # 30 seconds for bash commands
DEFAULT_READ_TTL = 300         # 5 minutes for read-only tools
DEFAULT_WRITE_TTL = 10         # 10 seconds for write tools (short: invalidation)
PERSIST_INTERVAL = 60          # seconds between auto-saves


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stable_hash(obj: Any) -> str:
    """Deterministic hash of any JSON-serializable object."""
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _now() -> float:
    return time.monotonic()


# ---------------------------------------------------------------------------
# Cache Entry
# ---------------------------------------------------------------------------

# Global sequence counter for LRU ordering (monotonic time has ~15ms
# resolution on Windows, which is not fine-grained enough for tests).
_seq_counter = 0
_seq_lock = threading.Lock()


def _next_seq() -> int:
    global _seq_counter
    with _seq_lock:
        _seq_counter += 1
        return _seq_counter


class _Entry:
    """A single cache entry with metadata."""
    __slots__ = ("key", "value", "created", "expires", "seq", "hits")

    def __init__(self, key: str, value: Any, ttl: int):
        self.key = key
        self.value = value
        self.created = _now()
        self.expires = self.created + max(ttl, 0)
        self.seq = _next_seq()
        self.hits = 0

    @property
    def expired(self) -> bool:
        return _now() >= self.expires

    def touch(self):
        self.seq = _next_seq()
        self.hits += 1

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "created": self.created,
            "expires": self.expires,
            "hits": self.hits,
        }


# ---------------------------------------------------------------------------
# Cache Store (TTL + LRU + Disk Persistence)
# ---------------------------------------------------------------------------

class CacheStore:
    """Thread-safe in-memory cache with TTL eviction, LRU, and disk persistence.

    Designed as a building block — ResponseCache and ToolResultCache
    wrap this with domain-specific key generation and TTL logic.
    """

    def __init__(
        self,
        name: str,
        max_size: int = DEFAULT_MAX_SIZE,
        persist: bool = True,
        cache_dir: Path | None = None,
    ):
        self.name = name
        self.max_size = max_size
        self._data: dict[str, _Entry] = {}
        self._lock = threading.RLock()
        self._persist = persist
        self._dir = cache_dir or DEFAULT_CACHE_DIR
        self._file = self._dir / f"{name}.json"
        self._last_save = 0.0

        if persist:
            self._load()

    # ── Public API ──────────────────────────────────────

    def get(self, key: str) -> Any | None:
        """Return cached value, or None if expired/missing."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._data[key]
                return None
            entry.touch()
            return entry.value

    def set(self, key: str, value: Any, ttl: int = DEFAULT_RESPONSE_TTL):
        """Store a value with TTL. Evicts LRU if at capacity."""
        with self._lock:
            # Evict expired entries
            expired = [k for k, e in self._data.items() if e.expired]
            for k in expired:
                del self._data[k]

            # If at capacity, evict LRU (lowest seq = least recently used)
            if len(self._data) >= self.max_size:
                lru_key = min(self._data.keys(),
                              key=lambda k: self._data[k].seq)
                del self._data[lru_key]

            self._data[key] = _Entry(key, value, ttl)
            self._maybe_save()

    def invalidate(self, key: str) -> bool:
        """Remove a specific key. Returns True if it existed."""
        with self._lock:
            existed = key in self._data
            self._data.pop(key, None)
            return existed

    def invalidate_pattern(self, prefix: str):
        """Remove all keys starting with `prefix`."""
        with self._lock:
            to_remove = [k for k in self._data if k.startswith(prefix)]
            for k in to_remove:
                del self._data[k]

    def clear(self):
        """Remove all entries."""
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            total = len(self._data)
            hits = sum(e.hits for e in self._data.values())
            expired = sum(1 for e in self._data.values() if e.expired)
            return {
                "name": self.name,
                "entries": total,
                "expired": expired,
                "hits": hits,
                "max_size": self.max_size,
            }

    # ── Persistence ─────────────────────────────────────

    def _maybe_save(self):
        if not self._persist:
            return
        now = _now()
        if now - self._last_save < PERSIST_INTERVAL:
            return
        self._last_save = now
        self._save()

    def _save(self):
        """Write cache to disk."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = [e.to_dict() for e in self._data.values() if not e.expired]
            tmp = str(self._file) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, str(self._file))
        except Exception:
            pass  # cache persistence failure is non-fatal

    def _load(self):
        """Load cache from disk."""
        try:
            if not self._file.exists():
                return
            with open(self._file, encoding="utf-8") as f:
                data = json.load(f)
            now = _now()
            with self._lock:
                for d in data:
                    entry = _Entry(d["key"], d["value"], 0)
                    entry.created = d.get("created", now)
                    entry.expires = d.get("expires", now + DEFAULT_RESPONSE_TTL)
                    entry.hits = d.get("hits", 0)
                    # Loaded entries get fresh seq (lowest priority in LRU)
                    entry.seq = _next_seq()
                    if not entry.expired:
                        self._data[entry.key] = entry
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Response Cache
# ---------------------------------------------------------------------------

class ResponseCache:
    """Caches LLM chat responses.

    Cache key = hash(provider_name, model, messages, temperature).
    Skip when temperature > 0 (non-deterministic output).
    """

    def __init__(self, store: CacheStore | None = None):
        self._store = store or CacheStore("responses", max_size=200)

    def make_key(
        self,
        provider: str,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
    ) -> str:
        """Generate a deterministic cache key."""
        payload = {
            "p": provider,
            "m": model,
            "msgs": [
                {"r": m.get("role", ""), "c": m.get("content", "")[:500]}
                for m in messages[-10:]  # last 10 messages only
            ],
            "t": temperature,
        }
        return _stable_hash(payload)

    def get(self, key: str) -> tuple[str, list] | None:
        """Return (content, tool_calls) or None."""
        return self._store.get(key)

    def set(self, key: str, content: str, tool_calls: list | None = None,
            ttl: int = DEFAULT_RESPONSE_TTL):
        """Cache a response."""
        self._store.set(key, (content, tool_calls or []), ttl)

    def should_cache(self, temperature: float) -> bool:
        """Only cache deterministic (temp=0) responses."""
        return temperature == 0.0

    def stats(self) -> dict:
        return self._store.stats()


# ---------------------------------------------------------------------------
# Tool Result Cache
# ---------------------------------------------------------------------------

# Tools whose results should NOT be cached (always fresh)
_UNCACHEABLE_TOOLS = {
    "bash",        # side effects — but we cache with short TTL
}

# TTL by tool category
_TOOL_TTL: dict[str, int] = {
    "bash":    DEFAULT_BASH_TTL,    # 30s — commands have side effects
    "write":   DEFAULT_WRITE_TTL,   # 10s — file writes change state
    "edit":    DEFAULT_WRITE_TTL,
    "read":    DEFAULT_READ_TTL,    # 5min — files rarely change rapidly
    "glob":    DEFAULT_READ_TTL,
    "grep":    DEFAULT_READ_TTL,
    "validate": DEFAULT_READ_TTL,
    "list_files": DEFAULT_READ_TTL,
}


class ToolResultCache:
    """Caches tool execution results.

    Auto-invalidates write-tool caches on subsequent writes.
    Short TTL for bash, longer for read-only tools.
    """

    def __init__(self, store: CacheStore | None = None):
        self._store = store or CacheStore("tools", max_size=500)

    def make_key(self, tool_name: str, args: dict) -> str:
        """Generate a deterministic cache key."""
        payload = {"tool": tool_name, "args": args}
        return _stable_hash(payload)

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, result: str, tool_name: str = ""):
        ttl = _TOOL_TTL.get(tool_name, DEFAULT_READ_TTL)
        self._store.set(key, result, ttl)

    def invalidate_on_write(self):
        """Called after any file write/edit to flush stale tool caches."""
        # Invalidate bash and write/edit tool caches
        self._store.invalidate_pattern("")  # full clear is safest for writes
        # In a future version we can do more targeted invalidation

    def stats(self) -> dict:
        return self._store.stats()


# ---------------------------------------------------------------------------
# Global Instances (singletons — safe across imports)
# ---------------------------------------------------------------------------

response_cache = ResponseCache()
tool_cache = ToolResultCache()
