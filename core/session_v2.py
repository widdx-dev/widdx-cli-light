
"""
Session V2 - Durable Session Management
Inspired by OpenCode's Session Architecture
"""

from __future__ import annotations
from pathlib import Path
from typing import Any

from .database import get_db


class SessionV2:
    def __init__(self, session_id: str | None = None, name: str = "New Session",
                 branch: str = "main", db: Any = None):
        self.db = db if db is not None else get_db()
        if session_id:
            existing = self.db.get_session(session_id)
            if existing:
                self.id = existing["id"]
                self.name = existing["name"]
                self.branch = existing["branch"]
                self.metadata = existing["metadata"]
                self._messages = self.db.get_messages(session_id)
                return
        self.id = self.db.create_session(name, branch)
        self.name = name
        self.branch = branch
        self.metadata = {}
        self._messages = []
    
    @property
    def messages(self) -> list[dict]:
        return self._messages.copy()

    def add_message(self, role: str, content: str, tool_calls: Any = None) -> str:
        msg_id = self.db.add_message(self.id, role, content, tool_calls)
        self._messages = self.db.get_messages(self.id)
        return msg_id

    def clear(self) -> None:
        self.db.clear_messages(self.id)
        self._messages = []

    def rename(self, new_name: str) -> None:
        self.name = new_name
        self.db.update_session(self.id, name=new_name)

    def switch_branch(self, new_branch: str) -> None:
        self.branch = new_branch
        self.db.update_session(self.id, branch=new_branch)

    def get_context(self, max_tokens: int = 8000, max_messages: int | None = None) -> list[dict]:
        messages = self._messages.copy()
        if max_messages:
            if len(messages) > max_messages:
                messages = messages[-max_messages:]
        
        total_chars = 0
        trimmed = []
        system_msgs = [m for m in messages if m["role"] == "system"]
        other_msgs = [m for m in messages if m["role"] != "system"]
        
        trimmed.extend(system_msgs)
        total_chars += sum(len(m["content"]) for m in system_msgs)
        
        for msg in reversed(other_msgs):
            msg_chars = len(msg["content"])
            if total_chars + msg_chars > max_tokens * 4:
                break
            trimmed.insert(len(system_msgs), msg)
            total_chars += msg_chars
        
        return trimmed
    
    @staticmethod
    def list_sessions(branch: str | None = None, limit: int = 50) -> list[dict]:
        db = get_db()
        return db.list_sessions(branch, limit)

    @staticmethod
    def delete(session_id: str) -> None:
        db = get_db()
        db.delete_session(session_id)
    
    def save(self, state: dict | None = None):
        """Persist session metadata and optional state to SQLite.

        Messages are already persisted in real time via ``add_message()``.
        This method syncs everything else: metadata, timestamps, and
        arbitrary state (cost, turns, model, etc.).

        ``update_session`` (database.py:136) automatically bumps
        ``updated_at`` when any field is passed.
        """
        if state:
            merged = dict(self.metadata)
            merged.update(state)
            self.metadata = merged

        self.db.update_session(self.id, metadata=self.metadata)

    def create_checkpoint(self, label: str = "") -> str:
        """Create a file-based project checkpoint (safe snapshot before edits)."""
        from core.checkpoint import CheckpointManager
        cpm = CheckpointManager(Path.cwd())
        cid = cpm.save(label or f"session_{self.id}")
        return cid or ""

    @staticmethod
    def search(query: str, branch: str | None = None, limit: int = 20) -> list[dict]:
        """Full-text search across sessions."""
        from core.session_search import SessionSearcher
        searcher = SessionSearcher()
        results = searcher.search(query, top_k=limit)
        if not branch:
            return results
        db = get_db()
        filtered = []
        for r in results:
            sess = db.get_session(r.get("session_id", ""))
            if sess and sess.get("branch") == branch:
                filtered.append(r)
        return filtered

    @staticmethod
    def save_with_messages(name: str, messages: list[dict]) -> str:
        """Create a new session, persist all messages, and return the session ID.

        This is a convenience wrapper used by the Web UI (Dashboard) for
        batch session persistence. Messages are saved in order — each
        dict must contain at least ``role`` and ``content`` keys, and
        may optionally contain a ``tool_calls`` key.

        Args:
            name: Human-readable session name.
            messages: List of message dicts with role, content [, tool_calls].

        Returns:
            The newly created session ID.
        """
        db = get_db()
        session_id = db.create_session(name)
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
            db.add_message(session_id, role, content, tool_calls)
        return session_id

    @staticmethod
    def load_as_dict(session_id: str) -> dict | None:
        """Load a session and its messages as a plain dict (Web UI format).

        The returned dict uses millisecond timestamps for JavaScript
        compatibility, mirroring the ``SessionDB.load()`` contract.

        Args:
            session_id: The session ID to load.

        Returns:
            Dict with keys ``id``, ``name``, ``branch``, ``created`` (ms),
            ``messages`` or ``None`` if the session does not exist.
        """
        db = get_db()
        session = db.get_session(session_id)
        if not session:
            return None
        messages = db.get_messages(session_id)
        return {
            "id": session["id"],
            "name": session["name"],
            "branch": session["branch"],
            "created": session["created_at"] * 1000,  # ms for JavaScript
            "messages": [
                {
                    "role": m["role"],
                    "content": m["content"],
                    "tool_calls": m["tool_calls"],
                    "timestamp": m["timestamp"],
                }
                for m in messages
            ]
        }


_current_session: SessionV2 | None = None


def get_current_session() -> SessionV2 | None:
    return _current_session


def set_current_session(session: SessionV2) -> None:
    global _current_session
    _current_session = session


def create_new_session(name: str = "New Session", branch: str = "main",
                       db: Any = None) -> SessionV2:
    session = SessionV2(name=name, branch=branch, db=db)
    set_current_session(session)
    return session


def load_session(session_id: str) -> SessionV2:
    session = SessionV2(session_id=session_id)
    if session:
        set_current_session(session)
    return session
