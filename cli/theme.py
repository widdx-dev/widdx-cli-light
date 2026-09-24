"""Modern CLI theme — professional dark theme with Arabic support."""

from rich.style import Style

from core.ui_visual import (
    CYAN, DIM, GOLD, GREEN, ORANGE, PURPLE, RED,
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


# ── Rich Style Objects (CLI-specific overrides) ──────────────

HEADER    = Style(bold=True, color=GREEN)
MODEL     = Style(bold=True, color=ORANGE)
USER      = Style(color=GREEN)
ASSISTANT = Style(color=ORANGE)
SYSTEM    = Style(color=CYAN)
ERROR     = Style(bold=True, color=RED)
DIM_STYLE = Style(color=DIM)
TOOL      = Style(color=PURPLE)
GOLD_STYLE = Style(color=GOLD)


# ── Role metadata tables (CLI-specific) ───────────────────────────

ROLE_META: dict[str, tuple[str, str, str]] = {
    "user":      ("󰀄",  "You",      GREEN),
    "assistant": ("󱙺",  "WIDDX",    ORANGE),
    "system":    ("",   "System",   CYAN),
    "tool":      ("󰠵",  "Tool",     PURPLE),
}

ROLE_META_ASCII: dict[str, tuple[str, str, str]] = {
    "user":      ("▸",  "You",      GREEN),
    "assistant": ("◆",  "WIDDX",    ORANGE),
    "system":    ("⊙",  "System",   CYAN),
    "tool":      ("⚙",  "Tool",     PURPLE),
}

ROLE_LABELS = {
    role: (f"{icon} {label}", color)
    for role, (icon, label, color) in ROLE_META_ASCII.items()
}

ROLE_ICONS = {role: icon for role, (icon, _, _) in ROLE_META_ASCII.items()}
