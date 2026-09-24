"""TUI State Management — central state for WIDDX TUI."""

from pathlib import Path

from core import tools
from core.config.settings import load as load_config
from core.providers.providers import create_provider
from core.memory import MemoryStore
from core.project import state as project_state
from core.project.scanner import ProjectScanner
from core.project_tracker import ensure_docs, build_context_block
from core.auto_setup import setup_project
from core.skills import skill_manager
from core.mcp.client import get_mcp_manager
from core.workflow import WorkflowEngine


class TUIState:
    """Central state for the TUI — replaces self._state dict pattern.

    All components read from here.  When something changes, update the
    attribute and post a message to trigger UI refresh.
    """

    def __init__(self):
        self.cfg: dict = load_config()
        self.provider = create_provider(self.cfg)
        self.mcp_mgr = get_mcp_manager()
        self.mcp_mgr.load_from_config(self.cfg)

        self.messages: list[dict] = []
        self.model: str = f"{self.provider.name}/{self.provider.model}"
        self.cost: float = 0.0
        self.turns: int = 0
        self.tools_used: list[str] = []
        self._last_reasoning: str = ""

        self.scanner = ProjectScanner()
        self.tool_defs: list[dict] = []
        self._rebuild_tool_defs()

    # ── Tool definitions (with MCP + skills + workflow) ─────
    def _rebuild_tool_defs(self):
        td = list(tools.TOOL_DEFINITIONS)
        use_skill = skill_manager.get_use_skill_tool_def()
        if use_skill:
            td.append(use_skill)
        skill_tools = skill_manager.get_active_tools()
        if skill_tools:
            td.extend(skill_tools)
        try:
            td.extend(self.mcp_mgr.get_all_tool_definitions())
        except Exception:
            pass
        try:
            wf = WorkflowEngine(self.provider, td, self.cfg, {})
            td.extend(wf.get_tool_definitions())
        except Exception:
            pass
        self.tool_defs = td

    # ── Startup ────────────────────────────────────────────
    def startup(self) -> list[str]:
        """Run all startup tasks. Returns list of log lines."""
        logs: list[str] = []

        # Session recovery
        session = project_state.load_session()
        if session:
            self.messages = session.get("messages", [])
            s = session.get("state", {})
            self.cost = s.get("cost", 0.0)
            self.turns = s.get("turns", 0)
            logs.append(f"🔄 Session restored: {len(self.messages)} messages")

        # Project context
        ctx = self.scanner.build_context_block()
        if ctx:
            self._inject_system("_project_context", ctx)
            logs.append("📁 Project context loaded")

        # Global + project memory
        global_mem = MemoryStore()
        project_mem = MemoryStore(project_dir=Path.cwd().resolve())
        seen = set()
        merged = []
        for src in [global_mem.list_all(), project_mem.list_all()]:
            for m in src:
                if m["name"] not in seen:
                    seen.add(m["name"])
                    merged.append(m)
        if merged:
            lines = "\n".join(f"  - {m['name']}: {m['description'][:80]}" for m in merged)
            self._inject_system("_memory_context", f"[PERSISTENT MEMORY — {len(merged)} fact(s)]\n{lines}")
            logs.append(f"🧠 Memory: {len(merged)} fact(s)")

        # Auto-setup
        try:
            ar = setup_project(Path.cwd().resolve())
            parts = []
            if ar["deps_installed"]:
                parts.append(f"deps: {', '.join(ar['deps_installed'])}")
            if ar["facts_learned"]:
                parts.append(f"learned: {ar['facts_learned']} facts")
            if parts:
                logs.append(f"⚡ Auto-setup: {' | '.join(parts)}")
        except Exception:
            pass

        # Project docs
        try:
            created = ensure_docs(Path.cwd().resolve())
            if created:
                logs.append(f"📋 Created docs: {', '.join(created)}")
            pt_ctx = build_context_block(Path.cwd().resolve())
            if pt_ctx:
                self._inject_system("_project_docs", pt_ctx)
                logs.append("📋 Project docs loaded")
        except Exception:
            pass

        # Update tool defs with project tracker tool
        self._rebuild_tool_defs()
        return logs

    def _inject_system(self, flag: str, content: str):
        """Add or replace a system message with the given flag."""
        self.messages = [m for m in self.messages if not m.get(flag)]
        self.messages.insert(0, {"role": "system", "content": content, flag: True})

    # ── Session persistence ────────────────────────────────
    def save_session(self):
        try:
            project_state.save_session(self.messages, {
                "model": self.model,
                "cost": self.cost,
                "turns": self.turns,
            })
        except Exception:
            pass

    def clear_session(self):
        self.messages = []
        self.cost = 0.0
        self.turns = 0
        self.tools_used = []
