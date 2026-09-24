"""
WIDDX TUI — Modern Terminal Interface
Professional dark theme with full Arabic support
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

try:
    from core._path import ensure_project_root
except ImportError:
    _root = str(Path(__file__).resolve().parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from core._path import ensure_project_root

ROOT = ensure_project_root()

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import RichLog, Input, Static, Button, Select
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual import work

from typing import Any
from core.ui_visual import (
    render_user_message, render_assistant_message, render_system_message, render_tool_message, render_reasoning, render_error, render_divider
)
from core.mcp.client import get_mcp_manager
from core.skills import skill_manager
from core.memory import MemoryStore

from .state import TUIState
from .chat_engine import ChatEngine, ResultMsg, ErrorMsg, StreamEndMsg, ThinkingMsg, ToolStepMsg
from .commands import CommandHandler
from .widgets import HeaderWidget
from .screens.ubuntu_grid import UbuntuGrid
from .theme_util import apply_app_theme

from core.log_setup import setup_logging, add_file_handler
setup_logging("widdx.tui", level=logging.DEBUG)
logger = logging.getLogger("widdx.tui")
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    add_file_handler(str(Path(ROOT) / "widdx-tui.log"))

_THINK_TAGS = ("[thinking]", "[/thinking]")


def _fix_rtl(text: str) -> str:
    if not text:
        return ""
    if any("؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ" for c in text):
        return get_display(text)
    return text


# Late import: bidi for RTL text support
try:
    from bidi.algorithm import get_display
except ImportError:
    def get_display(s: str) -> str:
        return s


# ── View Panel ──────────────────────────────────────────────
class ViewPanel(Vertical):
    """Side panel for tools, skills, history, memories."""

    def compose(self):
        yield Static(id="view-title")
        yield ScrollableContainer(id="view-list")
        yield Button("← Back to chat (Ctrl+B)", id="view-back", classes="btn-sm")

    def set_title(self, text: str):
        self.query_one("#view-title", Static).update(f"  [bold #f5a623]{text}[/]")


# ── Main Screen ──────────────────────────────────────────────
class MainScreen(Screen):
    """Main chat screen for WIDDX TUI."""

    _show_thinking: bool = False
    _anim_dots_count: int = 0
    _anim_timer: Any = None

    BINDINGS = [
        Binding("ctrl+q", "app.quit", "Quit", show=False, priority=True),
        Binding("escape", "cancel_or_focus", "Cancel/Focus", show=False),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
        Binding("ctrl+p", "show_help", "Help", show=False),
        Binding("ctrl+b", "show_chat", "Back to Chat", show=False),
        Binding("ctrl+t", "toggle_thinking", "𖥔 Thinking", show=False, tooltip="Toggle reasoning content display"),
        Binding("ctrl+up", "history_prev", "Previous Cmd", show=False),
        Binding("ctrl+down", "history_next", "Next Cmd", show=False),
    ]

    NAV_BUTTONS = [
        ("nav-chat", "💬", "Chat"), ("nav-tools", "🛠️", "Tools"),
        ("nav-skills", "🎯", "Skills"), ("nav-history", "📋", "History"),
        ("nav-memories", "💾", "Memories"),
        ("nav-settings", "⚙", "Settings"),
    ]

    def __init__(self):
        super().__init__()
        self.state = TUIState()
        self.chat = ChatEngine(self)
        self.cmds = CommandHandler(self)
        self._chat_log: RichLog = None
        self._stream_buffer = ""
        self._command_history: list[str] = []
        self._history_index = -1
        self._active_view: str | None = None

    def compose(self) -> ComposeResult:
        yield HeaderWidget()
        yield Static("", id="processing", classes="hidden")
        with Horizontal(id="body"):
            yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True, max_lines=500, auto_scroll=True)
            yield ViewPanel(id="view-panel")
        with Horizontal(id="input-container"):
            yield Static("❯", id="prompt-label")
            yield Input(placeholder="اكتب رسالة…  /help  •  !skill  •  Ctrl+P", id="input")
        yield Static(id="status")
        yield Static("", id="toast", classes="toast-hidden")

    def on_mount(self) -> None:
        self._chat_log = self.query_one("#chat-log", RichLog)
        self._show_chat()

        # Startup
        for log_line in self.state.startup():
            self._log_message("system", log_line)

        # Start cron scheduler
        try:
            from core.cron.scheduler import CronScheduler
            self._cron = CronScheduler()
            self._cron.set_executor(self._cron_executor)
            self._cron.start()
        except Exception as e:
            logger.debug("Cron scheduler start skipped: %s", e)

        self.query_one("#input", Input).focus()
        self._set_processing(False)
        hw = self.query_one(HeaderWidget)
        hw.initialize_provider(self.state.provider.name)
        self._update_status()

    def on_unmount(self) -> None:
        """Stop the background cron scheduler so the process can exit cleanly.

        Without this the daemon thread keeps the event loop / process alive
        after the TUI closes (headless tests hung here indefinitely).
        """
        cron = getattr(self, "_cron", None)
        if cron is not None and getattr(cron, "running", False):
            try:
                cron.stop()
            except Exception as e:
                logger.debug("Cron scheduler stop failed: %s", e)
        self._cron = None

    def _cron_executor(self, job) -> str:
        """Execute a cron job's prompt."""
        try:
            self.call_from_thread(
                self._log_message, "system",
                f"⏰ Cron job: {job.id[:8]} — {job.prompt[:100]}"
            )
            engine = ChatEngine(self)
            engine.start(job.prompt, self.state)
            return f"Executed: {job.prompt[:100]}"
        except Exception as e:
            logger.error("Cron executor: %s", e)
            return f"Error: {e}"

    def _apply_theme(self, cfg: dict | None = None):
        """Apply dark/light theme from config."""
        cfg = cfg or self.state.cfg
        name = apply_app_theme(self.app, cfg)
        self.state.cfg = cfg
        return name

    def _sync_provider_from_model(self):
        """Recreate provider object when model string changes."""
        from core.providers.providers import create_provider
        if "/" not in self.state.model:
            return
        prov_name, model_name = self.state.model.split("/", 1)
        cfg = self.state.cfg
        all_prov = cfg.get("all_providers", {})
        ap = all_prov.get(prov_name, cfg.get("provider", {}))
        cfg["provider"] = {
            "name": prov_name,
            "model": model_name,
            "base_url": ap.get("base_url", cfg.get("provider", {}).get("base_url", "")),
            "api_key": ap.get("api_key", cfg.get("provider", {}).get("api_key", "public")),
        }
        self.state.cfg = cfg
        self.state.provider = create_provider(cfg)
        self.state._rebuild_tool_defs()

    def _switch_session_branch(self, new_branch: str) -> bool:
        """Switch project session branch and reload chat state."""
        from core.project.state import set_current_branch, get_current_branch, load_session

        if new_branch == get_current_branch():
            return True
        self.state.save_session()
        if not set_current_branch(new_branch):
            self._log_message("system", f"❌ Session branch '{new_branch}' not found")
            return False

        session = load_session(branch=new_branch)
        if session:
            self.state.messages = session.get("messages", [])
            s = session.get("state", {})
            self.state.cost = s.get("cost", 0.0)
            self.state.turns = s.get("turns", 0)
            if s.get("model"):
                self.state.model = s["model"]
                self._sync_provider_from_model()
        else:
            self.state.messages = []
            self.state.turns = 0
            self.state.cost = 0.0

        self._log_message("system", f"🌿 Switched to session branch: {new_branch}")
        if self._chat_log:
            self._chat_log.clear()
            for m in self.state.messages[-20:]:
                role = m.get("role", "?")
                content = (m.get("content") or "")[:300]
                if role in ("user", "assistant", "system"):
                    self._log_message(role, content)
        try:
            hw = self.query_one(HeaderWidget)
            hw.refresh_branches(new_branch)
            hw.update_provider(self.state.provider.name)
        except Exception:
            pass
        self._update_status()
        return True

    def _update_status(self):
        """Refresh footer status bar and header info strip."""
        try:
            model_short = self.state.model.split("/")[-1] if "/" in self.state.model else self.state.model
            self.query_one("#status", Static).update(
                f"  {model_short}  │  turns: {self.state.turns}  │  "
                f"cost: ${self.state.cost:.4f}  │  tools: {len(self.state.tool_defs)}  │  "
                f"Ctrl+P help  •  Ctrl+B chat"
            )
            hw = self.query_one(HeaderWidget)
            hw.update_info(
                Path.cwd().name,
                self.state.model,
                self.state.cost,
                self.state.turns,
            )
        except Exception:
            pass

    def _set_processing(self, active: bool, label: str = "  ◈  WIDDX is thinking"):
        proc = self.query_one("#processing", Static)
        if active:
            self._anim_dots_count = 0
            proc.update(f"{label}   ")
            proc.set_class(True, "active")
            proc.set_class(True, "thinking")
            proc.set_class(True, "shimmer")
            self._anim_timer = self.set_interval(0.5, self._update_anim_dots, label)
        else:
            proc.set_class(False, "active")
            proc.set_class(False, "thinking")
            proc.set_class(False, "shimmer")
            if self._anim_timer:
                try:
                    self._anim_timer.stop()
                except Exception:
                    pass
                self._anim_timer = None

    def _update_anim_dots(self, label: str = "  ◈  WIDDX is thinking"):
        """Update the animated dots on the processing bar."""
        try:
            self._anim_dots_count = (self._anim_dots_count + 1) % 4
            dots = "." * self._anim_dots_count
            spaces = " " * (3 - self._anim_dots_count)
            proc = self.query_one("#processing", Static)
            proc.update(f"{label}{dots}{spaces}")
        except Exception:
            pass

    # ── Input handling ─────────────────────────────────────
    async def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if not text:
            return
        if text and (not self._command_history or text != self._command_history[-1]):
            self._command_history.append(text)
            if len(self._command_history) > 100:
                self._command_history.pop(0)
        self._history_index = -1
        self.query_one("#input", Input).value = ""
        self.query_one("#input", Input).disabled = True

        is_cmd = await self.cmds.handle(text, self.state)
        if not is_cmd:
            self._log_message("user", text)
            self.query_one("#input", Input).disabled = True
            self._set_processing(True)
            self.run_chat(text)
        else:
            self._finish_chat()

    @work(exclusive=True, thread=True)
    def run_chat(self, text: str) -> None:
        """Execute chat in a background thread."""
        from textual.worker import get_current_worker
        worker = get_current_worker()
        try:
            self.chat.start(text, self.state)
            if not worker.is_cancelled:
                self.app.call_from_thread(self._finish_chat)
        except Exception as e:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._log_message, "system", f"❌ {e}")
            self.app.call_from_thread(self._finish_chat)

    def _finish_chat(self):
        self.query_one("#input", Input).disabled = False
        self.query_one("#input", Input).focus()
        self._set_processing(False)
        self._update_status()

    def on_input_changed(self, event: Input.Changed):
        cc = self.query_one("#prompt-label", Static)
        n = len(event.value)
        cc.update(f"❯ {n}" if n else "❯")

    # ── UI helpers ─────────────────────────────────────────
    def _log_message(self, role: str, content: str,
                     tool_calls: list[tuple[str, str]] | None = None,
                     elapsed: float | None = None):
        if not self._chat_log:
            return
        ts = datetime.now().strftime("%H:%M")
        content = _fix_rtl(content)

        if role == "user":
            panel = render_user_message(content, ts)
        elif role == "assistant":
            panel = render_assistant_message(content, ts, elapsed, tool_calls)
        elif role == "system":
            panel = render_system_message(content)
        elif role == "tool":
            panel = render_tool_message(content[:60], content)
        elif role == "error":
            panel = render_error(content)
        elif role == "reasoning":
            panel = render_reasoning(content, elapsed)
        elif role == "divider":
            panel = render_divider()
        else:
            panel = render_system_message(content)

        self._chat_log.write(panel)
        self._chat_log.scroll_end(animate=False)

    def _log(self, text: str):
        pass

    def _show_chat(self):
        body = self.query_one("#body", Horizontal)
        vp = self.query_one("#view-panel", ViewPanel)
        body.remove_class("sidebar-open")
        vp.remove_class("active")
        self.set_timer(0.25, lambda: self._set_view_visibility(False))
        self._active_view = None

    def _set_view_visibility(self, visible: bool):
        try:
            vp = self.query_one("#view-panel", ViewPanel)
            vp.display = visible
        except Exception:
            pass

    def _show_view(self, title: str):
        self.query_one("#body", Horizontal)
        vp = self.query_one("#view-panel", ViewPanel)
        vp.display = True
        self.set_timer(0.01, lambda: self._activate_view(title))

    def _activate_view(self, title: str):
        try:
            body = self.query_one("#body", Horizontal)
            vp = self.query_one("#view-panel", ViewPanel)
            body.add_class("sidebar-open")
            vp.add_class("active")
            vp.set_title(title)
            self._active_view = title
        except Exception:
            pass

    # ── Navigation actions ─────────────────────────────────
    async def _do_action(self, action: str):
        if action == "chat":
            self._show_chat()
            self._log_message("system", "💬 Back to chat")
        elif action == "clear":
            self.action_clear_chat()
        elif action == "search":
            self._log_message("system", "🔍 Type /search <query> in the input bar")
            self._show_chat()
        elif action == "about":
            self._log_message(
                "system",
                "◈ WIDDX Nexus v3.0 — Terminal AI\n"
                "by Muhammad Muslih  •  Palestine 🇵🇸",
            )
            self._show_chat()
        elif action == "help":
            from .screens.help import HelpScreen
            self.app.push_screen(HelpScreen(), self._on_help_result)
        elif action == "tools":
            self._show_view("Tools")
            vlist = self.query_one("#view-list", ScrollableContainer)
            await vlist.remove_children()
            from textual.widgets import Button as TButton
            for i, td in enumerate(self.state.tool_defs):
                name = td["name"]
                desc = (td.get("description", "") or "")[:70]
                tag = " [MCP]" if name.startswith("mcp__") else ""
                tag += " [WORKFLOW]" if name in ("create_agent", "run_parallel") else ""
                await vlist.mount(TButton(f"  🛠️ {name}{tag}  —  {desc}", id=f"tool-{i}"))
        elif action == "skills":
            self._show_view("Skills")
            vlist = self.query_one("#view-list", ScrollableContainer)
            await vlist.remove_children()
            from textual.widgets import Button as TButton
            for s in skill_manager.list_all():
                active = skill_manager.active and s.name == skill_manager.active.name
                marker = "◉" if active else "○"
                icon = getattr(s, "icon", "") or "🎯"
                btn = TButton(f"  {marker}  {icon}  !{s.name}  —  {s.description[:50]}", id=f"sk-{s.name}")
                btn.set_class(True, "active") if active else None
                await vlist.mount(btn)
        elif action == "history":
            self._show_view("History")
            vlist = self.query_one("#view-list", ScrollableContainer)
            await vlist.remove_children()
            icons = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🛠️"}
            from textual.widgets import Button as TButton
            for i, m in enumerate(self.state.messages[-50:]):
                role = m.get("role", "?")
                c = (m.get("content") or "")[:60].replace("\n", " ")
                icon = icons.get(role, "•")
                idx_val = i
                await vlist.mount(TButton(f"  {icon}  [{role}]  {c}", id=f"hist-{idx_val}"))
        elif action == "memories":
            from .screens.memory_crud import MemoryListScreen
            self.app.push_screen(MemoryListScreen())
        elif action == "sessions":
            from .screens.session_crud import SessionListScreen
            self.app.push_screen(SessionListScreen(), self._on_session_result)
        elif action == "settings":
            from .screens.settings import SettingsScreen
            self.app.push_screen(SettingsScreen(), self._on_settings_result)
        elif action == "export":
            self._export_chat()
        elif action == "doctor":
            await self._do_doctor()

    async def _show_memories(self):
        mem = MemoryStore()
        all_m = mem.list_all()
        if not all_m:
            self._log_message("system", "No memories. Use /remember to save one.")
            return
        self._show_view("Memories")
        vlist = self.query_one("#view-list", ScrollableContainer)
        await vlist.remove_children()
        from textual.widgets import Button as TButton
        for m in all_m[:30]:
            await vlist.mount(TButton(f"  📌 {m['name']}: {m.get('description','')[:80]}", id=f"mem-{m['name']}"))

    def _export_chat(self):
        lines = []
        for m in self.state.messages:
            role = m.get("role", "?")
            content = (m.get("content") or "")[:500]
            lines.append(f"## {role.upper()}\n\n{content}\n")
        path = Path.cwd() / f"chat_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path.write_text("\n---\n".join(lines), encoding="utf-8")
        self._log_message("system", f"📤 Exported to {path.name}")

    async def _do_doctor(self):
        import subprocess
        from core.skills import skill_manager
        self._log_message("system", "🩺 Running doctor checks...")
        checks = []
        try:
            r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"Git: {r.stdout.strip()[:40] if r.returncode == 0 else 'not found'}")
        except Exception:
            checks.append("Git: not found")
        try:
            r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"Node: {r.stdout.strip() if r.returncode == 0 else 'not found'}")
        except Exception:
            checks.append("Node: not found")
        checks.append(f"Provider: {self.state.provider.name}/{self.state.provider.model}")
        checks.append(f"Project: {Path.cwd().name}")
        checks.append(f"Memory: {MemoryStore().total()} facts")
        checks.append(f"MCP: {get_mcp_manager().server_count} servers")
        checks.append(f"Skills: {len(skill_manager.list_all())}")
        checks.append(f"Tools: {len(self.state.tool_defs)}")
        checks.append(f"Theme: {self.state.cfg.get('cli_theme', 'dark')}")
        for c in checks:
            self._log_message("system", f"  • {c}")

    # ── Message handlers (from ChatEngine) ─────────────────
    def on_result_msg(self, msg: ResultMsg):
        display = msg.text or "[execution complete]"
        self._log_message("assistant", display)
        self._show_chat()
        self._set_processing(False)
        self._update_status()

    def on_error_msg(self, msg: ErrorMsg):
        self._log_message("system", f"❌ {msg.text}")
        self._set_processing(False)
        self._update_status()

    def on_tool_step_msg(self, msg: ToolStepMsg):
        self._log_message("tool", msg.tool + ": " + msg.detail[:200])

    def on_stream_end_msg(self, msg: StreamEndMsg):
        display = msg.content or "[tool execution complete]"
        self._log_message("assistant", display, elapsed=getattr(msg, "elapsed", None))
        self.state.messages = msg.msgs
        self.state.save_session()
        self._stream_buffer = ""
        self._show_chat()
        self._set_processing(False)
        self._update_status()

    def on_thinking_msg(self, msg: ThinkingMsg):
        """Show reasoning content only when toggle is on."""
        if not self._show_thinking:
            return
        text = _fix_rtl(msg.text)
        self._log_message("reasoning", text, elapsed=getattr(msg, "elapsed", None))

    # ── Navigation screens callbacks ───────────────────────
    def _on_help_result(self, cmd: str | None):
        if cmd:
            import asyncio
            asyncio.create_task(self.cmds.handle(cmd, self.state))
        self.query_one("#input", Input).focus()

    def _on_settings_result(self, result: dict | None):
        if result:
            from core.config.settings import load as reload_config
            from core.providers.providers import create_provider
            new_cfg = reload_config()
            self.state.cfg = new_cfg
            self.state.provider = create_provider(new_cfg)
            self.state.model = f"{self.state.provider.name}/{self.state.provider.model}"
            self.state._rebuild_tool_defs()
            try:
                hw = self.query_one(HeaderWidget)
                hw.initialize_provider(self.state.provider.name)
            except Exception:
                pass
        self.query_one("#input", Input).focus()

    def _on_session_result(self, result: tuple | None):
        if result:
            action = result[0]
            if action == "loaded" and len(result) > 1:
                msgs = result[1]
                self.state.messages = msgs
                self.state.turns = len(msgs)
                if len(result) > 2 and isinstance(result[2], dict):
                    meta = result[2]
                    if meta.get("model"):
                        self.state.model = meta["model"]
                        self._sync_provider_from_model()
                    self.state.cost = meta.get("cost", 0.0)
                
                self._log_message("system", f"📂 Session loaded: {len(msgs)} messages")
                if self._chat_log:
                    self._chat_log.clear()
                    self._show_chat()
                    for m in msgs[-20:]:
                        role = m.get("role", "?")
                        content = m.get("content", "")[:300]
                        if role in ("user", "assistant", "system"):
                            self._log_message(role, content)
            elif action == "new" and len(result) > 1:
                self.state.messages = []
                self.state.turns = 0
                self._log_message("system", "✨ New session started")
        self.query_one("#input", Input).focus()

    def action_cancel_or_focus(self):
        self.query_one("#input", Input).focus()

    def action_show_help(self):
        from .screens.help import HelpScreen
        self.app.push_screen(HelpScreen(), self._on_help_result)

    def action_show_chat(self):
        self._show_chat()
        self.query_one("#input", Input).focus()

    def action_clear_chat(self):
        if self._chat_log:
            self._chat_log.clear()
        self._show_chat()

    def action_toggle_thinking(self):
        """Toggle display of reasoning/thinking content."""
        self._show_thinking = not self._show_thinking
        status = "🟢 on" if self._show_thinking else "🔴 off"
        self._log_message("system", f"🧠 Thinking display: {status}")
        self._show_toast(f"Thinking: {status}")

    def action_history_prev(self):
        if self._command_history:
            max_idx = len(self._command_history) - 1
            self._history_index = min(max_idx, self._history_index + 1)
            idx = self._history_index
            inp = self.query_one("#input", Input)
            if 0 <= idx < len(self._command_history):
                inp.value = self._command_history[-(idx + 1)]

    def action_history_next(self):
        if self._command_history and self._history_index >= 0:
            self._history_index -= 1
            inp = self.query_one("#input", Input)
            idx = self._history_index
            if idx >= 0:
                inp.value = self._command_history[-(idx + 1)]
            else:
                inp.value = ""

    # ── Toast notifications (with slide animation) ─────────
    def _show_toast(self, msg: str, kind: str = "info", duration: float = 3.0):
        toast = self.query_one("#toast", Static)
        toast.update(f"  {msg}  ")
        toast.set_class(False, "toast-hidden")
        toast.set_class(True, "toast-visible")
        toast.set_class(False, "toast-fade-out")
        try:
            self.set_timer(duration, self._hide_toast_animated)
        except Exception:
            self.set_timer(duration, self._hide_toast)

    def _hide_toast_animated(self):
        try:
            toast = self.query_one("#toast", Static)
            toast.set_class(True, "toast-fade-out")
            toast.set_class(False, "toast-visible")
            self.set_timer(0.35, self._hide_toast)
        except Exception:
            self._hide_toast()

    def _hide_toast(self):
        try:
            toast = self.query_one("#toast", Static)
            toast.set_class(True, "toast-hidden")
            toast.set_class(False, "toast-visible")
            toast.set_class(False, "toast-fade-out")
        except Exception:
            pass

    # ── Header & View Panel event handlers ──────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses from header, nav, and view panel."""
        bid = event.button.id or ""
        if bid == "view-back":
            self._show_chat()
            self.query_one("#input", Input).focus()
            return
        if bid == "btn-grid":
            main_nav = self.NAV_BUTTONS
            act_btns = [
                ("act-doctor", "🩺", "Doctor", "doctor", "info"),
                ("act-sessions", "📦", "Sessions", "sessions", "info"),
                ("act-export", "📤", "Export", "export", "success"),
                ("act-clear", "🧹", "Clear", "clear", "warn"),
                ("act-search", "🔍", "Search", "search", "info"),
            ]
            help_btns = [
                ("help-help", "❓", "Help", "help", "info"),
                ("help-about", "ℹ️", "About", "about", "info"),
            ]
            self.app.push_screen(
                UbuntuGrid(nav_buttons=main_nav, act_buttons=act_btns, help_buttons=help_btns),
                self._on_grid_result
            )
            return

        if bid and bid.startswith("tool-"):
            idx = int(bid.split("-")[1])
            td = self.state.tool_defs[idx] if idx < len(self.state.tool_defs) else None
            if td:
                from .screens.tool_detail import ToolDetailScreen
                self.app.push_screen(ToolDetailScreen(td))
            return

        if bid and bid.startswith("sk-"):
            skill_name = bid[3:]
            self.cmds._do_skill(skill_name, self.state)
            return

        if bid and bid.startswith("hist-"):
            idx = int(bid.split("-")[1])
            shown = self.state.messages[-50:]
            if 0 <= idx < len(shown):
                m = shown[idx]
                from .screens.detail import TextDetailScreen
                title = f"Message [{m.get('role', '?')}]"
                body = m.get("content", "")
                self.app.push_screen(TextDetailScreen(title, body))
            return

        if bid and bid.startswith("mem-"):
            mem_name = bid[4:]
            mem = MemoryStore()
            content = mem.get(mem_name)
            if content:
                from .screens.detail import TextDetailScreen
                self.app.push_screen(TextDetailScreen(mem_name, content))
            return

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle provider and branch selector changes from header."""
        sid = event.select.id or ""
        if sid == "header-provider" and event.value and event.value != Select.BLANK:
            from core.providers.providers import create_provider
            from core.config.settings import load as reload_config
            new_name = str(event.value)
            cfg = reload_config()
            all_prov = cfg.get("all_providers", {})
            ap = all_prov.get(new_name, {})
            cfg["provider"] = {
                "name": new_name,
                "model": ap.get("model", ""),
                "base_url": ap.get("base_url", ""),
                "api_key": ap.get("api_key", "public"),
            }
            from core.config.settings import save as save_config
            save_config(cfg)
            self.state.cfg = cfg
            self.state.provider = create_provider(cfg)
            self.state.model = f"{self.state.provider.name}/{self.state.provider.model}"
            self.state._rebuild_tool_defs()
            self._log_message("system", f"🔄 Switched to {self.state.provider.name}/{self.state.provider.model}")
            try:
                hw = self.query_one(HeaderWidget)
                hw.update_provider(self.state.provider.name)
            except Exception:
                pass
            self._update_status()
        elif sid == "header-branch" and event.value and event.value != Select.BLANK:
            self._switch_session_branch(str(event.value))

    def _on_grid_result(self, action: str | None) -> None:
        """Handle result from UbuntuGrid launcher."""
        if action:
            import asyncio
            asyncio.create_task(self._do_action(action))
        self.query_one("#input", Input).focus()


# ── App Entry ────────────────────────────────────────────────
class WIDDXTUI(App):
    TITLE = "WIDDX Nexus"
    CSS_PATH = "app.tcss"
    SCREENS: dict = {}

    def __init__(self):
        super().__init__()
        self.main_screen = None

    def on_mount(self):
        self.main_screen = MainScreen()
        apply_app_theme(self, self.main_screen.state.cfg)
        self.push_screen(self.main_screen)


def run_tui():
    import warnings
    warnings.warn(
        "WIDDX TUI is deprecated. Use Web UI instead: python scripts/web_app.py",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        from core.diagnostics import error_collector
        error_collector.enable()
    except Exception:
        pass
    app = WIDDXTUI()
    app.run()


if __name__ == "__main__":
    run_tui()
