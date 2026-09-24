"""Permission system for WIDDX — controls which tools the AI can call.

Levels:
  permissive  — auto-allow everything (default, backward-compatible)
  normal      — auto-allow safe tools, ask for dangerous ones
  strict      — ask for every tool call
  silent      — auto-allow, no console output for tool calls

Permissions persist in .widdx/permissions.json so the user doesn't
have to re-approve the same tool twice.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional
from enum import Enum

logger = logging.getLogger("widdx.permissions")


class PermissionLevel(Enum):
    PERMISSIVE = "permissive"
    NORMAL = "normal"
    STRICT = "strict"
    SILENT = "silent"


# Tools that can modify the system
_DANGEROUS_TOOLS = {"bash", "write", "edit", "validate", "create_agent", "run_parallel", "docker", "db_query", "terminal", "pkg_mgr"}
_SAFE_TOOLS = {"read", "glob", "grep", "list_files", "web_fetch", "semantic_search", "dep_graph", "api_request"}


class PermissionManager:
    """Manages tool permissions with persistent storage."""
    def __init__(self, project_dir: str | Path | None = None):
        self._dir = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        # Check environment variable first (for tests/automation)
        env_level = os.environ.get("WIDDX_PERMISSION_LEVEL", "")
        if env_level:
            try:
                self._level = PermissionLevel(env_level)
            except ValueError:
                self._level = PermissionLevel.NORMAL
        else:
            self._level = PermissionLevel.NORMAL  # safer default — was PERMISSIVE
        self._remembered: dict[str, bool] = {}  # tool_name -> allow (True) / deny (False)
        self._tui_mode = False
        self._load()

    # ── Persistence ──────────────────────────────────────────────

    def _get_path(self) -> Path:
        return self._dir / ".widdx" / "permissions.json"

    def _load(self):
        path = self._get_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                level_str = data.get("level", "normal")
                self._level = PermissionLevel(level_str)
                self._remembered = data.get("remembered", {})
            except Exception as e:
                logging.getLogger("widdx.permissions").warning("Permissions load error: %s", e)

    def _save(self):
        path = self._get_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "level": self._level.value,
                "remembered": self._remembered,
            }, indent=2))
        except Exception:
            pass

    # ── Public API ───────────────────────────────────────────────

    @property
    def level(self) -> PermissionLevel:
        return self._level

    @level.setter
    def level(self, val: PermissionLevel | str):
        if isinstance(val, str):
            val = PermissionLevel(val)
        self._level = val
        self._save()

    def set_permission(self, tool_name: str, allow: bool):
        """Remember a permission decision for a specific tool."""
        self._remembered[tool_name] = allow
        self._save()

    def forget(self, tool_name: str | None = None):
        """Clear remembered permissions for a tool (or all)."""
        if tool_name:
            self._remembered.pop(tool_name, None)
        else:
            self._remembered.clear()
        self._save()

    def clear(self):
        """Reset everything to defaults."""
        self._level = PermissionLevel.NORMAL
        self._remembered.clear()
        self._save()

    def is_dangerous(self, tool_name: str) -> bool:
        """Check if a tool is considered dangerous."""
        return tool_name in _DANGEROUS_TOOLS

    def is_safe(self, tool_name: str) -> bool:
        """Check if a tool is safe (read-only)."""
        return tool_name in _SAFE_TOOLS

    # ── Core check ───────────────────────────────────────────────

    def check(self, tool_name: str, console=None) -> bool:
        """Check if a tool call is allowed.

        Returns True (allow) or False (deny).
        If interactive prompt is needed and console is provided, asks the user.
        """
        # Permissive / Silent: allow everything
        if self._level in (PermissionLevel.PERMISSIVE, PermissionLevel.SILENT):
            return True

        # Check remembered decisions
        if tool_name in self._remembered:
            return self._remembered[tool_name]

        # NORMAL: safe tools auto-allow, dangerous tools ask
        if self._level == PermissionLevel.NORMAL:
            if self.is_safe(tool_name):
                return True
            if self.is_dangerous(tool_name):
                return self._ask(tool_name, console)

            # Unknown tool: allow in NORMAL mode
            return True

        # STRICT: ask for everything
        if self._level == PermissionLevel.STRICT:
            if self.is_safe(tool_name):
                return self._ask(tool_name, console)
            return self._ask(tool_name, console)

        return True

    def _ask(self, tool_name: str, console=None) -> bool:
        """Ask the user for permission via console prompt.

        Returns True/False. If no console available, or in TUI mode, allows (fail-open).
        """
        if console is None:
            return True
        if getattr(self, '_tui_mode', False):
            # TUI can't use input() — check remembered permissions first
            if tool_name in self._remembered:
                return self._remembered[tool_name]
            # For STRICT mode, block unremembered tools in TUI
            if self._level == PermissionLevel.STRICT:
                return False
            # For NORMAL mode, warn but allow
            if self._level == PermissionLevel.NORMAL:
                # Could show TUI toast here — for now, allow with audit
                return True
            # PERMISSIVE: allow all
            return True

        from rich.prompt import Prompt as RPrompt
        from rich.text import Text

        danger = "⚠️  DANGEROUS" if self.is_dangerous(tool_name) else "ℹ️  safe"
        console.print()
        console.print(Text(
            f"  [{danger}] Allow {tool_name}? [y]es / [n]o / [a]lways / [d]eny",
            style="bold #f5a623",
        ))
        try:
            answer = RPrompt.ask("", default="y")
        except (EOFError, KeyboardInterrupt):
            return True

        if answer.lower() in ("a", "always"):
            self.set_permission(tool_name, True)
            return True
        elif answer.lower() in ("d", "deny", "never"):
            self.set_permission(tool_name, False)
            return False
        elif answer.lower() in ("n", "no"):
            return False
        else:
            return True

    def status(self) -> str:
        """Return a human-readable status string."""
        n_remembered = len(self._remembered)
        denied = sum(1 for v in self._remembered.values() if not v)
        return (f"level={self._level.value}, "
                f"{n_remembered} remembered ({denied} denied)")


# Singleton for the session
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """Get or create the global permission manager."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager


def enable_tui_mode():
    """Set permission manager to TUI-safe mode (non-blocking, auto-allow remembered)."""
    pm = get_permission_manager()
    pm._tui_mode = True


def enable_web_mode():
    """Set permission manager to Web-safe mode (non-blocking, no stdin prompts).

    In web mode:
    - NORMAL: safe tools auto-allow, dangerous tools auto-allow (non-blocking)
    - STRICT: falls back to NORMAL (no interactive prompts possible)
    """
    pm = get_permission_manager()
    pm._tui_mode = True
