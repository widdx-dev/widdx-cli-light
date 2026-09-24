"""Tool detail screen — shows tool info, parameters, and description."""

import json

from textual.screen import ModalScreen
from textual.widgets import Static, Button, RichLog
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.panel import Panel


class ToolDetailScreen(ModalScreen):
    """Shows tool name, description, parameters, and usage example."""

    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
        Binding("q", "dismiss", "Dismiss"),
    ]

    def __init__(self, tool_def: dict):
        super().__init__()
        self.tool_def = tool_def

    def compose(self):
        name = self.tool_def.get("name", "Unknown Tool")
        with Vertical(id="tool-detail-dialog", classes="dialog-box"):
            yield Static(f"  🛠️  {name}", classes="dialog-title")
            with ScrollableContainer(classes="dialog-form"):
                yield RichLog(highlight=True, markup=True, classes="dialog-body")
            with Horizontal(classes="dialog-actions"):
                yield Button("  Close (Esc)  ", id="btn-close", variant="primary")

    def on_mount(self):
        log = self.query_one(RichLog)
        td = self.tool_def

        desc = td.get("description", "No description provided.")
        log.write(Panel(
            Text.from_markup(f"[bold #818cf8]Description[/]\n\n[#cbd5e1]{desc}[/]"),
            border_style="#6366f1",
            padding=(1, 2),
        ))

        name = td.get("name", "")
        if name.startswith("mcp__"):
            parts = name.split("__", 2)
            server = parts[1] if len(parts) > 1 else "?"
            log.write(Panel(
                Text.from_markup(f"[bold #0891b2]MCP Server:[/]  {server}"),
                border_style="#0891b2",
                padding=(0, 1),
            ))

        params = td.get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])

        if props:
            table = Table(
                title="Parameters",
                border_style="#0891b2",
                header_style="bold #818cf8",
                title_style="bold #64748b",
                padding=(0, 1),
            )
            table.add_column("Parameter", style="bold #0891b2", width=18)
            table.add_column("Type", style="#64748b", width=10)
            table.add_column("Required", style="#f5a623", width=8)
            table.add_column("Description", style="#cbd5e1")
            for pname, pinfo in props.items():
                ptype = pinfo.get("type", "string")
                is_req = "✅" if pname in required else "⬜"
                pdesc = pinfo.get("description", "")
                table.add_row(pname, ptype, is_req, pdesc)
            log.write(table)
            try:
                schema_str = json.dumps(params, indent=2)
                log.write("")
                log.write(Panel(
                    Syntax(schema_str, "json", theme="monokai", word_wrap=True),
                    title="[bold #64748b]Schema[/]",
                    border_style="dim",
                    padding=(0, 1),
                ))
            except Exception:
                pass
        else:
            log.write(Panel(
                Text.from_markup("[dim]No parameters[/]"),
                border_style="dim",
                padding=(0, 1),
            ))

        log.write("")
        log.write(Panel(
            Text.from_markup("[dim]Press [bold #0891b2]Esc[/] or [bold #0891b2]q[/] to close[/]"),
            border_style="dim",
            padding=(0, 1),
        ))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
