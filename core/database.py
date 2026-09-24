
"""Durable Session Database for WIDDX

SQLite-based persistent storage for sessions, memories, and history
with connection pooling for production workloads.
"""

import sqlite3
import json
import uuid
import logging
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("widdx.database")


def get_db_path(project_dir: str | Path | None = None) -> Path:
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)
    widdx_dir = project_dir / ".widdx"
    widdx_dir.mkdir(exist_ok=True)
    return widdx_dir / "widdx.db"


# ── Connection Pool ─────────────────────────────────────────
# Thread-safe SQLite connection pool for production use.
# Reuses connections instead of opening/closing per request.

class ConnectionPool:
    """Simple thread-safe SQLite connection pool.

    Maintains up to ``max_connections`` open connections.
    Connections are returned to the pool after use.
    If the pool is exhausted, callers block up to ``timeout`` seconds.
    """

    def __init__(self, db_path: str | Path, max_connections: int = 5,
                 timeout: float = 5.0):
        self.db_path = str(db_path)
        self.max_connections = max_connections
        self.timeout = timeout
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue(max_connections)
        self._active_count = 0
        self._lock = threading.Lock()
        self._closed = False
        self._logger = logging.getLogger("widdx.db.pool")

    def acquire(self) -> sqlite3.Connection:
        """Get a connection from the pool (or create one if available)."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        # First, try to get an existing connection from the pool immediately
        try:
            conn = self._pool.get(block=False)
            try:
                conn.execute("SELECT 1")
                return conn
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                self._logger.debug("Recreating stale database connection")
                # Stale connection - will create new one below
        except queue.Empty:
            pass

        # Create new connection if under limit
        with self._lock:
            if self._active_count < self.max_connections:
                self._active_count += 1
            else:
                # Pool exhausted — wait for a connection to be released
                try:
                    conn = self._pool.get(block=True, timeout=self.timeout)
                    try:
                        conn.execute("SELECT 1")
                        return conn
                    except (sqlite3.OperationalError, sqlite3.DatabaseError):
                        self._logger.debug("Recreating stale database connection from wait")
                        # Stale connection - will create new one below
                except queue.Empty:
                    pass

        conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def release(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        if self._closed:
            try:
                conn.close()
            except Exception:
                logger.debug("Exception suppressed (line 99)")
            return
        try:
            self._pool.put(conn, block=False)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                logger.debug("Exception suppressed (line 107)")

    def close_all(self):
        """Close all connections in the pool."""
        self._closed = True
        while not self._pool.empty():
            try:
                conn = self._pool.get(block=False)
                conn.close()
            except (queue.Empty, Exception):
                break
        with self._lock:
            self._active_count = 0


# ── Global pool registry ────────────────────────────────────
# One pool per database file path so that multi-tenant setups
# (separate DB file per tenant) never share connections.
_pools: dict[str, ConnectionPool] = {}
_pool_lock = threading.Lock()


def get_pool(db_path: str | Path | None = None) -> ConnectionPool:
    """Get or create the connection pool for a specific database file."""
    path = str(db_path or get_db_path())
    pool = _pools.get(path)
    if pool is None:
        with _pool_lock:
            pool = _pools.get(path)
            if pool is None:
                pool = ConnectionPool(path, max_connections=5)
                _pools[path] = pool
    return pool


def close_all_pools() -> None:
    """Close every registered connection pool (used on shutdown/tests)."""
    with _pool_lock:
        for pool in _pools.values():
            try:
                pool.close_all()
            except Exception:
                logger.debug("Exception suppressed (line 149)")
        _pools.clear()


class Database:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = get_db_path()
        self.db_path = db_path
        self._pool = get_pool(db_path)
        self._init_db()

    def _get_conn(self):
        """Get a connection from the pool.
        
        Returns a context manager that releases the connection
        back to the pool when the context is exited.
        """
        return _PoolConnection(self._pool.acquire(), self._pool)

    def _return_conn(self, conn):
        """Return a connection to the pool."""
        self._pool.release(conn)


    # Schema version that the current code expects.
    # Increment this when you add a new migration to _MIGRATIONS.
    CURRENT_SCHEMA_VERSION = 1

    _MIGRATIONS: list[tuple[int, str]] = [
        # (version, sql_statement) — applied in order when version > current
        (1, """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                branch TEXT DEFAULT 'main',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """),
        (1, """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """),
        (1, """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                content TEXT NOT NULL,
                memory_type TEXT DEFAULT 'general',
                tags TEXT DEFAULT '[]',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """),
        (1, """
            CREATE TABLE IF NOT EXISTS provider_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_response_time REAL DEFAULT 0,
                last_used INTEGER,
                UNIQUE(provider_name, model_name)
            )
        """),
    ]

    _INDEX_MIGRATIONS: list[tuple[int, str]] = [
        (1, "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)"),
        (1, "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC)"),
        (1, "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)"),
        (1, "CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC)"),
    ]

    def _init_db(self):
        """Initialise the database and run any pending migrations."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at INTEGER NOT NULL
                )
            """)
            self._migrate(conn)
            conn.commit()

    def _migrate(self, conn):
        """Run pending migrations in version order."""
        current = self._get_schema_version(conn)

        # Collect all migration steps (table + index) and sort by version
        all_steps: list[tuple[int, str]] = []
        for v, sql in self._MIGRATIONS:
            if v > current:
                all_steps.append((v, sql))
        for v, sql in self._INDEX_MIGRATIONS:
            if v > current:
                all_steps.append((v, sql))
        all_steps.sort(key=lambda x: x[0])

        if not all_steps:
            return

        logger = logging.getLogger("widdx.db")
        max_v = current
        for v, sql in all_steps:
            try:
                conn.execute(sql)
                if v > max_v:
                    max_v = v
            except Exception as e:
                logger.warning("Migration v%d failed: %s", v, e)
                raise

        # Record the highest version applied
        if max_v > current:
            now = int(datetime.now().timestamp())
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                (max_v, now),
            )
            logger.info("Database migrated to schema v%d", max_v)

    def _get_schema_version(self, conn) -> int:
        """Return the current schema version, or 0 if never migrated."""
        try:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            return row[0] if row and row[0] is not None else 0
        except Exception:
            return 0
    
    def create_session(self, name: str, branch: str = "main", metadata: dict | None = None) -> str:
        session_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp())
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, name, branch, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, name, branch, now, now, json.dumps(metadata or {}))
            )
            conn.commit()
        return session_id
    
    def get_session(self, session_id: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "branch": row["branch"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": json.loads(row["metadata"])
                }
        return None
    
    def list_sessions(self, branch: str | None = None, limit: int = 50) -> list[dict]:
        with self._get_conn() as conn:
            if branch:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE branch = ? ORDER BY updated_at DESC LIMIT ?",
                    (branch, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "branch": r["branch"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "metadata": json.loads(r["metadata"])
                }
                for r in rows
            ]
    
    def count_messages(self, session_id: str) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return row["cnt"] if row else 0

    def update_session(self, session_id, **kwargs):
        allowed_fields = ["name", "branch", "metadata"]
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in allowed_fields:
                updates.append(f"{k} = ?")
                if k == "metadata":
                    params.append(json.dumps(v))
                else:
                    params.append(v)
        if updates:
            updates.append("updated_at = ?")
            params.append(str(int(datetime.now().timestamp())))
            params.append(str(session_id))
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                conn.commit()
    
    def delete_session(self, session_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
    
    def add_message(self, session_id: str, role: str, content: str, tool_calls: Any = None) -> str:
        msg_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp())
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO messages (id, session_id, role, content, tool_calls, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, session_id, role, content, json.dumps(tool_calls or []) if tool_calls else None, now)
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id)
            )
            conn.commit()
        return msg_id
    
    def get_messages(self, session_id, limit=None):
        with self._get_conn() as conn:
            if limit:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                    (session_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
                    (session_id,)
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "tool_calls": json.loads(r["tool_calls"]) if r["tool_calls"] else None,
                    "timestamp": r["timestamp"]
                }
                for r in rows
            ]
    
    def clear_messages(self, session_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()
    
    def add_memory(self, name, content, description=None, memory_type="general", tags=None):
        memory_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp())
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO memories (id, name, description, content, memory_type, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (memory_id, name, description or "", content, memory_type, json.dumps(tags or []), now, now)
            )
            conn.commit()
        return memory_id
    
    def get_memory(self, memory_id):
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "content": row["content"],
                    "memory_type": row["memory_type"],
                    "tags": json.loads(row["tags"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
        return None
    
    def list_memories(self, memory_type=None, limit=100):
        with self._get_conn() as conn:
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE memory_type = ? ORDER BY updated_at DESC LIMIT ?",
                    (memory_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "description": r["description"],
                    "content": r["content"],
                    "memory_type": r["memory_type"],
                    "tags": json.loads(r["tags"]),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"]
                }
                for r in rows
            ]
    
    def search_memories(self, query, limit=20):
        with self._get_conn() as conn:
            search = f"%{query}%"
            rows = conn.execute(
                "SELECT * FROM memories WHERE name LIKE ? OR description LIKE ? OR content LIKE ? ORDER BY updated_at DESC LIMIT ?",
                (search, search, search, limit)
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "description": r["description"],
                    "content": r["content"],
                    "memory_type": r["memory_type"],
                    "tags": json.loads(r["tags"]),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"]
                }
                for r in rows
            ]
    
    def delete_memory(self, memory_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
    
    def record_provider_usage(self, provider_name, model_name, success, response_time):
        now = int(datetime.now().timestamp())
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO provider_stats (provider_name, model_name, success_count, failure_count, avg_response_time, last_used)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_name, model_name) DO UPDATE SET
                    success_count = success_count + excluded.success_count,
                    failure_count = failure_count + excluded.failure_count,
                    avg_response_time = (avg_response_time + excluded.avg_response_time) / 2,
                    last_used = excluded.last_used
            """, (
                provider_name, model_name, 
                1 if success else 0, 0 if success else 1,
                response_time, now
            ))
            conn.commit()
    
    def get_provider_stats(self, provider_name=None, model_name=None):
        with self._get_conn() as conn:
            query = "SELECT * FROM provider_stats WHERE 1=1"
            params = []
            if provider_name:
                query += " AND provider_name = ?"
                params.append(provider_name)
            if model_name:
                query += " AND model_name = ?"
                params.append(model_name)
            query += " ORDER BY last_used DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ── Aggregate counts (Admin Dashboard / Telemetry) ────────
    def count_sessions(self) -> int:
        """Total number of sessions in this database."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
            return int(row[0]) if row else 0

    def count_all_messages(self) -> int:
        """Total number of messages across all sessions."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
            return int(row[0]) if row else 0

    def count_memories(self) -> int:
        """Total number of stored memories."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
            return int(row[0]) if row else 0



class _PoolConnection:
    """Context manager wrapper that returns a connection to the pool on exit."""
    def __init__(self, conn, pool):
        self.conn = conn
        self.pool = pool

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pool.release(self.conn)
        return False
    
_db = None
_db_path: str | None = None


def get_db():
    global _db, _db_path
    from pathlib import Path as _P
    current_cwd = str(_P.cwd().resolve())
    if _db is None or _db_path != current_cwd:
        _db = Database()
        _db_path = current_cwd
    return _db


class SessionDB:
    """Unified session wrapper that delegates to SessionV2.

    This class provides the ``save`` / ``load`` / ``delete`` interface
    required by the Web UI Dashboard, while internally routing all
    operations through ``SessionV2`` — unifying the two previously
    separate session wrappers.

    ``SessionDB`` remains importable from ``core.database`` for
    backward compatibility; all new code should use ``SessionV2``
    directly instead.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize the unified SessionDB wrapper.

        Note:
            ``db_path`` is accepted for backward compatibility but is
            **ignored** — ``SessionV2`` uses the default project-level
            database path from ``get_db()``. This is safe because all
            callers in the codebase pass ``None``.
        """

    def save(self, name: str, messages: list[dict]) -> str:
        """Save a new session and its messages.

        Delegates to :meth:`SessionV2.save_with_messages`.

        Args:
            name: Name of the session.
            messages: List of message dicts containing role and content.

        Returns:
            The generated session ID.
        """
        from core.session_v2 import SessionV2
        return SessionV2.save_with_messages(name, messages)

    def load(self, session_id: str) -> dict[str, Any] | None:
        """Load a session and its messages.

        Delegates to :meth:`SessionV2.load_as_dict`.

        Args:
            session_id: The ID of the session to load.

        Returns:
            A dictionary containing session details and message history,
            or None if the session does not exist.
        """
        from core.session_v2 import SessionV2
        return SessionV2.load_as_dict(session_id)

    def delete(self, session_id: str) -> None:
        """Delete a session.

        Delegates to :meth:`SessionV2.delete`.

        Args:
            session_id: The ID of the session to delete.
        """
        from core.session_v2 import SessionV2
        SessionV2.delete(session_id)

