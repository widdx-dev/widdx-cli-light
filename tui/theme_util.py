"""TUI theme helpers — sync cli_theme config with Textual CSS classes."""

from __future__ import annotations


PROVIDER_OPTIONS = [
    ("🌐 OpenCode Zen", "opencode-zen"),
    ("🔵 DeepSeek", "deepseek"),
    ("⚪ OpenAI", "openai"),
    ("🟠 Ollama", "ollama"),
    ("📦 GGUF", "gguf"),
]


def theme_name(cfg: dict | None = None) -> str:
    if cfg is None:
        from core.config.settings import load
        cfg = load()
    name = str(cfg.get("cli_theme", "dark")).lower()
    return name if name in ("dark", "light") else "dark"


def apply_app_theme(app, cfg: dict | None = None) -> str:
    """Apply dark/light CSS class on the Textual App root."""
    name = theme_name(cfg)
    app.remove_class("theme-dark", "theme-light")
    app.add_class(f"theme-{name}")
    return name
