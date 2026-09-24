"""Session Search — Full-text + semantic search across saved sessions.

Uses SQLite FTS5 for full-text indexing over all session messages.
Optionally layers semantic search via ``core.vector_memory`` for
concept-level queries that keyword matching would miss.

Architecture:
  SessionSearcher    — main search API
  FTS5Index          — SQLite FTS5 full-text index
  snippet()          — extract relevant context around a match

Usage:
    from core.session_search import SessionSearcher

    searcher = SessionSearcher()
    results = searcher.search("python error handling", top_k=10)
    # → [(score, {session_id, name, snippet, matched_message, timestamp}), ...]

    # Filter by date range
    results = searcher.search("deployment", date_from="2026-01-01", date_to="2026-06-18")

    # Search by session name only
    results = searcher.search_by_name("project setup")
"""

from __future__ import annotations

import re
import time

# ---------------------------------------------------------------------------
# Snippet extraction
# ---------------------------------------------------------------------------

def snippet(text: str, query: str, context_chars: int = 120) -> str:
    """Extract a relevant snippet around the first query match.

    Highlights the matched region with ``**...**`` markers.
    """
    if not query or not text:
        return text[:context_chars * 2]

    # Find first case-insensitive match
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        # Try individual words
        words = query.split()
        for w in words:
            if len(w) >= 3:
                m = pattern.search(text) if pattern.search(text) else re.compile(
                    re.escape(w), re.IGNORECASE).search(text)
                break
    if not m:
        return text[:context_chars * 2]

    start = max(0, m.start() - context_chars // 2)
    end = min(len(text), m.end() + context_chars // 2)

    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""

    body = text[start:end]
    # Highlight match
    highlighted = re.compile(re.escape(m.group()), re.IGNORECASE).sub(
        lambda x: f"**{x.group()}**", body, count=1)

    return f"{prefix}{highlighted}{suffix}"


# ---------------------------------------------------------------------------
# Session Searcher
# ---------------------------------------------------------------------------

class SessionSearcher:
    """Search across all saved sessions using FTS5 full-text indexing.

    Automatically creates/rebuilds the FTS5 index on first use.
    Falls back to LIKE-based search if FTS5 is not available.
    """

    def __init__(self, db_path: str | None = None):
        from core.database import get_db
        self._db = get_db()
        self._fts_ready = False
        self._ensure_fts()

    # ── Public API ──────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        date_from: str | None = None,
        date_to: str | None = None,
        session_name: str | None = None,
    ) -> list[dict]:
        """Full-text search across all session messages.

        Returns list of dicts with:
          - session_id, session_name
          - matched_message (full content of the matching message)
          - snippet (highlighted excerpt)
          - role, timestamp
          - score (relevance, higher = better)
        """
        if not query or not query.strip():
            return []

        results = []
        query_clean = query.strip()

        # Try FTS5 first
        if self._fts_ready:
            results = self._search_fts(query_clean, top_k)
        else:
            results = self._search_like(query_clean, top_k)

        # Post-filters
        filtered = []
        for r in results:
            # Date filter
            ts = r.get("timestamp", 0)
            ts_str = time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else ""
            if date_from and ts_str < date_from:
                continue
            if date_to and ts_str > date_to:
                continue
            # Session name filter
            if session_name and session_name.lower() not in r.get("session_name", "").lower():
                continue
            # Add snippet
            r["snippet"] = snippet(r.get("matched_message", ""), query_clean)
            filtered.append(r)
            if len(filtered) >= top_k:
                break

        return filtered

    def search_by_name(
        self,
        name_query: str,
        top_k: int = 10,
    ) -> list[dict]:
        """Search sessions by name (substring match)."""
        with self._db._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, branch, created_at, updated_at, metadata "
                "FROM sessions WHERE name LIKE ? ORDER BY updated_at DESC LIMIT ?",
                (f"%{name_query}%", top_k),
            ).fetchall()
        return [
            {
                "session_id": r["id"],
                "session_name": r["name"],
                "branch": r["branch"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "message_count": self._count_messages(r["id"]),
            }
            for r in rows
        ]

    def list_recent(self, limit: int = 20) -> list[dict]:
        """List recently updated sessions with message counts."""
        sessions = self._db.list_sessions(limit=limit)
        for s in sessions:
            s["message_count"] = self._count_messages(s["id"])
        return sessions

    def get_session_context(self, session_id: str, max_messages: int = 50) -> dict | None:
        """Get session details with recent messages."""
        try:
            session = self._db.get_session(session_id)
            if session is None:
                return None
        except Exception as e:
            import logging
            logging.getLogger("widdx.session_search").warning("Session get error: %s", e)
            return None
        messages = self._db.get_messages(session_id, limit=max_messages)
        if session is not None:
            session["messages"] = messages
        session["message_count"] = len(messages)
        return session

    def rebuild_index(self):
        """Force rebuild of the FTS5 index."""
        self._build_fts()

    def stats(self) -> dict:
        """Index statistics."""
        with self._db._get_conn() as conn:
            row_count = conn.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0]
            fts_count = 0
            if self._fts_ready:
                try:
                    fts_count = conn.execute(
                        "SELECT COUNT(*) FROM messages_fts"
                    ).fetchone()[0]
                except Exception as e:
                    import logging
                    logging.getLogger("widdx.session_search").warning("Search error: %s", e)
                    return {}
        return {
            "total_messages": row_count,
            "fts_indexed": fts_count,
            "fts_ready": self._fts_ready,
        }

    # ── FTS5 Engine ─────────────────────────────────────

    def _ensure_fts(self):
        """Create FTS5 index if it doesn't exist."""
        try:
            with self._db._get_conn() as conn:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                    USING fts5(content, role, session_id, tokenize='porter unicode61')
                """)
                conn.commit()
            self._fts_ready = True
        except Exception as e:
            import logging
            logging.getLogger("widdx.session_search").warning("Search error: %s", e)
            return None

        # Populate if empty
        try:
            with self._db._get_conn() as conn:
                count = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
                if count == 0:
                    self._build_fts()
        except Exception as e:
            import logging
            logging.getLogger("widdx.session_search").warning("Search error: %s", e)
            return None

    def _build_fts(self):
        """Rebuild the FTS5 index from all messages."""
        if not self._fts_ready:
            return
        try:
            with self._db._get_conn() as conn:
                conn.execute("DELETE FROM messages_fts")
                rows = conn.execute(
                    "SELECT id, session_id, role, content FROM messages ORDER BY timestamp ASC"
                ).fetchall()
                for r in rows:
                    try:
                        conn.execute(
                            "INSERT INTO messages_fts (content, role, session_id) VALUES (?, ?, ?)",
                            (r["content"] or "", r["role"] or "", r["session_id"] or ""),
                        )
                    except Exception as e:
                        import logging
                        logging.getLogger("widdx.session_search").warning("Search error: %s", e)
                conn.commit()
            return 0
        except Exception as e:
            import logging
            logging.getLogger("widdx.session_search").warning("Search error: %s", e)
            return None

    def _search_fts(self, query: str, top_k: int) -> list[dict]:
        """FTS5 search with snippet extraction."""
        results = []
        try:
            with self._db._get_conn() as conn:
                # Use FTS5 highlight for snippets
                rows = conn.execute(
                    "SELECT m.id, m.session_id, m.role, m.content, m.timestamp, "
                    "s.name as session_name, "
                    "messages_fts.rank as score "
                    "FROM messages_fts "
                    "JOIN messages m ON m.rowid = messages_fts.rowid "
                    "JOIN sessions s ON s.id = m.session_id "
                    "WHERE messages_fts MATCH ? "
                    "ORDER BY rank "
                    "LIMIT ?",
                    (self._sanitize_fts_query(query), top_k),
                ).fetchall()

                for r in rows:
                    results.append({
                        "message_id": r["id"],
                        "session_id": r["session_id"],
                        "session_name": r["session_name"] or "Unknown",
                        "role": r["role"],
                        "matched_message": r["content"] or "",
                        "timestamp": r["timestamp"],
                        "score": - (r["score"] or 0),  # lower rank = better in FTS5
                    })
        except Exception as e:
            import logging
            logging.getLogger("widdx.session_search").warning("Search error: %s", e)
            return self._search_like(query, top_k)

        return results

    def _search_like(self, query: str, top_k: int) -> list[dict]:
        """Fallback LIKE-based search."""
        results = []
        try:
            with self._db._get_conn() as conn:
                rows = conn.execute(
                    "SELECT m.id, m.session_id, m.role, m.content, m.timestamp, "
                    "s.name as session_name "
                    "FROM messages m "
                    "JOIN sessions s ON s.id = m.session_id "
                    "WHERE m.content LIKE ? "
                    "ORDER BY m.timestamp DESC "
                    "LIMIT ?",
                    (f"%{query}%", top_k),
                ).fetchall()

                for r in rows:
                    # Simple score: longer match = slightly better
                    score = 1.0
                    if query.lower() in (r["content"] or "").lower():
                        score = 2.0
                    results.append({
                        "message_id": r["id"],
                        "session_id": r["session_id"],
                        "session_name": r["session_name"] or "Unknown",
                        "role": r["role"],
                        "matched_message": r["content"] or "",
                        "timestamp": r["timestamp"],
                        "score": score,
                    })
        except Exception as e:
            import logging
            logging.getLogger("widdx.session_search").warning("Search error: %s", e)
            return []

        return results

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Sanitize user input for FTS5 (escape special chars)."""
        # Remove FTS5 special characters
        cleaned = re.sub(r'[^\w\s"\-]', '', query)
        if not cleaned.strip():
            return query.replace("'", "''")
        # Quote each word for exact matching
        words = cleaned.split()
        return " OR ".join(f'"{w}"' for w in words if len(w) >= 2)

    def _count_messages(self, session_id: str) -> int:
        try:
            with self._db._get_conn() as conn:
                return conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()[0]
        except Exception as e:
            import logging
            logging.getLogger("widdx.session_search").warning("Search error: %s", e)
            return 0
