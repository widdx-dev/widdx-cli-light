"""WIDDX CLI — main entry point for the terminal interface.

Clean architecture:
  - ``app.py``       — main loop, initialization
  - ``display.py``   — Rich rendering
  - ``input.py``     — prompt_toolkit input
  - ``commands.py``  — slash command processing
  - ``theme.py``     — colors and styles

All back-end logic lives in ``core/`` — this module only connects.
"""

import sys
import time
import hashlib
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


# ── Project change detection ──────────────────────────────────────
_last_index_hash: str | None = None
_last_index_check: float = 0.0
_INDEX_THROTTLE_SECONDS = 30
_MAX_FILES_TO_SCAN = 10000

IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", ".widdx",
               "node_modules", ".venv", "venv", "env",
               ".idea", ".vscode", ".DS_Store"}


def _project_changed(project_dir: Path, extra_ignore: list | None = None) -> bool:
    """Check if project files have changed since last index build (throttled)."""
    global _last_index_hash, _last_index_check
    now = time.time()
    if now - _last_index_check < _INDEX_THROTTLE_SECONDS:
        return False
    _last_index_check = now
    root = project_dir.resolve()
    ignore = set(IGNORE_DIRS)
    if extra_ignore:
        ignore.update(extra_ignore)
    entries: list[str] = []
    file_count = 0
    try:
        for f in sorted(root.rglob("*")):
            try:
                if f.is_file():
                    rel = f.relative_to(root)
                    if any(part in ignore or part.startswith(".") for part in rel.parts):
                        continue
                    st = f.stat()
                    entries.append(f"{rel}:{st.st_size}:{st.st_mtime_ns}")
                    file_count += 1
                    if file_count > _MAX_FILES_TO_SCAN:
                        break
            except (PermissionError, OSError):
                continue
    except OSError:
        pass
    current_hash = hashlib.md5("|".join(entries).encode()).hexdigest()
    if current_hash == _last_index_hash:
        return False
    _last_index_hash = current_hash
    return True

from core import tools  # noqa: E402
from core.config.settings import load as load_config  # noqa: E402
from core.providers.providers import create_provider  # noqa: E402
from core.mcp.client import get_mcp_manager  # noqa: E402
from core.project import state as project_state  # noqa: E402
from core.project.scanner import ProjectScanner  # noqa: E402
from core.project import git as git_utils  # noqa: E402
from core.project_tracker import ensure_docs, build_context_block  # noqa: E402
from core.auto_setup import setup_project  # noqa: E402
from core.memory import MemoryStore  # noqa: E402
from core.memory_learner import MemoryLearner  # noqa: E402
from core.skills import skill_manager  # noqa: E402
from core.uil import UnifiedIntelligenceLayer, ExecutionMode  # noqa: E402
from core.agents.executor_adapter import EXECUTOR_MAP  # noqa: E402
from core.workflow import WorkflowEngine  # noqa: E402
from core.config.keychain import prompt_key, has_key  # noqa: E402

from .display import (  # noqa: E402
    console,
    show_header, show_user_msg, show_system_msg, show_ai_msg,
    show_divider, show_table, show_panel, show_error, show_success,
)
from .input import CLIInput  # noqa: E402
from .commands import CLICommands  # noqa: E402

from core.constants import SYSTEM_PROMPT  # noqa: E402
from core.log_setup import setup_logging  # noqa: E402
logger = setup_logging("widdx.cli")


class CLIApp:
    """Main CLI application — ties everything together."""

    def __init__(self):
        self.cfg = load_config()
        self.provider = create_provider(self.cfg)
        self.mcp_mgr = get_mcp_manager()
        self.mcp_mgr.load_from_config(self.cfg)
        self.state: dict = {"model": f"{self.provider.name}/{self.provider.model}", "cost": 0.0, "turns": 0}
        self.messages: list[dict] = [{"role": "system", "content": "You are WIDDX Nexus, a helpful AI assistant."}]
        self.scanner = ProjectScanner()
        self.input_handler = CLIInput()
        self.cmds = CLICommands(self)

    # ── Startup ──────────────────────────────────────────────
    def startup(self):
        """Initialize everything and print startup messages."""

        # System prompt
        all_sk = skill_manager.list_all()
        skill_names = ", ".join(s.name for s in all_sk) if all_sk else "none"
        system_prompt = SYSTEM_PROMPT.replace("{skills_list}", skill_names)
        self.messages = [{"role": "system", "content": system_prompt}]

        # API key prompt
        if self.provider.name in ("deepseek", "openai") and not has_key(self.provider.name):
            if not self.provider.api_key or self.provider.api_key == "public":
                show_system_msg(f"No API key for {self.provider.name}. Enter one now:")
                key = prompt_key(self.provider.name)
                if key:
                    self.provider.api_key = key

        # MCP
        if self.mcp_mgr.server_count > 0:
            show_system_msg(f"MCP: {self.mcp_mgr.server_count} server(s) registered")

        # Header
        show_header(self.state["model"], self.state["cost"], self.state["turns"])

        # Session recovery
        session_data = project_state.load_session()
        if session_data:
            saved_msgs = session_data.get("messages", [])
            saved_state = session_data.get("state", {})
            if saved_msgs:
                saved_msgs = [m for m in saved_msgs if "[PROJECT STATE" not in (m.get("content") or "")]
                self.state["cost"] = saved_state.get("cost", 0.0)
                self.state["turns"] = saved_state.get("turns", 0)
                self.messages.extend(saved_msgs)
                show_system_msg(f"Session restored: {len(saved_msgs)} messages")

        # Project context — use both scanner (files) + context manager (git, env)
        ctx_parts = []
        scanner_ctx = self.scanner.build_context_block()
        if scanner_ctx:
            ctx_parts.append(scanner_ctx)
        try:
            from core.project_context import get_project_context as _get_pctx
            pctx = _get_pctx()
            rich_ctx = pctx.get_context_summary()
            if rich_ctx:
                ctx_parts.append(rich_ctx)
        except Exception:
            pass
        if ctx_parts:
            full_ctx = "\n\n".join(ctx_parts)
            self.messages.insert(1, {"role": "system", "content": full_ctx, "_project_context": True})
            show_system_msg("Project context loaded")

        # Memory
        global_mem = MemoryStore()
        project_mem = MemoryStore(project_dir=Path.cwd().resolve())
        seen_names = set()
        merged_mem = []
        for src in [global_mem.list_all(), project_mem.list_all()]:
            for m in src:
                if m["name"] not in seen_names:
                    seen_names.add(m["name"])
                    merged_mem.append(m)
        if merged_mem:
            mem_text = "\n".join(f"  - {m['name']}: {m['description'][:100]}" for m in merged_mem)
            self.messages.append({"role": "system", "content": f"[PERSISTENT MEMORY — {len(merged_mem)} fact(s)]\n{mem_text}"})
            show_system_msg(f"Memory: {len(merged_mem)} fact(s) loaded")

        # Project tracker
        try:
            ensure_docs(Path.cwd().resolve())
            pt_ctx = build_context_block(Path.cwd().resolve())
            if pt_ctx:
                self.messages.append({"role": "system", "content": pt_ctx, "_project_docs": True})
                show_system_msg("Project docs loaded (plan, tasks, roadmap)")
        except Exception:
            pass

        # Auto setup
        try:
            auto_result = setup_project(Path.cwd().resolve())
            parts = []
            if auto_result["deps_installed"]:
                parts.append(f"deps: {', '.join(auto_result['deps_installed'])}")
            if auto_result["facts_learned"]:
                parts.append(f"learned: {auto_result['facts_learned']} facts")
            if parts:
                show_system_msg(f"Auto-setup: {' | '.join(parts)}")
        except Exception:
            pass

    # ── Main Loop ────────────────────────────────────────────
    def run(self):
        """Start the main interaction loop."""
        self.startup()

        while True:
            try:
                user_input = self.input_handler.get_input(self.state["model"])
            except (KeyboardInterrupt, EOFError):
                show_system_msg("Goodbye — session saved.")
                break

            if not user_input:
                continue

            # ── Auto-Skill Suggestion ─────────────────────────────
            if not user_input.startswith("!") and not user_input.startswith("/"):
                suggested_skills = skill_manager.suggest_skills(user_input)
                if suggested_skills and not skill_manager.active:
                    icons = [s.icon for s in suggested_skills if s.icon]
                    names = [s.name for s in suggested_skills]
                    msg = f"💡 Suggested skills: {', '.join([f'{icon} {name}' for icon, name in zip(icons, names)])}"
                    show_system_msg(msg)
                    show_system_msg(f"   Activate with: !{suggested_skills[0].name}")

            # Command?
            is_cmd = self.cmds.handle(user_input, self.provider, self.state, self.messages)
            if is_cmd:
                continue

            # Normal message
            show_divider()
            show_user_msg(user_input)
            self._process_message(user_input)

        # Shutdown
        self._shutdown()

    def _process_message(self, user_input: str):
        """Process a normal message through UIL."""
        # ── Vision: detect images in input ──────────────────────
        try:
            from core.vision import process_user_input_with_vision
            clean_input, self.messages = process_user_input_with_vision(user_input, self.messages)
        except Exception:
            clean_input = user_input

        self.messages.append({"role": "user", "content": clean_input or user_input})

        # Build tool definitions
        tool_defs = list(tools.TOOL_DEFINITIONS)
        use_skill_def = skill_manager.get_use_skill_tool_def()
        if use_skill_def:
            tool_defs.append(use_skill_def)
        skill_tools = skill_manager.get_active_tools()
        if skill_tools:
            tool_defs.extend(skill_tools)
        try:
            tool_defs.extend(self.mcp_mgr.get_all_tool_definitions())
        except Exception:
            pass
        wf = WorkflowEngine(self.provider, tool_defs, self.cfg, self.state)
        tool_defs.extend(wf.get_tool_definitions())

        # UIL
        uil = UnifiedIntelligenceLayer(provider=self.provider)
        uil.set_tool_defs(tool_defs)

        executors = EXECUTOR_MAP

        result = None
        decision = None
        try:
            # Pass project card to UIL for project-aware classification
            project_card = getattr(self.scanner, '_card', None)
            if project_card is None:
                try:
                    self.scanner.quick_check() or self.scanner.scan()
                    project_card = getattr(self.scanner, '_card', None)
                except Exception:
                    pass

            result, decision = uil.process(
                user_input,
                messages=self.messages,
                executors=executors,
                cfg=self.cfg,
                state=self.state,
                project_card=project_card,
            )
            summary = result.summary

            # Show verification warnings/errors to user
            if result and result.verification and result.verification.findings:
                criticals = result.verification.criticals
                errors = result.verification.errors
                if criticals:
                    self.show_error(
                        f"🔴 Verification: {len(criticals)} critical issue(s):\n"
                        + "\n".join(f"  • {f.message}" for f in criticals[:3])
                    )
                if errors and not criticals:
                    self.show_system(
                        f"⚠️ Verification: {len(errors)} issue(s) found\n"
                        + "\n".join(f"  • {f.message}" for f in errors[:3])
                    )
        except Exception as e:
            show_error(str(e))
            summary = f"Error: {e}"

        self.messages.append({"role": "assistant", "content": summary})
        # SIMPLE_CHAT already streams via core.chat → skip redundant panel.
        # Show panel for errors or non-streaming modes (AUTONOMOUS, EXPERT_TEAM).
        is_simple_chat = (
            decision and decision.plan
            and decision.plan.mode == ExecutionMode.SIMPLE_CHAT
        )
        if not is_simple_chat or (result and result.error):
            show_ai_msg(summary)

        # Post-turn
        self._post_turn(user_input)

    def _post_turn(self, user_input: str):
        """Run after each turn: save, commit, reflect, learn, suggest."""
        try:
            project_state.save_session(self.messages, self.state)
        except Exception:
            pass

        # Index on project change
        try:
            proj_config = project_state.load_project_config()
            extra_ignore = proj_config.get("exclude_from_index", [])
            if _project_changed(Path.cwd().resolve(), extra_ignore):
                project_state.save_index(Path.cwd().resolve(), extra_ignore=extra_ignore)
        except Exception:
            pass

        # Auto commit
        try:
            if project_state.load_project_config().get("auto_commit", True):
                git_utils.auto_commit(Path.cwd().resolve(), user_input)
        except Exception:
            pass

        # Self-Reflection (every 4 turns)
        try:
            if self.state.get("turns", 0) % 4 == 0 and self.state.get("turns", 0) > 0:
                from core.self_reflection import reflect_on_last_turn
                reflect_on_last_turn(self.provider, self.messages, self.state)
        except Exception:
            pass

        # Self-improvement: learn from errors
        try:
            last_error = self.state.get("last_error")
            if last_error:
                from core.self_improve import get_improver
                improver = get_improver()
                improver.record_error("chat_turn", str(last_error)[:200], "unresolved")
                self.state["last_error"] = None  # clear after learning
        except Exception:
            pass

        # Auto-extract memories (every 2 turns)
        try:
            if self.state.get("turns", 0) % 2 == 0:
                from core.utils import get_last_turn
                last = get_last_turn(self.messages)
                if last:
                    ml = MemoryLearner(provider=self.provider)
                    tools_used = list(self.state.get("tools_used", []))
                    memories = ml.extract_from_turn(last["user"], last["assistant"], tools_used)
                    if memories:
                        ml.store_memories(memories)
                        for m in memories:
                            show_system_msg(f"[dim]Learned: [{m['type']}] {m['content'][:60]}[/]")
        except Exception:
            pass

        # Proactive suggestions
        try:
            from core.suggester import ProjectSuggester
            ps = ProjectSuggester()
            for s in ps.suggest()[:2]:
                show_system_msg(f"[dim]{s.icon}  Suggestion: {s.title}[/]")
        except Exception:
            pass

    # ── Display helpers (for CLICommands) ──────────────────────
    def show_system(self, text: str):
        show_system_msg(text)

    def show_table(self, title, columns, rows):
        show_table(title, columns, rows)

    def show_panel(self, title, content):
        show_panel(title, content)

    def show_error(self, text: str):
        show_error(text)

    def show_success(self, text: str):
        show_success(text)

    def show_header(self):
        show_header(self.state["model"], self.state["cost"], self.state["turns"])

    # ── Shutdown ───────────────────────────────────────────────
    def _shutdown(self):
        try:
            project_state.save_session(self.messages, self.state)
        except Exception:
            pass
        from rich.rule import Rule
        from rich.align import Align
        from rich.text import Text
        from .theme import DIM, GREEN, GOLD
        console.print()
        console.print(Rule(style=DIM))
        console.print(Align.center(Text.assemble(
            (" ◆ WIDDX  ", f"bold {GREEN}"),
            ("Session ended  ", f"{DIM}"),
            (f"turns: {self.state['turns']}  ", "bold white"),
            (f"cost: ${self.state['cost']:.4f}", f"bold {GOLD}"),
        )))
        console.print(Rule(style=DIM))
        console.print()


def run():
    """Entry point for the `widdx` command."""
    # Enable diagnostics to catch silent errors
    try:
        from core.diagnostics import error_collector
        error_collector.enable()
    except Exception:
        pass
    app = CLIApp()
    app.run()


if __name__ == "__main__":
    run()
