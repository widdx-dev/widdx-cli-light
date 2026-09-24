"""Dashboard mixin — storage."""
from __future__ import annotations
import logging

logger = logging.getLogger("widdx.web.dashboard")

import datetime  # noqa: E402


class StorageMixin:
    def memories(self) -> list[dict]:
        try:
            from core.memory import MemoryStore
            mem = MemoryStore()
            return mem.list_all()
        except Exception:
            return []

    # ── Sessions ──


    def sessions(self) -> list[dict]:
        try:
            from core.session_search import SessionSearcher
            searcher = SessionSearcher()
            return searcher.list_recent(limit=20)
        except Exception:
            return []

    # ── Activity Feed ──


    def sessions_search(self, query: str) -> list[dict]:
        try:
            from core.session_search import SessionSearcher
            searcher = SessionSearcher()
            return searcher.search(query)
        except Exception:
            return []

    def activity_feed(self, limit: int = 50) -> list[dict]:
        """Return recent activity events from the central ActivityStore."""
        try:
            from core.activity import get_store
            store = get_store()
            events = store.get_recent(limit=limit)
            if events:
                return events
        except Exception:
            pass
        return self._emergency_activity()


    def _emergency_activity(self) -> list[dict]:
        """Last resort — return placeholder events."""
        now = datetime.datetime.utcnow().isoformat()
        return [
            {"id": "welcome", "type": "message", "icon": "fa-star", "agent": "system",
             "detail": "WIDDX Nexus Mission Control active", "status": "done",
             "timestamp": now, "elapsed": "—"},
        ]

    @staticmethod

    def _get_activity_store():
        """Return the global ActivityStore."""
        from core.activity import get_store
        return get_store()

    # ── Skills ──


    def skills(self) -> list[dict]:
        try:
            from core.skills import skill_manager
            return [
                {"name": s.name, "description": s.description[:80]}
                for s in skill_manager.list_all()
            ]
        except Exception:
            return []

    # ── Gateway Status ──


    def memory_create(self, content: str, tags: str = "") -> dict:
        """Add a new memory entry."""
        try:
            from core.memory import MemoryStore
            mem = MemoryStore()
            name = tags.split(",")[0].strip() if tags else f"note-{hash(content) % 10000}"
            mem.save(name, content, metadata={"tags": [t.strip() for t in tags.split(",") if t.strip()]})
            return {"status": "ok", "message": "Memory added"}
        except Exception as e:
            return {"error": str(e)}


    def memory_delete(self, memory_id: str) -> dict:
        """Delete a memory entry."""
        try:
            from core.memory import MemoryStore
            mem = MemoryStore()
            mem.delete(memory_id)
            return {"status": "deleted"}
        except Exception as e:
            return {"error": str(e)}


    def memory_search(self, query: str) -> list[dict]:
        """Search memory entries."""
        try:
            from core.memory import MemoryStore
            mem = MemoryStore()
            return mem.search(query)
        except Exception:
            return []

    # ════════════════════════════════════════════════════════
    # NEW: Session Save / Load / Export
    # ════════════════════════════════════════════════════════


    def session_save(self, name: str, messages: list) -> dict:
        """Save current session with a name."""
        try:
            from core.database import SessionDB
            db = SessionDB()
            session_id = db.save(name, messages)
            return {"id": session_id, "status": "saved"}
        except Exception as e:
            return {"error": str(e)}


    def session_load(self, session_id: str) -> dict:
        """Load a saved session."""
        try:
            from core.database import SessionDB
            db = SessionDB()
            session = db.load(session_id)
            if session:
                return {"status": "ok", "session": session}
            return {"error": "Session not found"}
        except Exception as e:
            return {"error": str(e)}


    def session_delete(self, session_id: str) -> dict:
        """Delete a saved session."""
        try:
            from core.database import SessionDB
            db = SessionDB()
            db.delete(session_id)
            return {"status": "deleted"}
        except Exception as e:
            return {"error": str(e)}


    def session_export(self, session_id: str) -> dict:
        """Export session as markdown."""
        try:
            from core.database import SessionDB
            db = SessionDB()
            session = db.load(session_id)
            if not session:
                return {"error": "Session not found"}
            lines = [f"# Chat: {session.get('name', 'Untitled')}", ""]
            for msg in session.get("messages", []):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                lines.append(f"## {role.upper()}")
                lines.append(content)
                lines.append("")
            return {"status": "ok", "markdown": "\n".join(lines)}
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: MCP Management
    # ════════════════════════════════════════════════════════


