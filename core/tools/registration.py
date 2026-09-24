"""Tool registration — defines and registers all built-in tools.

Separated from execution logic. This module only calls register().
Importing this module populates the global registry.
"""
import logging


from .registry import register
from .handlers.file_ops import (
    _read, _write, _edit, _glob, _grep, _list_files, _search_replace,
)
from .handlers.bash import _bash, _handle_sandbox_exec
from .handlers.web import _web_fetch
from .handlers.validate import _validate, _project_validate
from .handlers.edit_files import _handle_edit_files
from .handlers.spawn import _handle_spawn_agent
from .handlers.linter import _handle_run_linter
from .handlers.semantic_search import _semantic_search
from .handlers.rename import _rename_symbol
from .handlers.dep_graph import _dep_graph
from .handlers.docker_mgr import _docker_mgr
from .handlers.db_query import _db_query
from .handlers.api_client import _api_request
from .handlers.pkg_mgr import _pkg_mgr
from .handlers.terminal_mux import _terminal_mux
from .handlers.ask_user import _ask_user
from .handlers.embeddings import _semantic_embedding
from .handlers.file_tree import _file_tree
from .handlers.scaffolder import _scaffold
from .handlers.test_runner import _run_tests
from .handlers.security_scan import _security_scan
from .handlers.tool_undo import _tool_undo

# ── Register all built-in tools ──

register(
    "read",
    "Read a file with line numbers. Supports offset/limit for partial reads.",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Absolute or relative path"},
            "offset": {"type": "integer", "description": "Starting line (1-based, negative = from end, 0 = beginning)"},
            "limit": {"type": "integer", "description": "Max lines (0 = all)"},
        },
        "required": ["file_path"],
    },
    _read,
)

register(
    "write",
    "Write content to a file (creates parent directories).",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to write to"},
            "content": {"type": "string", "description": "File content"},
        },
        "required": ["file_path", "content"],
    },
    _write,
)

register(
    "edit",
    "Replace text in a file. Shows diff preview. Supports replace_all. Use preview=true to see changes without applying them.",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "old_string": {"type": "string", "description": "Text to find (must be unique unless replace_all)"},
            "new_string": {"type": "string", "description": "Replacement text"},
            "replace_all": {"type": "boolean", "description": "Replace ALL occurrences (default: first only)"},
            "preview": {"type": "boolean", "description": "Show diff without making changes"},
        },
        "required": ["file_path", "old_string", "new_string"],
    },
    _edit,
)

register(
    "glob",
    "Find files by glob pattern (e.g. **/*.py).",
    {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "description": "Root directory (default: current)"},
        },
        "required": ["pattern"],
    },
    _glob,
)

register(
    "grep",
    "Search file contents by regex pattern.",
    {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern"},
            "path": {"type": "string", "description": "Root directory"},
            "include": {"type": "string", "description": "Glob filter (e.g. *.py)"},
        },
        "required": ["pattern"],
    },
    _grep,
)

register(
    "bash",
    "Execute a shell command (PowerShell on Windows, bash on Linux/Mac).",
    {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command to run"},
            "description": {"type": "string", "description": "Short description"},
        },
        "required": ["command"],
    },
    _bash,
)

register(
    "web_fetch",
    "Fetch and extract text content from a URL.",
    {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "format": {
                "type": "string",
                "enum": ["markdown", "text"],
                "description": "Output format (default: markdown)",
            },
        },
        "required": ["url"],
    },
    _web_fetch,
)

register(
    "list_files",
    "List files and directories in a directory.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path (default: current)"},
        },
    },
    _list_files,
)

register(
    "validate",
    "Validate syntax of a code file. Supports PHP, Python, JavaScript, JSON, HTML, and more.",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to file to validate"},
        },
        "required": ["file_path"],
    },
    _validate,
)

register(
    "project_validate",
    "Run project-level build/test validation. Detects Python, Node.js, Rust, Go, Java and runs appropriate test commands.",
    {
        "type": "object",
        "properties": {
            "project_dir": {"type": "string", "description": "Path to project root directory"},
        },
        "required": ["project_dir"],
    },
    _project_validate,
)

# ── Project Tracker tool ──
from typing import cast  # noqa: E402

from core.project_tracker import TOOL_DEFINITION as _PT_TOOL, handle_update_project_doc  # noqa: E402

register(
    cast(str, _PT_TOOL["name"]),
    cast(str, _PT_TOOL["description"]),
    cast(dict, _PT_TOOL["parameters"]),
    handle_update_project_doc,
)

register(
    "run_linter",
    "Run a code linter on the given file.",
    {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file to lint"},
            "language": {"type": "string", "description": "Language override (auto-detect if 'auto')", "default": "auto"},
        },
        "required": ["file_path"],
    },
    _handle_run_linter,
)

register(
    "sandbox_exec",
    "Execute a shell command in a resource-limited sandbox.",
    {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)", "default": 60},
            "cwd": {"type": "string", "description": "Working directory for the command", "default": ""},
        },
        "required": ["command"],
    },
    _handle_sandbox_exec,
)

register(
    "edit_files",
    "Apply multiple surgical file edits in a single atomic operation.",
    {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to edit"},
                        "old_string": {"type": "string", "description": "Text to replace"},
                        "new_string": {"type": "string", "description": "Replacement text"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
                "description": "List of file edits to apply atomically",
            },
        },
        "required": ["files"],
    },
    _handle_edit_files,
)

register(
    "spawn_agent",
    "Spawn a specialized sub-agent for a subtask.",
    {"type": "object", "properties": {
        "task": {"type": "string", "description": "The subtask for the sub-agent to complete"},
        "role": {"type": "string", "description": "Role: researcher, coder, tester, reviewer, debugger, writer"},
    }, "required": ["task", "role"]},
    _handle_spawn_agent,
)

register(
    "search_replace",
    "Search and replace text across multiple files. Use preview=true to see matches before replacing.",
    {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Text to search for"},
            "replacement": {"type": "string", "description": "Text to replace with"},
            "include": {"type": "string", "description": "File glob filter (e.g. *.py, *.{ts,tsx})"},
            "path": {"type": "string", "description": "Root directory (default: current)"},
            "preview": {"type": "boolean", "description": "Preview matches without replacing (default: true for safety)"},
        },
        "required": ["pattern", "replacement"],
    },
    _search_replace,
)

register(
    "semantic_search",
    "Semantic code search — finds code by meaning using TF-IDF and AST analysis. Understands function/class names, comments, and docstrings.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "path": {"type": "string", "description": "Root directory (default: current)"},
            "include": {"type": "string", "description": "File glob filter (e.g. *.py)"},
            "top_k": {"type": "integer", "description": "Max results (default: 10)"},
        },
        "required": ["query"],
    },
    _semantic_search,
)

register(
    "rename_symbol",
    "Smart rename — rename a symbol (function, class, variable) across all files using AST analysis. Shows usages before renaming with preview=true.",
    {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Current symbol name to rename"},
            "new_name": {"type": "string", "description": "New symbol name"},
            "path": {"type": "string", "description": "Root directory (default: current)"},
            "include": {"type": "string", "description": "File glob filter (e.g. *.py)"},
            "preview": {"type": "boolean", "description": "Preview usages without renaming (default: true for safety)"},
        },
        "required": ["symbol", "new_name"],
    },
    _rename_symbol,
)

register(
    "dep_graph",
    "Analyze import dependencies and detect circular dependencies. Supports Python, JS/TS, C/C++, Rust, Go.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Root directory (default: current)"},
            "include": {"type": "string", "description": "File glob filter (e.g. *.py)"},
            "depth": {"type": "integer", "description": "Analysis depth (default: 2)"},
            "format": {"type": "string", "enum": ["text", "json"], "description": "Output format (default: text)"},
        },
    },
    _dep_graph,
)

register(
    "docker",
    "Docker container/image management. Actions: list, ps, images, build, run, stop, rm, logs, compose.",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Action: list, ps, images, build, run, stop, rm, logs, compose"},
            "what": {"type": "string", "description": "For list: containers, images, volumes"},
            "image": {"type": "string", "description": "Docker image name (for run/build)"},
            "tag": {"type": "string", "description": "Image tag (default: latest)"},
            "name": {"type": "string", "description": "Container name"},
            "path": {"type": "string", "description": "Build context path"},
            "dockerfile": {"type": "string", "description": "Dockerfile path"},
            "ports": {"type": "string", "description": "Port mappings (comma-separated, e.g. 8080:80,443:443)"},
            "detach": {"type": "boolean", "description": "Run in background"},
            "command": {"type": "string", "description": "Command to run in container"},
            "container_id": {"type": "string", "description": "Container ID/name"},
            "force": {"type": "boolean", "description": "Force remove"},
            "tail": {"type": "integer", "description": "Show last N log lines (default: 50)"},
            "compose_file": {"type": "string", "description": "Docker compose file path"},
            "compose_action": {"type": "string", "description": "Compose action: up, down, stop"},
        },
        "required": ["action"],
    },
    _docker_mgr,
)

register(
    "db_query",
    "Query databases (SQLite, PostgreSQL). Supports SELECT, INSERT, UPDATE, DELETE.",
    {
        "type": "object",
        "properties": {
            "db_path": {"type": "string", "description": "SQLite database file path"},
            "query": {"type": "string", "description": "SQL query to execute"},
            "type": {"type": "string", "enum": ["sqlite", "postgres"], "description": "Database type (default: sqlite)"},
            "conn_str": {"type": "string", "description": "PostgreSQL connection string"},
            "action": {"type": "string", "enum": ["query", "tables", "describe"], "description": "Action (default: query)"},
            "table": {"type": "string", "description": "Table name for describe action"},
            "max_rows": {"type": "integer", "description": "Max rows to return (default: 50)"},
            "format": {"type": "string", "enum": ["text", "json"], "description": "Output format"},
        },
        "required": ["query"],
    },
    _db_query,
)

register(
    "api_request",
    "Make HTTP requests to test APIs. Supports GET, POST, PUT, PATCH, DELETE with headers, body, params.",
    {
        "type": "object",
        "properties": {
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "description": "HTTP method (default: GET)"},
            "url": {"type": "string", "description": "Request URL"},
            "headers": {"type": "object", "description": "HTTP headers as key-value pairs"},
            "body": {"type": "string", "description": "Request body (JSON string)"},
            "params": {"type": "object", "description": "URL query parameters"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30)"},
            "follow_redirects": {"type": "boolean", "description": "Follow redirects (default: true)"},
        },
        "required": ["url"],
    },
    _api_request,
)

register(
    "pkg_mgr",
    "Manage project packages. Detects npm, yarn, pnpm, pip, cargo, go. Actions: install, add, remove, update, list, detect.",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["detect", "install", "add", "remove", "update", "list"], "description": "Action (default: detect)"},
            "package": {"type": "string", "description": "Package name (for add/remove/update)"},
            "pkg_manager": {"type": "string", "description": "Package manager: npm, yarn, pnpm, pip, cargo, go, auto"},
            "path": {"type": "string", "description": "Project root directory"},
        },
        "required": ["action"],
    },
    _pkg_mgr,
)

register(
    "terminal",
    "Manage multiple terminal sessions. Actions: list, create/run, output/read, stop/kill, send, cleanup.",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "create", "run", "output", "read", "stop", "kill", "send", "cleanup"], "description": "Action (default: list)"},
            "name": {"type": "string", "description": "Session name/ID"},
            "command": {"type": "string", "description": "Shell command to run (for create/run) or input to send (for send)"},
            "cwd": {"type": "string", "description": "Working directory (default: current)"},
        },
        "required": ["action"],
    },
    _terminal_mux,
)

register(
    "ask_user",
    "Ask the user a clarifying question and wait for their answer. Use this when you need clarification, preferences, or decisions before continuing.",
    {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question to ask the user"},
        },
        "required": ["question"],
    },
    _ask_user,
)

register(
    "semantic_embedding",
    "Semantic search using embeddings (with TF-IDF fallback). Understands code meaning better than regex search.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "path": {"type": "string", "description": "Root directory (default: current)"},
            "include": {"type": "string", "description": "File glob filter"},
            "top_k": {"type": "integer", "description": "Max results (default: 10)"},
        },
        "required": ["query"],
    },
    _semantic_embedding,
)

register(
    "file_tree",
    "Display project file/directory tree structure.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Root directory (default: current)"},
            "depth": {"type": "integer", "description": "Max depth (default: 3)"},
            "include": {"type": "string", "description": "File glob filter"},
            "format": {"type": "string", "enum": ["text", "json"], "description": "Output format"},
        },
    },
    _file_tree,
)

register(
    "scaffold",
    "Scaffold a new project from a template. Templates: python-cli, python-web, node-cli, node-express, rust-cli, go-cli.",
    {
        "type": "object",
        "properties": {
            "template": {"type": "string", "enum": ["python-cli", "python-web", "node-cli", "node-express", "rust-cli", "go-cli"], "description": "Project template"},
            "name": {"type": "string", "description": "Project name"},
            "path": {"type": "string", "description": "Output path (default: ./<name>)"},
            "description": {"type": "string", "description": "Project description"},
        },
        "required": ["template"],
    },
    _scaffold,
)

register(
    "run_tests",
    "Detect and run tests for the project. Supports pytest, jest, cargo test, go test, npm test.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Project root (default: current)"},
            "test_path": {"type": "string", "description": "Specific test file/path"},
            "framework": {"type": "string", "description": "Override: pytest, unittest, jest, cargo, go, npm"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 120)"},
        },
    },
    _run_tests,
)

register(
    "security_scan",
    "Scan project for security vulnerabilities (pip-audit, npm audit, cargo audit) and detect secrets/API keys.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Project root (default: current)"},
            "scan_type": {"type": "string", "enum": ["all", "python", "node", "rust", "secrets"], "description": "Scan type (default: all)"},
        },
    },
    _security_scan,
)

register(
    "tool_undo",
    "Undo file changes made during this session. Actions: undo (revert last), list (show history), record (snapshot a file).",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["undo", "list", "record"], "description": "Action (default: undo)"},
            "file_path": {"type": "string", "description": "File path for record action"},
        },
        "required": ["action"],
    },
    _tool_undo,
)

# ── Browser tools (optional, via Playwright) ──
try:
    from core.tools.browser import (
        _browser_navigate, _browser_screenshot, _browser_click,
        _browser_snapshot, _browser_type, _browser_press,
    )
    _BROWSER_OK = True
except Exception as e:
    import logging
    logging.getLogger("widdx.tools").warning("Browser tools unavailable: %s", e)
    _BROWSER_OK = False

if _BROWSER_OK:
    register("browser_navigate", "Open a URL in the browser.", {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}, _browser_navigate)
    register("browser_screenshot", "Take a screenshot of the current page.", {"type": "object", "properties": {"url": {"type": "string"}, "selector": {"type": "string"}}}, _browser_screenshot)
    register("browser_click", "Click an element by CSS selector.", {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}, _browser_click)
    register("browser_snapshot", "Get accessibility snapshot.", {"type": "object", "properties": {}}, _browser_snapshot)
    register("browser_type", "Type text into an input field.", {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}, _browser_type)
    register("browser_press", "Press a keyboard key.", {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}, _browser_press)
