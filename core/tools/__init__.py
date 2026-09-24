"""Built-in tool definitions and execution for WIDDX.

Architecture:
  registry.py      — tool registration (register, register_dynamic, clear_dynamic)
  dispatch.py      — execution (execute, execute_with_skills)
  safety.py        — sandbox safety (configure, is_safe_path)
  registration.py  — all built-in tool definitions
  handlers/        — tool handler functions grouped by category
    file_ops.py    — read, write, edit, glob, grep, list_files
    bash.py        — bash, sandbox_exec
    web.py         — web_fetch
    validate.py    — validate, project_validate
    edit_files.py  — edit_files (atomic multi-edit)
    spawn.py       — spawn_agent
    linter.py      — run_linter
"""

# ── Re-export registry API ──
from .registry import (  # noqa: F401 — public re-export
    TOOL_DEFINITIONS,
    register,
    register_dynamic,
    clear_dynamic,
)


# ── Re-export dispatch API ──
from .dispatch import execute, execute_with_skills  # noqa: F401 — public re-export

# ── Re-export safety API ──
from .safety import configure, is_safe_path, get_safe_dir  # noqa: F401 — public re-export

# ── Re-export security scanner ──
from .security import scan_dangerous  # noqa: F401 — public re-export

# ── Re-export helpers ──
from .handlers.file_ops import get_tool_helpers as _get_file_helpers
_helpers = _get_file_helpers()
get_read_tool_def = _helpers["get_read_tool_def"]
get_write_tool_def = _helpers["get_write_tool_def"]
get_bash_tool_def = _helpers["get_bash_tool_def"]

# ── Trigger registration of all built-in tools ──
from . import registration  # noqa: E402, F401 — populates TOOL_DEFINITIONS

# ── Constants ──
MAX_TOKENS_DEFAULT = 32768
BASH_TIMEOUT = 120
MAX_STDOUT_CHARS = 5000
MAX_STDERR_CHARS = 2000


# ── Executor tool class (for LinterRunner) ──
def _handle_run_linter(file_path: str, language: str = "auto") -> str:
    from .handlers.linter import _handle_run_linter as _rn
    return _rn(file_path, language)
