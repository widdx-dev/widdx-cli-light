"""Shared CLI/TUI visual helpers — elegant chat UI.

Designed for a clean, modern look similar to high-end AI assistants.
Focus on readability, visual hierarchy, and minimal visual noise.
"""

import logging
import unicodedata
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich import box as rich_box
from rich.style import Style
from rich.box import ROUNDED, MINIMAL, SQUARE

logger = logging.getLogger("widdx.ui_visual")



@dataclass(frozen=True)
class Theme:
    name: str
    green: str
    orange: str
    dim: str
    red: str
    blue: str
    white: str
    bg: str
    purple: str
    cyan: str
    gold: str


# Palettes
DARK = Theme(
    name="dark",
    green="#00d4aa",
    orange="#f5a623",
    dim="#636e7a",
    red="#ff5370",
    blue="#82aaff",
    white="#cdd6f4",
    bg="#0b0f19",
    purple="#c792ea",
    cyan="#89dceb",
    gold="#ffd700",
)

LIGHT = Theme(
    name="light",
    green="#007550",
    orange="#b56800",
    dim="#7a8999",
    red="#c0392b",
    blue="#2a5ab5",
    white="#1e2030",
    bg="#eff1f5",
    purple="#7c3aed",
    cyan="#0077aa",
    gold="#b8860b",
)

_REGISTRY = {"dark": DARK, "light": LIGHT}


def get_current_theme():
    try:
        from core.config import settings
        name = settings.get("cli_theme", "dark")
        return _REGISTRY.get(str(name).lower(), DARK)
    except Exception:
        return DARK


T: Theme = get_current_theme()

# Color aliases
GREEN = T.green
ORANGE = T.orange
DIM = T.dim
RED = T.red
BLUE = T.blue
WHITE = T.white
BG = T.bg
PURPLE = T.purple
CYAN = T.cyan
GOLD = T.gold

# Styles
HEADER = Style(bold=True, color=GREEN)
USER_STYLE = Style(bold=True, color=GREEN)
ASSISTANT_STYLE = Style(bold=True, color=ORANGE)
SYSTEM_STYLE = Style(color=CYAN)
ERROR_STYLE = Style(bold=True, color=RED)
DIM_STYLE = Style(color=DIM)
TOOL_STYLE = Style(color=PURPLE)
GOLD_STYLE = Style(color=GOLD)

TOOL = PURPLE


# Backward compat — role metadata for CLI theming
ROLE_META_ASCII = {
    "user":      ("▸",  "You",      "#00d4aa"),
    "assistant": ("◆",  "WIDDX",    "#f5a623"),
    "system":    ("⊙",  "System",   "#89dceb"),
    "tool":      ("⚙",  "Tool",     "#c792ea"),
}


# Shared console
console = Console(highlight=False, markup=True, emoji=True, soft_wrap=True)


def _has_rtl(text: str) -> bool:
    for c in text:
        try:
            if unicodedata.bidirectional(c) in ("R", "AL", "RLE", "RLI"):
                return True
        except Exception:
            continue
    return False


# ── Enhanced Chat Rendering ─────────────────────────────────────


def render_user_message(content: str, timestamp: str = "") -> Panel:
    """Clean, minimal user message — no heavy borders."""
    body = _format_content(content)
    return Panel(
        body,
        title=f"[bold {GREEN}]  ●  You[/]",
        title_align="left",
        subtitle=f"[{DIM}]{timestamp}[/]" if timestamp else "",
        subtitle_align="right",
        border_style=DIM,
        box=SQUARE,
        padding=(0, 2),
    )


def render_assistant_message(content: str, timestamp: str = "",
                             elapsed: float | None = None,
                             tool_calls: list[tuple[str, str]] | None = None) -> Panel:
    """Assistant message with tool calls inline, like Manus style.

    Args:
        content: The text response.
        timestamp: Time string.
        elapsed: Seconds for the response.
        tool_calls: List of (tool_name, brief_result) for inline display.
    """
    parts: list[Any] = []

    # Tool calls strip (compact, before the text)
    if tool_calls:
        for name, result in tool_calls[:5]:
            parts.append(f"[{PURPLE}]  ⚙  {name}[/]  [{DIM}]{result[:80]}[/]")
        parts.append("")

    # Main content — render as markdown when possible
    body = _format_content(content)
    parts.append(body)

    combined = "\n".join(str(p) for p in parts) if parts else body

    sub = f"[{DIM}]{timestamp}[/]"
    if elapsed is not None:
        sub += f"  [{DIM}]({elapsed:.1f}s)[/]"

    return Panel(
        combined,
        title=f"[bold {ORANGE}]  ◆  WIDDX Nexus[/]",
        title_align="left",
        subtitle=sub,
        subtitle_align="right",
        border_style=ORANGE,
        box=ROUNDED,
        padding=(0, 2),
    )


def render_system_message(content: str) -> Panel:
    """Minimal system message — no border, just dim text."""
    return Panel(
        Text(content[:2000], style=DIM_STYLE),
        border_style=DIM,
        box=MINIMAL,
        padding=(0, 1),
    )


def render_tool_message(name: str, content: str) -> Panel:
    """Compact tool call display."""
    body = content[:500] if content else ""
    return Panel(
        Text(body, style=Style(color=PURPLE)),
        title=f"[bold {PURPLE}]  ⚙  {name}[/]",
        title_align="left",
        border_style=PURPLE,
        box=MINIMAL,
        padding=(0, 1),
    )


def render_reasoning(content: str, elapsed: float | None = None) -> Panel:
    """Collapsible thinking block — minimal."""
    sub = f"  [{DIM}]{elapsed:.1f}s[/]" if elapsed is not None else ""
    return Panel(
        Text(content[:1000], style=DIM_STYLE),
        title=f"[{PURPLE}]   󰙚  Thinking[/]{sub}",
        title_align="left",
        border_style=PURPLE,
        box=MINIMAL,
        padding=(0, 1),
    )


def render_error(content: str) -> Panel:
    """Error message — red, prominent."""
    return Panel(
        f"[bold {RED}]{content}[/]",
        title=f"[bold {RED}]  ✗  Error[/]",
        border_style=RED,
        box=ROUNDED,
        padding=(0, 2),
    )


def render_divider() -> Rule:
    """Thin separator between conversation turns."""
    return Rule(style=DIM)


def _format_content(content: str) -> str | Markdown:
    """Format content: render code blocks, strip thinking tags, detect markdown."""
    if not content:
        return ""

    # Strip thinking tags
    for tag in ("[thinking]", "[/thinking]", "<thinking>", "</thinking>"):
        content = content.replace(tag, "")

    content = content.strip()
    if not content:
        return "[done]"

    # If it has code blocks, try markdown rendering
    if "```" in content or "`" in content:
        try:
            return Markdown(content, code_theme="monokai")
        except Exception:
            pass

    # Detect simple markdown (headers, lists)
    try:
        if any(line.strip().startswith("# ") for line in content.split("\n")[:5]):
            return Markdown(content, code_theme="monokai")
    except Exception:
        pass

    return content


def header_bar(model: str, cost: float, turns: int) -> Panel:
    """Top header showing model, cost, state."""
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=3)
    grid.add_column(justify="center", ratio=5)
    grid.add_column(justify="right", ratio=3)

    brand = f"[bold {GREEN}]  ◆  WIDDX Nexus[/]"
    model_ = f"[{ORANGE}]{model}[/]"
    meta = f"[{DIM}]turns:[/][bold {WHITE}]{turns}[/]  [{DIM}]cost:[/][bold {GOLD}]${cost:.4f}[/]"
    grid.add_row(brand, model_, meta)

    return Panel(grid, border_style=DIM, box=ROUNDED, padding=(0, 1))


def show_panel(title: str, content: str) -> None:
    console.print(Panel(
        content[:2000],
        title=f"[bold {ORANGE}]  {title}[/]",
        title_align="left",
        border_style=DIM,
        box=rich_box.ROUNDED,
        padding=(0, 2),
    ))


def show_markdown(text: str) -> None:
    try:
        console.print(Markdown(text, code_theme="monokai"))
    except Exception:
        console.print(text)


def show_code(code: str, lang: str = "python") -> None:
    try:
        console.print(Syntax(code, lang, theme="one-dark", line_numbers=True,
                             word_wrap=True, background_color="default"))
        return
    except Exception:
        pass
    console.print(Panel(code, border_style=DIM, box=rich_box.ROUNDED))


def show_table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    table = Table(title=f"[bold {ORANGE}]{title}[/]", border_style=DIM,
                  header_style=f"bold {GREEN}", box=rich_box.ROUNDED,
                  show_lines=False, padding=(0, 1))
    for col in columns:
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(*[str(c) for c in row])
    console.print()
    console.print(table)
    console.print()


def show_list(items: list[str], title: str = "") -> None:
    if title:
        console.print(f"[bold {ORANGE}]{title}[/]")
    for item in items:
        console.print(f"  [{GREEN}]▸[/]  {item}")


def show_divider(label: str = "") -> None:
    if label:
        console.print(Rule(f"[{DIM}]{label}[/]", style=DIM))
    else:
        console.print(Rule(style=DIM))


def show_error(text: str) -> None:
    console.print(Panel(
        f"[bold {RED}]{text}[/]",
        title=f"[bold {RED}]  ✗  Error[/]",
        border_style=RED, box=rich_box.ROUNDED, padding=(0, 2),
    ))


def show_success(text: str) -> None:
    console.print(f"  [{GREEN}]✓[/]  {text}")
