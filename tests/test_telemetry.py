"""Tests — Anonymous Usage Telemetry (Task 4.5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import telemetry  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Fresh telemetry store + enabled state per test."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WIDDX_TELEMETRY_DISABLED", raising=False)
    telemetry.close()
    yield
    telemetry.close()


def test_enabled_by_default():
    assert telemetry.is_enabled() is True


def test_opt_out_via_env(monkeypatch):
    monkeypatch.setenv("WIDDX_TELEMETRY_DISABLED", "1")
    assert telemetry.is_enabled() is False
    # record becomes a no-op
    assert telemetry.record("anything") is False
    assert telemetry.summary()["event_count"] == 0
    assert telemetry.summary()["instance_fingerprint"] is None


def test_record_and_summary():
    assert telemetry.record("test_event") is True
    telemetry.record("test_event")
    telemetry.record("http_request", value=12.5, dims={"route": "/api/health"})
    s = telemetry.summary(days=14)
    assert s["enabled"] is True
    assert s["totals_by_event"]["test_event"]["count"] == 2
    assert s["totals_by_event"]["http_request"]["count"] == 1
    assert s["event_count"] == 3
    assert "/api/health" in s["top_routes"]


def test_sensitive_dims_are_scrubbed():
    telemetry.record(
        "evt",
        dims={
            "route": "/api/x",          # allowed
            "method": "GET",            # allowed
            "content": "SECRET TEXT",   # blocked
            "api_key": "abc123",        # blocked
            "ip": "1.2.3.4",            # blocked
            "path": "/home/user/x",     # blocked
        },
    )
    s = telemetry.summary()
    # The event exists but no sensitive labels leaked into storage.
    assert s["event_count"] == 1
    import sqlite3
    import json
    conn = sqlite3.connect(Path.cwd() / ".widdx" / "data" / "telemetry.db")
    row = conn.execute("SELECT dims FROM telemetry_events").fetchone()
    stored = json.loads(row[0])
    assert "SECRET TEXT" not in json.dumps(stored)
    assert "abc123" not in json.dumps(stored)
    assert set(stored) <= {"route", "method"}
    conn.close()


def test_instance_fingerprint_is_stable_and_anonymous():
    f1 = telemetry.instance_fingerprint()
    f2 = telemetry.instance_fingerprint()
    assert f1 == f2
    assert len(f1) == 16
    # not the raw id
    assert telemetry.instance_id() not in f1


def test_reset_clears_events():
    telemetry.record("a")
    telemetry.record("b")
    assert telemetry.summary()["event_count"] == 2
    removed = telemetry.reset()
    assert removed >= 2
    assert telemetry.summary()["event_count"] == 0


def test_middleware_counts_requests(monkeypatch):
    from fastapi.testclient import TestClient
    import scripts.web.server as server

    client = TestClient(server.app)
    for _ in range(3):
        assert client.get("/api/health").status_code == 200
    s = telemetry.summary()
    assert s["totals_by_event"].get("http_request", {}).get("count", 0) >= 3
    # static/probe paths are skipped, health is counted by template
    assert any("/api/health" in r for r in s["top_routes"])
