"""Web UI — Sandbox handler. Live terminal, browser, file tree.

Usage:
    from scripts.web.sandbox import SandboxHandler
    handler = SandboxHandler()
    handler.execute("ls -la")
    handler.screenshot()
    handler.file_tree()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("widdx.web.sandbox")

from core._path import ensure_project_root  # noqa: E402
ensure_project_root()


class SandboxHandler:
    """Exposes sandbox features to the Web UI: terminal, browser, files."""

    def __init__(self):
        self._sandbox: Any = None
        self._init_sandbox()

    def _init_sandbox(self):
        try:
            from core.sandbox import SandboxExecutor
            self._sandbox = SandboxExecutor(mode="auto")
            logger.info("Sandbox mode: %s", self._sandbox.mode)
        except Exception as e:
            logger.error("Sandbox init: %s", e)

    def execute(self, command: str, timeout: int = 60) -> dict:
        """Execute a command in the sandbox and return result."""
        if self._sandbox is None:
            result = self._fallback_execute(command, timeout)
        else:
            result = self._sandbox.execute(command, timeout)

        return {
            "stdout": result.stdout if hasattr(result, 'stdout') else (result or ""),
            "stderr": result.stderr if hasattr(result, 'stderr') else "",
            "exit_code": result.exit_code if hasattr(result, 'exit_code') else 0,
            "mode": result.mode if hasattr(result, 'mode') else "auto",
        }

    def _fallback_execute(self, command: str, timeout: int) -> Any:
        """Fallback using subprocess directly — security: uses shell=False with split."""
        import subprocess
        import shlex
        try:
            cmd_parts = shlex.split(command)
            proc = subprocess.run(
                cmd_parts, shell=False, capture_output=True, text=True, timeout=timeout
            )
            return proc
        except (ValueError, subprocess.TimeoutExpired):
            return type('obj', (object,), {
                'stdout': '', 'stderr': 'Timeout or parse error', 'exit_code': -1, 'mode': 'fallback'
            })()

    def screenshot(self) -> dict:
        """Take a browser screenshot via Playwright MCP."""
        try:
            from core.mcp.client import get_mcp_manager
            mgr = get_mcp_manager()

            # Try Playwright MCP
            for tool_name in ["mcp__playwright__screenshot", "mcp__playwright__browser_screenshot"]:
                if mgr.has_tool(tool_name):
                    result = mgr.call_tool(tool_name, {})
                    return {"success": True, "data": result}
            return {"success": False, "error": "Playwright not connected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def file_tree(self, path: str = ".") -> dict:
        """Get file tree of a project directory."""
        base = Path(path).resolve()
        if not base.exists():
            return {"error": f"Path not found: {path}"}

        def _walk(dir_path: Path, max_depth: int = 3) -> list[dict]:
            if max_depth <= 0:
                return []
            items = []
            try:
                for child in sorted(dir_path.iterdir()):
                    if child.name.startswith(".") or child.name == "__pycache__":
                        continue
                    entry: dict[str, object] = {
                        "name": child.name,
                        "type": "directory" if child.is_dir() else "file",
                        "path": str(child.relative_to(base)),
                    }
                    if child.is_dir():
                        entry["children"] = _walk(child, max_depth - 1)
                    else:
                        try:
                            entry["size"] = child.stat().st_size
                        except Exception:
                            entry["size"] = 0
                    items.append(entry)
            except PermissionError:
                pass
            return items

        return {"root": base.name, "files": _walk(base)}

    @property
    def mode(self) -> str:
        if self._sandbox:
            return self._sandbox.mode
        return "fallback"
