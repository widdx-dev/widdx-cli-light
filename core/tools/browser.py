"""Browser tools — navigate, screenshot, click, type, snapshot, press keys.

Uses Playwright MCP when available; falls back to HTTP fetch for navigation.
"""
from __future__ import annotations

# Lazy imports from core.tools done inside functions to avoid circular deps

logger = __import__("logging").getLogger("widdx.tools")

# ── Browser / Computer Use tools ─────────────────────────────


def _browser_navigate(url: str) -> str:
    """Open a URL in the browser and return the page content (text).

    Uses Playwright if available, otherwise falls back to HTTP fetch.
    """
    # Try Playwright MCP first (if connected)
    try:
        from core.mcp.client import get_mcp_manager
        mgr = get_mcp_manager()
        if mgr.has_tool("mcp__playwright__browser_navigate") or mgr.has_tool("mcp__playwright__navigate"):
            tool_name = "mcp__playwright__browser_navigate" if mgr.has_tool("mcp__playwright__browser_navigate") else "mcp__playwright__navigate"
            return mgr.call_tool(tool_name, {"url": url})
    except Exception:
        pass
    # Fallback: HTTP fetch
    # Lazy import to avoid circular dependency
    from .handlers.web import _web_fetch
    return _web_fetch(url)


def _browser_screenshot(url: str | None = None, selector: str | None = None) -> str:
    """Take a screenshot of the current page or a specific URL.

    Uses Playwright MCP if available.
    """
    try:
        from core.mcp.client import get_mcp_manager
        mgr = get_mcp_manager()
        # Navigate first if URL provided
        if url:
            tool_name = "mcp__playwright__browser_navigate" if mgr.has_tool("mcp__playwright__browser_navigate") else "mcp__playwright__navigate"
            mgr.call_tool(tool_name, {"url": url})
        # Take screenshot
        if mgr.has_tool("mcp__playwright__screenshot"):
            args = {}
            if selector:
                args["selector"] = selector
            return mgr.call_tool("mcp__playwright__screenshot", args)
        return "Screenshot not available — Playwright MCP not connected"
    except Exception as e:
        return f"Screenshot error: {e}"


def _browser_click(selector: str) -> str:
    """Click an element on the current page by CSS selector."""
    try:
        from core.mcp.client import get_mcp_manager
        mgr = get_mcp_manager()
        if mgr.has_tool("mcp__playwright__click"):
            return mgr.call_tool("mcp__playwright__click", {"selector": selector})
        return "Click not available — Playwright MCP not connected"
    except Exception as e:
        return f"Click error: {e}"


def _browser_snapshot() -> str:
    """Get the current page's accessibility snapshot (text-only)."""
    try:
        from core.mcp.client import get_mcp_manager
        mgr = get_mcp_manager()
        if mgr.has_tool("mcp__playwright__snapshot"):
            return mgr.call_tool("mcp__playwright__snapshot", {})
        return "Snapshot not available — Playwright MCP not connected"
    except Exception as e:
        return f"Snapshot error: {e}"


def _browser_type(selector: str, text: str) -> str:
    """Type text into an element identified by CSS selector."""
    try:
        from core.mcp.client import get_mcp_manager
        mgr = get_mcp_manager()
        if mgr.has_tool("mcp__playwright__fill") or mgr.has_tool("mcp__playwright__type"):
            tool_name = "mcp__playwright__fill" if mgr.has_tool("mcp__playwright__fill") else "mcp__playwright__type"
            return mgr.call_tool(tool_name, {"selector": selector, "text": text})
        return "Type not available — Playwright MCP not connected"
    except Exception as e:
        return f"Type error: {e}"


def _browser_press(key: str) -> str:
    """Press a keyboard key (Enter, Escape, Tab, etc.)."""
    try:
        from core.mcp.client import get_mcp_manager
        mgr = get_mcp_manager()
        if mgr.has_tool("mcp__playwright__press"):
            return mgr.call_tool("mcp__playwright__press", {"key": key})
        return "Key press not available — Playwright MCP not connected"
    except Exception as e:
        return f"Key press error: {e}"
