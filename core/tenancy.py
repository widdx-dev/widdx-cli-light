"""WIDDX Nexus — Multi-Tenant Isolation (Task 4.2).

Provides **physical data isolation** between tenants: every tenant gets
its own SQLite database file under ``.widdx/data/tenants/<tenant_id>/``
so one tenant can never read, corrupt, or lock another tenant's data.

Tenant resolution
-----------------
The active tenant for a request is resolved from the environment mode
(``WIDDX_TENANT_MODE``):

``off`` (default)
    Multi-tenancy disabled — every request maps to ``DEFAULT_TENANT``
    ("default") and legacy single-tenant behavior is preserved.

``keymap``
    Tenants are mapped to API keys via ``WIDDX_TENANT_KEYS``::

        WIDDX_TENANT_KEYS="acme:secret-key-1,globex:secret-key-2"

    The request's ``Authorization: Bearer <key>`` value is matched
    (constant-time) against the configured keys.  Unknown keys resolve
    to ``DEFAULT_TENANT`` so existing single-key deployments keep
    working.

``header``
    The tenant id is taken from the ``X-Tenant-ID`` request header
    (use behind a trusted gateway that injects the header, e.g. after
    authenticating the caller).  Invalid/missing ids fall back to
    ``DEFAULT_TENANT``.

Usage
-----
.. code-block:: python

    from core.tenancy import resolve_tenant_id, get_tenant_db

    tenant = resolve_tenant_id(bearer_key="secret-key-1", header_value=None)
    db = get_tenant_db(tenant)          # core.database.Database instance
    db.list_sessions()                  # only this tenant's sessions
"""

from __future__ import annotations

import hmac
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("widdx.tenancy")

# ── Constants ───────────────────────────────────────────────
DEFAULT_TENANT = "default"
MODE_OFF = "off"
MODE_KEYMAP = "keymap"
MODE_HEADER = "header"

TENANT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_cache_lock = threading.Lock()
_db_cache: dict[str, Any] = {}          # tenant_id -> Database
_keymap_cache: dict[str, str] | None = None  # api_key -> tenant_id


# ── Tenant id handling ──────────────────────────────────────

def sanitize_tenant_id(raw: str | None) -> Optional[str]:
    """Validate and normalize a raw tenant identifier.

    Returns the sanitized id (lowercase, 1-64 chars of ``a-z0-9_-``,
    starting with an alphanumeric) or ``None`` when invalid.  The
    strict charset prevents path traversal (``..``, ``/``) and keeps
    the on-disk layout predictable.
    """
    if not raw:
        return None
    candidate = raw.strip().lower()
    if TENANT_ID_RE.match(candidate):
        return candidate
    return None


def is_enabled() -> bool:
    """True when multi-tenant mode is explicitly enabled."""
    return get_mode() in (MODE_KEYMAP, MODE_HEADER)


def get_mode() -> str:
    """Return the configured tenancy mode (``off``/``keymap``/``header``)."""
    mode = os.environ.get("WIDDX_TENANT_MODE", MODE_OFF).strip().lower()
    if mode == MODE_KEYMAP and os.environ.get("WIDDX_TENANT_KEYS"):
        return MODE_KEYMAP
    if mode == MODE_HEADER:
        return MODE_HEADER
    return MODE_OFF


def _load_keymap() -> dict[str, str]:
    """Parse ``WIDDX_TENANT_KEYS="tenantA:keyA,tenantB:keyB"`` into a map."""
    global _keymap_cache
    if _keymap_cache is not None:
        return _keymap_cache
    mapping: dict[str, str] = {}
    raw = os.environ.get("WIDDX_TENANT_KEYS", "")
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        tenant_part, key_part = pair.split(":", 1)
        tenant_id = sanitize_tenant_id(tenant_part)
        key_part = key_part.strip()
        if tenant_id and key_part:
            mapping[key_part] = tenant_id
        elif pair:
            logger.warning("Ignoring invalid WIDDX_TENANT_KEYS entry: %r", pair)
    _keymap_cache = mapping
    return mapping


def reset_keymap_cache() -> None:
    """Drop the cached keymap (call after changing WIDDX_TENANT_KEYS)."""
    global _keymap_cache
    _keymap_cache = None


def resolve_tenant_id(bearer_key: str | None = None,
                      header_value: str | None = None) -> str:
    """Resolve the tenant for an incoming request.

    Always returns a valid tenant id — never raises.  Unknown or
    missing identifiers resolve to :data:`DEFAULT_TENANT`.
    """
    mode = get_mode()
    if mode == MODE_KEYMAP and bearer_key:
        keymap = _load_keymap()
        # Constant-time comparison against every configured key to avoid
        # leaking which prefix matched via timing differences.
        matched: str | None = None
        for key, tenant_id in keymap.items():
            if hmac.compare_digest(key.encode(), bearer_key.encode()):
                matched = tenant_id
        if matched:
            return matched
    if mode == MODE_HEADER:
        header_tenant = sanitize_tenant_id(header_value)
        if header_tenant:
            return header_tenant
    return DEFAULT_TENANT


# ── Per-tenant storage ──────────────────────────────────────

def tenant_data_dir(tenant_id: str, project_dir: str | Path | None = None) -> Path:
    """Return (and create) the data directory for a tenant.

    Layout::

        <project>/.widdx/data/tenants/<tenant_id>/widdx.db
    """
    tenant_id = sanitize_tenant_id(tenant_id) or DEFAULT_TENANT
    if project_dir is None:
        base = Path.cwd()
    else:
        base = Path(project_dir)
    data_dir = base / ".widdx" / "data" / "tenants" / tenant_id
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def tenant_db_path(tenant_id: str, project_dir: str | Path | None = None) -> Path:
    """Path of the tenant's isolated SQLite database file."""
    return tenant_data_dir(tenant_id, project_dir) / "widdx.db"


def get_tenant_db(tenant_id: str):
    """Return a cached :class:`core.database.Database` for the tenant.

    Each tenant gets its **own database file and connection pool** —
    this is the isolation boundary.
    """
    tenant_id = sanitize_tenant_id(tenant_id) or DEFAULT_TENANT
    with _cache_lock:
        db = _db_cache.get(tenant_id)
        if db is None:
            from core.database import Database
            db = Database(tenant_db_path(tenant_id))
            _db_cache[tenant_id] = db
            logger.info("Initialized isolated database for tenant %r", tenant_id)
        return db


def reset_cache() -> None:
    """Clear the Database instance cache (used by tests)."""
    with _cache_lock:
        _db_cache.clear()


def list_tenants(project_dir: str | Path | None = None) -> list[dict]:
    """List known tenants with basic storage statistics."""
    if project_dir is None:
        base = Path.cwd()
    else:
        base = Path(project_dir)
    root = base / ".widdx" / "data" / "tenants"
    tenants: list[dict] = []
    if not root.exists():
        return tenants
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        tenant_id = sanitize_tenant_id(entry.name)
        if not tenant_id:
            continue
        db_file = entry / "widdx.db"
        info: dict[str, Any] = {
            "tenant_id": tenant_id,
            "db_path": str(db_file),
            "db_size_bytes": db_file.stat().st_size if db_file.exists() else 0,
            "created_at": int(entry.stat().st_ctime),
            "sessions": 0,
            "memories": 0,
        }
        try:
            db = get_tenant_db(tenant_id)
            info["sessions"] = len(db.list_sessions(limit=10000))
            info["memories"] = len(db.list_memories(limit=10000))
        except Exception as exc:  # pragma: no cover — defensive
            info["error"] = str(exc)
        tenants.append(info)
    return tenants


def describe() -> dict:
    """Machine-readable summary of the tenancy configuration."""
    mode = get_mode()
    keymap = _load_keymap() if mode == MODE_KEYMAP else {}
    return {
        "enabled": is_enabled(),
        "mode": mode,
        "default_tenant": DEFAULT_TENANT,
        "configured_tenants": sorted(set(keymap.values())),
        "known_tenants": [t["tenant_id"] for t in list_tenants()],
    }


def now_ts() -> int:
    return int(time.time())
