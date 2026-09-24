"""Tests for the WIDDX Nexus Web UI server (FastAPI + WebSocket).

Tests the core infrastructure: health endpoint, security headers, favicon,
and WebSocket rate limiting.  All LLM/Dashboard dependencies are mocked
so no real providers or databases are required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from scripts.web.server import app, _RATELIMIT_STORE


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    _RATELIMIT_STORE.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health_returns_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "3.2.0"


def test_health_method_not_allowed(client):
    resp = client.post("/api/health")
    assert resp.status_code == 405


def test_favicon_no_content(client):
    resp = client.get("/favicon.ico")
    assert resp.status_code in (200, 204)


def test_security_headers(client):
    resp = client.get("/api/health")
    csp = resp.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-src" in csp          # must explicitly allow iframes
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") in ("DENY", "SAMEORIGIN")


def test_cors_headers_present(client):
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


def test_origin_validation_rejects_bad_origin(client):
    resp = client.post(
        "/api/chat",
        json={"message": "test"},
        headers={"Origin": "https://evil.com"},
    )
    assert resp.status_code == 403
    assert "Origin not allowed" in resp.text


def test_status_endpoint(client):
    with (
        patch("scripts.web.server.get_chat") as mock_get_chat,
        patch("scripts.web.server.get_sandbox") as mock_get_sandbox,
    ):
        mock_chat = MagicMock()
        mock_chat.info = {"provider": "mock", "model": "mock-model"}
        mock_get_chat.return_value = mock_chat
        mock_sandbox = MagicMock()
        mock_sandbox.mode = "subprocess"
        mock_get_sandbox.return_value = mock_sandbox

        resp = client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["provider"]["provider"] == "mock"


def test_version_endpoint(client):
    with patch("scripts.web.server.get_dashboard") as mock_get_dash:
        mock_dash = MagicMock()
        mock_dash.app_version.return_value = {"version": "3.2.0", "build": "test"}
        mock_get_dash.return_value = mock_dash

        resp = client.get("/api/version")

    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data


def test_chat_rate_limiting(client):
    """POST /api/chat respects rate limiter for the client IP."""
    _RATELIMIT_STORE["testclient"] = [0.0] * 30

    with patch("scripts.web.server.get_chat") as mock_get_chat:
        mock_chat = MagicMock()
        mock_chat.chat.return_value = {"content": "ok", "tool_calls": []}
        mock_get_chat.return_value = mock_chat

        with patch("scripts.web.server._check_rate_limit") as mock_rl:
            mock_rl.return_value = False
            resp = client.post(
                "/api/chat",
                json={"message": "hello"},
            )

    assert resp.status_code == 429
    data = resp.json()
    assert "error" in data


def test_ws_chat_rate_limiting(client):
    """WebSocket chat handler sends rate-limit error when throttled."""
    with patch("scripts.web.server._check_rate_limit") as mock_rl:
        mock_rl.return_value = False

        with client.websocket_connect("/ws/chat") as ws:
            ws.send_text(json.dumps({"message": "hello"}))
            msg_raw = ws.receive_text()
            msg = json.loads(msg_raw)
            assert msg["type"] == "error"
            assert "Rate limited" in msg["data"]


def test_new_session_endpoint(client):
    with patch("scripts.web.server.get_chat") as mock_get_chat:
        mock_chat = MagicMock()
        mock_chat.new_session.return_value = "sid-123"
        mock_get_chat.return_value = mock_chat

        resp = client.post("/api/new-session")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sid-123"


def test_ws_chat_passes_through_when_not_limited(client):
    """WebSocket chat does NOT send rate-limit error when not throttled."""
    with (
        patch("scripts.web.server._check_rate_limit") as mock_rl,
        patch("scripts.web.server.get_chat") as mock_get_chat,
    ):
        mock_rl.return_value = True
        mock_chat = MagicMock()
        mock_chat.chat_stream.return_value = [
            {"type": "content", "data": "hello"},
            {"type": "done", "data": ("done", [])},
        ]
        mock_get_chat.return_value = mock_chat

        with client.websocket_connect("/ws/chat") as ws:
            ws.send_text(json.dumps({"message": "hi"}))
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "content"
