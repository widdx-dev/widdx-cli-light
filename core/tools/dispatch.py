"""Tool dispatch — execute() and execute_with_skills() with timeout & safety.

All tool execution is wrapped with:
  - Timeout enforcement (per-tool configurable timeout)
  - Resource limit tracking (concurrent executions, memory)
  - Performance monitoring (latency tracking)
  - Error classification (transient vs permanent)
"""

import logging
import time
from typing import Any, Callable, Optional

from .registry import get_tool_map
from .safety import execute_safely, TimeoutError, get_tool_timeout
from core.monitoring import metrics_collector

logger = logging.getLogger("widdx.tools.dispatch")

# Transient errors that should trigger a retry
_TRANSIENT_ERRORS = (
    TimeoutError,
    ConnectionError, ConnectionRefusedError, ConnectionResetError,
    TimeoutError,
    OSError,  # file system may be temporarily unavailable
)

# Maximum retries for transient errors
_MAX_RETRIES = 2


def execute(name: str, args: dict[str, Any]) -> str:
    """Execute a registered tool by name with timeout + monitoring.

    Args:
        name: Tool name.
        args: Tool arguments.

    Returns:
        Tool result string (never raises — errors are returned as strings).
    """
    handler = get_tool_map().get(name)
    if not handler:
        return f"❌ Unknown tool: {name}"

    # Wrap handler with safety (timeout + resource limits)
    def _run():
        return handler(**args)

    try:
        return execute_safely(name, _run, timeout=get_tool_timeout(name))
    except TimeoutError:
        logger.warning("Tool '%s' timed out after %.1fs", name, get_tool_timeout(name))
        return f"❌ Tool '{name}' timed out after {get_tool_timeout(name):.1f}s. Try a simpler command."
    except Exception as e:
        logger.error("Tool '%s' failed: %s", name, e, exc_info=True)
        return f"❌ Tool '{name}' failed: {e}"


def execute_with_skills(name: str, args: dict) -> str:
    """Execute a tool, routing through skill_manager if a skill is active.

    All execution is wrapped with timeout enforcement, resource limits,
    and performance monitoring.

    Args:
        name: Tool name.
        args: Tool arguments.

    Returns:
        Tool result string.
    """
    from core.skills import skill_manager

    if name == "use_skill":
        skill_name = args.get("skill_name", "")
        if skill_name:
            ok = skill_manager.activate(skill_name)
            return f"Skill '{skill_name}' activated." if ok else f"❌ Unknown skill '{skill_name}'"
        skill_manager.deactivate()
        return "Skill deactivated."

    # Permission check
    from core.permissions import get_permission_manager
    from rich.console import Console as _RichConsole
    _console = _RichConsole(highlight=False)
    pm = get_permission_manager()
    if not pm.check(name, console=_console):
        return f"⛔ Permission denied: {name}"

    # Active skill routing
    if skill_manager.active and name in skill_manager.active.tools:
        return skill_manager.execute_tool(name, args)

    # Workflow tools
    if name in ("create_agent", "run_parallel"):
        from core.workflow import WorkflowEngine
        try:
            from core.config.settings import load as load_config
            cfg = load_config()
            from core.providers.providers import create_provider
            provider = create_provider(cfg)
            wf = WorkflowEngine(provider, [], cfg, {})
            return _execute_with_tracking(name, args, lambda: wf.execute_workflow_tool(name, args))
        except Exception as e:
            return f"❌ Workflow execution error: {e}"

    # MCP tools
    if name.startswith("mcp__"):
        from core.mcp.client import get_mcp_manager
        mcp = get_mcp_manager()
        if mcp.has_tool(name):
            return _execute_with_tracking(name, args, lambda: mcp.call_tool(name, args))
        return f"❌ MCP tool not available: {name}"

    # Normal tool execution with full safety
    return _execute_with_tracking(name, args, lambda: execute(name, args))


def _execute_with_tracking(name: str, args: dict, func: Callable[[], str]) -> str:
    """Execute a tool with performance monitoring and retry on transient errors.

    Args:
        name: Tool name.
        args: Tool arguments.
        func: The actual execution function.

    Returns:
        Tool result string.
    """
    # Track in performance monitoring
    with metrics_collector.track_tool(name):
        last_error: Optional[str] = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                t0 = time.monotonic()
                result = func()
                duration = time.monotonic() - t0
                logger.debug(
                    "Tool '%s' completed in %.2fs (attempt %d/%d)",
                    name, duration, attempt + 1, _MAX_RETRIES + 1,
                )
                return result
            except _TRANSIENT_ERRORS as e:
                last_error = str(e)
                if attempt < _MAX_RETRIES:
                    wait = 1.0 * (2 ** attempt)  # exponential backoff
                    logger.info(
                        "Tool '%s' transient error, retrying in %.1fs "
                        "(attempt %d/%d): %s",
                        name, wait, attempt + 1, _MAX_RETRIES + 1, e,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "Tool '%s' failed after %d retries: %s",
                        name, _MAX_RETRIES + 1, e,
                    )
                    return f"❌ Tool '{name}' failed after retries: {e}"
            except Exception as e:
                # Permanent error — no retry
                logger.error("Tool '%s' failed: %s", name, e, exc_info=True)
                return f"❌ Tool '{name}' failed: {e}"

    return f"❌ Tool '{name}' failed: {last_error}"
