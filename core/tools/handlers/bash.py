"""Bash and sandbox execution tools."""

import logging
import platform

from core.tools.security import scan_dangerous as _scan_dangerous
from core.tool_tracer import t as tool_tracer

logger = logging.getLogger("widdx.tools.bash")

BASH_TIMEOUT = 120
MAX_STDOUT_CHARS = 5000
MAX_STDERR_CHARS = 2000


def _bash(command: str, description: str | None = None) -> str:
    desc = description or command[:50]
    blocked, warnings_list = _scan_dangerous(command)
    if blocked:
        risk_list = "\n".join(f"  • {r}" for r in blocked)
        return (
            f"🚫 BLOCKED — Dangerous command detected:\n\n"
            f"Command: {command[:200]}\n\n"
            f"Risks found:\n{risk_list}\n\n"
            f"Tip: Use safer alternatives or confirm with the user first."
        )
    prefix = ""
    if warnings_list:
        prefix = "⚠️ WARNING — Suspicious patterns:\n" + "\n".join(f"  • {r}" for r in warnings_list) + "\n\n"
    try:
        tool_tracer.handler("bash")
        from core.sandbox import SandboxExecutor
        sandbox_mode = "subprocess" if platform.system() == "Windows" else "auto"
        sb = SandboxExecutor(mode=sandbox_mode)
        tool_tracer.before_sandbox(command)
        result = sb.execute(command, timeout=BASH_TIMEOUT)
        tool_tracer.after_sandbox(result.exit_code, result.elapsed_ms / 1000 if hasattr(result, 'elapsed_ms') else 0.0, result.stdout, result.stderr)
        for f in (result.files_created or []):
            tool_tracer.file_created(str(f))
        out = result.stdout[:MAX_STDOUT_CHARS]
        err = result.stderr[:MAX_STDERR_CHARS]
        ret = prefix + f"💲 {desc}\n"
        if out:
            ret += f"📤 stdout:\n{out}\n"
        if err:
            ret += f"📛 stderr:\n{err}\n"
        if result.was_timeout:
            ret += f"🔚 Exit code: timeout (killed after {BASH_TIMEOUT}s)"
        else:
            ret += f"🔚 Exit code: {result.exit_code}"
        return ret
    except Exception as e:
        logger.warning("bash tool error: %s | command: %s", e, command[:100])
        return f"⚠️ Failed: {e}"


def _handle_sandbox_exec(command: str, timeout: int = 60, cwd: str = "") -> str:
    from core.sandbox import SandboxExecutor
    sandbox_mode = "subprocess" if platform.system() == "Windows" else "auto"
    sb = SandboxExecutor(mode=sandbox_mode)
    result = sb.execute(command, timeout=timeout)
    out = result.stdout[:3000] if result.stdout else ""
    err = result.stderr[:1000] if result.stderr else ""
    status = f"exit={result.exit_code}" + (" [TIMEOUT]" if result.was_timeout else "")
    stderr_part = f"STDERR:\n{err}" if err else ""
    return f"[{status}]\n{out}\n{stderr_part}".strip()
