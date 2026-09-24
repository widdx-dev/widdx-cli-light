"""Session CRUD — manage saved chat sessions (list, load, rename, delete)."""

import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("widdx.tui.sessions")

from textual.screen import ModalScreen, Screen  # noqa: E402
from textual.widgets import Static, Input, Button, Label, RichLog  # noqa: E402
from textual.containers import Vertical, Horizontal, ScrollableContainer  # noqa: E402
from textual.binding import Binding  # noqa: E402
from rich.text import Text  # noqa: E402
from rich.panel import Panel  # noqa: E402
from core.ui_visual import ROLE_META_ASCII, BLUE, DIM, RED  # noqa: E402

# Import Session V2
from core.session_v2 import SessionV2, create_new_session  # noqa: E402


SESSION_DIR = Path.cwd().resolve()


def _find_sessions() -> list[dict]:
    sessions = []
    # First add SQLite sessions
    try:
        for sess in SessionV2.list_sessions():
            created_at = datetime.fromtimestamp(sess["created_at"]) if "created_at" in sess else datetime.now()
            modified_at = datetime.fromtimestamp(sess["updated_at"]) if "updated_at" in sess else created_at
            sessions.append({
                "type": "sqlite",
                "id": sess["id"],
                "name": sess["name"],
                "branch": sess.get("branch", "main"),
                "size_str": "DB",
                "modified": modified_at.strftime("%Y-%m-%d %H:%M"),
                "msg_count": None,
            })
    except Exception as e:
        logger.debug("Failed to load SQLite sessions: %s", e)

    # Now add legacy JSON sessions
    for pattern in ["chat_*.json", "chat_export_*.md"]:
        for f in sorted(SESSION_DIR.glob(pattern), reverse=True):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                sessions.append({
                    "path": str(f), "name": f.name, "size": f.stat().st_size,
                    "size_str": f"{f.stat().st_size // 1024}KB" if f.stat().st_size > 1024 else f"{f.stat().st_size}B",
                    "modified": mtime.strftime("%Y-%m-%d %H:%M"),
                    "type": "json" if f.suffix == ".json" else "markdown",
                })
            except Exception as e:
                logger.debug("Session scan skip %s: %s", f.name, e)
    ws = SESSION_DIR / ".widdx" / "session.json"
    if ws.exists():
        try:
            data = json.loads(ws.read_text(encoding="utf-8"))
            sessions.insert(0, {
                "path": str(ws), "name": ".widdx/session.json (auto)",
                "size": ws.stat().st_size, "size_str": "auto",
                "modified": "current", "type": "json",
                "msg_count": len(data.get("messages", [])), "is_auto": True,
            })
        except Exception as e:
            logger.debug("Auto-session load failed: %s", e)
    return sessions


# ── Session List (full-screen) ────────────────

class SessionListScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("l", "load", "Load", show=False),
        Binding("d", "delete", "Delete", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("s", "save_now", "Save Now", show=False),
        Binding("e", "export_md", "Export MD", show=False),
        Binding("n", "new_session", "New Session", show=False),
    ]

    def __init__(self, state: dict | None = None, messages: list | None = None):
        super().__init__()
        self._state = state or {}
        self._messages = messages or []
        self._sessions: list[dict] = []
        self._selected_idx: int = -1

    def compose(self):
        yield Static("  📦  Session Manager", classes="list-title")
        yield Static("", classes="list-status")
        with Horizontal(classes="list-toolbar"):
            yield Button("  ✨ New Session (N)  ", id="sess-new", variant="success")
            yield Button("  💾 Save Current (S)  ", id="sess-save", variant="primary")
            yield Button("  📂 Load (L)  ", id="sess-load")
            yield Button("  ✏️ Rename (R)  ", id="sess-rename")
            yield Button("  🗑️ Delete (D)  ", id="sess-delete")
            yield Button("  📤 Export MD (E)  ", id="sess-export")
            yield Button("  🔄 Refresh (R)  ", id="sess-refresh")
            yield Button("  🔙 Back (Esc)  ", id="sess-back")
        with Horizontal(id="sess-container"):
            yield ScrollableContainer(id="sess-sidebar")
            yield RichLog(id="sess-preview", highlight=True, markup=True, wrap=True)
        with Horizontal(classes="list-footer"):
            yield Static("  [dim][S]ave Current  [L]oad  [R]ename  [D]elete  [E]xport MD  [/]", classes="list-footer-text")

    def on_mount(self):
        self._load_sessions()

    def _load_sessions(self):
        try:
            sidebar = self.query_one("#sess-sidebar", ScrollableContainer)
            sidebar.remove_children()
            
            self._sessions = _find_sessions()
            self.query_one(".list-status", Static).update(
                f"  [dim]{len(self._sessions)} session(s) ({sum(1 for s in self._sessions if s.get('is_auto'))} auto)[/]"
            )
            
            preview = self.query_one("#sess-preview", RichLog)
            preview.clear()
            
            if not self._sessions:
                preview.write(Panel(
                    Text.from_markup("[dim]No saved sessions found.\n\nPress [bold #0891b2]S[/] to save the current session.[/]"),
                    border_style="dim", padding=(2, 4),
                ))
                self._selected_idx = -1
                return
                
            for i, s in enumerate(self._sessions):
                tag = "🟢 " if s.get("is_auto") else ""
                btn = Button(f"{tag}{s['name']}\n[dim]{s['size_str']}  |  {s.get('modified', '')}[/]", id=f"sess-item-{i}", classes="sess-btn")
                sidebar.mount(btn)
                
            # Select first session by default
            self._selected_idx = 0
            self.call_later(self._preview_session, 0)
        except Exception as e:
            logger.exception("Error loading sessions: %s", e)
            self._show_error(f"Failed to load sessions: {e}")

    def _preview_session(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._sessions):
            return
        self._selected_idx = idx
        preview = self.query_one("#sess-preview", RichLog)
        preview.clear()
        
        for i in range(len(self._sessions)):
            try:
                btn = self.query_one(f"#sess-item-{i}", Button)
                btn.set_class(i == idx, "active")
            except Exception:
                pass

        try:
            s = self._sessions[idx]
            preview.write(f"[bold {BLUE}]Previewing: {s['name']}[/]\n")
            preview.write(f"[dim]Modified: {s.get('modified', '')}  |  Size: {s.get('size_str', '')}[/]\n")
            preview.write("─" * 60 + "\n")
            
            if s["type"] == "sqlite":
                sess = SessionV2(s["id"])
                msgs = sess.messages
                
                role_icons = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🛠️"}
                
                preview.write(f"[dim]Branch: {s.get('branch', 'main')}[/]\n")
                preview.write(f"[dim]{len(msgs)} message(s)[/]\n")
                preview.write("─" * 60 + "\n")
                
                for m in msgs:
                    role = m.get("role", "?")
                    content = m.get("content", "")
                    meta = ROLE_META_ASCII.get(role, ("•", role.upper(), DIM))
                    icon, _, color = meta
                    icon = icon or role_icons.get(role, "•")
                    
                    preview_text = content[:600] + "\n[dim]… (truncated for preview)[/dim]" if len(content) > 600 else content
                    preview.write(f"[{color}]{icon} {role.upper()}[/]\n{preview_text}\n")
                    preview.write("─" * 60 + "\n")
            elif s["type"] == "json":
                path = Path(s["path"])
                data = json.loads(path.read_text(encoding="utf-8"))
                msgs = data.get("messages", [])
                
                role_icons = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🛠️"}
                
                for m in msgs:
                    role = m.get("role", "?")
                    content = m.get("content", "")
                    meta = ROLE_META_ASCII.get(role, ("•", role.upper(), DIM))
                    icon, _, color = meta
                    icon = icon or role_icons.get(role, "•")
                    
                    preview_text = content[:600] + "\n[dim]… (truncated for preview)[/dim]" if len(content) > 600 else content
                    preview.write(f"[{color}]{icon} {role.upper()}[/]\n{preview_text}\n")
                    preview.write("─" * 60 + "\n")
            else:
                path = Path(s["path"])
                content = path.read_text(encoding="utf-8")
                preview.write(content[:2000] + "\n[dim]… (truncated for preview)[/dim]" if len(content) > 2000 else content)
        except Exception as e:
            preview.write(f"[bold {RED}]Error reading session: {e}[/]")

    def on_descendant_focus(self, event) -> None:
        widget = event.widget
        if widget and widget.id and widget.id.startswith("sess-item-"):
            try:
                idx = int(widget.id.split("-")[-1])
                self._preview_session(idx)
            except Exception:
                pass

    def action_go_back(self):
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.dismiss()
    def action_refresh(self): self._load_sessions()
    def action_new_session(self):
        self.app.push_screen(SessionRenameScreen("New Session"), self._on_new_session_result)

    def action_save_now(self):
        if not self._messages:
            self.query_one("#sess-preview", RichLog).write(Panel(
                Text.from_markup("[bold #ef4444]No messages to save.[/]"), border_style="#ef4444", padding=(1, 2),
            ))
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SESSION_DIR / f"chat_{ts}.json"
        try:
            path.write_text(json.dumps({"messages": self._messages}, indent=2, ensure_ascii=False), encoding="utf-8")
            self._load_sessions()
        except (OSError, PermissionError) as e:
            self._show_error(f"Save failed: {e}")

    def action_export_md(self):
        if not self._messages:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SESSION_DIR / f"chat_export_{ts}.md"
        try:
            lines = ["# WIDDX Chat Export\n"]
            for m in self._messages:
                lines.append(f"## {m.get('role', '?')}\n\n{(m.get('content') or '')}\n\n---\n")
            path.write_text("\n".join(lines), encoding="utf-8")
            self._load_sessions()
        except Exception as e:
            logger.debug("Export MD failed: %s", e)

    def action_load(self):
        if self._selected_idx < 0 or self._selected_idx >= len(self._sessions):
            return
        s = self._sessions[self._selected_idx]
        if s.get("is_auto"):
            return
        try:
            if s["type"] == "sqlite":
                sess = SessionV2(s["id"])
                msgs = sess.messages
                meta = sess.metadata
                self._state["_messages"] = msgs
                self._state["turns"] = len(msgs)
                self.dismiss(("loaded", msgs, meta))
            else:
                path = Path(s["path"])
                data = json.loads(path.read_text(encoding="utf-8"))
                msgs = data.get("messages", [])
                meta = data.get("state", {})
                self._state["_messages"] = msgs
                self._state["turns"] = len(msgs)
                self.dismiss(("loaded", msgs, meta))
        except Exception as e:
            self._show_error(f"Load failed: {e}")

    def action_rename(self):
        if self._selected_idx < 0 or self._selected_idx >= len(self._sessions):
            return
        s = self._sessions[self._selected_idx]
        if s.get("is_auto"):
            return
        if s["type"] == "sqlite":
            self.app.push_screen(SessionRenameScreen(s["name"]), lambda r: self._on_sqlite_rename_result(r, s["id"]))
        else:
            self.app.push_screen(SessionRenameScreen(s["name"]), self._on_rename_result)

    def action_delete(self):
        if self._selected_idx < 0 or self._selected_idx >= len(self._sessions):
            return
        s = self._sessions[self._selected_idx]
        if s.get("is_auto"):
            return
        if s["type"] == "sqlite":
            self.app.push_screen(SessionDeleteScreen(s["name"]), lambda r: self._on_sqlite_delete_result(r, s["id"]))
        else:
            self.app.push_screen(SessionDeleteScreen(s["name"]), self._on_delete_result)

    def _on_rename_result(self, r):
        if r:
            old, new = r
            try:
                (SESSION_DIR / old).rename(SESSION_DIR / new)
                self._load_sessions()
            except Exception as e:
                self._show_error(f"Rename failed: {e}")
    
    def _on_sqlite_rename_result(self, r, session_id):
        if r:
            _, new = r
            try:
                sess = SessionV2(session_id)
                sess.rename(new)
                self._load_sessions()
            except Exception as e:
                self._show_error(f"Rename failed: {e}")

    def _on_delete_result(self, r):
        if r:
            self._load_sessions()
    
    def _on_sqlite_delete_result(self, r, session_id):
        if r:
            try:
                SessionV2.delete(session_id)
                self._load_sessions()
            except Exception as e:
                self._show_error(f"Delete failed: {e}")
    
    def _on_new_session_result(self, r):
        if r:
            _, name = r
            try:
                sess = create_new_session(name=name)
                self._state["_messages"] = []
                self._state["turns"] = 0
                self.dismiss(("new", sess))
            except Exception as e:
                self._show_error(f"Create failed: {e}")

    def _show_error(self, msg):
        self.query_one("#sess-preview", RichLog).write(Panel(
            Text.from_markup(f"[bold #ef4444]{msg}[/]"), border_style="#ef4444", padding=(1, 2),
        ))

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if not bid:
            return
            
        if bid.startswith("sess-item-"):
            try:
                idx = int(bid.split("-")[-1])
                self._preview_session(idx)
            except Exception:
                pass
            return

        handler = {
            "sess-new": self.action_new_session,
            "sess-save": self.action_save_now,
            "sess-load": self.action_load,
            "sess-rename": self.action_rename,
            "sess-delete": self.action_delete,
            "sess-export": self.action_export_md,
            "sess-refresh": self.action_refresh,
            "sess-back": self.action_go_back,
        }.get(bid)
        if handler:
            handler()


# ── Session Picker (modal) ────────────────────

class SessionPickerScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, names: list[str], action: str):
        super().__init__()
        self._names = names
        self._action = action

    def compose(self):
        label = {"load": "Load", "rename": "Rename", "delete": "Delete"}.get(self._action, "Select")
        with Vertical(classes="picker-dialog"):
            yield Static(f"  {label} session", classes="picker-title")
            yield ScrollableContainer(classes="picker-list", id="sess-picker-list")
            with Horizontal(classes="picker-actions"):
                yield Button("  Cancel  ", id="sess-picker-cancel")

    def on_mount(self):
        c = self.query_one("#sess-picker-list", ScrollableContainer)
        for name in self._names[:30]:
            c.mount(Button(f"  {name}", id=f"spick-{name}", classes="pick-btn"))

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "sess-picker-cancel":
            self.dismiss(None)
        elif bid and bid.startswith("spick-"):
            self.dismiss((bid[6:], self._action))


# ── Session Rename (modal) ────────────────────

class SessionRenameScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, old_name: str):
        super().__init__()
        self._old_name = old_name

    def compose(self):
        with Vertical(id="sess-rename-dialog", classes="dialog-box"):
            yield Static("  ✏️  Rename Session", classes="dialog-title")
            yield Label("Current name:")
            yield Static(f"  [dim]{self._old_name}[/]", classes="rename-old")
            yield Label("New name:")
            yield Input(value=self._old_name, id="sess-rename-input", placeholder="chat_20250101_120000.json")
            with Horizontal(classes="dialog-actions"):
                yield Button("  Rename  ", id="sess-rename-do", variant="primary")
                yield Button("  Cancel  ", id="sess-rename-cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "sess-rename-do":
            new = self.query_one("#sess-rename-input", Input).value.strip()
            if new and new != self._old_name:
                self.dismiss((self._old_name, new))
        elif event.button.id == "sess-rename-cancel":
            self.dismiss(None)


# ── Session Delete Confirmation (modal) ───────

class SessionDeleteScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel"), Binding("y", "confirm", "Yes", show=False)]

    def __init__(self, name: str):
        super().__init__()
        self._name = name

    def compose(self):
        with Vertical(id="sess-delete-dialog", classes="dialog-box delete-dialog"):
            yield Static("  ⚠️  Delete Session", classes="dialog-title delete-title")
            yield Static(f"\n  Delete:\n\n  [bold #ef4444]{self._name}[/]\n\n  This cannot be undone.\n", classes="delete-msg")
            with Horizontal(classes="dialog-actions-center"):
                yield Button("  ✅ Yes, Delete  ", id="sess-delete-yes", variant="error")
                yield Button("  Cancel  ", id="sess-delete-no")

    def action_confirm(self):
        path = SESSION_DIR / self._name
        try:
            if path.exists():
                path.unlink()
            self.dismiss(True)
        except Exception as e:
            logger.debug("Session delete failed: %s", e)
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "sess-delete-yes":
            self.action_confirm()
        else:
            self.dismiss(None)
