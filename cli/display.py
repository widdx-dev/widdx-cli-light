"""Modern CLI display — professional dark theme with Arabic support."""

from datetime import datetime
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich import box as rich_box

from core.ui_visual import (
    CYAN, DIM, GREEN, ORANGE, PURPLE, RED, WHITE,
    console, header_bar,
    render_user_message, render_assistant_message,
)
# Re-exported for cli.app and cli.commands — keep in sync with that import list.
from core.ui_visual import (  # noqa: F401
    show_divider, show_table, show_panel, show_error, show_success,
)


# ── Modern Color Palette ─────────────────────────────────
class ModernColors:
    """Modern dark theme colors."""
    BG_DARK = "#1a1a1a"
    BG_CARD = "#252525"
    BG_INPUT = "#333333"
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#b0b0b0"
    TEXT_MUTED = "#707070"
    ACCENT = "#007aff"
    ACCENT_HOVER = "#0056b3"
    SUCCESS = "#30d158"
    WARNING = "#ff9f0a"
    DANGER = "#ff3b30"
    BORDER = "#404040"
    BORDER_LIGHT = "#353535"


# ── Helpers ──────────────────────────────────────────────────────


def _fix_rtl(text: str) -> str:
    """Apply bidirectional reordering for Arabic/Hebrew text."""
    try:
        from bidi.algorithm import get_display
        if any('؀' <= c <= 'ۿ' or '֐' <= c <= '׿' for c in text):
            return get_display(text)
    except ImportError:
        pass
    return text


def _ts() -> str:
    """Current time as HH:MM string."""
    return datetime.now().strftime("%H:%M")


# ── Modern CLI Panels ──────────────────────────────────────────


def show_header(model: str, cost: float, turns: int) -> None:
    """Clear screen and render the top header bar."""
    console.clear()
    console.print(header_bar(model, cost, turns))
    console.print()


def show_user_msg(text: str) -> None:
    """Render the user's message in a modern panel."""
    text = _fix_rtl(text)
    console.print()
    console.print(render_user_message(text, _ts()))


def show_ai_msg(text: str) -> None:
    """Render the AI response — markdown inside a modern panel."""
    text = _fix_rtl(text)
    try:
        md = Markdown(text, code_theme="monokai", hyperlinks=True)
        panel = Panel(
            md,
            title=f"[bold {ORANGE}] ◆ WIDDX [/]",
            title_align="left",
            subtitle=f"[{DIM}] {_ts()} [/]",
            subtitle_align="right",
            border_style=ORANGE,
            box=rich_box.ROUNDED,
            padding=(0, 2),
        )
    except Exception:
        panel = render_assistant_message(text, _ts())
    console.print()
    console.print(panel)


def show_system_msg(text: str) -> None:
    """Render a system notification — slim modern panel."""
    text = _fix_rtl(text)
    panel = Panel(
        f"[{CYAN}]{text}[/]",
        border_style=DIM,
        box=rich_box.SIMPLE,
        padding=(0, 2),
    )
    console.print(panel)


# ── Agent progress (CLI-specific) ────────────────────────────────


def show_agent_progress(steps: list) -> None:
    """Display agent step progress inline."""
    for s in steps:
        icon = f"[{GREEN}]✓[/]" if s.status == "done" else (
               f"[{RED}]✗[/]"  if s.status == "failed" else
               f"[{ORANGE}]…[/]")
        console.print(f"  {icon}  [{DIM}]step {s.step_num}[/]  {s.tool_name}")


def show_agent_done(steps: list, summary: str) -> None:
    """Display agent completion summary in a table + panel."""
    table = Table(
        title=f"[bold {ORANGE}] ◆ Agent Complete [/]",
        border_style=DIM,
        header_style=f"bold {GREEN}",
        box=rich_box.ROUNDED,
    )
    table.add_column("#",      style=DIM, width=4)
    table.add_column("Tool",   style=f"bold {PURPLE}")
    table.add_column("Status", style=WHITE)
    for s in steps:
        icon = f"[{GREEN}]✓[/]" if s.status == "done" else (
               f"[{RED}]✗[/]"  if s.status == "failed" else
               f"[{ORANGE}]…[/]")
        table.add_row(str(s.step_num), s.tool_name, icon)
    console.print(table)
    if summary:
        console.print(Panel(
            summary,
            title=f"[bold {GREEN}] Summary [/]",
            border_style=GREEN,
            box=rich_box.ROUNDED,
            padding=(0, 2),
        ))
