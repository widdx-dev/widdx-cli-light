"""MCP (Model Context Protocol) client — connect to MCP servers and expose their tools.

Uses direct subprocess-based JSON-RPC communication over stdio (no asyncio).

Phase 3 enhancements:
  - Dynamic loading: add/remove servers at runtime
  - Auto-discovery: scan npm/uvx + .widdx/mcp.json
  - OAuth token storage for authenticated servers
  - Auto-reconnect with exponential backoff
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time


def _setup_windows_job(proc) -> bool:
    """Assign a Windows subprocess to a Job Object with resource limits.
    
    Uses ctypes to create a job with 512MB memory, 5min CPU, and
    kill-on-close limits. Returns True if successful.
    """
    try:
        import ctypes
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            return False
        kernel32 = win_dll('kernel32', use_last_error=True)
        
        JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
        JOB_OBJECT_LIMIT_JOB_TIME = 0x00000004
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
        
        # Create job object
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return False
        
        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("ChildProcessCount", wintypes.DWORD),
                ("MaxMemoryLimit", ctypes.c_size_t),
            ]
        
        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", ctypes.c_ulonglong * 3),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]
        
        # 5 min CPU in 100ns ticks
        five_min_ns = -5 * 60 * 10_000_000
        
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_JOB_TIME |
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
            JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
            JOB_OBJECT_LIMIT_PROCESS_MEMORY
        )
        info.BasicLimitInformation.PerJobUserTimeLimit = wintypes.LARGE_INTEGER(five_min_ns)
        info.BasicLimitInformation.ActiveProcessLimit = 1
        info.ProcessMemoryLimit = 512 * 1024 * 1024  # 512 MB
        info.JobMemoryLimit = 512 * 1024 * 1024
        
        JobObjectExtendedLimitInformation = 9
        kernel32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info)
        )
        
        # Assign process (must be created suspended)
        pid = proc.pid if hasattr(proc, 'pid') else proc._proc.pid if hasattr(proc, '_proc') else 0
        windll = getattr(ctypes, "windll", None)
        if pid and windll is not None and not kernel32.AssignProcessToJobObject(
            job, ctypes.wintypes.HANDLE(windll.kernel32.OpenProcess(0x40000, False, pid))
        ):
            return False
        
        return True
    except Exception:
        return False


def _mcp_resource_limits():
    """Apply resource limits to MCP subprocess (Unix only).
    Limits: 512MB memory, 300s CPU, 256 open files.
    """
    if sys.platform == "win32":
        return
    try:
        import resource
    except ImportError:
        return
    try:
        # 512 MB virtual memory
        resource.setrlimit(resource.RLIMIT_AS,
                           (512 * 1024 * 1024, 512 * 1024 * 1024))
        # 5 minutes CPU time
        resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
        # 256 open file descriptors
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    except (AttributeError, ValueError, OSError):
        pass  # restricted environment — skip
CREATE_NO_WINDOW = 0x08000000  # Windows only; defined here for cross-platform type safety
import base64  # noqa: E402
import hashlib  # noqa: E402
import socket  # noqa: E402
import uuid  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Optional, TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

logger = logging.getLogger("widdx.mcp")


PROJECT_ROOT = str(Path(__file__).parent.parent.parent.resolve()).replace("\\", "/")
USER_HOME = os.environ.get("USERPROFILE", "").replace("\\", "/") or os.environ.get("HOME", "")

DEFAULT_MCP_SERVERS = [
    {"name": "filesystem", "command": "node",
     "args": ["{PROJECT_ROOT}/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js", "{CWD}"]},
    {"name": "memory", "command": "node",
     "args": ["{PROJECT_ROOT}/node_modules/@modelcontextprotocol/server-memory/dist/index.js"]},
    {"name": "fetch", "command": "uvx",
     "args": ["mcp-server-fetch", "--ignore-robots-txt"]},
    {"name": "sequential-thinking", "command": "node",
     "args": ["{PROJECT_ROOT}/node_modules/@modelcontextprotocol/server-sequential-thinking/dist/index.js"]},
    {"name": "playwright", "command": "node",
     "args": ["{PROJECT_ROOT}/node_modules/@playwright/mcp/cli.js"]},
    {"name": "sqlite", "command": "uvx",
     "args": ["mcp-server-sqlite", "--db-path", "{CWD}/.widdx/data/mcp_data.db"]},
    {"name": "chrome-devtools", "command": "npx",
     "args": ["-y", "chrome-devtools-mcp@latest"]},
]

# Cache for discovered servers (refreshed on demand)
_DISCOVERED_CACHE: list[dict] | None = None
_DISCOVERED_CACHE_TIME: float = 0

READ_TIMEOUT = 30  # seconds -- max wait for a JSON-RPC response
_MAX_RECONNECT_ATTEMPTS = 3
_RECONNECT_BACKOFF = [1, 3, 10]  # seconds


_ALLOWED_MCP_COMMANDS = {"node", "uvx", "uv", "python3", "python", "bash", "npx", "npx.cmd", "docker"}

class MCPServerConnection:
    """A single MCP server connected via stdio using direct subprocess communication."""

    def __init__(self, name: str, command: str, args: list[str] | None = None):
        self.name = name
        self.command = command
        self.args = args or []
        # Validate command is allowed
        import os as _os
        cmd_name = _os.path.basename(command) if _os.sep in command else command
        if cmd_name not in _ALLOWED_MCP_COMMANDS:
            raise ValueError(
                f"MCP command '{cmd_name}' not in allowlist: {sorted(_ALLOWED_MCP_COMMANDS)}"
            )
        self._proc: Optional[subprocess.Popen] = None
        self._tools: list[dict] = []
        self._error: Optional[str] = None
        self._read_timed_out: bool = False

    def _timeout_read(self):
        """Kill the subprocess on timeout to unblock readline()."""
        self._read_timed_out = True
        self._error = f"Read timed out after {READ_TIMEOUT}s"
        if self._proc:
            try:
                self._proc.kill()
            except Exception as e:
                logger.debug("Failed to kill MCP subprocess: %s", e)

    def _send_jsonrpc(self, method: str, params: dict | None = None, msg_id: int = 1) -> dict | None:
        """Send a JSON-RPC message and read the response."""
        if not self._proc:
            return None
        msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params:
            msg["params"] = params
        payload = json.dumps(msg) + "\n"
        try:
            if self._proc.stdin:
                self._proc.stdin.write(payload)
                self._proc.stdin.flush()
        except Exception as e:
            self._error = f"Write error: {e}"
            return None

        # Read response line by line until we find a matching id
        self._read_timed_out = False
        timer = threading.Timer(READ_TIMEOUT, self._timeout_read)
        timer.start()
        try:
            while self._proc.stdout and not self._read_timed_out:
                try:
                    line = self._proc.stdout.readline()
                except Exception:
                    break
                if not line:
                    # Process died
                    err = self._proc.stderr.read() if self._proc.stderr else ""
                    if not self._error:
                        self._error = f"Process exited: {err[:200]}"
                    return None
                line = line.strip()
                if not line:
                    continue
                try:
                    resp = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Accept any response (could be a notification or our response)
                if resp.get("id") == msg_id:
                    if "error" in resp:
                        self._error = resp["error"].get("message", str(resp["error"]))
                        return None
                    return resp.get("result")
                # It's a notification or another message — ignore
        finally:
            timer.cancel()
        return None

    def connect(self, retry: bool = True) -> bool:
        """Connect to the MCP server and discover tools.

        Args:
            retry: If True, retry with exponential backoff on failure.

        Returns: True on success.
        """
        attempts = _MAX_RECONNECT_ATTEMPTS if retry else 1
        last_err = ""

        for attempt in range(attempts):
            self._error = None
            self._read_timed_out = False
            try:
                # ── v4.0: Isolation Engine — run MCP in container ──
                _use_container = False
                if os.name != 'nt':  # container support varies on Windows
                    try:
                        from core.isolation.container import get_container_manager
                        cm = get_container_manager()
                        # Check if isolation engine is enabled AND container available
                        if cm.available:
                            _use_container = True
                            self._proc = subprocess.Popen(
                                [cm.runtime_name, "run", "--rm",
                                 "--memory=512m", "--cpus=1.0",
                                 "--network=none", "--read-only",
                                 "--tmpfs", "/tmp",
                                 "node:20-alpine",
                                 self.command] + self.args,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                creationflags=CREATE_NO_WINDOW,
                            )
                    except (ImportError, Exception):
                        pass

                if not _use_container:
                    self._proc = subprocess.Popen(
                        [self.command] + self.args,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        preexec_fn=_mcp_resource_limits if os.name != 'nt' else None,
                        creationflags=CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    )
                    # Windows: assign to job object for resource limits
                    if os.name == 'nt' and self._proc and self._proc.pid:
                        _setup_windows_job(self._proc)
            except Exception as e:
                last_err = f"Launch failed: {e}"
                if attempt < attempts - 1:
                    time.sleep(_RECONNECT_BACKOFF[min(attempt, len(_RECONNECT_BACKOFF) - 1)])
                continue

            # Check process is alive
            if self._proc and self._proc.poll() is not None:
                err = self._proc.stderr.read() if self._proc.stderr else ""
                last_err = f"Process exited on launch: {err[:200]}"
                self._disconnect_proc()
                if attempt < attempts - 1:
                    time.sleep(_RECONNECT_BACKOFF[min(attempt, len(_RECONNECT_BACKOFF) - 1)])
                continue

            # Send initialize
            result = self._send_jsonrpc("initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "widdx-mcp", "version": "1.0"},
            }, msg_id=1)
            if result is None:
                last_err = self._error or "initialize failed"
                self._disconnect_proc()
                if attempt < attempts - 1:
                    time.sleep(_RECONNECT_BACKOFF[min(attempt, len(_RECONNECT_BACKOFF) - 1)])
                continue

            # Send initialized notification
            try:
                notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
                if self._proc and self._proc.stdin:
                    self._proc.stdin.write(notif)
                    self._proc.stdin.flush()
            except Exception as e:
                logger.debug("MCP server %s: initialized notification failed: %s", self.name, e)

            # List tools
            tools_result = self._send_jsonrpc("tools/list", msg_id=2)
            if tools_result is None:
                last_err = self._error or "tools/list failed"
                self._disconnect_proc()
                if attempt < attempts - 1:
                    time.sleep(_RECONNECT_BACKOFF[min(attempt, len(_RECONNECT_BACKOFF) - 1)])
                continue

            raw_tools = tools_result.get("tools", [])
            self._tools = self._convert_tools(raw_tools)
            return True

        self._error = last_err
        return False

    def _disconnect_proc(self):
        """Internal: kill subprocess without clearing tool list."""
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                logger.debug("MCP server %s: process kill failed", self.name)
        self._proc = None

    def _convert_tools(self, raw_tools: list[dict]) -> list[dict]:
        """Convert MCP tool definitions to OpenAI-compatible tool definitions."""
        result = []
        for t in raw_tools:
            name = t.get("name", "")
            prefixed_name = f"mcp__{self.name}__{name}"
            schema = t.get("inputSchema", {})
            params = self._schema_to_params(schema)
            result.append({
                "name": prefixed_name,
                "description": f"[MCP {self.name}] {t.get('description', '') or name}",
                "parameters": params,
                "_mcp_server": self.name,
                "_mcp_tool": name,
            })
        return result

    @staticmethod
    def _schema_to_params(schema: dict) -> dict:
        """Convert JSON Schema to OpenAI-compatible parameters dict."""
        if not schema or schema.get("type") != "object":
            return {}
        props = schema.get("properties", {})
        required = schema.get("required", [])
        result_props = {}
        for key, val in props.items():
            ptype = val.get("type", "string")
            desc = val.get("description", "")
            entry: dict[str, Any] = {"type": ptype, "description": desc}
            if val.get("default") is not None:
                entry["default"] = val["default"]
            if val.get("enum"):
                entry["enum"] = val["enum"]
            result_props[key] = entry
        return {"type": "object", "properties": result_props, "required": required}

    def get_tool_definitions(self) -> list[dict]:
        return self._tools

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool on this MCP server."""
        result = self._send_jsonrpc("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        }, msg_id=3)
        if result is None:
            return f"MCP error: {self._error or 'unknown'}"

        content = result.get("content", [])
        parts = []
        is_error = result.get("isError", False)
        for item in content:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "resource":
                parts.append(f"[resource: {item.get('blob', '')[:100]}]")
            else:
                parts.append(str(item))
        text = "\n".join(parts)
        if is_error:
            return f"MCP error: {text}"
        return text

    @property
    def is_connected(self) -> bool:
        return self._proc is not None and self._proc.poll() is None and self._error is None

    @property
    def error(self) -> Optional[str]:
        return self._error

    def disconnect(self):
        """Cleanup — terminate the process."""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                    self._proc.wait(timeout=2)
                except Exception:
                    logger.debug("MCP server %s: force kill failed", self.name)
        self._proc = None
        self._tools = []
        self._error = None

    def __repr__(self):
        status = "connected" if self.is_connected else f"error: {self._error}"
        return f"MCPServer({self.name}, {len(self._tools)} tools, {status})"


# ---------------------------------------------------------------------------
# Per-project MCP config auto-generation
# ---------------------------------------------------------------------------


def _resolve_placeholders(val, cwd: str):
    """Replace {PROJECT_ROOT}, {USER_HOME}, and {CWD} in config values."""
    if isinstance(val, str):
        return (val.replace("{PROJECT_ROOT}", PROJECT_ROOT)
                   .replace("{USER_HOME}", USER_HOME)
                   .replace("{CWD}", cwd))
    elif isinstance(val, dict):
        return {k: _resolve_placeholders(v, cwd) for k, v in val.items()}
    elif isinstance(val, list):
        return [_resolve_placeholders(v, cwd) for v in val]
    return val


def _get_all_drive_roots() -> list[str]:
    """Detect all available drive roots on Windows."""
    roots = []
    if os.name == "nt":
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:"
            if os.path.exists(drive + "\\"):
                roots.append(drive.replace("\\", "/"))
    return roots


def generate_project_mcp_config(cwd: Path) -> list[dict]:
    """Generate .widdx/mcp_servers.json in the given directory if missing.

    Returns the list of server configs (loaded or freshly generated).
    """
    widdx_dir = cwd / ".widdx"
    widdx_dir.mkdir(parents=True, exist_ok=True)
    config_path = widdx_dir / "mcp_servers.json"

    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug("MCP: config_path load failed: %s", e)

    cwd_str = str(cwd.resolve()).replace("\\", "/")
    servers = _resolve_placeholders(DEFAULT_MCP_SERVERS, cwd_str)

    # For filesystem server: add all drive roots so AI can access any drive
    drive_roots = _get_all_drive_roots()
    for s in servers:
        if s["name"] == "filesystem":
            s["args"].extend(drive_roots)

    config_path.write_text(json.dumps(servers, indent=2), encoding="utf-8")
    return servers


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

_mcp_manager: Optional["MCPClientManager"] = None


class MCPClientManager:
    """Manages all MCP server connections.

    Connections are LAZY — servers register at startup but don't connect
    until the first tool call or tool-definition listing.  This avoids
    blocking startup on 6+ subprocesses (node, uvx, etc.).
    """

    def __init__(self):
        self._servers: dict[str, MCPServerConnection] = {}
        self._tool_map: dict[str, tuple[str, str]] = {}
        self._connected_once: bool = False

    def load_from_config(self, cfg: dict):
        """Register MCP servers from config WITHOUT connecting immediately.

        Auto-generates .widdx/mcp_servers.json from DEFAULT_MCP_SERVERS
        template if missing, then registers each server as a lazy stub.
        Falls back to cfg['mcp_servers'] if generation fails.
        """
        try:
            servers = generate_project_mcp_config(Path.cwd())
        except Exception:
            servers = cfg.get("mcp_servers", [])
        for s in servers:
            name = s.get("name", "")
            command = s.get("command", "")
            args = s.get("args", [])
            if name and command:
                conn = MCPServerConnection(name, command, args)
                self._servers[name] = conn

    def _ensure_connected(self):
        """Lazy-connect all registered servers on first use."""
        if self._connected_once:
            return
        self._connected_once = True
        for conn in self._servers.values():
            if not conn.is_connected:
                conn.connect(retry=False)
                for td in conn.get_tool_definitions():
                    self._tool_map[td["name"]] = (conn.name, td["_mcp_tool"])

    def connect_all(self):
        """Eagerly connect to every registered server.

        Use only when tool definitions from all servers are genuinely needed
        up front; it spawns one subprocess per server and is slow.
        """
        self._ensure_connected()

    def add_server(self, name: str, command: str, args: list[str] | None = None):
        """Add and immediately connect a new MCP server."""
        # Resolve {CWD}, {PROJECT_ROOT}, {USER_HOME} in command and args
        cwd_str = Path.cwd().as_posix()
        command = _resolve_placeholders(command, cwd_str)
        if args:
            args = [_resolve_placeholders(a, cwd_str) if isinstance(a, str) else a for a in args]
        conn = MCPServerConnection(name, command, args)
        self._servers[name] = conn
        ok = conn.connect()
        for td in conn.get_tool_definitions():
            self._tool_map[td["name"]] = (name, td["_mcp_tool"])
        return ok

    def start(self):
        """Connect to all configured servers (legacy, now lazy)."""
        self._ensure_connected()

    def stop(self):
        """Disconnect all servers."""
        for conn in self._servers.values():
            conn.disconnect()
        self._servers.clear()
        self._tool_map.clear()
        self._connected_once = False

    def get_all_tool_definitions(self) -> list[dict]:
        """Return tool definitions from all *already connected* servers.

        Deliberately does NOT force a connection: the class documents that
        servers register lazily and connect on first use. Forcing all six
        subprocesses (node, uvx, ...) here blocked every TUIState() build by
        60-80 seconds. Use ``connect_all()`` first when definitions are
        genuinely required.
        """
        tools = []
        for conn in self._servers.values():
            if conn.is_connected:
                tools.extend(conn.get_tool_definitions())
        return tools

    def call_tool(self, prefixed_name: str, arguments: dict) -> str:
        mapping = self._tool_map.get(prefixed_name)
        if not mapping:
            return f"Unknown MCP tool: {prefixed_name}"
        server_name, tool_name = mapping
        conn = self._servers.get(server_name)
        if not conn:
            return f"MCP server '{server_name}' not found"

        # Try up to 2 times: once + one reconnect attempt
        for attempt in range(2):
            if conn.is_connected:
                result = conn.call_tool(tool_name, arguments)
                # Check if result indicates a disconnected server
                if "MCP error" not in result or attempt == 1:
                    return result
            # Attempt reconnection
            if attempt == 0:
                conn.disconnect()
                ok = conn.connect(retry=True)
                if not ok:
                    return f"MCP server '{server_name}' reconnection failed: {conn.error or 'unknown'}"

        return f"MCP server '{server_name}' error after reconnect: {conn.error or 'unknown'}"

    def remove_server(self, name: str):
        """Remove and disconnect a server by name."""
        conn = self._servers.pop(name, None)
        if conn:
            conn.disconnect()
            # Remove all tools registered to this server
            keys = [k for k, v in self._tool_map.items() if v[0] == name]
            for k in keys:
                self._tool_map.pop(k, None)

    def has_tool(self, prefixed_name: str) -> bool:
        return prefixed_name in self._tool_map

    def get_servers(self) -> list[MCPServerConnection]:
        return list(self._servers.values())

    def get_server(self, name: str) -> Optional[MCPServerConnection]:
        return self._servers.get(name)

    @property
    def server_count(self) -> int:
        return len(self._servers)

    @property
    def tool_count(self) -> int:
        """Return cached tool count (0 before first lazy connect)."""
        return len(self._tool_map)

    @property
    def pending_server_count(self) -> int:
        """Return number of servers not yet connected."""
        return sum(1 for c in self._servers.values() if not c.is_connected)


# ---------------------------------------------------------------------------
# Auto-discovery — scan for available MCP packages and configs
# ---------------------------------------------------------------------------


def discover_mcp_servers(force_refresh: bool = False) -> list[dict]:
    """Auto-discover MCP servers from multiple sources.

    Sources:
      1. .widdx/mcp_servers.json (project config)
      2. config.json mcp_servers (global config)
      3. ~/.widdx/mcp_servers.json (WIDDX config)
      4. npm global packages matching @modelcontextprotocol/*
      5. uvx available tools (mcp-server-*)

    Returns a deduplicated list of {name, command, args} dicts.
    """
    global _DISCOVERED_CACHE, _DISCOVERED_CACHE_TIME
    now = time.time()
    if not force_refresh and _DISCOVERED_CACHE is not None and (now - _DISCOVERED_CACHE_TIME) < 300:
        return _DISCOVERED_CACHE

    discovered: list[dict] = []
    seen_names: set[str] = set()

    def _add(name, command, args):
        if name not in seen_names:
            seen_names.add(name)
            discovered.append({"name": name, "command": command, "args": args})

    # 1. Start with defaults
    for s in DEFAULT_MCP_SERVERS:
        _add(s["name"], s["command"], s.get("args", []))

    # 2. Load from .widdx/mcp_servers.json
    try:
        widdx_servers = json.loads((Path.cwd() / ".widdx" / "mcp_servers.json").read_text())
        for s in widdx_servers:
            _add(s["name"], s["command"], s.get("args", []))
    except Exception as e:
        logger.debug("MCP: .widdx/mcp_servers.json load failed: %s", e)

    # 3. WIDDX config
    for widdx_config in [
        Path(USER_HOME) / ".widdx" / "mcp_servers.json",
        Path(USER_HOME) / ".codex" / "mcp.json",
    ]:
        try:
            if widdx_config.exists():
                raw = json.loads(widdx_config.read_text())
                for name, config in raw.items():
                    cmd = config.get("command", "")
                    args = config.get("args", [])
                    if cmd:
                        _add(name, cmd, args)
        except Exception as e:
            logger.debug("MCP: config load failed for %s: %s", widdx_config, e)

    # 4. Detect npm global packages
    try:
        npm_list = subprocess.run(
            ["npm", "list", "-g", "--json", "--depth=0"],
            capture_output=True, text=True, timeout=10,
        )
        if npm_list.returncode == 0:
            pass
            # We just note it, don't auto-add unknown packages
    except Exception as e:
        logger.debug("MCP: npm list failed: %s", e)

    _DISCOVERED_CACHE = discovered
    _DISCOVERED_CACHE_TIME = now
    return discovered


def get_mcp_manager() -> MCPClientManager:
    """Get or create the global MCP manager singleton."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()
    return _mcp_manager


# ---------------------------------------------------------------------------
# OAuth token storage for MCP servers — encrypted at rest
# ---------------------------------------------------------------------------

_MCP_TOKENS: dict[str, str] = {}
_MCP_KEY: bytes | None = None


def _derive_key() -> bytes:
    """Derive a machine-local encryption key using PBKDF2.

    Uses MAC address + hostname as the seed, so the key is:
    - Deterministic for the same machine (tokens survive restarts)
    - Not portable to another machine (security boundary)
    - Resistant to casual file reading

    Returns:
        32 bytes (256 bits) for AES-256-compatible key.
    """
    seed = f"{uuid.getnode():016x}-{socket.gethostname()}"
    return hashlib.pbkdf2_hmac(
        "sha256",
        seed.encode("utf-8"),
        salt=b"widdx-mcp-token-v1",
        iterations=600_000,  # OWASP 2023 recommendation for PBKDF2-HMAC-SHA256
        dklen=32,
    )


def _get_key() -> bytes:
    """Get the cached encryption key."""
    global _MCP_KEY
    if _MCP_KEY is None:
        _MCP_KEY = _derive_key()
    return _MCP_KEY


def _fernet() -> "Fernet":
    """Build a Fernet cipher keyed on the machine-local PBKDF2 secret.

    This replaces the previous XOR keystream with authenticated encryption
    (AES-128-CBC + HMAC-SHA256), while keeping the same machine-binding
    property so tokens remain non-portable across machines.
    """
    from cryptography.fernet import Fernet

    return Fernet(base64.urlsafe_b64encode(_get_key()))


def _encrypt_token(plaintext: str) -> str:
    """Encrypt a token string using Fernet (AES-128-CBC + HMAC).

    Format: ``v2:<urlsafe base64 Fernet token>``
    Legacy format (XOR keystream + base64) is still readable by
    ``_decrypt_token`` for transparent migration of stored tokens.
    """
    return "v2:" + _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def _decrypt_token(encoded: str) -> str:
    """Reverse _encrypt_token(), with legacy XOR fallback."""
    if encoded.startswith("v2:"):
        try:
            return _fernet().decrypt(encoded[3:].encode("ascii")).decode("utf-8")
        except Exception as enc_e:
            logger.debug("MCP: Fernet decrypt failed, trying legacy XOR: %s", enc_e)
    # Legacy: base64(salt(16) + XOR keystream)
    key = _get_key()
    raw = base64.b64decode(encoded)
    salt, cipher = raw[:16], raw[16:]
    data = bytes(cipher[i] ^ key[i % len(key)] ^ salt[i % len(salt)] for i in range(len(cipher)))
    return data.decode("utf-8")


def _get_token_path() -> Path:
    return Path.cwd() / ".widdx" / "mcp_tokens.json"


def load_mcp_tokens():
    """Load and decrypt stored OAuth tokens from .widdx/mcp_tokens.json."""
    global _MCP_TOKENS
    path = _get_token_path()
    if path.exists():
        try:
            raw: dict[str, str] = json.loads(path.read_text())
            decrypted = {}
            for server, token in raw.items():
                try:
                    decrypted[server] = _decrypt_token(token)
                except Exception:
                    logger.debug("MCP: failed to decrypt token for %s, skipping", server)
                    continue
            _MCP_TOKENS = decrypted
        except Exception:
            _MCP_TOKENS = {}


def save_mcp_token(server_name: str, token: str):
    """Encrypt and store an OAuth token for a server."""
    load_mcp_tokens()
    _MCP_TOKENS[server_name] = token
    encrypted = {s: _encrypt_token(t) for s, t in _MCP_TOKENS.items()}
    _get_token_path().write_text(json.dumps(encrypted, indent=2))


def get_mcp_token(server_name: str) -> Optional[str]:
    """Retrieve stored token for a server."""
    load_mcp_tokens()
    return _MCP_TOKENS.get(server_name)
