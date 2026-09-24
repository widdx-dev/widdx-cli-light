"""Tests — Admin Dashboard (Task 4.3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
import scripts.web.server as server  # noqa: E402

client = TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WIDDX_ADMIN_KEY", raising=False)
    yield


def test_disabled_when_no_key():
    r = client.get("/admin/api/overview")
    assert r.status_code == 403
    assert "disabled" in r.json()["error"].lower()
    status = client.get("/admin/api/status").json()
    assert status["enabled"] is False


def test_page_served_without_key():
    r = client.get("/admin/")
    assert r.status_code == 200
    assert "<title>" in r.text


def test_wrong_key_rejected(monkeypatch):
    monkeypatch.setenv("WIDDX_ADMIN_KEY", "correct-key")
    r = client.get("/admin/api/overview", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 401


def test_overview_with_valid_key(monkeypatch):
    monkeypatch.setenv("WIDDX_ADMIN_KEY", "correct-key")
    r = client.get("/admin/api/overview", headers={"X-Admin-Key": "correct-key"})
    assert r.status_code == 200
    data = r.json()
    assert data["app"]["name"] == "WIDDX Nexus"
    assert "uptime_seconds" in data["app"]
    assert data["features"]["admin_dashboard"] is True
    assert set(data["data"]) >= {"sessions", "messages", "memories"}


def test_bearer_auth_accepted(monkeypatch):
    monkeypatch.setenv("WIDDX_ADMIN_KEY", "correct-key")
    r = client.get("/admin/api/overview",
                   headers={"Authorization": "Bearer correct-key"})
    assert r.status_code == 200


def test_tenants_and_telemetry_endpoints(monkeypatch):
    monkeypatch.setenv("WIDDX_ADMIN_KEY", "correct-key")
    h = {"X-Admin-Key": "correct-key"}
    tenants = client.get("/admin/api/tenants", headers=h).json()
    assert "tenants" in tenants and "config" in tenants
    tel = client.get("/admin/api/telemetry", headers=h).json()
    assert "event_count" in tel
    reset = client.post("/admin/api/telemetry/reset", headers=h).json()
    assert reset["status"] == "ok"
