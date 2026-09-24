"""Stress tests for Provider Reliability Layer."""
import time
from core.provider_reliability import (
    ProviderPool, ReliableProvider, CheckpointManager, UnifiedToolCall,
    RateLimitError, ProviderAuthError,
    get_reliable_provider,
)


class MockFailingProvider:
    def __init__(self, name="mock", fail_count=0, fail_with=None):
        self.name = name
        self.model = "mock"
        self._fail_count = fail_count
        self._attempts = 0
        self._fail_with = fail_with

    def _should_fail(self) -> bool:
        """Returns True if this attempt should fail. One attempt = one chat() or stream() call from ReliableProvider."""
        self._attempts += 1
        return self._attempts <= self._fail_count

    def chat(self, messages, tool_defs=None, temperature=0.7):
        if self._should_fail():
            if self._fail_with:
                raise self._fail_with("Simulated failure")
            raise Exception("Simulated failure")
        return f"Response from {self.name}", []

    def stream(self, messages, tool_defs=None, temperature=0.7):
        # If we should fail, don't yield anything useful - force fallback to chat
        if self._should_fail():
            if self._fail_with:
                raise self._fail_with("Simulated failure")
            raise Exception("Simulated failure")
        yield {"type": "done", "data": (f"Response from {self.name}", [])}


def test_terminal_payload_is_consumed_without_second_request():
    from unittest.mock import Mock

    provider = Mock(name="provider")
    provider.name = "mock"
    provider.stream.return_value = iter([
        {"type": "content", "data": "partial"},
        {"type": "done", "data": ("complete response", [])},
    ])
    rp = ReliableProvider.__new__(ReliableProvider)
    assert rp._call_provider(provider, [], [], 0.2) == ("complete response", [])
    provider.stream.assert_called_once_with([], [], 0.2)
    provider.chat.assert_not_called()


class TestProviderPool:
    """Test provider failover pool."""

    def test_pool_marks_failure_and_cooldown(self):
        pool = ProviderPool()
        pool._providers = [
            {"provider": MockFailingProvider("a"), "priority": 1, "name": "a"},
            {"provider": MockFailingProvider("b"), "priority": 2, "name": "b"},
        ]
        pool.mark_failure("a", "test error")
        assert pool._health["a"]["failures"] == 1
        assert pool._health["a"]["cooldown_until"] > time.time()

    def test_pool_skips_unhealthy(self):
        pool = ProviderPool()
        pool._providers = [
            {"provider": MockFailingProvider("a"), "priority": 1, "name": "a"},
            {"provider": MockFailingProvider("b"), "priority": 2, "name": "b"},
        ]
        pool.mark_failure("a", "error")
        provider = pool.get_provider()
        assert provider is not None
        assert provider.name == "b"  # Should skip 'a'

    def test_pool_marks_success_clears_failures(self):
        pool = ProviderPool()
        pool._providers = [
            {"provider": MockFailingProvider("a"), "priority": 1, "name": "a"},
        ]
        pool.mark_failure("a", "error")
        pool.mark_success("a")
        assert pool._health["a"]["failures"] == 0

    def test_pool_available_count(self):
        pool = ProviderPool()
        pool._providers = [
            {"provider": MockFailingProvider("a"), "priority": 1, "name": "a"},
            {"provider": MockFailingProvider("b"), "priority": 2, "name": "b"},
        ]
        assert pool.available_count == 2
        pool.mark_failure("a", "error")
        assert pool.available_count == 1


class TestReliableProvider:
    """Test retry + failover."""

    def test_succeeds_on_first_attempt(self):
        rp = ReliableProvider()
        rp._pool._providers = [
            {"provider": MockFailingProvider("ok"), "priority": 1, "name": "ok"},
        ]
        result = rp.chat_with_retry([{"role": "user", "content": "hi"}])
        assert result.content == "Response from ok"
        assert result.attempts == 1
        assert result.recovered is False

    def test_failover_on_failure(self):
        rp = ReliableProvider()
        # fail_count=3: stream() fails, chat() fails, next attempt gets backup
        rp._pool._providers = [
            {"provider": MockFailingProvider("bad", fail_count=3), "priority": 1, "name": "bad"},
            {"provider": MockFailingProvider("good"), "priority": 2, "name": "good"},
        ]
        rp._max_retries = 3
        result = rp.chat_with_retry([{"role": "user", "content": "hi"}])
        assert result.provider_used == "good"
        assert result.recovered is True

    def test_rate_limit_backoff(self):
        rp = ReliableProvider()
        rp._pool._providers = [
            {"provider": MockFailingProvider("limited", fail_count=3, fail_with=RateLimitError), "priority": 1, "name": "limited"},
            {"provider": MockFailingProvider("backup"), "priority": 2, "name": "backup"},
        ]
        rp._max_retries = 3
        t0 = time.time()
        result = rp.chat_with_retry([{"role": "user", "content": "hi"}])
        elapsed = time.time() - t0
        assert result.provider_used == "backup"
        assert elapsed >= 0.9  # At least 1s backoff

    def test_auth_error_permanent_fail(self):
        rp = ReliableProvider()
        rp._pool._providers = [
            {"provider": MockFailingProvider("authbad", fail_count=3, fail_with=ProviderAuthError), "priority": 1, "name": "authbad"},
            {"provider": MockFailingProvider("backup"), "priority": 2, "name": "backup"},
        ]
        rp._max_retries = 2
        result = rp.chat_with_retry([{"role": "user", "content": "hi"}])
        # Auth errors force long cooldown, should use backup
        assert result.provider_used == "backup"


class TestUnifiedToolCall:
    """Test unified tool protocol."""

    def test_from_provider_dict(self):
        tc = UnifiedToolCall.from_provider("deepseek", {
            "id": "call_1",
            "function": {"name": "write", "arguments": {"file_path": "test.py", "content": "x=1"}},
        })
        assert tc.name == "write"
        assert tc.arguments["file_path"] == "test.py"

    def test_to_openai_format(self):
        tc = UnifiedToolCall("write", {"file_path": "test.py", "content": "x=1"}, "call_1")
        fmt = tc.to_openai_format()
        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "write"

    def test_from_object_with_attrs(self):
        class MockTC:
            name = "bash"
            args = {"command": "echo hello"}
            id = "call_2"
        tc = UnifiedToolCall.from_provider("ollama", MockTC())
        assert tc.name == "bash"


class TestCheckpointManager:
    """Test checkpoint save/load."""

    def test_save_and_load(self):
        import tempfile
        import shutil
        import os
        orig_dir = os.getcwd()
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            cm = CheckpointManager()
            cm.save("task1", [], [{"role": "user", "content": "hi"}], "test goal")
            loaded = cm.load("task1")
            assert loaded is not None
            assert loaded["goal"] == "test goal"
            assert len(loaded["messages"]) == 1
            cm.clear("task1")
            assert cm.load("task1") is None
        finally:
            os.chdir(orig_dir)
            shutil.rmtree(tmp, ignore_errors=True)


class TestSingleton:
    """Test singleton access."""

    def test_get_reliable_provider(self):
        a = get_reliable_provider()
        b = get_reliable_provider()
        assert a is b


# ===================================================================
# Tests: Route-by-complexity
# ===================================================================

class TestRouteByComplexity:
    """ProviderPool.route_by_complexity(): selects provider settings by task complexity."""

    def test_returns_dict_with_keys(self):
        pool = ProviderPool()
        pool._providers = [
            {"provider": MockFailingProvider("p1"), "priority": 1, "name": "p1"},
        ]
        route = pool.route_by_complexity(0.5)
        assert "provider_name" in route
        assert "temperature" in route
        assert "max_tokens" in route

    def test_low_complexity_uses_higher_temp(self):
        pool = ProviderPool()
        pool._providers = [
            {"provider": MockFailingProvider("p1"), "priority": 1, "name": "p1"},
        ]
        low = pool.route_by_complexity(0.1)
        high = pool.route_by_complexity(0.9)
        assert low["temperature"] > high["temperature"]

    def test_low_complexity_uses_fewer_tokens(self):
        pool = ProviderPool()
        pool._providers = [
            {"provider": MockFailingProvider("p1"), "priority": 1, "name": "p1"},
        ]
        low = pool.route_by_complexity(0.1)
        high = pool.route_by_complexity(0.9)
        assert low["max_tokens"] < high["max_tokens"]

    def test_medium_complexity(self):
        pool = ProviderPool()
        pool._providers = [
            {"provider": MockFailingProvider("p1"), "priority": 1, "name": "p1"},
        ]
        route = pool.route_by_complexity(0.5)
        assert route["temperature"] == 0.6
        assert route["max_tokens"] == 4096

    def test_empty_pool_returns_defaults(self):
        pool = ProviderPool()
        pool._providers = []
        route = pool.route_by_complexity(0.5)
        assert route["provider_name"] == "unknown"
        assert route["temperature"] == 0.7
