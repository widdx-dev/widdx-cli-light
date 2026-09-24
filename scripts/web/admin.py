"""WIDDX Nexus — Admin Dashboard (Task 4.3).

A lightweight, dependency-free administration panel exposing
operational visibility:

* System overview (version, uptime, runtime, memory, object counts)
* Multi-tenant registry (per-tenant storage stats)
* Anonymous telemetry summary
* Telemetry management (reset collected events)

Security
--------
Every endpoint requires the admin key configured via
``WIDDX_ADMIN_KEY`` (sent as ``X-Admin-Key`` header or
``Authorization: Bearer <key>``).  When the env var is **not set the
dashboard is fully disabled** — every endpoint returns 403 — so it can
never be exposed accidentally.  Comparisons use ``hmac.compare_digest``
to be timing-safe.

The static HTML shell (``/admin/``) is served without the key because
it contains no data; all data endpoints enforce the key.
"""

from __future__ import annotations

import hmac
import logging
import os
import platform
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("widdx.web.admin")

_START_TIME = time.time()

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:  # pragma: no cover
    raise SystemExit("FastAPI required for the admin dashboard")

ADMIN_KEY_HEADER = "X-Admin-Key"
ADMIN_HTML_PATH = Path(__file__).resolve().parent.parent / "static" / "admin.html"

router = APIRouter(tags=["admin"])


# ── Auth ────────────────────────────────────────────────────

def admin_key() -> Optional[str]:
    """The configured admin key, or None when the dashboard is off."""
    key = os.environ.get("WIDDX_ADMIN_KEY", "").strip()
    return key or None


def is_admin_enabled() -> bool:
    return admin_key() is not None


def _extract_key(request: Request) -> str:
    header_key = request.headers.get(ADMIN_KEY_HEADER, "")
    if header_key:
        return header_key
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _authorized(request: Request) -> bool:
    expected = admin_key()
    if not expected:
        return False
    provided = _extract_key(request)
    if not provided:
        return False
    return hmac.compare_digest(expected.encode(), provided.encode())


def _guard(request: Request) -> Optional[JSONResponse]:
    """Return an error response if unauthorized, else None."""
    if _authorized(request):
        return None
    if not is_admin_enabled():
        return JSONResponse(
            status_code=403,
            content={
                "error": "Admin dashboard disabled",
                "detail": "Set the WIDDX_ADMIN_KEY environment variable to enable it.",
            },
        )
    return JSONResponse(
        status_code=401,
        content={"error": "Invalid admin key", "header": ADMIN_KEY_HEADER},
    )


# ── Helpers ─────────────────────────────────────────────────

def _memory_mb() -> float:
    """Current process RSS in MB (best effort, cross-platform)."""
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KB, macOS reports bytes.
        return round(rss / 1024.0, 1) if sys.platform != "darwin" else round(rss / (1024.0 * 1024.0), 1)
    except Exception:
        return -1.0


def _db_counts() -> dict:
    try:
        from core.database import get_db
        db = get_db()
        return {
            "sessions": db.count_sessions(),
            "messages": db.count_all_messages(),
            "memories": db.count_memories(),
        }
    except Exception as exc:  # pragma: no cover — defensive
        return {"sessions": 0, "messages": 0, "memories": 0, "error": str(exc)}


def _app_version() -> str:
    try:
        from core.version import __version__  # type: ignore
        return str(__version__)
    except Exception:
        return "3.3.0"


# ── Routes ──────────────────────────────────────────────────

@router.get("/admin/", include_in_schema=False)
@router.get("/admin", include_in_schema=False)
async def admin_page() -> HTMLResponse:
    """Serve the dashboard shell (static; data endpoints are key-protected)."""
    try:
        html = ADMIN_HTML_PATH.read_text(encoding="utf-8")
    except OSError:
        html = "<h1>WIDDX Admin</h1><p>admin.html not found.</p>"
    return HTMLResponse(content=html)


@router.get("/admin/api/status")
async def admin_status(request: Request):
    """Whether the dashboard is enabled and the key is valid."""
    enabled = is_admin_enabled()
    return {
        "enabled": enabled,
        "authenticated": _authorized(request),
        "message": None if enabled else "Set WIDDX_ADMIN_KEY to enable the admin dashboard.",
    }


@router.get("/admin/api/overview")
async def admin_overview(request: Request):
    denied = _guard(request)
    if denied is not None:
        return denied

    from core import tenancy, telemetry

    return {
        "app": {
            "name": "WIDDX Nexus",
            "version": _app_version(),
            "uptime_seconds": round(time.time() - _START_TIME, 1),
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pid": os.getpid(),
            "memory_rss_mb": _memory_mb(),
        },
        "data": _db_counts(),
        "tenancy": tenancy.describe(),
        "telemetry": {
            "enabled": telemetry.is_enabled(),
            "event_count": telemetry.summary(days=30).get("event_count", 0)
            if telemetry.is_enabled() else 0,
        },
        "features": {
            "admin_dashboard": True,
            "multi_tenant": tenancy.is_enabled(),
            "telemetry": telemetry.is_enabled(),
        },
    }


@router.get("/admin/api/tenants")
async def admin_tenants(request: Request):
    denied = _guard(request)
    if denied is not None:
        return denied
    from core import tenancy
    return {"tenants": tenancy.list_tenants(), "config": tenancy.describe()}


@router.get("/admin/api/telemetry")
async def admin_telemetry(request: Request, days: int = 14):
    denied = _guard(request)
    if denied is not None:
        return denied
    from core import telemetry
    days = max(1, min(int(days), 90))
    return telemetry.summary(days=days)


@router.post("/admin/api/telemetry/reset")
async def admin_telemetry_reset(request: Request):
    denied = _guard(request)
    if denied is not None:
        return denied
    from core import telemetry
    removed = telemetry.reset()
    logger.info("Admin reset telemetry (%d events removed)", removed)
    return {"status": "ok", "removed": removed}
