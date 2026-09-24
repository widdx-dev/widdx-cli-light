"""Tests for Architecture Decision Records."""
import tempfile
import shutil
from core.adr import ADRManager


def test_adr_record_and_search():
    tmp = tempfile.mkdtemp()
    try:
        m = ADRManager(tmp)
        adr_id = m.record(
            "Use SQLite",
            "Need persistence",
            "SQLite chosen",
            ["Redis", "Postgres"],
            "Single-writer limitation",
        )
        assert adr_id.startswith("ADR-"), f"Expected ADR-xxx, got {adr_id}"

        results = m.search("SQLite")
        assert len(results) >= 1, "Should find the ADR"
        assert results[0]["id"] == adr_id

        context = m.get_context_for_prompt()
        assert "SQLite" in context
    finally:
        shutil.rmtree(tmp)


def test_adr_context_includes_rejected():
    tmp = tempfile.mkdtemp()
    try:
        m = ADRManager(tmp)
        m.record("Pick cache", "Need caching", "Redis", ["Memcached", "None"])
        context = m.get_context_for_prompt()
        assert "Rejected:" in context or "Memcached" in context
    finally:
        shutil.rmtree(tmp)


def test_adr_list_all():
    tmp = tempfile.mkdtemp()
    try:
        m = ADRManager(tmp)
        m.record("A", "ctx", "dec")
        m.record("B", "ctx", "dec")
        assert len(m.list_all()) >= 2
    finally:
        shutil.rmtree(tmp)
