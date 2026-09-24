"""Dashboard mixin — core."""
from __future__ import annotations
import logging

logger = logging.getLogger("widdx.web.dashboard")

from pathlib import Path  # noqa: E402
ROOT = Path(__file__).resolve().parent.parent.parent


class CoreDashboardMixin:
    def __init__(self):
        """
        ═══ MIXIN INIT CHAIN ═══
        This is the only mixin with __init__. All other mixins rely
        on Python's MRO to resolve methods. If you add __init__ to
        another mixin, ensure it calls: super().__init__()
        """
        self._ready = False
        self._init_systems()


    def _init_systems(self):
        try:
            from core import config, tools
            self._cfg = config.settings.load()
            self._tool_defs = list(tools.TOOL_DEFINITIONS)
            self._ready = True
        except Exception as e:
            logger.error("Dashboard init: %s", e)

    # ── System Info (WIDDX Computer) ──


    def system_info(self) -> dict:
        """OS, CPU, RAM, disk, Python version."""
        import os
        import platform
        import shutil
        info = {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count() or 0,
        }
        try:
            total, used, free = shutil.disk_usage(ROOT)
            info["disk"] = {"total": total, "used": used, "free": free}
        except Exception:
            pass
        return info


    def running_processes(self) -> list[dict]:
        """List running background processes."""
        try:
            from core.background import BackgroundTaskManager
            mgr = BackgroundTaskManager()
            return [
                {"id": t.id, "status": t.status.value, "elapsed": t.elapsed}
                for t in mgr.list_agents()  # type: ignore[attr-defined]
            ]
        except Exception:
            return []

    # ── Cron Jobs ──


    def computer_info(self) -> dict:
        """Full WIDDX Computer state."""
        try:
            from core.sandbox import SandboxExecutor
            sb = SandboxExecutor(mode="auto")
            mode = sb.mode
        except Exception:
            mode = "unknown"

        return {
            "mode": mode,
            "system": self.system_info(),
            "processes": self.running_processes(),
            "cron": self.cron_jobs(),  # type: ignore[attr-defined]
            "background": self.background_tasks(),  # type: ignore[attr-defined]
            "agents": self.sub_agents(),  # type: ignore[attr-defined]
            "memories": len(self.memories()),  # type: ignore[attr-defined]
            "sessions": len(self.sessions()),  # type: ignore[attr-defined]
            "skills": len(self.skills()),  # type: ignore[attr-defined]
        }


    def computer_exec(self, command: str) -> dict:
        """Execute a command in the WIDDX Computer sandbox."""
        try:
            from core.sandbox import SandboxExecutor
            sb = SandboxExecutor(mode="auto")
            result = sb.execute(command, timeout=60)
            return {
                "stdout": result.stdout if hasattr(result, 'stdout') else str(result),
                "stderr": result.stderr if hasattr(result, 'stderr') else "",
                "exit_code": result.exit_code if hasattr(result, 'exit_code') else 0,
                "mode": result.mode if hasattr(result, 'mode') else sb.mode,
            }
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1, "mode": "error"}

    # ════════════════════════════════════════════════════════
    # NEW: Memory CRUD (Create, Update, Delete)
    # ════════════════════════════════════════════════════════


