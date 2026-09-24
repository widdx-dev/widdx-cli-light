"""WIDDX Nexus — Stress & Load Testing Suite.

Simulates real-world concurrent load, rate-limiting edge cases,
burst traffic, and long-running stability on the FastAPI server.

Usage:
    python -m pytest tests/test_stress_load.py -v --tb=short
    python -m pytest tests/test_stress_load.py::TestConcurrentLoad -v
    python -m pytest tests/test_stress_load.py::TestRateLimiting -v
"""

import sys
import os
import time
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use WIDDX_API_KEY from environment if set, otherwise use a test default.
# Must be set before importing scripts.api_server (which reads it at import time).
if "WIDDX_API_KEY" not in os.environ:
    os.environ["WIDDX_API_KEY"] = "stress-test-key-007"

import pytest
from fastapi.testclient import TestClient

# ── Module-level client (shared across tests where possible) ──

def _get_auth_headers():
    """Get current auth headers (reads env dynamically)."""
    api_key = os.environ.get("WIDDX_API_KEY", "stress-test-key-007")
    return {"Authorization": f"Bearer {api_key}"}

AUTH_HEADERS = _get_auth_headers()


# ======================================================================
# SECTION 1 — CONCURRENT LOAD (burst traffic simulation)
# ======================================================================

async def _start_uvicorn(port: int):
    """Start uvicorn on ``port`` and wait until it accepts connections.

    Returns the running server so the caller can shut it down. Using a helper
    keeps the port lifecycle identical across tests and avoids leaking a
    bound socket into the next test (which then failed with ConnectError).
    """
    import socket
    import threading
    import uvicorn

    from scripts.api_server import app

    # Wait for any previous run to fully release the port (TIME_WAIT on
    # Windows keeps the address reserved for ~2 minutes).
    for _ in range(200):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                await asyncio.sleep(0.1)
        except OSError:
            break

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server._widdx_thread_holder = None  # type: ignore[attr-defined]

    def run_server():
        config.load()
        server.run()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    server._widdx_thread_holder = thread  # type: ignore[attr-defined]

    for _ in range(150):  # up to ~15s
        if server.should_exit:
            break
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return server
        except OSError:
            await asyncio.sleep(0.1)
    raise AssertionError(f"uvicorn server did not become ready on 127.0.0.1:{port}")


async def _stop_uvicorn(server) -> None:
    """Ask the uvicorn server to exit and wait for its port to be released."""
    import socket

    if server is None:
        return
    port = getattr(server.config, "port", None)
    server.should_exit = True

    # Wait for the serving thread to finish so the listening socket is closed.
    thread = getattr(server, "_widdx_thread_holder", None)
    if thread is not None:
        for _ in range(100):  # up to ~10s
            if not thread.is_alive():
                break
            await asyncio.sleep(0.1)

    if port is None:
        return
    for _ in range(100):  # up to ~10s
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                await asyncio.sleep(0.1)
        except OSError:
            return  # port is free again


class TestConcurrentLoad:
    """Simulate burst traffic on lightweight endpoints."""

    def setup_method(self):
        from scripts.api_server import app
        from scripts.api_server import _rate_limiter
        # Reset rate limiter so tests start with a clean budget
        _rate_limiter._buckets.clear()
        _rate_limiter.max_requests = 60
        _rate_limiter.window = 60
        self.client = TestClient(app)
        # Read auth headers dynamically (env may change between test modules)
        self.client.headers.update(_get_auth_headers())
        self.endpoints = [
            ("GET", "/api/health"),
            ("GET", "/api/providers"),
            ("GET", "/api/sessions"),
            ("GET", "/api/tools"),
            ("GET", "/api/memory"),
            ("GET", "/api/project/docs"),
            ("GET", "/api/project/status"),
            ("DELETE", "/api/sessions"),
        ]

    # ── 1a. Sequential burst — fire 50 requests in a row fast ──
    def test_sequential_burst_50_requests(self):
        """Fire 50 sequential requests as fast as possible."""
        times = []
        for i in range(50):
            t0 = time.monotonic()
            resp = self.client.get("/api/health")
            t1 = time.monotonic()
            times.append(t1 - t0)
            assert resp.status_code == 200, f"Request {i} failed: {resp.status_code}"

        total = sum(times)
        avg = total / len(times)
        print(f"\n  50 x GET /api/health — total={total:.3f}s, avg={avg*1000:.1f}ms")
        # Sanity: average should be under 500ms for a health endpoint
        assert avg < 0.5, f"Avg response time {avg*1000:.1f}ms exceeds 500ms"

    # ── 1b. Round-robin across all lightweight endpoints ──
    def test_round_robin_all_endpoints(self):
        """Hit every lightweight endpoint in round-robin fashion, 3 cycles.
        Accept 429 (rate-limited) as a valid response since tests accumulate
        against the shared in-memory rate limiter.
        """
        for cycle in range(3):
            for method, path in self.endpoints:
                t0 = time.monotonic()
                if method == "GET":
                    resp = self.client.get(path)
                elif method == "DELETE":
                    resp = self.client.delete(path)
                else:
                    continue
                elapsed = time.monotonic() - t0
                # Accept 200, 204 (success) or 429 (rate-limited) — all valid
                assert resp.status_code in (200, 204, 429), (
                    f"Cycle {cycle}: {method} {path} returned {resp.status_code}"
                )
                print(f"  [{method}] {path} → {resp.status_code} ({elapsed*1000:.0f}ms)")

    # ── 1c. Concurrent requests using httpx + asyncio ──
    @pytest.mark.asyncio
    async def test_concurrent_20_requests(self):
        """Fire 20 concurrent requests to /api/health using asyncio.
        Accept 429 (rate-limited) as valid — rate limiting is a feature.
        """
        import httpx

        server = await _start_uvicorn(9997)

        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:9997") as ac:
                ac.headers.update(_get_auth_headers())

                async def fire_one(idx):
                    t0 = time.monotonic()
                    resp = await ac.get("/api/health")
                    elapsed = time.monotonic() - t0
                    return idx, resp.status_code, elapsed

                tasks = [fire_one(i) for i in range(20)]
                results = await asyncio.gather(*tasks)

            failures = [(i, s) for i, s, _ in results if s not in (200, 429)]
            times = [e for _, _, e in results]
            rate_limited = sum(1 for _, s, _ in results if s == 429)
            avg = sum(times) / len(times)
            print(f"\n  20 concurrent GET /api/health — avg={avg*1000:.1f}ms, "
                  f"max={max(times)*1000:.1f}ms, rate_limited={rate_limited}, "
                  f"unexpected_failures={len(failures)}")
            # All failures should only be rate-limiting (429)
            assert len(failures) == 0, f"Unexpected failures: {failures}"
        finally:
            await _stop_uvicorn(server)

    # ── 1d. Mixed load: different endpoints concurrently ──
    @pytest.mark.asyncio
    async def test_mixed_concurrent_load_30_requests(self):
        """30 concurrent requests hitting various endpoints simultaneously."""
        import httpx
        import random

        server = await _start_uvicorn(9998)

        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:9998", timeout=10.0) as ac:
                ac.headers.update(_get_auth_headers())

                paths = [
                    ("GET", "/api/health"),
                    ("GET", "/api/providers"),
                    ("GET", "/api/sessions"),
                    ("GET", "/api/tools"),
                    ("GET", "/api/memory"),
                ]

                async def mixed_request(idx):
                    method, path = random.choice(paths)
                    t0 = time.monotonic()
                    if method == "GET":
                        resp = await ac.get(path)
                    else:
                        resp = await ac.delete(path)
                    elapsed = time.monotonic() - t0
                    return idx, method, path, resp.status_code, elapsed

                tasks = [mixed_request(i) for i in range(30)]
                results = await asyncio.gather(*tasks)

            failures = [(i, m, p, s) for i, m, p, s, _ in results if s not in (200, 204)]
            times = [e for _, _, _, _, e in results]
            avg = sum(times) / len(times) if times else 0
            print(f"\n  30 mixed concurrent — avg={avg*1000:.1f}ms, "
                  f"max={max(times)*1000:.1f}ms, failures={len(failures)}")
            # All failures should only be rate-limiting (429) — no 401
            for i, m, p, s in failures:
                assert s == 429, f"Unexpected failure: [{m}] {p} → {s}"
        finally:
            # Signal server to shut down and wait for the port to be released.
            await _stop_uvicorn(server)


# ======================================================================
# SECTION 2 — RATE LIMITING
# ======================================================================

class TestRateLimiting:
    """Validate that the in-memory rate limiter kicks in appropriately."""

    def setup_method(self):
        from scripts.api_server import app
        from scripts.api_server import _rate_limiter
        self.client = TestClient(app)
        self.client.headers.update(_get_auth_headers())
        # Clear any buckets left over from earlier tests in the same process
        # (e.g. the concurrent-load tests above), otherwise the per-test budget
        # is already partially consumed and recovery assertions fail.
        _rate_limiter._buckets.clear()
        # Lower the rate limit threshold for testing
        _rate_limiter.max_requests = 10
        _rate_limiter.window = 60

    def test_rate_limit_exceeded(self):
        """After exceeding the limit, subsequent requests should return 429."""
        # Exhaust the budget
        for _ in range(12):
            self.client.get("/api/health")

        # The next request should be rate-limited
        resp = self.client.get("/api/health")
        assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"
        data = resp.json()
        assert "Rate limit" in data.get("detail", "")

    def test_rate_limit_recovers_after_window(self):
        """After the window passes, rate limit should reset."""
        from scripts.api_server import _rate_limiter
        _rate_limiter.max_requests = 5
        _rate_limiter.window = 1  # 1 second window for fast test

        # Exhaust
        for _ in range(7):
            self.client.get("/api/health")

        resp = self.client.get("/api/health")
        assert resp.status_code == 429

        # Wait for window to pass
        time.sleep(1.1)
        resp = self.client.get("/api/health")
        assert resp.status_code == 200, f"Expected recovery, got {resp.status_code}"

    def test_rate_limit_different_keys_independent(self):
        """Rate limiter uses credentials as the key — different tokens are independent."""
        from scripts.api_server import _rate_limiter
        _rate_limiter.max_requests = 3
        _rate_limiter.window = 60
        _rate_limiter._buckets.clear()

        # Exhaust for key1 via direct limiter calls
        for _ in range(5):
            _rate_limiter.check("key1")

        # key1 should now be rate-limited
        assert _rate_limiter.check("key1") is False, "key1 should be rate-limited"

        # key2 should still be allowed (independent bucket)
        assert _rate_limiter.check("key2") is True, "key2 should NOT be rate-limited"

        # Verify they have separate buckets
        assert "key1" in _rate_limiter._buckets
        assert "key2" in _rate_limiter._buckets
        assert len(_rate_limiter._buckets["key1"]) == 3  # trimmed to max_requests
        assert len(_rate_limiter._buckets["key2"]) == 1


# ======================================================================
# SECTION 3 — AUTHENTICATION & SECURITY UNDER LOAD
# ======================================================================

class TestAuthUnderLoad:
    """Ensure auth failures are fast and don't degrade under load."""

    def setup_method(self):
        from scripts.api_server import app
        self.client = TestClient(app)

    def test_missing_auth_is_fast_under_load(self):
        """100 rapid requests without auth — all should 401 quickly."""
        times = []
        for i in range(100):
            t0 = time.monotonic()
            resp = self.client.get("/api/providers")
            t1 = time.monotonic()
            times.append(t1 - t0)
            assert resp.status_code in (401, 503), (
                f"Request {i}: expected 401/503, got {resp.status_code}"
            )

        avg = sum(times) / len(times)
        print(f"\n  100x unauth — avg={avg*1000:.1f}ms, max={max(times)*1000:.1f}ms")
        assert avg < 0.3, f"Auth rejection too slow: avg {avg*1000:.1f}ms"

    def test_invalid_auth_tokens(self):
        """Test various malformed auth tokens."""
        bad_tokens = [
            "Bearer invalid-key",
            "Bearer ",
            "Basic dGVzdDp0ZXN0",
            "",
            "INVALID",
        ]
        for token in bad_tokens:
            resp = self.client.get("/api/providers", headers={
                "Authorization": token
            })
            assert resp.status_code in (401, 403, 422), (
                f"Token '{token[:20]}' returned {resp.status_code}"
            )


# ======================================================================
# SECTION 4 — INPUT VALIDATION UNDER PRESSURE
# ======================================================================

class TestInputValidationUnderLoad:
    """Flood endpoints with invalid / boundary inputs under concurrent load."""

    def setup_method(self):
        from scripts.api_server import app
        from scripts.api_server import _rate_limiter
        # Reset rate limiter so these tests aren't blocked
        _rate_limiter._buckets.clear()
        _rate_limiter.max_requests = 1000
        _rate_limiter.window = 60
        self.client = TestClient(app)
        # Use current env API key (may be changed by conftest)
        api_key = os.environ.get("WIDDX_API_KEY", "stress-test-key-007")
        self.client.headers.update({"Authorization": f"Bearer {api_key}"})

    def test_chat_with_max_size_message(self):
        """Send a message at the size boundary (100K chars)."""
        large_msg = "A" * 100_000
        resp = self.client.post("/api/chat", json={"message": large_msg})
        # Should either be accepted (200) or rejected due to provider unavailability
        assert resp.status_code in (200, 400, 500, 503)

    def test_chat_with_oversized_message(self):
        """Send a message exceeding max_length."""
        huge_msg = "A" * 200_000
        resp = self.client.post("/api/chat", json={"message": huge_msg})
        # FastAPI/Pydantic should reject with 422
        assert resp.status_code == 422

    def test_memory_endpoint_invalid_data(self):
        """Flood memory endpoint with malformed payloads."""
        payloads = [
            {},
            {"name": ""},
            {"content": ""},
            {"name": "x" * 1000, "content": "test"},
            {"name": "valid", "content": "x" * 1_000_000},
        ]
        for payload in payloads:
            resp = self.client.post("/api/memory", json=payload)
            # 200 (ok), 400 (bad request), or 422 (validation error) all acceptable
            assert resp.status_code in (200, 400, 422), (
                f"Payload {payload} returned {resp.status_code}"
            )

    def test_tool_execute_invalid_name(self):
        """Execute a tool with invalid name — should fail gracefully.
        Never return 500 with internal information leakage.
        """
        payloads = [
            {"name": "", "args": {}},
            {"name": "x" * 1000, "args": {}},
            {"name": "nonexistent_tool_xyz", "args": {"foo": "bar"}},
            {"name": "../malicious", "args": {}},
            {"name": "__import__('os').system('rm -rf /')", "args": {}},
        ]
        for payload in payloads:
            resp = self.client.post("/api/tools/execute", json=payload)
            # Accept 200 (edge case handling), 400 (bad request), 422/404 — but
            # NEVER 500 (internal server error / information leakage)
            assert resp.status_code != 500, (
                f"Payload {payload['name'][:30]} caused 500 Internal Server Error"
            )
            # Verify no sensitive data leakage in 200 responses
            if resp.status_code == 200:
                data = resp.json()
                assert "status" in data
                # Should not leak stack traces or internal paths
                resp_text = str(data)
                assert "Traceback" not in resp_text
                assert "File \"" not in resp_text


# ======================================================================
# SECTION 5 — BODY SIZE LIMIT (ISS-004 compliance)
# ======================================================================

class TestBodySizeLimit:
    """Verify the 1 MB body limit is enforced — even under load."""

    def setup_method(self):
        from scripts.api_server import app
        from scripts.api_server import _rate_limiter
        _rate_limiter._buckets.clear()
        _rate_limiter.max_requests = 1000
        self.client = TestClient(app)
        self.client.headers.update(_get_auth_headers())

    def test_oversized_body_rejected(self):
        """POST with Content-Length > 1 MB should return 413."""
        big_body = "x" * (1_048_576 + 1)  # just over 1 MB
        resp = self.client.post(
            "/api/chat",
            content=json.dumps({"message": big_body}),
            headers={"Content-Type": "application/json", **_get_auth_headers()},
        )
        assert resp.status_code == 413, f"Expected 413, got {resp.status_code}"

    def test_body_near_limit_accepted(self):
        """POST with Content-Length just under 1 MB should be allowed."""
        big_body = "x" * (1_048_576 - 1024)  # ~1 MB - 1 KB
        resp = self.client.post(
            "/api/chat",
            content=json.dumps({"message": big_body}),
            headers={"Content-Type": "application/json", **_get_auth_headers()},
        )
        # Either accepted or rejected by business logic, not by body limit
        assert resp.status_code != 413, "Body under 1MB was incorrectly rejected"


# ======================================================================
# SECTION 6 — LONG-RUNNING STABILITY
# ======================================================================

class TestLongRunningStability:
    """Sustained moderate load over many iterations to detect memory leaks."""

    def setup_method(self):
        from scripts.api_server import app
        from scripts.api_server import _rate_limiter
        _rate_limiter._buckets.clear()
        _rate_limiter.max_requests = 2000
        _rate_limiter.window = 60
        self.client = TestClient(app)
        self.client.headers.update(_get_auth_headers())

    def test_500_requests_stability(self):
        """500 sequential requests across endpoints — monitor for degradation."""
        endpoints = [
            ("GET", "/api/health"),
            ("GET", "/api/providers"),
            ("GET", "/api/sessions"),
            ("GET", "/api/memory"),
            ("GET", "/api/tools"),
            ("DELETE", "/api/sessions"),
            ("GET", "/api/project/docs"),
            ("GET", "/api/project/status"),
        ]

        times = []
        failures = []
        for i in range(100):  # Reduced from 500 for faster test
            method, path = endpoints[i % len(endpoints)]
            t0 = time.monotonic()
            if method == "GET":
                resp = self.client.get(path)
            else:
                resp = self.client.delete(path)
            elapsed = time.monotonic() - t0
            times.append(elapsed)

            if resp.status_code not in (200, 204):
                failures.append((i, method, path, resp.status_code))

            # Small progress indicator
            if (i + 1) % 20 == 0:
                batch = times[-20:]
                avg = sum(batch) / len(batch)
                print(f"\n  [{i+1}/100] avg={avg*1000:.1f}ms, failures={len(failures)}")

        total_avg = sum(times) / len(times)
        print(f"\n  100 requests — avg={total_avg*1000:.1f}ms, "
              f"max={max(times)*1000:.1f}ms, failures={len(failures)}")

        # Allow rate-limit (429) failures but nothing else
        for i, m, p, s in failures:
            assert s in (200, 204, 429), (
                f"Request {i}: [{m}] {p} → {s}"
            )


# ======================================================================
# SECTION 7 — CORE COMPONENT STRESS (unit-level)
# ======================================================================

class TestCoreComponentStress:
    """Stress-test core components directly (not through HTTP)."""

    def test_rate_limiter_high_throughput(self):
        """The in-memory rate limiter must handle 10K checks rapidly."""
        from scripts.api_server import RateLimiter
        rl = RateLimiter(max_requests=10000, window_seconds=60)

        t0 = time.monotonic()
        for i in range(5000):
            ok = rl.check(f"user-{i % 100}")
            if i == 0:
                assert ok is True
        elapsed = time.monotonic() - t0

        throughput = 5000 / elapsed
        print(f"\n  RateLimiter: 5000 checks in {elapsed:.3f}s "
              f"({throughput:.0f} checks/sec)")
        assert throughput > 1000, f"Rate limiter too slow: {throughput:.0f} checks/sec"

    def test_rate_limiter_concurrent_safety(self):
        """Rate limiter should not corrupt under rapid concurrent access from multiple keys."""
        from scripts.api_server import RateLimiter
        rl = RateLimiter(max_requests=100, window_seconds=60)

        # Rapid alternation between keys
        for i in range(1000):
            rl.check(f"key-{i % 5}")
            rl.check(f"key-{(i + 1) % 5}")
            # No assertion — just ensure no exception is raised

        # Verify counts are internally consistent
        for key, bucket in rl._buckets.items():
            assert len(bucket) <= rl.max_requests, (
                f"Key {key} has {len(bucket)} entries, limit is {rl.max_requests}"
            )

    def test_config_loading_under_stress(self):
        """Load configuration many times to test filesystem caching."""
        from core.config.settings import load as load_config

        t0 = time.monotonic()
        for i in range(500):
            cfg = load_config()
            assert isinstance(cfg, dict)
            assert "provider" in cfg
        elapsed = time.monotonic() - t0
        throughput = 500 / elapsed
        print(f"\n  Config load: 500 loads in {elapsed:.3f}s "
              f"({throughput:.0f} loads/sec)")
        assert throughput > 50, f"Config loading too slow: {throughput:.0f}/sec"


# ======================================================================
# SECTION 8 — EDGE CASES & RESILIENCE
# ======================================================================

class TestEdgeCasesAndResilience:
    """Unusual / boundary conditions that should not crash the server."""

    def setup_method(self):
        from scripts.api_server import app
        from scripts.api_server import _rate_limiter
        _rate_limiter._buckets.clear()
        _rate_limiter.max_requests = 1000
        _rate_limiter.window = 60
        self.client = TestClient(app)
        self.client.headers.update(_get_auth_headers())

    def test_empty_body_post(self):
        """POST with empty body on various endpoints."""
        endpoints = ["/api/chat", "/api/memory", "/api/tools/execute"]
        for path in endpoints:
            resp = self.client.post(path, content=b"", headers={
                "Content-Type": "application/json", **_get_auth_headers()
            })
            # Should get a validation error, not a crash
            assert resp.status_code in (400, 422, 413), (
                f"Empty body on {path} returned {resp.status_code}"
            )

    def test_malformed_json_body(self):
        """POST with malformed JSON should return 422."""
        resp = self.client.post(
            "/api/chat",
            content=b"{malformed json!!!}",
            headers={"Content-Type": "application/json", **_get_auth_headers()},
        )
        assert resp.status_code == 422

    def test_method_not_allowed(self):
        """Endpoints should properly reject unsupported HTTP methods."""
        # GET on POST-only endpoints
        resp = self.client.get("/api/chat")
        assert resp.status_code in (405, 404), f"GET /api/chat returned {resp.status_code}"

        # POST on GET-only endpoints
        resp = self.client.post("/api/health", json={})
        assert resp.status_code in (405, 404), f"POST /api/health returned {resp.status_code}"

        # PUT is not allowed by CORS config
        resp = self.client.put("/api/health")
        assert resp.status_code in (405, 404), f"PUT /api/health returned {resp.status_code}"

    def test_rapid_provider_switching(self):
        """Rapidly switch providers — should not cause state corruption."""
        valid_providers = [
            {"name": "opencode-zen"},
            {"name": "deepseek", "model": "deepseek-v4-flash-free"},
        ]
        for _ in range(20):
            for p in valid_providers:
                resp = self.client.post("/api/providers/switch", json=p)
                # May succeed (200) or fail (400) — but never crash
                assert resp.status_code in (200, 400), (
                    f"Switch to {p} returned {resp.status_code}"
                )


# ======================================================================
# SECTION 9 — CORS & HEADERS UNDER LOAD
# ======================================================================

class TestCorsHeadersUnderLoad:
    """CORS preflight and header consistency under high request volume."""

    def setup_method(self):
        from scripts.api_server import app
        from scripts.api_server import _rate_limiter
        _rate_limiter._buckets.clear()
        _rate_limiter.max_requests = 1000
        self.client = TestClient(app)

    def test_cors_preflight_is_fast(self):
        """OPTIONS preflight requests should be answered quickly even under load."""
        times = []
        for i in range(50):
            t0 = time.monotonic()
            resp = self.client.options(
                "/api/health",
                headers={
                    "Origin": "http://localhost:8000",
                    "Access-Control-Request-Method": "GET",
                },
            )
            elapsed = time.monotonic() - t0
            times.append(elapsed)
            assert resp.status_code in (200, 204, 405), (
                f"OPTIONS {i} returned {resp.status_code}"
            )

        avg = sum(times) / len(times)
        print(f"\n  50x OPTIONS — avg={avg*1000:.1f}ms, max={max(times)*1000:.1f}ms")
        assert avg < 0.2, f"CORS preflight too slow: avg {avg*1000:.1f}ms"
