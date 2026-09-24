"""Memory CRUD — Create, Read, Update, Delete persistent memories."""

from textual.screen import ModalScreen, Screen
from textual.widgets import Static, Input, Button, Label, Select, RichLog, TextArea
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from core.ui_visual import CYAN, ORANGE, BLUE, DIM
from core.memory import MemoryStore


MEMORY_TYPES = [
    ("user", "👤 User"),
    ("feedback", "💬 Feedback"),
    ("project", "📦 Project"),
    ("reference", "📚 Reference"),
]


# ── Memory List (full-screen) ──────────────────

class MemoryListScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("c", "create", "Create", show=False),
        Binding("d", "delete", "Delete", show=False),
        Binding("e", "edit", "Edit", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("/", "search", "Search", show=False),
    ]

    def __init__(self, state: dict | None = None):
        super().__init__()
        self._state = state or {}
        self._mem_store = MemoryStore()
        self._memories: list[dict] = []
        self._query = ""

    def compose(self):
        yield Static("  💾  Memory Manager", classes="list-title")
        yield Static("", classes="list-status")
        with Horizontal(classes="list-toolbar"):
            yield Button("  ➕ New (C)  ", id="mem-create", variant="primary")
            yield Button("  🔄 Refresh (R)  ", id="mem-refresh")
            yield Button("  🔙 Back (Esc)  ", id="mem-back")
            yield Input(placeholder="Search memories...", classes="list-search", id="mem-search")
        yield RichLog(highlight=True, markup=True, classes="list-content", id="mem-list")
        with Horizontal(classes="list-footer"):
            yield Static("  [dim][C]reate  [E]dit  [D]elete  [/]", classes="list-footer-text")

    def on_mount(self):
        self._load_memories()
        self.query_one("#mem-search", Input).focus()

    def _load_memories(self):
        log = self.query_one("#mem-list", RichLog)
        log.clear()
        try:
            self._memories = self._mem_store.search(self._query) if self._query else self._mem_store.list_all()
        except Exception:
            self._memories = []
        count = len(self._memories)
        self.query_one(".list-status", Static).update(
            f"  [dim]{count} memory(s)  |  {'search: ' + self._query if self._query else 'all'}[/]"
        )
        if not self._memories:
            log.write(Panel(
                Text.from_markup(f"[dim]No memories yet.\n\nPress [bold {CYAN}]C[/] to create one, or type a search query above.[/]") ,
                border_style=DIM, padding=(2, 4),
            ))
            return
        table = Table(border_style=CYAN, header_style=f"bold {BLUE}", padding=(0, 1))
        table.add_column("#", style="dim", width=3)
        table.add_column("Name", style=f"bold {CYAN}", width=22)
        table.add_column("Type", style=f"{DIM}", width=12)
        table.add_column("Description", style=f"{DIM}")
        table.add_column("Actions", style=f"{ORANGE}", width=10)
        for i, mem in enumerate(self._memories, 1):
            table.add_row(str(i), mem.get("name", "?"), (mem.get("type", "unknown")[:10]),
                          mem.get("description", "")[:60], "[E]dit [D]el")
        log.write(table)

    def action_go_back(self): self.dismiss()
    def action_refresh(self): self._load_memories()
    def action_search(self): self.query_one("#mem-search", Input).focus()

    def action_create(self):
        self.app.push_screen(MemoryEditScreen(), self._on_edit_result)

    def action_edit(self):
        if self._memories:
            self._show_memory_picker("edit")

    def action_delete(self):
        if self._memories:
            self._show_memory_picker("delete")

    def _show_memory_picker(self, action: str):
        names = [m["name"] for m in self._memories[:20]]
        self.app.push_screen(MemoryPickerScreen(names, action), self._on_picker_result)

    def _on_picker_result(self, result: tuple | None):
        if not result:
            return
        name, action = result
        if action == "edit":
            content = self._mem_store.get(name) or ""
            meta = {"name": name, "type": "user"}
            for m in self._memories:
                if m["name"] == name:
                    meta["type"] = m.get("type", "user")
                    break
            self.app.push_screen(MemoryEditScreen(name=name, content=content, meta=meta), self._on_edit_result)
        elif action == "delete":
            self.app.push_screen(MemoryDeleteScreen(name), self._on_delete_result)

    def _on_edit_result(self, r): self._load_memories() if r else None
    def _on_delete_result(self, r): self._load_memories() if r else None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "mem-search":
            self._query = event.value.strip()
            self._load_memories()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        return {
            "mem-create": self.action_create,
            "mem-refresh": self.action_refresh,
            "mem-back": self.action_go_back,
        }.get(event.button.id, lambda: None)()


# ── Memory Create / Edit (modal) ──────────────

class MemoryEditScreen(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "save", "Save", show=False)]

    def __init__(self, name: str = "", content: str = "", meta: dict | None = None):
        super().__init__()
        self._original_name = name
        self._content = content
        self._meta = meta or {"name": "", "type": "user"}
        self._is_new = not name

    def compose(self):
        title = "  ➕  New Memory" if self._is_new else f"  ✏️  Edit: {self._original_name}"
        with Vertical(id="mem-edit-dialog", classes="dialog-box"):
            yield Static(title, classes="dialog-title")
            with ScrollableContainer(classes="dialog-form"):
                yield Label("Name (slug):")
                yield Input(value=self._meta.get("name", self._original_name), id="mem-edit-name", placeholder="my-memory-name")
                yield Label("Type:")
                yield Select([(label, v) for v, label in MEMORY_TYPES], value=self._meta.get("type", "user"), id="mem-edit-type")
                yield Label("Content:")
                yield TextArea(self._content, id="mem-edit-content", language="markdown", theme="monokai")
            with Horizontal(classes="dialog-actions"):
                yield Button("  💾 Save (Ctrl+S)  ", id="mem-save", variant="primary")
                yield Button("  Cancel (Esc)  ", id="mem-cancel")

    def action_save(self):
        name = self.query_one("#mem-edit-name", Input).value.strip()
        content = self.query_one("#mem-edit-content", TextArea).text.strip()
        mtype = self.query_one("#mem-edit-type", Select).value
        if not name or not content:
            return
        store = MemoryStore()
        store.save(name, content, {"type": mtype or "user"})
        if not self._is_new and name != self._original_name:
            store.delete(self._original_name)
        self.dismiss(True)

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mem-save":
            self.action_save()
        elif event.button.id == "mem-cancel":
            self.action_cancel()


# ── Memory Picker (modal) ─────────────────────

class MemoryPickerScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, names: list[str], action: str):
        super().__init__()
        self._names = names
        self._action = action

    def compose(self):
        label = {"edit": "Edit", "delete": "Delete"}.get(self._action, "Select")
        with Vertical(classes="picker-dialog"):
            yield Static(f"  Select memory to {label}", classes="picker-title")
            yield ScrollableContainer(classes="picker-list", id="mem-picker-list")
            with Horizontal(classes="picker-actions"):
                yield Button("  Cancel  ", id="mem-picker-cancel")

    def on_mount(self):
        c = self.query_one("#mem-picker-list", ScrollableContainer)
        for name in self._names:
            c.mount(Button(f"  {name}", id=f"pick-{name}", classes="pick-btn"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "mem-picker-cancel":
            self.dismiss(None)
        elif bid and bid.startswith("pick-"):
            self.dismiss((bid[5:], self._action))


# ── Memory Delete Confirmation (modal) ────────

class MemoryDeleteScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel"), Binding("y", "confirm", "Yes", show=False)]

    def __init__(self, name: str):
        super().__init__()
        self._name = name

    def compose(self):
        with Vertical(id="mem-delete-dialog", classes="dialog-box delete-dialog"):
            yield Static("  ⚠️  Delete Memory", classes="dialog-title delete-title")
            yield Static(f"\n  Are you sure you want to delete:\n\n  [bold #ef4444]{self._name}[/]\n\n  This action cannot be undone.\n", classes="delete-msg")
            with Horizontal(classes="dialog-actions-center"):
                yield Button("  ✅ Yes, Delete  ", id="mem-delete-yes", variant="error")
                yield Button("  ❌ Cancel  ", id="mem-delete-no")

    def action_confirm(self):
        MemoryStore().delete(self._name)
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mem-delete-yes":
            self.action_confirm()
        else:
            self.dismiss(None)
