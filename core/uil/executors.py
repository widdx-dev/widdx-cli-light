"""Shared UIL executors — reusable execution helpers for CLI and TUI."""

from __future__ import annotations

from typing import Any


def _tool_name(tool_def: dict) -> str:
    if "name" in tool_def:
        return tool_def["name"]
    fn = tool_def.get("function") or {}
    return fn.get("name", "")


def _default_args(tool_name: str, user_input: str) -> dict[str, Any]:
    text = user_input.strip()
    if tool_name == "bash":
        return {"command": text, "description": text[:80] or "direct tool"}
    if tool_name == "read":
        return {"filePath": text}
    if tool_name == "grep":
        return {"pattern": text, "path": "."}
    if tool_name == "glob":
        return {"pattern": text or "*"}
    if tool_name == "web_fetch":
        return {"url": text}
    if tool_name == "list_files":
        return {"path": text or "."}
    if tool_name == "validate":
        return {"filePath": text}
    return {"command": text}


def pick_direct_tool(tool_defs: list[dict]) -> str | None:
    """Choose the best single tool from a filtered tool list."""
    if not tool_defs:
        return None
    names = [_tool_name(td) for td in tool_defs if _tool_name(td)]
    if not names:
        return None
    if "bash" in names:
        return "bash"
    return names[0]


def run_direct_tool(ctx_or_decision: Any, user_input: str) -> str:
    """Execute one tool from the routing decision's filtered tool list."""
    from core import tools

    tool_defs = getattr(ctx_or_decision, "tool_defs", None) or []
    tool_name = pick_direct_tool(tool_defs)
    if not tool_name:
        return "No tools available for direct execution."

    args = _default_args(tool_name, user_input)
    return tools.execute(tool_name, args)
