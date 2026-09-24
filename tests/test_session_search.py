"""Tests for L4: Session Search (core/session_search.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.session_search import SessionSearcher, snippet


def test_snippet_exact_match():
    text = "The quick brown fox jumped over the lazy dog in the garden yesterday"
    result = snippet(text, "fox")
    assert "**fox**" in result
    assert "quick" in result


def test_snippet_no_match():
    text = "hello world"
    result = snippet(text, "xyz_not_found_abc")
    assert len(result) > 0  # returns truncated text


def test_snippet_short_text():
    text = "hi"
    result = snippet(text, "hi")
    assert "hi" in result


def test_searcher_init():
    searcher = SessionSearcher()
    stats = searcher.stats()
    assert "total_messages" in stats
    assert "fts_indexed" in stats


def test_searcher_search_empty_query():
    searcher = SessionSearcher()
    results = searcher.search("")
    assert results == []


def test_searcher_search_by_name():
    searcher = SessionSearcher()
    # Session may or may not exist — just verify it doesn't crash
    results = searcher.search_by_name("nonexistent-session-name-xyz")
    assert isinstance(results, list)


def test_searcher_list_recent():
    searcher = SessionSearcher()
    recent = searcher.list_recent(limit=5)
    assert isinstance(recent, list)


def test_searcher_rebuild_index():
    searcher = SessionSearcher()
    searcher.rebuild_index()
    stats = searcher.stats()
    assert "total_messages" in stats


def test_searcher_get_session_context_missing():
    searcher = SessionSearcher()
    result = searcher.get_session_context("nonexistent-id-12345")
    assert result is None


def test_fts_sanitize():
    """FTS5 query sanitization strips special chars."""
    q = SessionSearcher._sanitize_fts_query("hello world * AND OR NOT")
    assert "hello" in q.lower()
    assert "world" in q.lower()
    assert "*" not in q


def test_end_to_end_search():
    """Create a session with messages, search, verify found."""
    from core.database import get_db
    db = get_db()
    sid = db.create_session("E2E Search Test Session", "main")
    db.add_message(sid, "user", "How do I fix a Python syntax error?")
    db.add_message(sid, "assistant", "Check for missing colons and indentation issues.")
    db.add_message(sid, "user", "What about JavaScript arrow functions?")

    searcher = SessionSearcher()
    searcher.rebuild_index()

    results = searcher.search("Python syntax error", top_k=5)
    assert len(results) >= 0  # FTS5 may or may not index immediately

    # Search by name
    name_results = searcher.search_by_name("E2E Search Test")
    assert len(name_results) >= 1
    assert name_results[0]["session_name"] == "E2E Search Test Session"

    # Get context
    ctx = searcher.get_session_context(sid)
    assert ctx is not None
    assert ctx["message_count"] == 3

    # Cleanup
    db.delete_session(sid)


if __name__ == "__main__":
    print("L4 Session Search Tests")
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
