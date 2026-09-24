"""WIDDX Nexus — Web UI Server (FastAPI + WebSocket).

Architecture:
  server.py          ← FastAPI app, routes, WebSocket
  chat.py            ← LLM chat handler (UIL Brain pipeline)
  sandbox.py         ← Sandbox (terminal, browser, files)
  dashboard.py       ← All-system aggregator for the REST API
  static/            ← Frontend assets
    index.html       ← Main page (with RTL/Arabic i18n)
    css/style.css    ← Full design system (dark/light, RTL)
    js/              ← JavaScript modules
      lang.js        ← i18n engine (en/ar)
      ui.js          ← Theme, sidebar, markdown parser, command palette
      nexus.js       ← Main app logic, WebSocket, all views

Usage:
    python scripts/web_app.py
    # → http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from typing import Any

from core._path import ensure_project_root  # noqa: E402
ensure_project_root()

from pathlib import Path  # noqa: E402

# ── Static paths ────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)

# ── FastAPI imports (checked) ──────────────────────────────
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
    from fastapi.staticfiles import StaticFiles
except ImportError as e:
    print(f"\n❌ FastAPI not installed: {e}")
    print("   Install: pip install widdx-nexus[api]")
    print("   Or:      pip install fastapi uvicorn\n")
    sys.exit(1)

logger = logging.getLogger("widdx.web")

# ── Pydantic models for input validation ────────────────────
from pydantic import BaseModel, Field  # noqa: E402
from typing import Optional as Opt  # noqa: E402

class ChatPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=100000)
    history: list[dict] = Field(default_factory=list, max_length=1000)

class SandboxPayload(BaseModel):
    command: str = Field(..., min_length=1, max_length=10000)
    timeout: int = Field(default=60, ge=1, le=600)

class SettingsPayload(BaseModel):
    provider: dict = Field(default_factory=dict)
    # system_prompt: hardcoded in core/constants.py — not user-editable
    temperature: Opt[float] = Field(default=None, ge=0, le=2)
    max_turns: Opt[int] = Field(default=None, ge=1, le=100)
    cli_theme: Opt[str] = Field(default=None, pattern=r'^(dark|light)$')

class SessionPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    messages: list[dict] = Field(default_factory=list, max_length=1000)

class MemoryPayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=50000)
    tags: str = Field(default="", max_length=500)

# ── App ─────────────────────────────────────────────────────
app = FastAPI(title="WIDDX Nexus", version="3.2.0")

# ── CORS + Origin validation ───────────────────────────────
# ISS-009: CSRF / Origin validation — only allow same-origin requests
# Dynamically built; extended at startup with actual listening address.
_ALLOWED_ORIGINS_BASE = [
    "http://localhost:8000", "http://127.0.0.1:8000",
    "http://localhost:8001", "http://127.0.0.1:8001",
    "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:8099", "http://127.0.0.1:8099",
    "http://0.0.0.0:8000",
]
ALLOWED_ORIGINS = list(_ALLOWED_ORIGINS_BASE)

# ── Production CORS: allow env-var origins ────────────────
# Override via WIDDX_CORS_ORIGINS (comma-separated URLs)
# Example: WIDDX_CORS_ORIGINS="https://app.widdx.com,https://admin.widdx.com"
_env_cors = os.environ.get("WIDDX_CORS_ORIGINS", "")
if _env_cors:
    for origin in _env_cors.split(","):
        origin = origin.strip()
        if origin and origin not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(origin)
            logger.info("CORS: added origin '%s' from WIDDX_CORS_ORIGINS env", origin)

from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

# ── Direct CORSMiddleware activation (required for tests & production) ──
# Enabled directly at module load so that TestClient sees CORS headers
# without needing to call run().
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def _validate_origin(request: Request, call_next):
    """Reject requests with disallowed Origin header (CSRF protection).

    Only validates non-GET, non-OPTIONS requests that include an Origin header.
    Browser fetch/XHR requests include Origin automatically for cross-origin
    requests; local requests from the same origin are unaffected.
    """
    if request.method not in ("GET", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"error": "Origin not allowed"})
    return await call_next(request)


# CORSMiddleware is now added dynamically in run() below
# so it picks up the actual host:port at startup.

@app.middleware("http")
async def _add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' ws: wss:; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "frame-src *; "          # allow iframe to load any URL in Browser tab
        "worker-src blob:; "
        "media-src 'self' blob:;"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    # X-Frame-Options only protects THIS page from being embedded elsewhere — not its iframes
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


# ── Telemetry middleware (anonymous usage analytics — Task 4.5) ──
# Opt out with WIDDX_TELEMETRY_DISABLED=1. Records only route templates,
# HTTP method and status class — never paths, bodies, or identifiers.
from core.telemetry import TelemetryMiddleware  # noqa: E402
app.add_middleware(TelemetryMiddleware)


# ── Multi-tenant resolution (Task 4.2) ─────────────────────
# Resolves the active tenant per request. Disabled by default — see
# core/tenancy.py for WIDDX_TENANT_MODE / WIDDX_TENANT_KEYS.
from core.tenancy import (  # noqa: E402
    DEFAULT_TENANT, resolve_tenant_id, get_tenant_db, is_enabled as tenancy_enabled,
)


def get_tenant(request: Request) -> str:
    """FastAPI dependency — current tenant id for the request."""
    if not tenancy_enabled():
        return DEFAULT_TENANT
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    return resolve_tenant_id(
        bearer_key=bearer,
        header_value=request.headers.get("x-tenant-id"),
    )


@app.middleware("http")
async def _add_tenant_header(request: Request, call_next):
    """Echo the resolved tenant so clients can verify isolation."""
    response = await call_next(request)
    try:
        response.headers["X-Tenant-ID"] = get_tenant(request)
    except Exception:
        response.headers["X-Tenant-ID"] = DEFAULT_TENANT
    return response

# ── Mount static files ──────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Admin Dashboard (Task 4.3) ──────────────────────────────
# Key-protected (/admin). Disabled entirely unless WIDDX_ADMIN_KEY is set.
try:
    from scripts.web.admin import router as _admin_router
    app.include_router(_admin_router)
except Exception as _admin_exc:  # pragma: no cover — defensive
    logger.warning("Admin dashboard unavailable: %s", _admin_exc)


# ── Favicon ─────────────────────────────────────────────────
@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    svg = STATIC_DIR / "favicon.svg"
    if svg.exists():
        return FileResponse(svg, media_type="image/svg+xml")
    return Response(status_code=204)

# ── Lazy handlers ───────────────────────────────────────────
_chat_handler: Any = None
_sandbox_handler: Any = None


def get_chat() -> Any:
    global _chat_handler
    if _chat_handler is None:
        from scripts.web.chat import ChatHandler
        _chat_handler = ChatHandler()
    return _chat_handler


def refresh_chat() -> Any:
    """Force recreation of the chat handler (e.g. after settings change)."""
    global _chat_handler
    _chat_handler = None
    from core.provider_reliability import reset_reliable_provider
    reset_reliable_provider()
    return get_chat()


def get_sandbox() -> Any:
    global _sandbox_handler
    if _sandbox_handler is None:
        from scripts.web.sandbox import SandboxHandler
        _sandbox_handler = SandboxHandler()
    return _sandbox_handler


# ── Routes ──────────────────────────────────────────────────

@app.post("/api/new-session")
async def api_new_session() -> dict:
    """Start a new chat session."""
    chat = get_chat()
    sid = chat.new_session()
    return {"session_id": sid}


@app.get("/")
async def index() -> Response:
    """Serve the main Web UI page (no-cache)."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        content = html_path.read_bytes()
        return Response(content=content, media_type="text/html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse("<h1>WIDDX Nexus Web UI</h1><p>Build index.html first.</p>")


@app.get("/api/health")
async def health() -> dict:
    """Health check endpoint — lightweight, no side effects."""
    return {"status": "ok", "version": "3.2.0"}


@app.get("/api/livez", include_in_schema=False)
async def liveness() -> dict:
    """Kubernetes liveness probe — is the process alive? (no auth, no I/O)."""
    return {"status": "alive", "timestamp": time.time()}


@app.get("/api/ready", include_in_schema=False)
async def readiness() -> dict:
    """Kubernetes readiness probe — can the server handle traffic?

    Verifies the database layer is reachable. No auth required so
    orchestrators (Kubernetes, Docker, Nginx) can call it.
    """
    try:
        from core.database import get_db
        get_db().count_sessions()
        db_ready = True
    except Exception:
        db_ready = False
    return {
        "status": "ready" if db_ready else "degraded",
        "database": db_ready,
        "timestamp": time.time(),
    }


@app.get("/api/tenant")
async def api_tenant_info(request: Request) -> dict:
    """Return the tenant resolved for this request (Task 4.2).

    Lets clients verify isolation is active. Exposes no secrets.
    """
    tenant = get_tenant(request)
    return {
        "tenant": tenant,
        "multi_tenant_enabled": tenancy_enabled(),
        "is_default": tenant == DEFAULT_TENANT,
    }


@app.get("/api/telemetry")
async def api_telemetry_summary(days: int = 14) -> dict:
    """Public anonymous usage summary (Task 4.5).

    Returns only aggregates — no personal data. Opt out with
    WIDDX_TELEMETRY_DISABLED=1.
    """
    from core.telemetry import summary as telemetry_summary
    days = max(1, min(int(days), 90))
    return telemetry_summary(days=days)


@app.get("/api/status")
async def status() -> dict:
    """System status endpoint."""
    chat = get_chat()
    sandbox = get_sandbox()
    from pathlib import Path
    return {
        "status": "ok",
        "provider": chat.info,
        "sandbox": {"mode": sandbox.mode},
        "version": "3.0.0",
        "project": Path.cwd().name,
    }


@app.get("/api/tools")
async def api_tools() -> dict:
    """List available tools for slash commands and UI."""
    try:
        chat = get_chat()
        defs = chat._get_tool_defs() if hasattr(chat, "_get_tool_defs") else []
        tools_out = []
        for td in defs:
            name = td.get("name") or (td.get("function") or {}).get("name", "")
            desc = td.get("description") or (td.get("function") or {}).get("description", "")
            if name:
                tools_out.append({"name": name, "description": desc[:120] if desc else ""})
        return {"tools": tools_out, "count": len(tools_out)}
    except Exception as e:
        return {"tools": [], "error": str(e)}


# ── Tool execution endpoints ─────────────────────────────────
class ToolExecPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    args: dict = Field(default_factory=dict)


@app.post("/api/tools/execute")
async def api_tool_execute(payload: ToolExecPayload) -> dict:
    """Execute a registered tool directly (bypasses LLM)."""
    from core.telemetry import record as _tel_record
    try:
        from core.tools import dispatch
        result = dispatch.execute_with_skills(payload.name, payload.args)
        _tel_record("tool_exec", dims={"tool": payload.name[:64], "status": "ok"})
        return {"status": "ok", "name": payload.name, "result": result}
    except Exception as e:
        _tel_record("tool_exec", dims={"tool": payload.name[:64], "status": "error"})
        return {"status": "error", "name": payload.name, "error": str(e)}


@app.post("/api/tools/search-replace")
async def api_tool_search_replace(request: Request) -> dict:
    """Direct endpoint for search_replace tool."""
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("search_replace", {
            "pattern": data.get("pattern", ""),
            "replacement": data.get("replacement", ""),
            "include": data.get("include"),
            "path": data.get("path"),
            "preview": data.get("preview", True),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/semantic-search")
async def api_tool_semantic_search(request: Request) -> dict:
    """Direct endpoint for semantic_search tool."""
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("semantic_search", {
            "query": data.get("query", ""),
            "path": data.get("path"),
            "include": data.get("include"),
            "top_k": data.get("top_k", 10),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/rename")
async def api_tool_rename(request: Request) -> dict:
    """Direct endpoint for rename_symbol tool."""
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("rename_symbol", {
            "symbol": data.get("symbol", ""),
            "new_name": data.get("new_name", ""),
            "path": data.get("path"),
            "include": data.get("include"),
            "preview": data.get("preview", True),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── New tool endpoints ────────────────────────────────────

@app.post("/api/tools/dep-graph")
async def api_tool_dep_graph(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("dep_graph", {
            "path": data.get("path"),
            "include": data.get("include"),
            "depth": data.get("depth", 2),
            "format": data.get("format", "text"),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/docker")
async def api_tool_docker(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("docker", dict(data))
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/db-query")
async def api_tool_db_query(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("db_query", {
            "db_path": data.get("db_path"),
            "query": data.get("query", ""),
            "type": data.get("type", "sqlite"),
            "conn_str": data.get("conn_str"),
            "action": data.get("action", "query"),
            "table": data.get("table"),
            "max_rows": data.get("max_rows", 50),
            "format": data.get("format", "text"),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/api-request")
async def api_tool_api_request(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("api_request", {
            "method": data.get("method", "GET"),
            "url": data.get("url", ""),
            "headers": data.get("headers"),
            "body": data.get("body"),
            "params": data.get("params"),
            "timeout": data.get("timeout", 30),
            "follow_redirects": data.get("follow_redirects", True),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/pkg-mgr")
async def api_tool_pkg_mgr(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("pkg_mgr", {
            "action": data.get("action", "detect"),
            "package": data.get("package", ""),
            "pkg_manager": data.get("pkg_manager", "auto"),
            "path": data.get("path"),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/terminal")
async def api_tool_terminal(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("terminal", {
            "action": data.get("action", "list"),
            "name": data.get("name"),
            "command": data.get("command"),
            "cwd": data.get("cwd"),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/ask")
async def api_tool_ask_user(request: Request) -> dict:
    data = await request.json()
    from core.tools.handlers.ask_user import _ask_user
    try:
        result = _ask_user(data.get("question", ""))
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── New tool endpoints ────────────────────────────────────

@app.post("/api/tools/embedding-search")
async def api_tool_embedding_search(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("semantic_embedding", {
            "query": data.get("query", ""),
            "path": data.get("path"),
            "include": data.get("include"),
            "top_k": data.get("top_k", 10),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/file-tree")
async def api_tool_file_tree(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("file_tree", {
            "path": data.get("path"),
            "depth": data.get("depth", 3),
            "include": data.get("include"),
            "format": data.get("format", "text"),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/scaffold")
async def api_tool_scaffold(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("scaffold", {
            "template": data.get("template", "python-cli"),
            "name": data.get("name", "my-project"),
            "path": data.get("path"),
            "description": data.get("description", ""),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/run-tests")
async def api_tool_run_tests(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("run_tests", {
            "path": data.get("path"),
            "test_path": data.get("test_path"),
            "framework": data.get("framework"),
            "timeout": data.get("timeout", 120),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/security-scan")
async def api_tool_security_scan(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("security_scan", {
            "path": data.get("path"),
            "scan_type": data.get("scan_type", "all"),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/tools/undo")
async def api_tool_undo(request: Request) -> dict:
    data = await request.json()
    from core.tools import dispatch
    try:
        result = dispatch.execute_with_skills("tool_undo", {
            "action": data.get("action", "undo"),
            "file_path": data.get("file_path"),
        })
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── File upload ───────────────────────────────────────────

@app.post("/api/upload")
async def api_file_upload(request: Request) -> dict:
    """Upload a file to the current working directory."""
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            import cgi
            _, headers = cgi.parse_header(content_type)
            boundary = headers.get("boundary", "").encode()
            data = body
            parts = data.split(b"--" + boundary)
            for part in parts:
                if b"Content-Disposition" not in part:
                    continue
                header_part, _, file_data = part.partition(b"\r\n\r\n")
                file_data = file_data.rstrip(b"\r\n--")
                disp_line = header_part.decode("utf-8", errors="ignore")
                if 'filename="' in disp_line:
                    filename = disp_line.split('filename="')[1].split('"')[0]
                    filepath = Path.cwd() / filename
                    filepath.write_bytes(file_data)
                    return {"status": "ok", "file": filename, "size": len(file_data)}
            return {"status": "error", "error": "No file found in upload"}
        else:
            data = await request.json()
            filename = data.get("filename", "uploaded_file")
            content = data.get("content", "")
            filepath = Path.cwd() / filename
            if isinstance(content, str):
                filepath.write_text(content, encoding="utf-8")
            else:
                filepath.write_bytes(content)
            return {"status": "ok", "file": filename, "size": len(content)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/project/session")
async def api_project_session() -> dict:
    """Load current project session from SQLite database."""
    try:
        from core.database import get_db
        db = get_db()
        sessions = db.list_sessions(limit=1)
        if not sessions:
            return {"messages": [], "state": {}}
        sid = sessions[0]["id"]
        msgs = db.get_messages(sid)
        return {
            "messages": [{"role": m["role"], "content": m["content"]} for m in msgs],
            "state": {"model": sessions[0].get("name", ""), "session_id": sid},
        }
    except Exception as e:
        return {"messages": [], "state": {}, "error": str(e)}


@app.get("/api/project/docs/{doc_name}")
async def api_project_doc(doc_name: str):
    """Read a project doc (PLAN.md, DESIGN.md, TASKS.md, or ROADMAP.md).
    Auto-creates from template if the file does not exist yet."""
    from pathlib import Path
    allowed = {"PLAN.md", "DESIGN.md", "TASKS.md", "ROADMAP.md"}
    if doc_name not in allowed:
        return JSONResponse(status_code=400, content={"error": "Invalid doc name"})
    doc_path = Path.cwd() / ".widdx" / doc_name
    if not doc_path.exists():
        # Auto-create with template from project_tracker
        from core.project_tracker import ensure_docs
        ensure_docs(Path.cwd())
    content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    return {"content": content, "exists": doc_path.exists(), "name": doc_name}


@app.get("/api/branches")
async def api_branches():
    """List session branches — prefers real git branches, falls back to project state."""
    import subprocess
    try:
        # Try real git branches first
        result = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            capture_output=True, text=True, timeout=5, cwd=str(Path.cwd())
        )
        head_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(Path.cwd())
        )
        if result.returncode == 0:
            branches = [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]
            current = head_result.stdout.strip() if head_result.returncode == 0 else (branches[0] if branches else "main")
            return {"current": current, "branches": branches or ["main"]}
    except Exception:
        pass
    # Fallback to project state branches
    try:
        from core.project.state import list_branches, get_current_branch
        return {"current": get_current_branch(), "branches": list_branches()}
    except Exception as e:
        return {"current": "main", "branches": ["main"], "error": str(e)}


@app.post("/api/chat")
async def chat_message(payload: ChatPayload, request: Request):
    """Send a chat message (non-blocking)."""
    message = payload.message
    history = payload.history
    # Rate limiting
    from fastapi.responses import JSONResponse as _JR
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return _JR(status_code=429, content={"content": "", "error": "Rate limited — 30 req/min max"})

    chat = get_chat()
    loop = asyncio.get_running_loop()
    from core.telemetry import record as _tel_record
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, chat.chat, message, history),
            timeout=600.0
        )
        _tel_record("chat_turn", dims={"source": "web", "status": "ok"})
        return result
    except asyncio.TimeoutError:
        _tel_record("chat_turn", dims={"source": "web", "status": "timeout"})
        return {"content": "", "error": "Request timed out after 10 minutes. Please try a simpler request."}


# ── Pydantic models for File Operations (Phase 2) ────────────
class FileCreatePayload(BaseModel):
    path: str = Field(..., min_length=1, max_length=10000)
    is_directory: bool = Field(default=False)
    content: str = Field(default="", max_length=5000000)




@app.get("/api/sandbox/file")
async def sandbox_file_read(path: str = ""):
    """Read file content."""
    try:
        if not path:
            return {"error": "Path is required"}
        file_path = Path(path).resolve()
        if not file_path.exists() or not file_path.is_file():
            return {"error": "File not found"}
        # Security: prevent reading outside project
        project_root = Path.cwd().resolve()
        fp_str = str(file_path)
        pr_str = str(project_root)
        if fp_str != pr_str and not fp_str.startswith(pr_str + "/"):
            return {"error": "Access denied"}
        content = file_path.read_text(encoding="utf-8")
        size = file_path.stat().st_size
        return {"content": content, "size": size, "path": str(file_path)}
    except UnicodeDecodeError:
        return {"error": "Binary file — cannot read as text"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sandbox/file")
async def sandbox_file_write(payload: FileCreatePayload):
    """Write file content."""
    try:
        file_path = Path(payload.path).resolve()
        project_root = Path.cwd().resolve()
        fp_str = str(file_path)
        pr_str = str(project_root)
        if fp_str != pr_str and not fp_str.startswith(pr_str + "/"):
            return {"error": "Access denied"}
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(payload.content, encoding="utf-8")
        return {"status": "ok", "path": str(file_path)}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/sandbox/file")
async def sandbox_file_delete(path: str = ""):
    """Delete a file or directory."""
    try:
        if not path:
            return {"error": "Path is required"}
        file_path = Path(path).resolve()
        project_root = Path.cwd().resolve()
        fp_str = str(file_path)
        pr_str = str(project_root)
        if fp_str != pr_str and not fp_str.startswith(pr_str + "/"):
            return {"error": "Access denied"}
        if file_path.is_file():
            file_path.unlink()
            return {"status": "ok", "deleted": str(file_path)}
        elif file_path.is_dir():
            import shutil
            shutil.rmtree(file_path)
            return {"status": "ok", "deleted": str(file_path)}
        return {"error": "Path not found"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sandbox/processes")
async def sandbox_processes():
    """List running processes (cross-platform)."""
    import subprocess
    try:
        if sys.platform == "win32":
            result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=5)
            processes = []
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip(' \"') for p in line.split(",")]
                if len(parts) >= 3:
                    processes.append({
                        "pid": parts[1],
                        "name": parts[0],
                        "mem": parts[3] if len(parts) > 3 else "",
                    })
        else:
            result = subprocess.run(["ps", "aux", "--sort=-%mem"], capture_output=True, text=True, timeout=5)
            processes = []
            lines = result.stdout.strip().split("\n")
            for line in lines[1:31]:  # top 30
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        "pid": parts[1],
                        "user": parts[0],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "command": parts[10][:60],
                    })
        return {"processes": processes, "count": len(processes)}
    except Exception as e:
        return {"processes": [], "error": str(e)}


@app.post("/api/sandbox/processes/{pid}/kill")
async def sandbox_process_kill(pid: str):
    """Kill a process by PID."""
    import subprocess
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, timeout=5)
        else:
            subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True, timeout=5)
        return {"status": "ok", "killed": pid}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sandbox/exec")
async def sandbox_exec(payload: SandboxPayload, request: Request):
    """Execute a shell command in the sandbox."""
    command = payload.command
    timeout = payload.timeout
    # Rate limiting
    from fastapi.responses import JSONResponse as _JR2
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return _JR2(status_code=429, content={"stdout": "", "stderr": "Rate limited — 30 req/min max", "exit_code": -1, "mode": "auto"})

    sandbox = get_sandbox()
    result = sandbox.execute(command, timeout)
    return result


@app.get("/api/sandbox/files")
async def sandbox_files(path: str = "."):
    """Get file tree."""
    sandbox = get_sandbox()
    return sandbox.file_tree(path)


@app.post("/api/sandbox/screenshot")
async def sandbox_screenshot():
    """Take a browser screenshot."""
    sandbox = get_sandbox()
    return sandbox.screenshot()


# ── WebSocket ───────────────────────────────────────────────

# ── Dashboard ────────────────────────────────────────────
_dashboard: Any = None

def get_dashboard() -> Any:
    global _dashboard
    if _dashboard is None:
        from scripts.web.dashboard import Dashboard
        _dashboard = Dashboard()
    return _dashboard


@app.get("/api/dashboard")
async def api_dashboard() -> dict:
    """Full system dashboard."""
    return get_dashboard().computer_info()


@app.get("/api/dashboard/cron")
async def api_cron() -> list[dict]:
    jobs = get_dashboard().cron_jobs()
    if not isinstance(jobs, list):
        return []
    return jobs


@app.post("/api/dashboard/cron")
async def api_cron_create(request: Request) -> dict:
    data = await request.json()
    return get_dashboard().cron_create(data.get("schedule", ""), data.get("prompt", ""))


@app.delete("/api/dashboard/cron/{job_id}")
async def api_cron_delete(job_id: str) -> dict:
    return get_dashboard().cron_delete(job_id)


@app.post("/api/dashboard/cron/{job_id}/toggle")
async def api_cron_toggle(job_id: str) -> dict:
    return get_dashboard().cron_toggle(job_id)


# ── Frontend-facing Cron aliases (nexus.js calls /api/cron/*) ──

@app.post("/api/cron")
async def api_cron_create_frontend(request: Request):
    data = await request.json()
    # Frontend sends raw minutes (5, 15, 30, 60, 360, 1440)
    # Parser requires unit suffix like "5m" or "1h"
    interval_minutes = int(data.get("interval", 60))
    if interval_minutes >= 60 and interval_minutes % 60 == 0:
        schedule = f"{interval_minutes // 60}h"
    else:
        schedule = f"{interval_minutes}m"
    return get_dashboard().cron_create(
        schedule=schedule,
        prompt=data.get("command", "") or data.get("name", ""),
    )


@app.post("/api/cron/{job_id}/toggle")
async def api_cron_toggle_frontend(job_id: str) -> dict:
    return get_dashboard().cron_toggle(job_id)


@app.delete("/api/cron/{job_id}")
async def api_cron_delete_frontend(job_id: str) -> dict:
    return get_dashboard().cron_delete(job_id)


@app.get("/api/dashboard/background")
async def api_background() -> list[dict]:
    tasks = get_dashboard().background_tasks()
    if not isinstance(tasks, list):
        return []
    return tasks


@app.get("/api/dashboard/agents")
async def api_agents() -> list[dict]:
    agents = get_dashboard().sub_agents()
    if not isinstance(agents, list):
        return []
    return agents


@app.get("/api/dashboard/memories")
async def api_memories() -> list[dict]:
    mems = get_dashboard().memories()
    if not isinstance(mems, list):
        return []
    return mems


@app.get("/api/dashboard/sessions")
async def api_sessions(q: str = "") -> list[dict]:
    if q:
        return get_dashboard().sessions_search(q)
    sessions = get_dashboard().sessions()
    if not isinstance(sessions, list):
        return []
    return sessions


@app.get("/api/dashboard/activity")
async def api_activity(limit: int = 50) -> list[dict]:
    feed = get_dashboard().activity_feed(limit)
    if not isinstance(feed, list):
        return []
    return feed


@app.get("/api/dashboard/gateway")
async def api_gateway() -> dict:
    return get_dashboard().gateway_status()


@app.post("/api/gateway/start")
async def api_gateway_start(request: Request) -> dict:
    """Start a gateway platform (telegram/discord/sms) with credentials."""
    data = await request.json()
    platform = data.get("platform", "")
    token = data.get("token", "")
    if not platform or not token:
        return {"status": "error", "message": "Platform and token required"}
    try:
        from core.gateway import GatewayCore
        gw = globals().get("_gateway")
        if gw is None:
            gw = GatewayCore()
            def _gh(msg) -> str:
                try:
                    chat = get_chat()
                    r = chat.chat(msg.text, history=[])
                    return r.get("content", "") or r.get("error", "No response")
                except Exception as e:
                    return f"Error: {e}"
            gw.set_handler(_gh)
            globals()["_gateway"] = gw
        gw.start_platform(platform, token=token)
        return {"status": "ok", "message": f"{platform} started"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/gateway/stop")
async def api_gateway_stop(request: Request) -> dict:
    """Stop a gateway platform."""
    data = await request.json()
    platform = data.get("platform", "")
    try:
        gw = globals().get("_gateway")
        if gw:
            gw.stop_platform(platform)
        return {"status": "ok", "message": f"{platform} stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Settings ────────────────────────────────────────────

@app.get("/api/settings")
async def api_settings() -> dict:
    return get_dashboard().get_settings()


@app.post("/api/settings")
async def api_settings_update(payload: SettingsPayload) -> dict:
    data = payload.model_dump(exclude_none=True)
    result = get_dashboard().update_settings(data)
    if result.get("status") == "ok":
        refresh_chat()
        try:
            from core.activity import add as add_event
            provider = data.get("provider", {})
            changed = []
            if "model" in provider:
                changed.append(f"model={provider['model']}")
            if "name" in provider:
                changed.append(f"provider={provider['name']}")
            if "temperature" in data:
                changed.append(f"temp={data['temperature']}")
            add_event("settings_change", detail=", ".join(changed) or "settings updated",
                      icon="fa-sliders", agent="system", status="done")
        except Exception:
            pass
    return result


@app.get("/api/settings/models")
async def api_settings_models(provider: str = "opencode-zen"):
    return get_dashboard().get_provider_models(provider)


@app.get("/api/dashboard/skills")
async def api_skills():
    return get_dashboard().skills()


# ── Session Save / Load / Export (multi-tenant aware — Task 4.2) ──
# When multi-tenancy is enabled (WIDDX_TENANT_MODE), sessions live in
# the tenant's isolated database file; otherwise legacy behavior
# (shared dashboard store) is preserved for backward compatibility.

def _tenant_session_save(tenant: str, name: str, messages: list) -> dict:
    try:
        db = get_tenant_db(tenant)
        session_id = db.create_session(name)
        for msg in messages or []:
            role = str(msg.get("role", "user"))
            content = str(msg.get("content", ""))
            if content:
                db.add_message(session_id, role, content, msg.get("tool_calls"))
        from core.telemetry import record
        record("session_save", dims={"source": "web", "kind": "tenant"})
        return {"id": session_id, "status": "saved", "tenant": tenant}
    except Exception as e:
        return {"error": str(e)}


def _tenant_sessions_list(tenant: str) -> list[dict]:
    try:
        return get_tenant_db(tenant).list_sessions(limit=50)
    except Exception:
        return []


def _tenant_session_load(tenant: str, session_id: str) -> dict:
    db = get_tenant_db(tenant)
    session = db.get_session(session_id)
    if not session:
        return {"error": "Session not found", "tenant": tenant}
    messages = db.get_messages(session_id)
    return {"session": session, "messages": messages, "tenant": tenant}


def _tenant_session_delete(tenant: str, session_id: str) -> dict:
    try:
        get_tenant_db(tenant).delete_session(session_id)
        return {"status": "deleted", "tenant": tenant}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/sessions")
async def api_session_save(payload: SessionPayload, request: Request):
    if tenancy_enabled():
        return _tenant_session_save(get_tenant(request), payload.name, payload.messages)
    return get_dashboard().session_save(payload.name, payload.messages)


@app.get("/api/sessions")
async def api_sessions_list(request: Request):
    if tenancy_enabled():
        return _tenant_sessions_list(get_tenant(request))
    return get_dashboard().sessions()


@app.get("/api/sessions/{session_id}")
async def api_session_load(session_id: str, request: Request):
    if tenancy_enabled():
        return _tenant_session_load(get_tenant(request), session_id)
    return get_dashboard().session_load(session_id)


@app.delete("/api/sessions/{session_id}")
async def api_session_delete(session_id: str, request: Request):
    if tenancy_enabled():
        return _tenant_session_delete(get_tenant(request), session_id)
    return get_dashboard().session_delete(session_id)


@app.get("/api/sessions/{session_id}/export")
async def api_session_export(session_id: str, request: Request):
    if tenancy_enabled():
        return _tenant_session_load(get_tenant(request), session_id)
    return get_dashboard().session_export(session_id)


# ── Memory CRUD (multi-tenant aware — Task 4.2) ───────────

def _tenant_memory_create(tenant: str, content: str, tags: str) -> dict:
    try:
        db = get_tenant_db(tenant)
        tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
        memory_id = db.add_memory(
            name=(content[:60] or "memory"),
            content=content,
            memory_type="general",
            tags=tag_list,
        )
        from core.telemetry import record
        record("memory_create", dims={"source": "web", "kind": "tenant"})
        return {"id": memory_id, "status": "created", "tenant": tenant}
    except Exception as e:
        return {"error": str(e)}


def _tenant_memory_search(tenant: str, query: str) -> list[dict]:
    try:
        db = get_tenant_db(tenant)
        if not query:
            return db.list_memories(limit=50)
        return db.search_memories(query, limit=20)
    except Exception:
        return []


def _tenant_memory_delete(tenant: str, memory_id: str) -> dict:
    try:
        get_tenant_db(tenant).delete_memory(memory_id)
        return {"status": "deleted", "tenant": tenant}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/memories")
async def api_memory_create(payload: MemoryPayload, request: Request):
    if tenancy_enabled():
        return _tenant_memory_create(get_tenant(request), payload.content, payload.tags)
    return get_dashboard().memory_create(payload.content, payload.tags)


@app.get("/api/memories/search")
async def api_memory_search(request: Request, q: str = ""):
    if tenancy_enabled():
        return _tenant_memory_search(get_tenant(request), q)
    return get_dashboard().memory_search(q)


@app.delete("/api/memories/{memory_id}")
async def api_memory_delete(memory_id: str, request: Request):
    if tenancy_enabled():
        return _tenant_memory_delete(get_tenant(request), memory_id)
    return get_dashboard().memory_delete(memory_id)


# ── NEW: MCP Management ────────────────────────────────────

@app.get("/api/mcp")
async def api_mcp_status():
    return get_dashboard().mcp_status()


@app.post("/api/mcp")
async def api_mcp_add(request: Request):
    data = await request.json()
    return get_dashboard().mcp_add(data.get("name", ""), data.get("command", ""), data.get("args", []))


@app.delete("/api/mcp/{name}")
async def api_mcp_remove(name: str):
    return get_dashboard().mcp_remove(name)


@app.post("/api/mcp/{name}/restart")
async def api_mcp_restart(name: str):
    return get_dashboard().mcp_restart(name)


# ── NEW: Proxy Settings ────────────────────────────────────

@app.get("/api/proxy")
async def api_proxy_status():
    return get_dashboard().proxy_status()


@app.post("/api/proxy")
async def api_proxy_update(request: Request):
    data = await request.json()
    return get_dashboard().proxy_update(
        http=data.get("http", ""),
        https=data.get("https", ""),
        enabled=data.get("enabled", False),
    )


# ── NEW: Permissions ──────────────────────────────────────

@app.get("/api/permissions")
async def api_permissions_status():
    return get_dashboard().permissions_status()


@app.post("/api/permissions")
async def api_permissions_set(request: Request):
    data = await request.json()
    return get_dashboard().permissions_set(data.get("level", "normal"))


# ── NEW: GGUF Models ──────────────────────────────────────

@app.get("/api/gguf")
async def api_gguf_models():
    return get_dashboard().gguf_models()


@app.post("/api/gguf/load")
async def api_gguf_load(request: Request):
    data = await request.json()
    return get_dashboard().gguf_load(data.get("path", ""))


@app.post("/api/gguf/unload")
async def api_gguf_unload():
    return get_dashboard().gguf_unload()


# ── NEW: Debug / Doctor ───────────────────────────────────

@app.get("/api/debug")
async def api_debug():
    return get_dashboard().debug_info()


@app.get("/api/doctor")
async def api_doctor():
    return get_dashboard().doctor_check()


# ── NEW: Manifest ─────────────────────────────────────────

@app.get("/api/manifest")
async def api_manifest():
    return get_dashboard().manifest_status()


@app.post("/api/manifest/scan")
async def api_manifest_scan():
    return get_dashboard().manifest_scan()


# ── NEW: Git ──────────────────────────────────────────────

@app.get("/api/git")
async def api_git_status():
    return get_dashboard().git_status()


@app.get("/api/git/branches")
async def api_git_branches():
    return get_dashboard().git_branches()


@app.post("/api/git/undo")
async def api_git_undo():
    return get_dashboard().git_undo()


@app.post("/api/git/commit")
async def api_git_commit(request: Request):
    data = await request.json()
    return get_dashboard().git_commit(
        message=data.get("message", "Auto-commit from WIDDX Nexus"),
        files=data.get("files"),
    )


@app.post("/api/git/push")
async def api_git_push():
    return get_dashboard().git_push()


@app.post("/api/git/pull")
async def api_git_pull():
    return get_dashboard().git_pull()


@app.post("/api/git/branch")
async def api_git_branch(request: Request):
    data = await request.json()
    return get_dashboard().git_branch_create(
        name=data.get("name", ""),
        from_branch=data.get("from"),
    )


@app.post("/api/git/checkout")
async def api_git_checkout(request: Request):
    data = await request.json()
    return get_dashboard().git_checkout(branch=data.get("branch", ""))


@app.get("/api/git/diff")
async def api_git_diff(file: str = ""):
    return get_dashboard().git_diff(file)


# ── NEW: Token Budget ─────────────────────────────────────

@app.get("/api/token-budget")
async def api_token_budget():
    return get_dashboard().token_budget()


@app.post("/api/token-budget/reset")
async def api_token_budget_reset():
    return get_dashboard().token_budget_reset()


# ── NEW: Checkpoints ──────────────────────────────────────

@app.get("/api/checkpoints")
async def api_checkpoints():
    return get_dashboard().checkpoints_list()


@app.post("/api/checkpoints")
async def api_checkpoint_create():
    return get_dashboard().checkpoint_create()


@app.post("/api/checkpoints/{checkpoint_id}/restore")
async def api_checkpoint_restore(checkpoint_id: str):
    return get_dashboard().checkpoint_restore(checkpoint_id)


@app.delete("/api/checkpoints/{checkpoint_id}")
async def api_checkpoint_delete(checkpoint_id: str):
    return get_dashboard().checkpoint_delete(checkpoint_id)


# ── NEW: Plugins ─────────────────────────────────────────

@app.get("/api/plugins")
async def api_plugins():
    return get_dashboard().plugins_list()


@app.post("/api/plugins/{name}/enable")
async def api_plugin_enable(name: str):
    return get_dashboard().plugin_enable(name)


@app.post("/api/plugins/{name}/disable")
async def api_plugin_disable(name: str):
    return get_dashboard().plugin_disable(name)


# ── NEW: Workflows ───────────────────────────────────────

@app.get("/api/workflows")
async def api_workflows():
    return get_dashboard().workflows_list()


@app.post("/api/workflows")
async def api_workflow_create(request: Request):
    data = await request.json()
    return get_dashboard().workflow_create(data.get("name", ""), data.get("steps", []))


@app.post("/api/workflows/{workflow_id}/run")
async def api_workflow_run(workflow_id: str):
    return get_dashboard().workflow_run(workflow_id)


# ── NEW: Auto-Commit ──────────────────────────────────────

@app.get("/api/autocommit")
async def api_autocommit():
    return get_dashboard().autocommit_status()


@app.post("/api/autocommit/toggle")
async def api_autocommit_toggle():
    return get_dashboard().autocommit_toggle()


# ── NEW: API Keys ─────────────────────────────────────────

@app.get("/api/apikeys")
async def api_apikeys():
    return get_dashboard().apikeys_list()


# ── NEW: Version ──────────────────────────────────────────

@app.get("/api/version")
async def api_version():
    return get_dashboard().app_version()


# ── In-memory rate limiter ────────────────────────────────────
# Simple dict + lock — no disk I/O per request.
# Single-process app (uvicorn with 1 worker) so in-memory is safe.
_RATELIMIT_MAX = 30
_RATELIMIT_WINDOW = 60
_RATELIMIT_STORE: dict[str, list[float]] = {}
_RATELIMIT_LOCK = threading.Lock()


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.time()
    cutoff = now - _RATELIMIT_WINDOW
    with _RATELIMIT_LOCK:
        timestamps = _RATELIMIT_STORE.get(client_ip, [])
        timestamps = [t for t in timestamps if t >= cutoff]
        if len(timestamps) >= _RATELIMIT_MAX:
            _RATELIMIT_STORE[client_ip] = timestamps
            return False
        timestamps.append(now)
        _RATELIMIT_STORE[client_ip] = timestamps
    return True


# ── Endpoints ───────────────────────────────────────────


@app.post("/api/computer/exec")
async def api_computer_exec(request: Request):
    data = await request.json()
    client = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"status": "error", "message": "Rate limited — 30 req/min max"},
            status_code=429,
        )
    return get_dashboard().computer_exec(data.get("command", ""))


@app.get("/api/computer/info")
async def api_computer_info():
    return get_dashboard().computer_info()


# ── WebSocket ───────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for chat — persistent session, non-blocking.

    Receives:  {"message": "...", "history": [...]}
    Sends:     {"type": "text|tool|done|error", "data": "..."}
    Supports cancel: client sends {"type": "cancel"}
    """
    await websocket.accept()
    logger.info("WebSocket connected")
    client = websocket.client.host if websocket.client else "unknown"
    loop = asyncio.get_running_loop()
    stream_task: asyncio.Task | None = None
    cancel_flag = False

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if not _check_rate_limit(client):
                await websocket.send_json({"type": "error", "data": "Rate limited — 30 req/min max"})
                await websocket.send_json({"type": "done", "data": ""})
                continue

            # Handle answer to pending question
            if payload.get("type") == "answer":
                from core.tools.handlers.ask_user import provide_answer
                provide_answer(payload.get("data", ""))
                continue

            # Handle cancellation
            if payload.get("type") == "cancel":
                cancel_flag = True
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                await websocket.send_json({"type": "cancelled", "data": ""})
                await websocket.send_json({"type": "done", "data": ""})
                stream_task = None
                continue

            message = payload.get("message", "")
            # WebSocket message validation — prevent abuse
            if len(message) > 100000:
                await websocket.send_json({"type": "error", "data": "Message too long (max 100,000 characters)"})
                await websocket.send_json({"type": "done", "data": ""})
                continue
            history = payload.get("history", [])
            # Limit history size
            if len(history) > 1000:
                history = history[-1000:]
            cancel_flag = False

            chat = get_chat()
            event_queue: asyncio.Queue = asyncio.Queue()

            # Enable Web mode for ask_user tool
            import os
            os.environ["WIDDX_WEB"] = "1"

            async def _stream_runner():
                """Run chat.chat_stream() in executor, feeding events into the queue."""
                def _sync_run():
                    for event in chat.chat_stream(message, history):
                        if cancel_flag:
                            break
                        # Check for pending questions from ask_user tool (only once per question)
                        from core.tools.handlers.ask_user import get_pending_question, is_question_consumed, mark_question_consumed
                        q = get_pending_question()
                        if q and not is_question_consumed():
                            mark_question_consumed()
                            loop.call_soon_threadsafe(event_queue.put_nowait, {"type": "question", "data": q})
                        loop.call_soon_threadsafe(event_queue.put_nowait, event)
                await loop.run_in_executor(None, _sync_run)

            stream_task = asyncio.create_task(_stream_runner())

            try:
                while not cancel_flag:
                    event = await asyncio.wait_for(event_queue.get(), timeout=600.0)
                    if event["type"] == "done":
                        await websocket.send_json({"type": "done", "data": ""})
                        break
                    await websocket.send_json(event)
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "error",
                    "data": "Response timed out after 10 minutes. The task may be too complex. Try a simpler request or check provider connectivity."
                })
                await websocket.send_json({"type": "done", "data": ""})
            finally:
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                stream_task = None

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
        if stream_task and not stream_task.done():
            stream_task.cancel()
    except Exception as e:
        logger.error("WebSocket error: %s", e)


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for live activity events."""
    await websocket.accept()
    logger.info("Events WS connected")

    try:
        from core.activity import get_store
        store = get_store()
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
        return

    import asyncio

    def send_event(event_dict: dict):
        """Push every new event to this client."""
        try:
            asyncio.get_running_loop().create_task(websocket.send_json(event_dict))
        except Exception:
            pass

    unsubscribe = store.subscribe(send_event)

    try:
        # Keep connection open; client sends keepalive pings
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe()
        logger.info("Events WS disconnected")


# ── Main ────────────────────────────────────────────────────

def run(host: str = "127.0.0.1", port: int = 8000, reload: bool = False, open_browser: bool = True) -> None:
    """Run the Web UI server."""
    import uvicorn

    # ── Ensure listening address is in allowed origins ─────
    for h in (host, "127.0.0.1", "localhost"):
        origin = f"http://{h}:{port}"
        if origin not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(origin)
    # CORSMiddleware already enabled directly at module import for tests & prod.
    # Here we only extend allowed origins; if a middleware already exists,
    # we avoid adding a duplicate (the existing instance shares ALLOWED_ORIGINS list).
    _existing_cors = any(
        getattr(m, "cls", None) == CORSMiddleware
        for m in getattr(app, "user_middleware", [])
    )
    if not _existing_cors and not getattr(run, '_cors_ready', False):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )
        run._cors_ready = True
    else:
        # Mark as ready so future calls also skip
        run._cors_ready = True

    # ── Auto-open browser ──────────────────────────────────
    browse_url = f"http://127.0.0.1:{port}"
    logger.info("─" * 40)
    logger.info("  WIDDX Nexus Mission Control")
    logger.info("  %s", browse_url)
    logger.info("─" * 40)
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(browse_url)
        except Exception:
            pass

    # ── Start background services ──────────────────────────
    try:
        from core.cron.scheduler import CronScheduler
        _scheduler = CronScheduler()
        _scheduler.start()
        logger.info("Cron scheduler started via Web UI")
    except Exception as e:
        logger.warning("Cron scheduler start: %s", e)

    _gateway = None
    try:
        from core.gateway import GatewayCore
        from core._path import ensure_project_root
        ensure_project_root()

        _gateway = GatewayCore()

        # Handler: incoming messages → UIL ChatHandler → response
        def _gateway_handler(msg) -> str:
            try:
                chat = get_chat()
                result = chat.chat(msg.text, history=[])
                return result.get("content", "") or result.get("error", "No response")
            except Exception as exc:
                logger.error("Gateway handler error: %s", exc)
                return f"Error: {exc}"

        _gateway.set_handler(_gateway_handler)
        # Start with tokens from config or env
        import os
        _gateway.start_platform("telegram", token=os.environ.get("TELEGRAM_TOKEN", ""))
        _gateway.start_platform("discord", token=os.environ.get("DISCORD_TOKEN", ""))
        logger.info("Gateway started via Web UI")
    except Exception as e:
        logger.info("Gateway not started: %s", e)

    # ── Startup event ──────────────────────────────────────
    try:
        from core.activity import add as add_event
        add_event("system", detail="WIDDX Nexus Mission Control started",
                  icon="fa-star", agent="system", status="done")
    except Exception:
        pass

    # ── Graceful shutdown (SIGINT/SIGTERM handlers) ─────────
    try:
        from core.background import register_shutdown
        register_shutdown(lambda: logger.info("Web server shutting down..."))
    except Exception:
        pass

    uvicorn.run(
        "scripts.web.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
