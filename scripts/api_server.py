"""WIDDX Nexus — REST API Server.

This script lives in `scripts/` to keep the repository root tidy. It adds the
project root to sys.path before importing the core application logic.
"""

import sys
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
import time  # noqa: E402
import logging  # noqa: E402
import asyncio  # noqa: E402
import os  # noqa: E402
from typing import Literal, Optional  # noqa: E402
from copy import deepcopy  # noqa: E402

from contextlib import asynccontextmanager  # noqa: E402

try:
    from fastapi import FastAPI, HTTPException, Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
except ImportError:
    print("❌ FastAPI required. Install: pip install fastapi uvicorn")
    sys.exit(1)

logger = logging.getLogger("widdx.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

# ── API Security ───────────────────────────────────────────────

_API_KEY: str = os.environ.get("WIDDX_API_KEY", "")
if not _API_KEY:
    logger.warning(
        "WIDDX_API_KEY environment variable is not set.\n"
        "  The API server will REJECT all requests (401 Unauthorized).\n"
        "  Set the key: $env:WIDDX_API_KEY=\"your-secret-key\"   (PowerShell)\n"
        "  Or:        export WIDDX_API_KEY=\"your-secret-key\"    (Bash)\n"
        "  Then restart the server."
    )

security_scheme = HTTPBearer(auto_error=False)


def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> None:
    """Dependency: require valid API key on every endpoint."""
    api_key = os.environ.get("WIDDX_API_KEY", "")
    # Reject everything if the key was never configured
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Server not configured: WIDDX_API_KEY is not set."
        )
    # Normal token check
    if credentials is None or credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ── Rate Limiter (in-memory sliding window) ────────────────────

class RateLimiter:
    """Simple in-memory rate limiter using sliding window."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def check(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        bucket = self._buckets.get(key)
        if bucket is None:
            self._buckets[key] = [now]
            return True
        self._buckets[key] = [t for t in bucket if t > cutoff]
        if len(self._buckets[key]) >= self.max_requests:
            return False
        self._buckets[key].append(now)
        return True


_rate_limiter = RateLimiter()


def rate_limit(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> None:
    """Dependency: apply rate limiting per API key (or IP if no key)."""
    client_id = credentials.credentials if credentials else "anonymous"
    if not _rate_limiter.check(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
from core import tools  # noqa: E402
from core.config.settings import load as load_config, save as save_config  # noqa: E402
from core.providers.providers import (  # noqa: E402
    create_provider, get_available_models,
)
from core.memory import MemoryStore  # noqa: E402
from core.memory_learner import MemoryLearner  # noqa: E402
from core.project import state as project_state  # noqa: E402
from core.project.scanner import ProjectScanner  # noqa: E402
from core.project_tracker import ensure_docs, load_docs, update_doc, build_context_block  # noqa: E402
from core.auto_setup import detect_project_deps  # noqa: E402
from core.skills import skill_manager  # noqa: E402
from core.mcp.client import get_mcp_manager  # noqa: E402
from core.chat import run_stream_turn  # noqa: E402
from core.monitoring import metrics_collector, system_monitor  # noqa: E402

# ── App State ────────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.cfg = load_config()
        self.provider = create_provider(self.cfg)
        self.mcp_mgr = get_mcp_manager()
        self.mcp_mgr.load_from_config(self.cfg)
        self.messages: list[dict] = []
        self.state: dict = {"model": f"{self.provider.name}/{self.provider.model}", "cost": 0.0, "turns": 0}
        self.scanner = ProjectScanner()
        self.chat_lock = asyncio.Lock()

state = AppState()

# ── Pydantic Models ──────────────────────────────────────────
class ChatContext(BaseModel):
    model_config = {"extra": "forbid"}
    file_path: str = Field(default="", max_length=4096)
    file_content: str = Field(default="", max_length=100000)
    selection: str = Field(default="", max_length=100000)

class ChatRequest(BaseModel):
    model_config = {"extra": "forbid"}
    message: str = Field(..., max_length=100000, description="Chat message (max 100K chars)")
    stream: Literal[False] = False
    session_id: Literal["shared"] = "shared"
    context: Optional[ChatContext] = None

class ChatResponse(BaseModel):
    response: str
    model: str
    turns: int
    cost: float
    session_id: Literal["shared"] = "shared"

class ProviderSwitch(BaseModel):
    name: str
    model: Optional[str] = ""
    base_url: Optional[str] = ""

class MemoryFact(BaseModel):
    name: str
    content: str
    type: str = "feedback"

class DocUpdate(BaseModel):
    doc: str  # PLAN.md, DESIGN.md, TASKS.md, ROADMAP.md
    content: str

class ToolExecRequest(BaseModel):
    name: str = Field(..., max_length=100)
    args: dict = Field(default_factory=dict)

class SearchReplaceRequest(BaseModel):
    pattern: str = Field(..., max_length=5000)
    replacement: str = Field(..., max_length=50000)
    include: Optional[str] = None
    path: Optional[str] = None
    preview: bool = True

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., max_length=1000)
    path: Optional[str] = None
    include: Optional[str] = None
    top_k: int = 10

class RenameRequest(BaseModel):
    symbol: str = Field(..., max_length=500)
    new_name: str = Field(..., max_length=500)
    path: Optional[str] = None
    include: Optional[str] = None
    preview: bool = True

class DepGraphRequest(BaseModel):
    path: Optional[str] = None
    include: Optional[str] = None
    depth: int = 2
    format: str = "text"

class DockerRequest(BaseModel):
    action: str = Field(..., max_length=50)
    what: Optional[str] = None
    image: Optional[str] = None
    tag: str = "latest"
    name: Optional[str] = None
    path: Optional[str] = None
    dockerfile: Optional[str] = None
    ports: Optional[str] = None
    detach: bool = True
    command: Optional[str] = None
    container_id: Optional[str] = None
    force: bool = False
    tail: int = 50
    compose_file: Optional[str] = None
    compose_action: Optional[str] = None

class DbQueryRequest(BaseModel):
    db_path: Optional[str] = None
    query: str = ""
    type: str = "sqlite"
    conn_str: Optional[str] = None
    action: str = "query"
    table: Optional[str] = None
    max_rows: int = 50
    format: str = "text"

class ApiRequest(BaseModel):
    method: str = "GET"
    url: str = ""
    headers: Optional[dict] = None
    body: Optional[str] = None
    params: Optional[dict] = None
    timeout: int = 30
    follow_redirects: bool = True

class PkgMgrRequest(BaseModel):
    action: str = "detect"
    package: str = ""
    pkg_manager: str = "auto"
    path: Optional[str] = None

class TerminalRequest(BaseModel):
    action: str = "list"
    name: Optional[str] = None
    command: Optional[str] = None
    cwd: Optional[str] = None

class AskUserRequest(BaseModel):
    question: str

# ── FastAPI App ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    state.cfg = load_config()
    state.provider = create_provider(state.cfg)
    state.state["model"] = f"{state.provider.name}/{state.provider.model}"
    # Start MCP manager so tools are available
    try:
        state.mcp_mgr.load_from_config(state.cfg)
        state.mcp_mgr.start()
        logger.info("MCP manager started — %d servers", state.mcp_mgr.server_count)  # type: ignore[attr-defined,unused-ignore]
    except Exception as e:
        logger.warning("MCP manager start skipped: %s", e)
    ensure_docs(Path.cwd().resolve())
    logger.info("WIDDX API started — provider: %s/%s", state.provider.name, state.provider.model)
    yield
    # Shutdown
    try:
        state.mcp_mgr.stop()
    except Exception:
        pass

app = FastAPI(
    title="WIDDX Nexus API",
    version="3.0.0",
    description="REST API for WIDDX Nexus — Terminal AI Engineering Assistant",
    lifespan=lifespan,
)

# Restrict CORS to local origins by default; override via WIDDX_CORS_ORIGINS env var
_allowed_origins = os.environ.get("WIDDX_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Monitoring Middleware (performance tracking on every request) ──

from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware  # noqa: E402
from starlette.requests import Request as _Request  # noqa: E402

class _MonitoringMiddleware(_BaseHTTPMiddleware):
    """Tracks request latency and error rates via metrics_collector."""
    async def dispatch(self, request: _Request, call_next):
        endpoint = request.url.path
        with metrics_collector.track_request(endpoint) as tracker:
            try:
                response = await call_next(request)
                if response.status_code >= 400:
                    tracker.error = True
                return response
            except Exception:
                tracker.error = True
                raise

app.add_middleware(_MonitoringMiddleware)

# ── Request size limit (ISS-004) ──────────────────────────────
_MAX_BODY_BYTES = int(os.environ.get("WIDDX_MAX_BODY_BYTES", 1_048_576))  # 1 MB default

from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402

class _BodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds _MAX_BODY_BYTES."""
    async def dispatch(self, request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body exceeds {_MAX_BODY_BYTES} bytes limit."},
            )
        return await call_next(request)

app.add_middleware(_BodySizeMiddleware)

# ─── Rate Limit Headers Middleware ────────────────────────────
# يضيف X-RateLimit-* headers لكل استجابة
from starlette.middleware.base import BaseHTTPMiddleware as _RateLimitMiddlewareBase  # noqa: E402
from starlette.requests import Request as _RateLimitRequest  # noqa: E402

class _RateLimitHeadersMiddleware(_RateLimitMiddlewareBase):
    """Adds X-RateLimit-* headers to every API response."""
    async def dispatch(self, request: _RateLimitRequest, call_next):
        response = await call_next(request)
        client_id = (
            request.headers.get("authorization", "").replace("Bearer ", "")[:20]
            or request.client.host if request.client else "unknown"
        )
        # Check remaining budget
        remaining = max(0, _rate_limiter.max_requests - len(
            _rate_limiter._buckets.get(client_id, [])
        ))
        response.headers["X-RateLimit-Limit"] = str(_rate_limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + _rate_limiter.window))
        return response

app.add_middleware(_RateLimitHeadersMiddleware)

# ─── Readiness & Liveness Probes ─────────────────────────────
@app.get("/api/livez")
async def liveness():
    """Kubernetes liveness probe — checks if the process is alive.
    No auth required — this is called by the orchestrator."""
    return {"status": "alive", "timestamp": time.time()}

@app.get("/api/ready")
async def readiness():
    """Kubernetes readiness probe — checks if the server can handle traffic.
    No auth required — this is called by the orchestrator."""
    # Check MCP manager
    try:
        if state.mcp_mgr and hasattr(state.mcp_mgr, 'server_count'):
            mcp_ready = state.mcp_mgr.server_count >= 0
        else:
            mcp_ready = True
    except Exception:
        mcp_ready = False

    mem = system_monitor.get_memory_usage()

    return {
        "status": "ready" if mcp_ready else "degraded",
        "mcp_ready": mcp_ready,
        "memory_mb": round(mem.get("rss_mb", 0), 1),
        "uptime_seconds": metrics_collector.report(detailed=False).get("uptime_seconds", 0),
        "timestamp": time.time(),
    }

# ─── Prometheus Metrics ──────────────────────────────────────
# Re-export core.monitoring metrics in Prometheus format
@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint — returns metrics in text format.
    No auth required for Prometheus scraping."""
    from core.monitoring import metrics_collector as _mc
    report = _mc.report(detailed=True)

    lines = [
        "# HELP widdx_uptime_seconds Total uptime of the server",
        "# TYPE widdx_uptime_seconds gauge",
        f"widdx_uptime_seconds {report.get('uptime_seconds', 0)}",
        "",
        "# HELP widdx_requests_total Total number of HTTP requests",
        "# TYPE widdx_requests_total counter",
        f"widdx_requests_total {report.get('total_requests', 0)}",
        "",
        "# HELP widdx_errors_total Total number of HTTP errors",
        "# TYPE widdx_errors_total counter",
        f"widdx_errors_total {report.get('total_errors', 0)}",
        "",
        "# HELP widdx_error_rate Error rate (0.0-1.0)",
        "# TYPE widdx_error_rate gauge",
        f"widdx_error_rate {report.get('error_rate', 0.0)}",
        "",
    ]

    # Per-endpoint metrics
    endpoints = report.get("endpoints", {})
    for name, m in endpoints.items():
        lines.append(f"# HELP widdx_endpoint_calls_total Total calls to {name}")
        lines.append("# TYPE widdx_endpoint_calls_total counter")
        lines.append(f'widdx_endpoint_calls_total{{endpoint="{name}"}} {m["calls"]}')
        lines.append(f'# HELP widdx_endpoint_errors_total Total errors for {name}')
        lines.append('# TYPE widdx_endpoint_errors_total counter')
        lines.append(f'widdx_endpoint_errors_total{{endpoint="{name}"}} {m["errors"]}')
        lines.append("")

    # Per-tool metrics
    tools_data = report.get("tools", {})
    for name, m in tools_data.items():
        lines.append(f"# HELP widdx_tool_calls_total Total calls to tool {name}")
        lines.append("# TYPE widdx_tool_calls_total counter")
        lines.append(f'widdx_tool_calls_total{{tool="{name}"}} {m["calls"]}')
        p = m.get("percentiles", {})
        lines.append(f'widdx_tool_duration_seconds{{tool="{name}",quantile="0.5"}} {p.get("p50", 0)}')
        lines.append(f'widdx_tool_duration_seconds{{tool="{name}",quantile="0.95"}} {p.get("p95", 0)}')
        lines.append(f'widdx_tool_duration_seconds{{tool="{name}",quantile="0.99"}} {p.get("p99", 0)}')
        lines.append("")

    # System metrics
    mem = system_monitor.get_memory_usage()
    lines.append("# HELP widdx_memory_rss_bytes Resident memory in bytes")
    lines.append("# TYPE widdx_memory_rss_bytes gauge")
    lines.append(f"widdx_memory_rss_bytes {mem.get('rss_mb', 0) * 1024 * 1024}")
    lines.append("")

    return Response(
        content="\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )

# ─── Health ──────────────────────────────────────────────────
@app.get("/api/health")
async def health(_rl=Depends(rate_limit)):
    mem = system_monitor.get_memory_usage()
    cpu = system_monitor.get_cpu_usage()
    metrics = metrics_collector.report(detailed=False)
    return {
        "status": "ok",
        "version": "3.0.0",
        "provider": state.provider.name,
        "model": state.provider.model,
        "turns": state.state.get("turns", 0),
        "cost": state.state.get("cost", 0.0),
        "system": {
            "memory_rss_mb": round(mem.get("rss_mb", 0), 1),
            "memory_vms_mb": round(mem.get("vms_mb", 0), 1),
            "cpu_count": cpu.get("count", 0),
        },
        "performance": {
            "total_requests": metrics.get("total_requests", 0),
            "error_rate": metrics.get("error_rate", 0.0),
            "requests_per_second": metrics.get("requests_per_second", 0.0),
            "uptime_seconds": metrics.get("uptime_seconds", 0),
        },
    }

# ─── Performance Monitoring ──────────────────────────────────
@app.get("/api/monitoring")
async def get_monitoring(_auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    """Return detailed performance metrics and system health."""
    perf = metrics_collector.report(detailed=True)
    mem = system_monitor.get_memory_usage()
    cpu = system_monitor.get_cpu_usage()
    return {
        "performance": perf,
        "system": {
            "memory": mem,
            "cpu": cpu,
        },
    }

# ─── Chat ────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    async with state.chat_lock:
        task = asyncio.create_task(_chat(req))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                raise


async def _chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "message is required")

    msgs = deepcopy(state.messages)
    if not any(m.get("role") == "system" for m in msgs):
        from core.constants import SYSTEM_PROMPT
        sn = ", ".join(s.name for s in skill_manager.list_all()) or "none"
        msgs.insert(0, {"role": "system", "content": SYSTEM_PROMPT.replace("{skills_list}", sn)})

    try:
        ctx = state.scanner.build_context_block()
        if ctx:
            msgs = [m for m in msgs if not m.get("_project_context")]
            msgs.insert(0, {"role": "system", "content": ctx, "_project_context": True})
    except Exception as e:
        logger.debug("Scanner context skipped: %s", e)

    try:
        pt_ctx = build_context_block(Path.cwd().resolve())
        if pt_ctx:
            msgs = [m for m in msgs if not m.get("_project_docs")]
            msgs.insert(0, {"role": "system", "content": pt_ctx, "_project_docs": True})
    except Exception as e:
        logger.debug("Project docs context skipped: %s", e)

    try:
        ml = MemoryLearner(provider=state.provider)
        mem_ctx = ml.load_relevant(req.message)
        if mem_ctx:
            msgs = [m for m in msgs if not m.get("_memory_context")]
            msgs.insert(0, {"role": "system", "content": mem_ctx, "_memory_context": True})
    except Exception as e:
        logger.debug("Memory context skipped: %s", e)

    content = req.message
    if req.context:
        parts = [content, "Editor context (user-provided):"]
        if req.context.file_path:
            parts.append(f"File: {req.context.file_path}")
        if req.context.file_content:
            parts.append(f"File content:\n{req.context.file_content}")
        if req.context.selection:
            parts.append(f"Selection:\n{req.context.selection}")
        content = "\n\n".join(parts)
    msgs.append({"role": "user", "content": content})

    td = list(tools.TOOL_DEFINITIONS)
    try:
        td.extend(state.mcp_mgr.get_all_tool_definitions())
    except Exception as e:
        logger.debug("MCP tool defs skipped: %s", e)

    try:
        msgs_out, state_out = await asyncio.to_thread(
            run_stream_turn, state.provider, msgs, deepcopy(state.state), td, deepcopy(state.cfg)
        )
    except Exception:
        raise HTTPException(500, "Chat failed. Please retry.") from None

    last_content = ""
    for m in reversed(msgs_out):
        if m.get("role") == "assistant":
            last_content = m.get("content", "")
            break

    state.messages = msgs_out
    state.state = state_out

    try:
        project_state.save_session(state.messages, state.state)
    except Exception as e:
        logger.debug("Session save skipped: %s", e)

    return ChatResponse(
        response=last_content or "",
        model=state.state.get("model", ""),
        turns=state.state.get("turns", 0),
        cost=state.state.get("cost", 0.0),
    )

# ─── Providers ───────────────────────────────────────────────────
@app.get("/api/providers")
async def list_providers(_auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    return {
        "current": state.provider.name,
        "model": state.provider.model,
        "available": ["opencode-zen", "ollama", "deepseek", "openai", "gguf"],
        "models": get_available_models(state.provider.name, state.provider.base_url, force_refresh=True),
    }

@app.post("/api/providers/switch")
async def switch_provider(req: ProviderSwitch, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    async with state.chat_lock:
        return _switch_provider(req)


def _switch_provider(req: ProviderSwitch):
    try:
        new_provider = create_provider({
            "provider": {
                "name": req.name,
                "model": req.model or "",
                "base_url": req.base_url or "",
            }
        })
        state.provider = new_provider
        state.state["model"] = f"{new_provider.name}/{new_provider.model}"
        state.cfg["provider"] = {"name": req.name, "model": new_provider.model}
        save_config(state.cfg)
        return {"status": "ok", "provider": new_provider.name, "model": new_provider.model}
    except Exception as e:
        raise HTTPException(400, f"Failed to switch provider: {e}")

@app.get("/api/sessions")
async def list_sessions(_auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    async with state.chat_lock:
        return {"session_id": "shared", "messages": len(state.messages), "turns": state.state.get("turns", 0)}

@app.delete("/api/sessions")
async def clear_session(_auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    async with state.chat_lock:
        state.messages = []
        state.state = {"model": f"{state.provider.name}/{state.provider.model}", "turns": 0, "cost": 0.0}
        try:
            project_state.save_session(state.messages, state.state)
        except Exception as e:
            logger.debug("Session save skipped: %s", e)
        return {"status": "cleared", "session_id": "shared"}

@app.get("/api/memory")
async def list_memory(query: str = "", _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    mem = MemoryStore()
    if query:
        return {"facts": mem.search(query)}
    return {"facts": mem.list_all(), "total": mem.total()}

@app.post("/api/memory")
async def save_memory(fact: MemoryFact, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    mem = MemoryStore()
    mem.save(fact.name, fact.content, {"type": fact.type})
    return {"status": "saved", "name": fact.name}

@app.delete("/api/memory/{name}")
async def delete_memory(name: str, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    mem = MemoryStore()
    if mem.delete(name):
        return {"status": "deleted"}
    raise HTTPException(404, f"Memory '{name}' not found")

@app.get("/api/tools")
async def list_tools(_auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    base = [{"name": t["name"], "description": t.get("description", "")[:100]} for t in tools.TOOL_DEFINITIONS]
    try:
        mcp_tools = [{"name": t["name"], "description": t.get("description", "")[:100]} for t in state.mcp_mgr.get_all_tool_definitions()]
    except Exception:
        mcp_tools = []
    return {"base": base, "mcp": mcp_tools, "total": len(base) + len(mcp_tools)}

@app.post("/api/tools/execute")
async def tool_execute(req: ToolExecRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills(req.name, req.args)
        return {"status": "ok", "name": req.name, "result": result}
    except Exception as e:
        raise HTTPException(400, f"Tool execution failed: {e}")

@app.post("/api/tools/search-replace")
async def tool_search_replace(req: SearchReplaceRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("search_replace", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"search_replace failed: {e}")

@app.post("/api/tools/semantic-search")
async def tool_semantic_search(req: SemanticSearchRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("semantic_search", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"semantic_search failed: {e}")

@app.post("/api/tools/rename")
async def tool_rename(req: RenameRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("rename_symbol", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"rename_symbol failed: {e}")

@app.post("/api/tools/dep-graph")
async def tool_dep_graph(req: DepGraphRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("dep_graph", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"dep_graph failed: {e}")

@app.post("/api/tools/docker")
async def tool_docker(req: DockerRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("docker", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"docker failed: {e}")

@app.post("/api/tools/db-query")
async def tool_db_query(req: DbQueryRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("db_query", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"db_query failed: {e}")

@app.post("/api/tools/api-request")
async def tool_api_request(req: ApiRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("api_request", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"api_request failed: {e}")

@app.post("/api/tools/pkg-mgr")
async def tool_pkg_mgr(req: PkgMgrRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("pkg_mgr", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"pkg_mgr failed: {e}")

@app.post("/api/tools/terminal")
async def tool_terminal(req: TerminalRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.dispatch import execute_with_skills
    try:
        result = execute_with_skills("terminal", req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"terminal failed: {e}")

@app.post("/api/tools/ask")
async def tool_ask_user(req: AskUserRequest, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    from core.tools.handlers.ask_user import _ask_user
    try:
        result = _ask_user(req.question)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(400, f"ask_user failed: {e}")

@app.get("/api/project/docs")
async def get_docs(_auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    return load_docs(Path.cwd().resolve())

@app.post("/api/project/docs")
async def update_docs(update: DocUpdate, _auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    valid = ("PLAN.md", "DESIGN.md", "TASKS.md", "ROADMAP.md")
    if update.doc not in valid:
        raise HTTPException(400, f"Invalid doc. Use: {', '.join(valid)}")
    ok = update_doc(Path.cwd().resolve(), update.doc, update.content)
    if ok:
        return {"status": "updated", "doc": update.doc}
    raise HTTPException(500, "Failed to update doc")

@app.get("/api/project/status")
async def project_status(_auth=Depends(verify_api_key), _rl=Depends(rate_limit)):
    ctx = state.scanner.build_context_block()
    deps = detect_project_deps(Path.cwd().resolve())
    return {
        "context": ctx,
        "dependencies": {k: bool(v) for k, v in deps.items()},
    }

def main():
    try:
        from core.diagnostics import error_collector
        error_collector.enable()
    except Exception:
        pass
    import uvicorn

    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000
    host = os.environ.get("WIDDX_API_HOST", "127.0.0.1")
    log_level = os.environ.get("WIDDX_LOG_LEVEL", "info").lower()

    # ── Graceful Shutdown ──────────────────────────────
    # uvicorn handles SIGTERM/SIGINT by default, but we configure
    # timeout_graceful_shutdown to allow in-flight requests to complete
    print(f"🚀 WIDDX API running at http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print("   Graceful shutdown timeout: 30s")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        timeout_graceful_shutdown=30,  # max seconds to wait for in-flight requests
    )


if __name__ == "__main__":
    main()
