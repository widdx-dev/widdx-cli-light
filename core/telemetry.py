"""WIDDX Nexus — Anonymous Usage Telemetry (Task 4.5).

Collects **aggregate, anonymous** usage statistics so the project can
understand which features are used and how the system performs in the
wild.  Privacy guarantees:

* **Opt-out first-class**: set ``WIDDX_TELEMETRY_DISABLED=1`` (or
  ``WIDDX_TELEMETRY_DISABLED=true``) to disable all collection.  When
  disabled, :func:`record` is a no-op and nothing is written to disk.
* **No personal data**: request bodies, message contents, file paths,
  IPs, credentials and free-text are never stored.  A scrubber drops
  any dimension key that looks sensitive even if a caller passes one.
* **Pseudonymous instance id**: each installation generates a random
  UUID stored in ``.widdx/data/.instance_id``; only its SHA-256 prefix
  is ever reported, so installs are distinguishable but not linkable
  to a person or machine.

Storage: a single SQLite file at ``.widdx/data/telemetry.db`` (shared
across tenants by design — it contains only counters and safe labels).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("widdx.telemetry")

# ── Configuration ───────────────────────────────────────────

_DISABLED_VALUES = {"1", "true", "yes", "on"}

# Dimension keys that may NEVER be persisted, even if passed in.
_BLOCKED_DIM_KEYS = {
    "content", "message", "messages", "payload", "body", "prompt",
    "response", "path", "file", "filepath", "filename", "url", "uri",
    "ip", "ip_address", "client_ip", "user", "username", "email",
    "key", "api_key", "apikey", "token", "password", "secret",
    "authorization", "cookie", "header", "headers", "query",
    "name", "session_id", "session", "tenant", "tenant_id",
    "stack", "stacktrace", "traceback", "error_message", "detail",
}

# Keys that are safe labels (allow-list applied on top of block-list).
_ALLOWED_DIM_KEYS = {
    "route", "method", "status_class", "endpoint_group", "tool",
    "provider", "model_family", "status", "source", "kind", "unit",
}

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None
_conn_path: Optional[str] = None


def is_enabled() -> bool:
    """Telemetry is enabled unless explicitly disabled via env var."""
    return os.environ.get("WIDDX_TELEMETRY_DISABLED", "").strip().lower() \
        not in _DISABLED_VALUES


def _telemetry_dir(project_dir: str | Path | None = None) -> Path:
    base = Path(project_dir) if project_dir is not None else Path.cwd()
    data_dir = base / ".widdx" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def instance_id(project_dir: str | Path | None = None) -> str:
    """Stable per-install random identifier (never derived from PII)."""
    data_dir = _telemetry_dir(project_dir)
    id_file = data_dir / ".instance_id"
    try:
        if id_file.exists():
            value = id_file.read_text(encoding="utf-8").strip()
            if value:
                return value
    except OSError:
        pass
    value = str(uuid.uuid4())
    try:
        id_file.write_text(value + "\n", encoding="utf-8")
    except OSError as exc:
        logger.debug("Could not persist instance id: %s", exc)
    return value


def instance_fingerprint(project_dir: str | Path | None = None) -> str:
    """Short anonymous fingerprint (first 16 hex chars of SHA-256)."""
    return hashlib.sha256(instance_id(project_dir).encode()).hexdigest()[:16]


# ── Storage ─────────────────────────────────────────────────

def _get_conn(project_dir: str | Path | None = None) -> sqlite3.Connection:
    global _conn, _conn_path
    db_path = str(_telemetry_dir(project_dir) / "telemetry.db")
    if _conn is None or _conn_path != db_path:
        conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                value REAL NOT NULL DEFAULT 1,
                day TEXT NOT NULL,
                ts INTEGER NOT NULL,
                dims TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_telemetry_event ON telemetry_events(event, day)"
        )
        conn.commit()
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                logger.debug("Exception suppressed (line 127)")
        _conn = conn
        _conn_path = db_path
    return _conn


def _scrub_dims(dims: dict[str, Any] | None) -> dict[str, str]:
    """Keep only safe string labels; drop anything possibly sensitive."""
    if not dims:
        return {}
    clean: dict[str, str] = {}
    for key, value in dims.items():
        key_l = str(key).lower()
        if key_l in _BLOCKED_DIM_KEYS or key_l not in _ALLOWED_DIM_KEYS:
            continue
        if value is None:
            continue
        text = str(value)
        if len(text) > 64:  # labels only, never free text
            continue
        clean[key_l] = text
    return clean


def record(event: str, value: float = 1.0, dims: dict[str, Any] | None = None,
           project_dir: str | Path | None = None) -> bool:
    """Record a single anonymous event.  Returns True if stored.

    Never raises — telemetry must not break the product.
    """
    if not is_enabled():
        return False
    event_name = str(event)[:64]
    safe_dims = _scrub_dims(dims)
    now = time.time()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with _lock:
            conn = _get_conn(project_dir)
            conn.execute(
                "INSERT INTO telemetry_events (event, value, day, ts, dims) "
                "VALUES (?, ?, ?, ?, ?)",
                (event_name, float(value), day, int(now), json.dumps(safe_dims)),
            )
            conn.commit()
        return True
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Telemetry record failed: %s", exc)
        return False


def summary(days: int = 14, project_dir: str | Path | None = None) -> dict:
    """Aggregate summary — the only shape ever exposed via the API."""
    result: dict[str, Any] = {
        "enabled": is_enabled(),
        "anonymous": True,
        "instance_fingerprint": instance_fingerprint(project_dir) if is_enabled() else None,
        "window_days": days,
        "totals_by_event": {},
        "daily_series": {},
        "top_routes": {},
        "event_count": 0,
    }
    if not is_enabled():
        return result
    try:
        with _lock:
            conn = _get_conn(project_dir)
            rows = conn.execute(
                "SELECT event, SUM(value), COUNT(*) FROM telemetry_events "
                "WHERE ts >= ? GROUP BY event ORDER BY COUNT(*) DESC LIMIT 50",
                (int(time.time()) - days * 86400,),
            ).fetchall()
            for event, total, count in rows:
                result["totals_by_event"][event] = {
                    "count": int(count), "total_value": round(float(total or 0), 3),
                }
                result["event_count"] += int(count)
            series = conn.execute(
                "SELECT day, COUNT(*) FROM telemetry_events "
                "WHERE ts >= ? GROUP BY day ORDER BY day",
                (int(time.time()) - days * 86400,),
            ).fetchall()
            result["daily_series"] = {day: int(count) for day, count in series}
            routes = conn.execute(
                "SELECT json_extract(dims, '$.route') AS route, COUNT(*) "
                "FROM telemetry_events WHERE event = 'http_request' AND ts >= ? "
                "GROUP BY route ORDER BY COUNT(*) DESC LIMIT 15",
                (int(time.time()) - days * 86400,),
            ).fetchall()
            result["top_routes"] = {
                (route or "unknown"): int(count) for route, count in routes
            }
    except Exception as exc:  # pragma: no cover — defensive
        result["error"] = str(exc)
    return result


def reset(project_dir: str | Path | None = None) -> int:
    """Delete all collected events.  Returns rows removed."""
    try:
        with _lock:
            conn = _get_conn(project_dir)
            cur = conn.execute("DELETE FROM telemetry_events")
            conn.commit()
            return int(cur.rowcount or 0)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Telemetry reset failed: %s", exc)
        return 0


def close() -> None:
    """Close the shared connection (used by tests/shutdown)."""
    global _conn, _conn_path
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                logger.debug("Exception suppressed (line 246)")
        _conn = None
        _conn_path = None


# ── ASGI middleware ─────────────────────────────────────────

class TelemetryMiddleware:
    """Counts HTTP requests anonymously (route template + status class).

    Route *templates* (e.g. ``/api/sessions/{session_id}``) are used —
    never concrete paths — so no identifiers leak into the store.
    Static assets and probe endpoints are skipped to keep signal high.
    """

    SKIP_PREFIXES = ("/static", "/favicon", "/metrics")

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(self.SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        status_holder = {"status": 500}

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                status_holder["status"] = int(message.get("status", 500))
            await send(message)

        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            try:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                route = self._route_template(scope)
                status = status_holder["status"]
                record(
                    "http_request",
                    value=elapsed_ms,
                    dims={
                        "route": route,
                        "method": scope.get("method", "GET"),
                        "status_class": f"{status // 100}xx",
                    },
                )
            except Exception:  # pragma: no cover — defensive
                logger.debug("Exception suppressed (line 301)")

    @staticmethod
    def _route_template(scope: dict) -> str:
        route = scope.get("route")
        template = getattr(route, "path", None)
        if template:
            return template
        # Fallback: first two path segments, no ids.
        parts = [p for p in scope.get("path", "").split("/") if p][:2]
        return "/" + "/".join(parts) if parts else "/"
