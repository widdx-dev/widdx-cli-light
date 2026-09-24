"""Help screen modal — commands, shortcuts, and quick-action buttons."""

from textual.screen import ModalScreen
from textual.widgets import Static, RichLog, Button
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from core.ui_visual import BLUE, CYAN, DIM
from textual.message import Message


class HelpScreen(ModalScreen):
    """Commands, shortcuts, and one-click quick actions."""

    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
        Binding("q",      "dismiss", "Dismiss"),
    ]

    # Commands shown as clickable quick-action buttons
    QUICK_ACTIONS = [
        ("/tools",    "🛠  Tools",    "info"),
        ("/skills",   "🎯  Skills",   "info"),
        ("/memories", "💾  Memories", "info"),
        ("/history",  "📋  History",  "info"),
        ("/settings", "⚙  Settings", "info"),
        ("/doctor",   "🩺  Doctor",   "info"),
        ("/save",     "💿  Save",     "success"),
        ("/export",   "📤  Export",   "success"),
        ("/clear",    "🧹  Clear",    "warn"),
    ]

    CATEGORIES = {
        "💬 Commands": [
            ("/help",           "This help screen"),
            ("/clear",          "Clear chat history"),
            ("/tools",          "Show available tools"),
            ("/skills",         "List & toggle skills"),
            ("/history",        "Review chat history"),
            ("/search",         "Search messages"),
            ("/version",        "Show version info"),
        ],
        "📦 Sessions & Memory": [
            ("/save",           "Save session as JSON"),
            ("/sessions",       "Manage saved sessions"),
            ("/export",         "Export as Markdown"),
            ("/memories",       "Manage saved memories"),
            ("/remember <msg>", "Save a quick memory"),
        ],
        "⚙️  Settings": [
            ("/settings",       "Open settings panel"),
            ("/doctor",         "Run system diagnostics"),
            ("/agent <task>",   "Run autonomous agent"),
        ],
        "⌨️  Shortcuts": [
            ("Ctrl+Q",          "Quit application"),
            ("Ctrl+L",          "Clear chat"),
            ("Ctrl+P",          "Open this help"),
            ("Ctrl+B",          "Back to chat / close sidebar"),
            ("Ctrl+T",          "Toggle thinking display"),
            ("Esc",             "Close modals / Back"),
            ("!skill_name",     "Activate skill"),
            ("!off",            "Deactivate skill"),
        ],
        "🌿 Session Branches": [
            ("/branch list",    "List session branches"),
            ("/branch create",  "Create a new branch"),
            ("/branch switch",  "Switch session branch"),
            ("/theme",          "Toggle dark/light theme"),
        ],
    }

    class CommandSelected(Message):
        """Posted when user clicks a quick-action button."""
        def __init__(self, command: str):
            self.command = command
            super().__init__()

    def compose(self):
        with Vertical(id="help-dialog", classes="dialog-box"):
            yield Static("❓  Help & Reference", classes="dialog-title")
            yield Static(
                "  [dim]Quick actions — click to run, or type in the input bar[/]",
                classes="dialog-subtitle"
            )

            # ── Quick-action buttons ──────────────────────
            with Horizontal(id="help-quick-row"):
                for cmd, label, _ in self.QUICK_ACTIONS:
                    yield Button(label, id=f"qa-{cmd.lstrip('/').replace(' ', '-')}", classes="help-qa-btn")

            # ── Reference table ───────────────────────────
            yield RichLog(highlight=True, markup=True, classes="dialog-body", id="help-log")

            with Horizontal(classes="dialog-actions"):
                yield Button("  Close (Esc)  ", id="btn-close", variant="primary")

    def on_mount(self):
        log = self.query_one("#help-log", RichLog)
        log.write(Panel(
            Text.from_markup(
                "[bold ◈  WIDDX Nexus  —  Terminal AI]\n"
                "[dim]by Muhammad Muslih  •  widdx[/]"
            ),
            border_style=BLUE,
            padding=(0, 2),
        ))
        for category, cmds in self.CATEGORIES.items():
            log.write("")
            table = Table(
                title=category,
                border_style=CYAN,
                header_style=f"bold {BLUE}",
                title_style=f"bold {DIM}",
                padding=(0, 2),
                box=None,
            )
            table.add_column("Command / Key", style=f"bold {CYAN}", width=22)
            table.add_column("Description",   style=f"{DIM}")
            for cmd, desc in cmds:
                table.add_row(cmd, desc)
            log.write(table)
        log.write("")
        log.write(Panel(
            Text.from_markup(
                f"[dim]Press [bold {CYAN}]Esc[/] or [bold {CYAN}]q[/] to close  │  "
                "Click a button above to run a command instantly[/]"
            ),
            border_style=DIM,
            padding=(0, 1),
        ))

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id or ""
        if bid == "btn-close":
            self.dismiss(None)
            return
        # Quick-action buttons — map id back to command
        for cmd, label, _ in self.QUICK_ACTIONS:
            expected = f"qa-{cmd.lstrip('/').replace(' ', '-')}"
            if bid == expected:
                self.dismiss(cmd)
                return
