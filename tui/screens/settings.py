"""Full-screen settings — tabbed provider config for WIDDX Nexus."""

from textual.screen import Screen
from textual.widgets import Static, Input, Button, Select, Switch, TabbedContent, TabPane
from textual.containers import Horizontal, ScrollableContainer
from textual.binding import Binding
from pathlib import Path
import threading

from typing import Any
from core import config
from core.config.keychain import set_key, forget_key, has_key
from core.providers.providers import (
    fetch_free_models, fetch_ollama_models,
    _TOOL_CAPABLE_PATTERNS, _REASONING_PATTERNS,
)

# ── Provider definitions ──────────────────────────────────
from core.providers.providers import _DEFAULT_BASE_URLS, _DEFAULT_MODELS
PROVIDER_LIST: list[dict[str, Any]] = [
    {
        "id": "opencode-zen",
        "label": "🌐 OpenCode Zen",
        "tab":   "opencode-zen",
        "desc":  "Free tier — no API key needed, rotating models & proxies",
        "default_url": _DEFAULT_BASE_URLS["opencode-zen"],
        "default_models": _DEFAULT_MODELS["opencode-zen"],
        "needs_key": False,
        "badge": "[bold #10b981]FREE[/]",
    },
    {
        "id": "deepseek",
        "label": "🔵 DeepSeek",
        "tab":   "deepseek",
        "desc":  "Official API — requires key from platform.deepseek.com",
        "default_url": _DEFAULT_BASE_URLS["deepseek"],
        "default_models": _DEFAULT_MODELS["deepseek"],
        "needs_key": True,
        "badge": "[bold #0891b2]API KEY[/]",
    },
    {
        "id": "openai",
        "label": "⚪ OpenAI",
        "tab":   "openai",
        "desc":  "Official API — requires key from platform.openai.com",
        "default_url": _DEFAULT_BASE_URLS["openai"],
        "default_models": _DEFAULT_MODELS["openai"],
        "needs_key": True,
        "badge": "[bold #94a3b8]API KEY[/]",
    },
    {
        "id": "ollama",
        "label": "🟠 Ollama",
        "tab":   "ollama",
        "desc":  "Local models — run 'ollama serve' first",
        "default_url": _DEFAULT_BASE_URLS["ollama"],
        "default_models": _DEFAULT_MODELS["ollama"],
        "needs_key": False,
        "badge": "[bold #f5a623]LOCAL[/]",
    },
    {
        "id": "gguf",
        "label": "📦 GGUF Models",
        "tab":   "gguf",
        "desc":  "Imported .gguf files — runs via Ollama or directly (llama-cpp)",
        "default_url": _DEFAULT_BASE_URLS["gguf"],
        "default_models": _DEFAULT_MODELS["gguf"],
        "needs_key": False,
        "badge": "[bold #c084fc]GGUF[/]",
    },
]


def _guess_ollama_caps(model_name: str) -> str:
    lower = model_name.lower()
    badges = []
    if any(pat in lower for pat in _TOOL_CAPABLE_PATTERNS):
        badges.append("[bold #00c896]🧰 tools[/]")
    else:
        badges.append("[dim]⚠ no-tools[/]")
    if any(pat in lower for pat in _REASONING_PATTERNS) or "think" in lower:
        badges.append("[bold #f5a623]🧠 thinking[/]")
    return "  ".join(badges)


def _fmt_key(key: str) -> str:
    if not key or key == "public":
        return key or ""
    if len(key) <= 8:
        return "•" * len(key)
    return key[:4] + "•" * (len(key) - 8) + key[-4:]


# ── Provider Tab Content ──────────────────────────────────

class ProviderTab(ScrollableContainer):
    """One tab's content for a single provider."""

    def __init__(self, pi: dict, current_model: str = "", current_url: str = "", is_active: bool = False):
        super().__init__()
        self._pi = pi
        self._pid = pi["id"]
        self._current_model = current_model
        self._current_url = current_url
        self._is_active = is_active

    def compose(self):
        pi = self._pi
        pid = self._pid

        # Status badge + description
        yield Static(
            f"  {pi['badge']}  [dim]{pi['desc']}[/]",
            id=f"prov-desc-{pid}",
            classes="prov-desc"
        )

        # ── Model row ──────────────────────────────────
        yield Static("Model", classes="field-label")
        with Horizontal(classes="field-row"):
            yield Select(options=[], id=f"model-{pid}", classes="field-select")
            yield Button("↻", id=f"btn-refresh-{pid}", classes="btn-icon", tooltip="Refresh model list")
        yield Static("", id=f"model-status-{pid}", classes="field-hint")

        # ── Base URL ───────────────────────────────────
        yield Static("Base URL", classes="field-label")
        yield Input(
            value=self._current_url if self._is_active else pi["default_url"],
            id=f"url-{pid}",
            placeholder="https://api.example.com/v1",
            classes="field-input",
        )

        # ── API Key ────────────────────────────────────
        yield Static("API Key", classes="field-label")
        with Horizontal(classes="field-row"):
            yield Input(
                id=f"key-{pid}",
                password=True,
                placeholder="Enter API key…" if pi["needs_key"] else "No key required",
                classes="field-input",
            )
            yield Button("✓ Set", id=f"btn-key-{pid}", classes="btn-sm")
            yield Button("✕ Forget", id=f"btn-forget-{pid}", classes="btn-sm btn-danger")
        yield Static("", id=f"key-status-{pid}", classes="field-hint")

        # ── DeepSeek: thinking toggle ──────────────────
        if pid == "deepseek":
            yield Static("Reasoning / Thinking Mode", classes="field-label")
            with Horizontal(classes="field-row"):
                yield Switch(value=config.load().get("thinking", True), id="thinking-switch")
                yield Static("[dim]Deep step-by-step reasoning (slower but more accurate)[/]", classes="field-hint-inline")

        # ── Ollama: capabilities + refresh hint ────────
        if pid == "ollama":
            yield Static("", id="ollama-caps", classes="field-hint")
            yield Static(
                "[dim]💡 Tip: Change the URL above then press ↻ to discover installed models[/]",
                classes="field-hint"
            )

    def on_mount(self):
        self._fill_models()
        self._fill_key_status()

    # ── Model population ────────────────────────────────

    def _fill_models(self, force_refresh: bool = False):
        pi = self._pi
        pid = self._pid
        select = self.query_one(f"#model-{pid}", Select)

        # Immediate defaults so widget is never BLANK
        if pid in ("deepseek", "openai"):
            defaults = list(pi["default_models"])
            opts = [(m, m) for m in defaults]
            select.set_options(opts)
            self._preselectmodel(select, opts)
            return  # static list, no network needed

        # For opencode-zen + ollama + gguf: show defaults first, then fetch in bg
        if pid == "gguf":
            # GGUF: start with empty list, fetch from import log
            opts = [("⟳ Loading GGUF models…", "")]
            select.set_options(opts)
        elif pi:
            opts = [(m, m) for m in pi["default_models"]]
            select.set_options(opts)
            self._preselectmodel(select, opts)

        self._fetch_models_bg(force_refresh)

    def _preselectmodel(self, select: Select, opts: list):
        if not opts:
            return
        if self._is_active and self._current_model:
            for _, val in opts:
                if val == self._current_model:
                    select.value = val
                    return
        select.value = opts[0][1]

    def _fetch_models_bg(self, force_refresh: bool = False):
        pi = self._pi
        pid = self._pid
        app_ref = self.app  # capture before entering thread

        def _run():
            try:
                app_ref.call_from_thread(
                    self.query_one(f"#model-status-{pid}", Static).update,
                    "[dim]⟳ Fetching models…[/]"
                )
            except Exception:
                pass

            try:
                if pid == "opencode-zen":
                    models = fetch_free_models()
                elif pid == "ollama":
                    try:
                        url = self.query_one(f"#url-{pid}", Input).value
                    except Exception:
                        url = pi["default_url"]
                    installed = fetch_ollama_models(base_url=url, force_refresh=force_refresh)
                    models = [m["name"] for m in installed]
                elif pid == "gguf":
                    from core.providers.providers import fetch_gguf_models
                    models = fetch_gguf_models()
                else:
                    models = []
            except Exception:
                models = []

            if not models:
                models = list(pi["default_models"])

            def _apply():
                try:
                    select = self.query_one(f"#model-{pid}", Select)
                    if pid == "ollama":
                        opts = [(f"{m}  {_guess_ollama_caps(m)}", m) if _guess_ollama_caps(m) else (m, m) for m in models]
                    else:
                        opts = [(m, m) for m in models]
                    select.set_options(opts)
                    self._preselectmodel(select, opts)
                    try:
                        self.query_one(f"#model-status-{pid}", Static).update(
                            f"[dim #10b981]✓ {len(models)} models available[/]"
                        )
                    except Exception:
                        pass
                    # Ollama caps
                    if pid == "ollama":
                        self._update_ollama_caps()
                except Exception:
                    pass

            app_ref.call_from_thread(_apply)

        threading.Thread(target=_run, daemon=True).start()

    def _update_ollama_caps(self):
        try:
            sel = self.query_one("#model-ollama", Select)
            caps_widget = self.query_one("#ollama-caps", Static)
            if sel.value and sel.value != Select.BLANK:
                caps = _guess_ollama_caps(str(sel.value))
                caps_widget.update(f"Capabilities: {caps}" if caps else "[dim]Capabilities: auto-detected[/]")
        except Exception:
            pass

    # ── Key status ──────────────────────────────────────

    def _fill_key_status(self):
        pid = self._pid
        pi = self._pi
        try:
            status = self.query_one(f"#key-status-{pid}", Static)
            forget_btn = self.query_one(f"#btn-forget-{pid}", Button)
            key_input = self.query_one(f"#key-{pid}", Input)

            if has_key(pid):
                from core.config.keychain import get_key
                k = get_key(pid) or ""
                key_input.value = _fmt_key(k)
                status.update("[bold #10b981]✓ Key saved[/]")
                forget_btn.display = True
            else:
                key_input.value = ""
                if pi["needs_key"]:
                    status.update("[bold #e74c3c]⚠ API key required[/]")
                else:
                    status.update("[dim]No key needed[/]")
                forget_btn.display = False
        except Exception:
            pass

    # ── Events ─────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id or ""
        pid = self._pid
        event.stop()

        if bid == f"btn-key-{pid}":
            k = self.query_one(f"#key-{pid}", Input).value.strip()
            if k:
                set_key(pid, k)
                self._fill_key_status()
            return

        if bid == f"btn-forget-{pid}":
            forget_key(pid)
            self._fill_key_status()
            return

        if bid == f"btn-refresh-{pid}":
            self._fill_models(force_refresh=True)
            return

    def on_select_changed(self, event: Select.Changed):
        event.stop()
        if event.select.id == "model-ollama":
            self._update_ollama_caps()


# ── GGUF Tab ──────────────────────────────────────────────

class GGUFTab(ScrollableContainer):
    """GGUF model import tab."""

    def compose(self):
        yield Static(
            "  [bold #f5a623]📦 GGUF Model Import[/]  [dim]— Import local GGUF models into Ollama[/]",
            classes="prov-desc"
        )
        yield Static("GGUF File Path", classes="field-label")
        with Horizontal(classes="field-row"):
            yield Input(
                id="gguf-path",
                placeholder=r"E:\Models\...\model.gguf",
                classes="field-input",
            )
            yield Button("📥 Import", id="btn-gguf-import", classes="btn-sm")
        with Horizontal(classes="field-row"):
            yield Button("🔍 Scan computer for .gguf files", id="btn-gguf-scan")
            yield Button("📋 List imported", id="btn-gguf-list")
        yield Static("", id="gguf-status", classes="field-hint")

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id or ""
        event.stop()
        if bid == "btn-gguf-import":
            self._do_import()
        elif bid == "btn-gguf-scan":
            self._do_scan()
        elif bid == "btn-gguf-list":
            self._do_list()

    def _do_scan(self):
        status = self.query_one("#gguf-status", Static)
        status.update("[dim]🔍 Scanning your computer for .gguf files…[/]")
        app_ref = self.app
        import threading
        def _run():
            try:
                from core.providers.gguf import scan_gguf_files
                found = scan_gguf_files(force_refresh=True)
                if not found:
                    app_ref.call_from_thread(status.update, "[dim]No .gguf files found. Try importing manually.[/]")
                    return
                lines = [f"[bold #10b981]✅ Found {len(found)} GGUF files:[/]"]
                for f in found[:10]:
                    size_str = f"{f['size_gb']:.1f} GB" if f["size_gb"] >= 1 else f"{f['size_mb']:.0f} MB"
                    lines.append(f"  • [bold]{f['name']}[/] [dim]({size_str})[/]")
                    lines.append(f"    [dim]{f['path']}[/]")
                if len(found) > 10:
                    lines.append(f"  … and {len(found)-10} more")
                app_ref.call_from_thread(status.update, "\n".join(lines))
            except Exception as e:
                app_ref.call_from_thread(status.update, f"[bold #e74c3c]❌ Scan failed: {e}[/]")
        threading.Thread(target=_run, daemon=True).start()

    def _do_import(self):
        path = self.query_one("#gguf-path", Input).value.strip()
        status = self.query_one("#gguf-status", Static)
        if not path:
            status.update("[bold #e74c3c]❌ Please enter a .gguf file path[/]")
            return
        if not Path(path).exists():
            status.update(f"[bold #e74c3c]❌ File not found:[/] {path}")
            return
        if Path(path).is_dir():
            status.update("[bold #e74c3c]❌ Path is a directory, not a file[/]")
            return
        status.update(f"[dim]Reading {Path(path).name}…[/]")
        try:
            from core.providers.gguf import suggest_model_name, read_gguf_metadata
            meta = read_gguf_metadata(path)
            name = suggest_model_name(path, meta)
            status.update(f"[dim]Importing as '{name}'… (may take minutes)[/]")
            self.run_worker(self._async_import(path, name, meta, status))
        except Exception as e:
            status.update(f"[bold #e74c3c]❌ {e}[/]")

    async def _async_import(self, path, name, meta, status):
        import asyncio
        from core.providers.gguf import import_gguf, log_import
        try:
            result = await asyncio.to_thread(import_gguf, path, name)
            if result["success"]:
                log_import(result)
                fetch_ollama_models(force_refresh=True)
                self.query_one("#gguf-path", Input).value = ""
                status.update(
                    f"[bold #00c896]✅ Imported: {result['model_name']}[/] "
                    f"({meta.get('architecture', '?')})"
                )
            else:
                status.update(f"[bold #e74c3c]❌ {result.get('error', 'unknown error')}[/]")
        except Exception as e:
            status.update(f"[bold #e74c3c]❌ {e}[/]")

    def _do_list(self):
        status = self.query_one("#gguf-status", Static)
        try:
            from core.providers.gguf import list_imports
            from datetime import datetime
            imports = list_imports()
            if not imports:
                status.update("[dim]No GGUF models imported yet.[/]")
                return
            lines = ["[bold]Imported GGUF Models:[/]"]
            for e in imports:
                meta = e.get("metadata", {})
                ds = datetime.fromtimestamp(e.get("imported_at", 0)).strftime("%Y-%m-%d")
                lines.append(f"  • [bold]{e['model_name']}[/] ({meta.get('architecture','?')}) [dim]{ds}[/]")
            status.update("\n".join(lines))
        except Exception as e:
            status.update(f"[bold #e74c3c]❌ {e}[/]")


# ── Main Settings Screen ──────────────────────────────────

class SettingsScreen(Screen):
    """Full-screen provider configuration — tabbed layout."""

    BINDINGS = [Binding("escape", "dismiss", "Back")]

    def __init__(self):
        super().__init__()
        cfg = config.load()
        p = cfg.get("provider", {})
        self._active_provider = p.get("name", "opencode-zen")
        self._current_model   = p.get("model", "")
        self._current_url     = p.get("base_url", "")
        self._saved = False

    def compose(self):
        # ── Title ──────────────────────────────────────
        yield Static("  ⚙️  Settings", classes="list-title")
        
        # ── Status ──────────────────────────────────────
        yield Static("", classes="list-status")
        
        # ── Active provider selector (toolbar) ──
        with Horizontal(id="active-prov-row", classes="list-toolbar"):
            yield Static("  Active Provider:", id="active-prov-label")
            yield Select(
                options=[(pi["label"], pi["id"]) for pi in PROVIDER_LIST],
                value=self._active_provider,
                id="active-provider",
            )
            yield Static("", id="active-badge")

        # ── Tabbed provider panels ───────────────────────
        with TabbedContent(id="settings-tabs"):
            for pi in PROVIDER_LIST:
                pid = pi["id"]
                is_active = (pid == self._active_provider)
                current_model = self._current_model if is_active else ""
                current_url = self._current_url if is_active else ""
                with TabPane(pi["label"], id=f"tab-{pid}"):
                    if pid == "gguf":
                        yield GGUFTab()
                    else:
                        yield ProviderTab(pi, current_model, current_url, is_active)

        # ── Footer ──────────────────────────────────────
        with Horizontal(id="settings-footer", classes="list-footer"):
            from core.config import get_config_path
            yield Static(f"  Config: [dim]{get_config_path()}[/]", id="footer-path", classes="list-footer-text")
            yield Button("  💾 Save & Switch  ", id="btn-save", variant="primary")
            yield Button("  ✕ Cancel  ", id="btn-close")

    def on_mount(self):
        self._update_active_badge()
        # Switch to the tab of the active provider
        try:
            self.query_one("#settings-tabs", TabbedContent).active = f"tab-{self._active_provider}"
        except Exception:
            pass

    # ── Events ─────────────────────────────────────────

    def on_select_changed(self, event: Select.Changed):
        event.stop()
        if (event.select.id or "") == "active-provider":
            if event.value and event.value != Select.BLANK:
                self._active_provider = str(event.value)
                self._update_active_badge()
                # Switch tab to match
                try:
                    self.query_one("#settings-tabs", TabbedContent).active = f"tab-{self._active_provider}"
                except Exception:
                    pass

    def _update_active_badge(self):
        pi = next((p for p in PROVIDER_LIST if p["id"] == self._active_provider), None)
        try:
            badge_widget = self.query_one("#active-badge", Static)
            if pi:
                badge_widget.update(f"  {pi['badge']}  [dim]{pi['desc']}[/]")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id or ""
        event.stop()
        if bid == "btn-save":
            self._do_save()
        elif bid == "btn-close":
            self.dismiss(None)

    # ── Save ───────────────────────────────────────────

    def _do_save(self):
        """Collect settings from all tabs and save to config."""
        try:
            new_cfg = config.load()
            all_providers: dict[str, dict] = {}

            for pi in PROVIDER_LIST:
                pid = pi["id"]

                # Model — guard against BLANK
                try:
                    raw = self.query_one(f"#model-{pid}", Select).value
                    if raw is None or raw == Select.BLANK or str(raw).upper() == "BLANK":
                        model = pi["default_models"][0]
                    else:
                        model = str(raw)
                except Exception:
                    model = pi["default_models"][0]

                # URL
                try:
                    url = self.query_one(f"#url-{pid}", Input).value.strip() or pi["default_url"]
                except Exception:
                    url = pi["default_url"]

                # API key
                try:
                    from core.config.keychain import set_key, get_key
                    key_input = self.query_one(f"#key-{pid}", Input).value.strip()
                    if key_input and not key_input.startswith("•"):
                        set_key(pid, key_input)
                    key = get_key(pid) or ("public" if not pi["needs_key"] else "")
                except Exception:
                    key = "public" if not pi["needs_key"] else ""

                all_providers[str(pid)] = {"model": model, "base_url": url, "api_key": key}

            # Active provider config
            active = self._active_provider
            ap: dict[str, Any] = all_providers.get(active, {})
            pi_active: dict[str, Any] = next((p for p in PROVIDER_LIST if p["id"] == active), {})

            new_cfg["provider"] = {
                "name":     active,
                "model":    ap.get("model") or pi_active.get("default_models", ["deepseek-v4-flash-free"])[0],
                "base_url": ap.get("base_url") or pi_active.get("default_url", "https://opencode.ai/zen/v1"),
                "api_key":  ap.get("api_key", "public"),
            }

            # Thinking toggle
            try:
                new_cfg["thinking"] = self.query_one("#thinking-switch", Switch).value
            except Exception:
                pass

            new_cfg["temperature"] = config.load().get("temperature", 0.7)
            new_cfg["all_providers"] = all_providers

            config.save(new_cfg)
            self._saved = True

            self.dismiss({
                "provider": active,
                "model":    new_cfg["provider"]["model"],
                "base_url": new_cfg["provider"]["base_url"],
                "api_key":  new_cfg["provider"]["api_key"],
                "all_providers": all_providers,
            })

        except Exception as e:
            try:
                # Show error in GGUF tab's status (visible fallback)
                self.query_one("#gguf-status", Static).update(f"[bold #e74c3c]❌ Save failed: {e}[/]")
            except Exception:
                pass

    def action_dismiss(self):
        self.dismiss(None)
