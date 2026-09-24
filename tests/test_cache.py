"""Tests for L1: Cache Layer (core/cache.py)."""
import time
from core.cache import (
    CacheStore, ResponseCache, ToolResultCache,
    _stable_hash,
)


def test_stable_hash_deterministic():
    """Same input → same hash."""
    a = _stable_hash({"key": "value"})
    b = _stable_hash({"key": "value"})
    assert a == b
    assert len(a) == 24


def test_stable_hash_order_independent():
    """Dict key order doesn't matter."""
    a = _stable_hash({"a": 1, "b": 2})
    b = _stable_hash({"b": 2, "a": 1})
    assert a == b


def test_cache_store_set_get():
    store = CacheStore("test", persist=False)
    store.set("k1", "v1", ttl=60)
    assert store.get("k1") == "v1"


def test_cache_store_miss():
    store = CacheStore("test", persist=False)
    assert store.get("nonexistent") is None


def test_cache_store_expiry():
    store = CacheStore("test", persist=False)
    store.set("k1", "v1", ttl=0)  # expires immediately
    time.sleep(0.01)
    assert store.get("k1") is None


def test_cache_store_lru_eviction():
    store = CacheStore("test", max_size=3, persist=False)
    store.set("a", 1)
    store.set("b", 2)
    store.set("c", 3)
    # Access a to make it recently used
    store.get("a")
    # Add d — should evict b (LRU)
    store.set("d", 4)
    assert store.get("a") == 1
    assert store.get("b") is None
    assert store.get("c") == 3
    assert store.get("d") == 4


def test_cache_store_invalidate():
    store = CacheStore("test", persist=False)
    store.set("k1", "v1")
    assert store.invalidate("k1") is True
    assert store.get("k1") is None
    assert store.invalidate("k1") is False


def test_cache_store_invalidate_pattern():
    store = CacheStore("test", persist=False)
    store.set("bash:ls", "result1")
    store.set("bash:pwd", "result2")
    store.set("read:file", "result3")
    store.invalidate_pattern("bash:")
    assert store.get("bash:ls") is None
    assert store.get("bash:pwd") is None
    assert store.get("read:file") == "result3"


def test_cache_store_stats():
    store = CacheStore("test", persist=False)
    store.set("a", 1)
    store.set("b", 2)
    store.get("a")
    store.get("a")
    s = store.stats()
    assert s["name"] == "test"
    assert s["entries"] == 2
    assert s["hits"] == 2


def test_response_cache_key_consistent():
    rc = ResponseCache()
    msgs = [{"role": "user", "content": "hello"}]
    k1 = rc.make_key("test", "model", msgs)
    k2 = rc.make_key("test", "model", msgs)
    assert k1 == k2


def test_response_cache_key_different():
    rc = ResponseCache()
    k1 = rc.make_key("p1", "m", [{"role": "user", "content": "hi"}])
    k2 = rc.make_key("p2", "m", [{"role": "user", "content": "hi"}])
    assert k1 != k2


def test_response_cache_set_get():
    rc = ResponseCache()
    key = rc.make_key("p", "m", [{"role": "user", "content": "q"}])
    rc.set(key, "answer", [{"name": "tool1"}])
    content, calls = rc.get(key)
    assert content == "answer"
    assert len(calls) == 1


def test_response_cache_temperature_skip():
    rc = ResponseCache()
    assert rc.should_cache(0.0) is True   # deterministic → cache
    assert rc.should_cache(0.7) is False  # non-deterministic → skip


def test_tool_cache_key_consistent():
    tc = ToolResultCache()
    k1 = tc.make_key("bash", {"command": "ls"})
    k2 = tc.make_key("bash", {"command": "ls"})
    assert k1 == k2


def test_tool_cache_key_different():
    tc = ToolResultCache()
    k1 = tc.make_key("bash", {"command": "ls"})
    k2 = tc.make_key("bash", {"command": "pwd"})
    assert k1 != k2


def test_tool_cache_set_get():
    tc = ToolResultCache()
    key = tc.make_key("read", {"path": "/tmp"})
    tc.set(key, "file contents", tool_name="read")
    assert tc.get(key) == "file contents"


def test_tool_cache_short_ttl_bash():
    tc = ToolResultCache()
    key = tc.make_key("bash", {"command": "echo hi"})
    tc.set(key, "hi", tool_name="bash")
    # Should be available immediately
    assert tc.get(key) == "hi"


def test_tool_cache_invalidate_on_write():
    tc = ToolResultCache()
    key = tc.make_key("read", {"path": "/x"})
    tc.set(key, "data", tool_name="read")
    assert tc.get(key) == "data"
    tc.invalidate_on_write()
    assert tc.get(key) is None  # cache cleared after write


if __name__ == "__main__":
    print("L1 Cache Tests")
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
