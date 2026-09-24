"""Tests — Multi-Tenant Isolation (Task 4.2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import tenancy  # noqa: E402


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    """Isolated working dir + clean tenancy env/caches for every test."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WIDDX_TENANT_MODE", raising=False)
    monkeypatch.delenv("WIDDX_TENANT_KEYS", raising=False)
    tenancy.reset_keymap_cache()
    tenancy.reset_cache()
    yield
    tenancy.reset_keymap_cache()
    tenancy.reset_cache()


# ── sanitize_tenant_id ──────────────────────────────────────

def test_sanitize_valid_ids():
    assert tenancy.sanitize_tenant_id("Acme") == "acme"
    assert tenancy.sanitize_tenant_id("team-1_x") == "team-1_x"


@pytest.mark.parametrize("bad", ["", None, "../evil", "a/b", "-lead", "x" * 65,
                                 "sp ace", "dot.dot", "شركة"])
def test_sanitize_rejects_unsafe(bad):
    assert tenancy.sanitize_tenant_id(bad) is None


# ── mode handling ───────────────────────────────────────────

def test_default_mode_is_off(monkeypatch):
    assert tenancy.get_mode() == tenancy.MODE_OFF
    assert not tenancy.is_enabled()
    assert tenancy.resolve_tenant_id() == tenancy.DEFAULT_TENANT


def test_keymap_mode_requires_keys(monkeypatch):
    monkeypatch.setenv("WIDDX_TENANT_MODE", "keymap")
    # no WIDDX_TENANT_KEYS → falls back to off
    assert tenancy.get_mode() == tenancy.MODE_OFF


def test_keymap_resolution(monkeypatch):
    monkeypatch.setenv("WIDDX_TENANT_MODE", "keymap")
    monkeypatch.setenv("WIDDX_TENANT_KEYS", "acme:key-a, globex:key-g")
    tenancy.reset_keymap_cache()
    assert tenancy.get_mode() == tenancy.MODE_KEYMAP
    assert tenancy.resolve_tenant_id(bearer_key="key-a") == "acme"
    assert tenancy.resolve_tenant_id(bearer_key="key-g") == "globex"
    # unknown key → default tenant (no data leak, no crash)
    assert tenancy.resolve_tenant_id(bearer_key="nope") == tenancy.DEFAULT_TENANT
    assert tenancy.resolve_tenant_id() == tenancy.DEFAULT_TENANT


def test_header_resolution(monkeypatch):
    monkeypatch.setenv("WIDDX_TENANT_MODE", "header")
    assert tenancy.resolve_tenant_id(header_value="Acme") == "acme"
    # invalid header falls back to default — path traversal blocked
    assert tenancy.resolve_tenant_id(header_value="../etc") == tenancy.DEFAULT_TENANT
    assert tenancy.resolve_tenant_id() == tenancy.DEFAULT_TENANT


# ── physical isolation ──────────────────────────────────────

def test_per_tenant_db_files_are_distinct():
    db_a = tenancy.get_tenant_db("acme")
    db_b = tenancy.get_tenant_db("globex")
    assert str(db_a.db_path) != str(db_b.db_path)
    assert "tenants/acme" in str(db_a.db_path).replace("\\", "/")
    assert "tenants/globex" in str(db_b.db_path).replace("\\", "/")


def test_data_isolation_between_tenants():
    db_a = tenancy.get_tenant_db("acme")
    db_b = tenancy.get_tenant_db("globex")

    sid_a = db_a.create_session("acme secret")
    db_a.add_message(sid_a, "user", "classified")
    db_a.add_memory("acme note", "private knowledge")

    sid_b = db_b.create_session("globex session")
    db_b.add_message(sid_b, "user", "globex data")

    # Globex cannot see Acme's data
    names_b = [s["name"] for s in db_b.list_sessions(limit=100)]
    assert names_b == ["globex session"]
    assert db_b.get_session(sid_a) is None
    assert all("private knowledge" not in m["content"]
               for m in db_b.list_memories(limit=100))

    # Acme cannot see Globex's data
    names_a = [s["name"] for s in db_a.list_sessions(limit=100)]
    assert names_a == ["acme secret"]
    assert db_a.get_session(sid_b) is None


def test_list_tenants_reports_stats():
    db_a = tenancy.get_tenant_db("acme")
    db_a.create_session("s1")
    tenants = {t["tenant_id"]: t for t in tenancy.list_tenants()}
    assert "acme" in tenants
    assert tenants["acme"]["sessions"] == 1
    assert tenants["acme"]["db_size_bytes"] > 0


def test_describe_shape(monkeypatch):
    monkeypatch.setenv("WIDDX_TENANT_MODE", "keymap")
    monkeypatch.setenv("WIDDX_TENANT_KEYS", "acme:k1,globex:k2")
    tenancy.reset_keymap_cache()
    info = tenancy.describe()
    assert info["enabled"] is True
    assert info["mode"] == "keymap"
    assert set(info["configured_tenants"]) == {"acme", "globex"}


# ── HTTP-level isolation via the web server ─────────────────

def test_http_cross_tenant_invisible(monkeypatch):
    monkeypatch.setenv("WIDDX_TENANT_MODE", "keymap")
    monkeypatch.setenv("WIDDX_TENANT_KEYS", "acme:key-a,globex:key-g")
    tenancy.reset_keymap_cache()
    tenancy.reset_cache()

    from fastapi.testclient import TestClient
    import scripts.web.server as server

    client = TestClient(server.app)
    A = {"Authorization": "Bearer key-a"}
    G = {"Authorization": "Bearer key-g"}

    assert client.get("/api/tenant", headers=A).json()["tenant"] == "acme"

    saved = client.post(
        "/api/sessions",
        json={"name": "acme-only", "messages": [{"role": "user", "content": "secret"}]},
        headers=A,
    ).json()
    sid = saved["id"]
    client.post("/api/memories", json={"content": "acme memory", "tags": "x"}, headers=A)

    # Globex: sees nothing of Acme's
    assert client.get("/api/sessions", headers=G).json() == []
    assert client.get("/api/memories/search", headers=G).json() == []
    assert "error" in client.get(f"/api/sessions/{sid}", headers=G).json()

    # Acme: sees its own
    sessions = client.get("/api/sessions", headers=A).json()
    assert [s["name"] for s in sessions] == ["acme-only"]

    # Response carries the resolved tenant
    assert client.get("/api/tenant", headers=A).headers["x-tenant-id"] == "acme"
