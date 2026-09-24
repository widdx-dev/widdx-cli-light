"""Tool registry — registration and dynamic tool management."""

from typing import Callable

TOOL_DEFINITIONS: list[dict] = []
_TOOL_MAP: dict[str, Callable] = {}
_DYNAMIC_TOOLS: list[dict] = []


def register(name: str, description: str, parameters: dict, handler: Callable):
    """Register a tool: adds its definition and maps name -> handler."""
    TOOL_DEFINITIONS.append({
        "name": name,
        "description": description,
        "parameters": parameters,
    })
    _TOOL_MAP[name] = handler


def register_dynamic(tool_defs: list[dict], tool_map: dict[str, Callable]):
    """Register dynamically-created tools (e.g. workflow tools)."""
    global _DYNAMIC_TOOLS
    _DYNAMIC_TOOLS = tool_defs
    for td in tool_defs:
        handler = tool_map.get(td["name"])
        if handler:
            _TOOL_MAP[td["name"]] = handler


def clear_dynamic():
    """Remove all dynamically-registered tools."""
    global _DYNAMIC_TOOLS
    for td in _DYNAMIC_TOOLS:
        _TOOL_MAP.pop(td["name"], None)
    _DYNAMIC_TOOLS = []


def get_tool_map() -> dict[str, Callable]:
    return _TOOL_MAP
