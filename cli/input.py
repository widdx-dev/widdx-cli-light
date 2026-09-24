"""CLI Input — Professional prompt_toolkit input handling for WIDDX.

Features:
  - Persistent command history (across sessions).
  - Auto-suggest from history.
  - Tab completion for all slash commands and skill names.
  - Multi-line input (Escape+Enter).
  - Styled prompt: teal accent with model indicator.
"""

from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML

from .theme import GREEN, DIM, PURPLE


# ════════════════════════════════════════════════════════════════════
#  History File
# ════════════════════════════════════════════════════════════════════

_HISTORY_FILE = Path.home() / ".widdx" / "cli_history.txt"


# ════════════════════════════════════════════════════════════════════
#  Prompt Toolkit Style
# ════════════════════════════════════════════════════════════════════

_PT_STYLE = PTStyle.from_dict({
    # Prompt characters
    "prompt":      f"bold {GREEN}",
    "prompt.sep":  f"{DIM}",
    "prompt.model": f"italic {DIM}",

    # Auto-suggest ghost text
    "auto-suggest": f"italic {DIM}",

    # Completion menu
    "completion-menu":                  f"bg:{DIM} {DIM}",
    "completion-menu.completion":       "noinherit",
    "completion-menu.completion.current": f"bg:{GREEN} #0b0f19 bold",

    # Selected text
    "selected-text": f"bg:{PURPLE} #ffffff",
})


# ════════════════════════════════════════════════════════════════════
#  Tab Completer
# ════════════════════════════════════════════════════════════════════

def _build_completer() -> WordCompleter:
    """Return a WordCompleter with all commands + active skill names."""
    try:
        from core.skills import skill_manager
        skill_words = [f"!{s.name}" for s in skill_manager.list_all()]
    except Exception:
        skill_words = []

    commands = [
        "/help", "/clear", "/model", "/provider", "/proxy",
        "/history", "/save", "/load", "/export", "/tools",
        "/skills", "/sandbox", "/undo", "/doctor", "/debug",
        "/remember", "/memories", "/permissions", "/theme",
        "/version", "/gguf", "/branch", "/mcp", "/exit", "/quit",
        "/replay",
        "/vision", "/reasoning", "/manifest",
        "/search-replace", "/semantic", "/rename", "/dep-graph",
        "/docker", "/db", "/api", "/pkg", "/terminal",
        # sub-commands
        "/vision mode", "/vision model",
        "/mcp discover", "/mcp add", "/mcp remove",
        "/branch list", "/branch create", "/branch switch",
        "/gguf import", "/gguf list", "/gguf scan", "/gguf remove",
        "/permissions level", "/permissions forget",
    ]

    return WordCompleter(
        sorted(set(commands + skill_words)),
        ignore_case=True,
        sentence=True,
    )


# ════════════════════════════════════════════════════════════════════
#  Input Handler
# ════════════════════════════════════════════════════════════════════

class CLIInput:
    """Wraps prompt_toolkit session; falls back gracefully to plain input()."""

    def __init__(self):
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._session: Optional[PromptSession] = None

    @property
    def session(self) -> Optional[PromptSession]:
        if self._session is None:
            try:
                self._session = PromptSession(
                    history=FileHistory(str(_HISTORY_FILE)),
                    auto_suggest=AutoSuggestFromHistory(),
                    completer=_build_completer(),
                    style=_PT_STYLE,
                    complete_while_typing=True,
                    multiline=False,  # Enter submits; Escape+Enter for newline
                    enable_history_search=True,
                )
            except Exception:
                self._session = None
        return self._session

    # ── Prompt HTML builder ─────────────────────────────────────
    @staticmethod
    def _prompt_html(model: str) -> HTML:
        """Build the styled prompt string.

        Visual:  ◆ WIDDX  model-name  ❯
        Colors:  green     dim         green bold
        """
        # Trim model to keep prompt compact (max 28 chars)
        m = model[:28] if model else ""
        sep = f"<style fg='{DIM}'> │ </style>"
        brand = f"<style fg='{GREEN}' class='prompt'> ◆ WIDDX</style>"
        model_part = f"<style fg='{DIM}' class='prompt.model'>{m}</style>" if m else ""
        arrow = f"<style fg='{GREEN}' class='prompt'> ❯ </style>"

        return HTML(f"{brand}{sep}{model_part}{arrow}")

    # ── Public API ──────────────────────────────────────────────
    def get_input(self, model: str = "") -> str:
        """Prompt the user; returns stripped text or '' on interrupt."""
        if self.session:
            try:
                result = self.session.prompt(self._prompt_html(model))
                return result.strip()
            except (KeyboardInterrupt, EOFError):
                return ""
            except Exception:
                pass  # fall through

        # Plain fallback
        try:
            return input(" ◆ WIDDX ❯ ").strip()
        except (KeyboardInterrupt, EOFError):
            return ""

    def refresh_completer(self) -> None:
        """Rebuild the completer (call after /skills or skill changes)."""
        if self._session is not None:
            self._session.completer = _build_completer()
