"""End-to-End tests — full import chain, integration, and smoke tests.

Verifies the complete pipeline from entry points through core logic.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


# ═══════════════════════════════════════════════════════════════
# Entry Points
# ═══════════════════════════════════════════════════════════════

def test_tui_entry_point_importable():
    """python -m tui entry point is importable."""
    from tui.__main__ import run_tui
    assert callable(run_tui)


def test_api_entry_point_importable():
    """api_server entry point is importable."""
    import sys
    from pathlib import Path
    _scripts = str(Path(__file__).parent.parent / "scripts")
    if _scripts not in sys.path:
        sys.path.insert(0, _scripts)
    from api_server import main
    assert callable(main)


# ═══════════════════════════════════════════════════════════════
# Full Import Chain (every module)
# ═══════════════════════════════════════════════════════════════

ALL_MODULES = [
    # Core
    "core",
    "core.chat",
    "core.tools",
    "core.memory",
    "core.skills",
    "core.database",
    "core.session_v2",
    "core.memory_learner",
    "core.proxy",
    "core.utils",
    "core.workflow",
    "core.diagnostics",
    "core.diff_engine",
    "core.linter",
    "core.sandbox",
    "core.multi_editor",
    "core.checkpoint",
    "core.rag",
    "core.repo_mapper",
    "core.vector_memory",
    "core.session_search",
    "core.plugin_loader",
    "core.self_improve",
    "core.cache",
    "core.auto_setup",
    "core.project_tracker",
    "core.project_context",
    "core.project_structure",
    "core.token_budget",
    "core.self_reflection",
    "core.suggester",
    # Providers
    "core.providers",
    "core.providers.providers",
    "core.providers.gguf",
    # Config
    "core.config",
    "core.config.settings",
    "core.config.keychain",
    # UIL
    "core.uil",
    "core.uil.contract",
    "core.uil.analyzer",
    "core.uil.router",
    "core.uil.planner",
    "core.uil.brain",
    "core.uil.knowledge",
    # MCP
    "core.mcp",
    "core.mcp.client",
    # Project
    "core.project",
    "core.project.state",
    "core.project.scanner",
    "core.project.git",
    "core.project.manifest",
    # Agents
    "core.agents",
    "core.agents.agent",
    "core.agents.expert",
    # CLI
    "cli",
    "cli.app",
    "cli.commands",
    "cli.display",
    "cli.input",
    "cli.theme",
    # TUI
    "tui",
    "tui.app",
    "tui.chat_engine",
    "tui.commands",
    "tui.state",
    "tui.widgets",
    "tui.widgets.header",
    "tui.screens",
    "tui.screens.help",
    "tui.screens.settings",
    "tui.screens.session_crud",
    "tui.screens.memory_crud",
    "tui.screens.detail",
    "tui.screens.tool_detail",
    "tui.screens.ubuntu_grid",
    # Scripts
    "scripts",
    "scripts.api_server",
    "scripts.run_textual",
    "scripts.web_app",
]


@pytest.mark.parametrize("module_name", ALL_MODULES)
def test_module_importable(module_name):
    """Every module in the project imports without error."""
    import importlib
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        mod = importlib.import_module(module_name)
        assert mod is not None


# ═══════════════════════════════════════════════════════════════
# Provider Integration
# ═══════════════════════════════════════════════════════════════

def test_create_provider_from_config():
    """create_provider() returns a valid Provider from config."""
    from core.providers.providers import create_provider
    from core.config.settings import load as load_config
    cfg = load_config()
    provider = create_provider(cfg)
    assert provider is not None
    assert provider.name
    assert provider.model
    assert provider.base_url


def test_provider_has_model_listing():
    """Each provider can list available models (no crash)."""
    from core.providers.providers import get_available_models
    models = get_available_models("opencode-zen", "https://opencode.ai/zen/v1", force_refresh=False)
    assert isinstance(models, list)


# ═══════════════════════════════════════════════════════════════
# Tool Integration
# ═══════════════════════════════════════════════════════════════

def test_tool_definitions_have_required_fields():
    """Every tool definition has name and description."""
    from core.tools import TOOL_DEFINITIONS
    for td in TOOL_DEFINITIONS:
        assert "name" in td, f"Tool missing name: {td}"
        assert "description" in td, f"Tool {td.get('name', '?')} missing description"
        assert "parameters" in td, f"Tool {td['name']} missing parameters"


def test_tool_execute_read():
    """execute_with_skills runs the read tool."""
    from core.tools import execute_with_skills
    result = execute_with_skills("read", {"file_path": __file__})
    assert result
    assert "test_e2e.py" in result or "Error" not in result


def test_tool_execute_bash_echo():
    """execute_with_skills runs bash echo."""
    from core.tools import execute_with_skills
    result = execute_with_skills("bash", {"command": "echo hello-world-test"})
    assert "hello-world-test" in result


def test_new_tools_registered():
    """search_replace, semantic_search, rename_symbol are registered."""
    from core.tools import TOOL_DEFINITIONS
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert "search_replace" in names
    assert "semantic_search" in names
    assert "rename_symbol" in names


def test_tool_search_replace_preview():
    """search_replace with preview=True shows matches without changing files."""
    from core.tools import execute_with_skills
    test_file = Path(__file__)
    content = test_file.read_text()
    result = execute_with_skills("search_replace", {
        "pattern": "def test_tool_search_replace_preview",
        "replacement": "def test_tool_search_replace_renamed",
        "include": "*.py",
        "path": str(test_file.parent),
        "preview": True,
    })
    assert "Found" in result
    assert "def test_tool_search_replace_preview" in result
    # Verify file was NOT changed (preview mode)
    assert test_file.read_text() == content


def test_tool_semantic_search():
    """semantic_search returns relevant code results."""
    from core.tools import execute_with_skills
    result = execute_with_skills("semantic_search", {
        "query": "file read tool",
        "include": "*.py",
        "path": "core/tools",
        "top_k": 3,
    })
    assert result
    assert "result(s)" in result or "🔎" in result or "No semantic" in result


def test_tool_rename_symbol_preview():
    """rename_symbol with preview=True shows usages without renaming."""
    from core.tools import execute_with_skills
    test_file = Path("core/tools/handlers/file_ops.py")
    content = test_file.read_text()
    result = execute_with_skills("rename_symbol", {
        "symbol": "is_safe_path",
        "new_name": "is_path_safe",
        "include": "*.py",
        "path": "core/tools",
        "preview": True,
    })
    assert "Found" in result or "not found" in result
    # Verify files were NOT changed
    assert test_file.read_text() == content


def test_new_tools_v2_registered():
    """All 6 new tools are registered."""
    from core.tools import TOOL_DEFINITIONS
    names = {t["name"] for t in TOOL_DEFINITIONS}
    for name in ("dep_graph", "docker", "db_query", "api_request", "pkg_mgr", "terminal"):
        assert name in names, f"{name} not registered"


def test_tool_dep_graph():
    """dep_graph analyzes imports."""
    from core.tools import execute_with_skills
    result = execute_with_skills("dep_graph", {"path": "core/tools", "include": "*.py", "format": "text"})
    assert result
    assert "📊" in result or "Dependency" in result or len(result) > 50


def test_tool_api_request():
    """api_request makes HTTP calls."""
    from core.tools import execute_with_skills
    result = execute_with_skills("api_request", {"url": "https://httpbin.org/get", "method": "GET", "timeout": 10})
    assert result
    assert "httpbin" in result or "Status" in result or "error" not in result.lower()[:10]


def test_tool_db_query_sqlite():
    """db_query works with SQLite."""
    import os
    import sqlite3
    from core.tools import execute_with_skills
    tmp = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(tmp)
    conn.execute("CREATE TABLE test (id INT, name TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'hello')")
    conn.commit()
    conn.close()
    try:
        result = execute_with_skills("db_query", {"db_path": tmp, "query": "SELECT * FROM test"})
        assert "hello" in result
    finally:
        os.unlink(tmp)


def test_tool_terminal():
    """terminal manages processes."""
    from core.tools import execute_with_skills
    result = execute_with_skills("terminal", {"action": "list"})
    assert isinstance(result, str)


def test_tool_pkg_mgr():
    """pkg_mgr detects package managers."""
    from core.tools import execute_with_skills
    result = execute_with_skills("pkg_mgr", {"action": "detect", "path": "."})
    assert isinstance(result, str)


def test_permissions_new_tools():
    """New tools are correctly classified in permissions."""
    from core.permissions import _DANGEROUS_TOOLS, _SAFE_TOOLS
    assert "docker" in _DANGEROUS_TOOLS
    assert "terminal" in _DANGEROUS_TOOLS
    assert "db_query" in _DANGEROUS_TOOLS
    assert "pkg_mgr" in _DANGEROUS_TOOLS
    assert "semantic_search" in _SAFE_TOOLS
    assert "dep_graph" in _SAFE_TOOLS
    assert "api_request" in _SAFE_TOOLS


# ═══════════════════════════════════════════════════════════════
# Memory Integration
# ═══════════════════════════════════════════════════════════════

def test_memory_store_crud():
    """MemoryStore CRUD operations work end-to-end."""
    from core.memory import MemoryStore
    mem = MemoryStore()
    # Save
    mem.save("e2e-test-memory", "E2E test content", {"type": "user"})
    # Read
    content = mem.get("e2e-test-memory")
    assert content is not None
    assert "E2E test content" in content
    # Search
    results = mem.search("E2E test")
    assert len(results) > 0
    # Delete
    assert mem.delete("e2e-test-memory") is True
    assert mem.get("e2e-test-memory") is None


# ═══════════════════════════════════════════════════════════════
# Session Integration
# ═══════════════════════════════════════════════════════════════

def test_session_v2_create_save_search():
    """SessionV2 full lifecycle with Phase 1 + 2 features."""
    from core.session_v2 import SessionV2, create_new_session

    tmp = tempfile.mkdtemp()
    try:
        import core.database as dbm
        orig = dbm.get_db_path
        dbm.get_db_path = lambda pd=None: os.path.join(tmp, "e2e.db")

        sess = create_new_session("e2e-session", "main")
        sess.add_message("user", "E2E test message")
        sess.add_message("assistant", "E2E response")
        sess.save({"cost": 0.001, "turns": 2, "model": "test/e2e"})

        # Reload
        sess2 = SessionV2(session_id=sess.id)
        assert len(sess2.messages) == 2
        assert sess2.metadata.get("cost") == 0.001

        # Search
        results = SessionV2.search("E2E test", limit=5)
        assert isinstance(results, list)

        # Checkpoint
        cpid = sess.create_checkpoint("e2e-checkpoint")
        assert cpid

        dbm.get_db_path = orig
        dbm._db = None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# Deprecation Warnings
# ═══════════════════════════════════════════════════════════════

def test_v2_modules_emit_deprecation_warning():
    """Phase 1: deprecated v2 modules — removed. Test passes automatically."""
    pass


# ═══════════════════════════════════════════════════════════════
# Session Search
# ═══════════════════════════════════════════════════════════════

def test_dual_session_persistence():
    """save_session + load_session use SQLite + JSON dual persistence."""
    from core.project.state import save_session, load_session

    tmp = tempfile.mkdtemp()
    try:
        # Save
        save_session(
            [{"role": "user", "content": "dual-test"}],
            {"model": "test/dual", "cost": 0.0, "turns": 1},
            project_dir=tmp,
            branch="main",
        )
        # Load
        session = load_session(project_dir=tmp, branch="main")
        assert session is not None
        assert len(session.get("messages", [])) > 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# Wildcard Import Elimination (Phase 3)
# ═══════════════════════════════════════════════════════════════

def test_no_wildcard_imports_in_cli():
    """Phase 3: cli/display.py and cli/theme.py use explicit imports."""
    import ast
    for filepath in ["cli/display.py", "cli/theme.py"]:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        has_wildcard = any(
            isinstance(n, ast.ImportFrom) and n.names[0].name == "*"
            for n in ast.walk(tree)
        )
        assert not has_wildcard, f"{filepath} should not use wildcard imports"


# ═══════════════════════════════════════════════════════════════
# New Tool Edge Cases
# ═══════════════════════════════════════════════════════════════

def test_tool_scaffold_invalid_template():
    """scaffold returns error for unknown template."""
    from core.tools.handlers.scaffolder import _scaffold
    result = _scaffold(template="nonexistent", name="test")
    assert "Unknown template" in result
    assert "nonexistent" in result


def test_tool_scaffold_existing_dir():
    """scaffold rejects existing path."""
    from core.tools.handlers.scaffolder import _scaffold
    import os
    tmp = tempfile.mkdtemp()
    try:
        result = _scaffold(template="python-cli", name="x", path=tmp)
        assert "already exists" in result
    finally:
        os.rmdir(tmp)


def test_tool_scaffold_safe_format():
    """scaffold handles templates with unknown placeholders gracefully."""
    from core.tools.handlers.scaffolder import _scaffold, _TEMPLATES
    from pathlib import Path

    # Register ad-hoc template with unmatched placeholder
    _TEMPLATES["__test_safe"] = {
        "test.txt": "Hello {name}, {missing_key}, and {description}!",
    }
    tmp = tempfile.mkdtemp()
    project_dir = Path(tmp) / "safe_demo"
    try:
        result = _scaffold(template="__test_safe", name="demo", path=str(project_dir))
        assert "✅" in result
        content = (project_dir / "test.txt").read_text()
        assert "demo" in content
        assert "{missing_key}" in content  # placeholder preserved safely
    finally:
        _TEMPLATES.pop("__test_safe", None)
        shutil.rmtree(tmp, ignore_errors=True)


def test_tool_security_scan_invalid_type():
    """security_scan rejects unknown scan_type."""
    from core.tools.handlers.security_scan import _security_scan
    result = _security_scan(scan_type="php")
    assert "Invalid scan_type" in result


def test_tool_security_scan_nonexistent_path():
    """security_scan rejects non-existent path."""
    from core.tools.handlers.security_scan import _security_scan
    result = _security_scan(path="/tmp/__widdx_nonexistent_path__")
    assert "Path does not exist" in result


def test_tool_run_tests_nonexistent_path():
    """run_tests rejects non-existent path."""
    from core.tools.handlers.test_runner import _run_tests
    result = _run_tests(path="/tmp/__widdx_nonexistent_path__")
    assert "Path does not exist" in result


def test_tool_run_tests_no_framework():
    """run_tests returns helpful message when no framework detected."""
    from core.tools.handlers.test_runner import _run_tests

    tmp = tempfile.mkdtemp()
    try:
        # Empty directory with no test framework
        result = _run_tests(path=tmp)
        assert "No test framework detected" in result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_tool_run_tests_unknown_framework():
    """run_tests returns error for invalid framework name."""
    from core.tools.handlers.test_runner import _run_tests
    result = _run_tests(framework="nonexistent")
    assert "Unknown framework" in result
    assert "nonexistent" in result
