"""Dashboard mixin — settings."""
from __future__ import annotations
import logging

logger = logging.getLogger("widdx.web.dashboard")

import threading  # noqa: E402


def _has_keychain_key(provider_name: str) -> bool:
    """Check if an API key exists in the keychain (env vars)."""
    try:
        from core.config.keychain import has_key
        return has_key(provider_name)
    except Exception:
        return False


class SettingsMixin:
    PROVIDERS_META = [
        {"id": "opencode-zen", "name": "OpenCode Zen", "icon": "fa-cloud", "default_base": "https://opencode.ai/zen/v1"},
        {"id": "deepseek", "name": "DeepSeek", "icon": "fa-brain", "default_base": "https://api.deepseek.com"},
        {"id": "openai", "name": "OpenAI", "icon": "fa-openai", "default_base": "https://api.openai.com/v1"},
        {"id": "ollama", "name": "Ollama (Local)", "icon": "fa-microchip", "default_base": "http://localhost:11434"},
        {"id": "gguf", "name": "GGUF (Local)", "icon": "fa-box", "default_base": "http://localhost:11434"},
    ]

    def get_settings(self) -> dict:
        """Return full settings with available providers and models."""
        cfg = {}
        try:
            from core.config.settings import load as load_cfg
            cfg = load_cfg()
        except Exception:
            pass

        provider_cfg = cfg.get("provider", {})
        current_provider = provider_cfg.get("name") or cfg.get("default_provider", "opencode-zen")

        # Build provider list
        providers = []
        for meta in self.PROVIDERS_META:
            models = self._fetch_models(meta["id"])
            providers.append({
                "id": meta["id"],
                "name": meta["name"],
                "icon": meta["icon"],
                "default_base": meta["default_base"],
                "models": models,
            })

        return {
            "provider": {
                "name": current_provider,
                "model": provider_cfg.get("model", ""),
                "base_url": provider_cfg.get("base_url", ""),
                "api_key": "",  # Never expose the actual key
                "has_key": bool(provider_cfg.get("api_key")) or _has_keychain_key(current_provider),
            },
            "cli_theme": cfg.get("cli_theme", "dark"),
            "system_prompt": "",  # Hardcoded in core/constants.py — not user-editable
            "temperature": cfg.get("temperature", 0.7),
            "max_turns": cfg.get("max_turns", 10),
            "available_providers": providers,
            "config_path": str(cfg.get("_path", "")),
        }


    def update_settings(self, data: dict) -> dict:
        """Update config with new settings."""
        try:
            from core.config.settings import load as load_cfg, save as save_cfg
            cfg = load_cfg()

            provider = data.get("provider", {})
            if "name" in provider:
                cfg.setdefault("provider", {})["name"] = provider["name"]
            if "model" in provider:
                cfg.setdefault("provider", {})["model"] = provider["model"]
            if "base_url" in provider and provider["base_url"]:
                cfg.setdefault("provider", {})["base_url"] = provider["base_url"]
            if "api_key" in provider and provider["api_key"]:
                # Store in keychain (env var) — the canonical location for API keys
                try:
                    from core.config.keychain import set_key
                    provider_name = provider.get("name") or cfg.get("provider", {}).get("name", "")
                    if provider_name:
                        set_key(provider_name, provider["api_key"])
                except Exception:
                    pass

            # system_prompt is hardcoded in core/constants.py — not user-editable
            if "temperature" in data:
                cfg["temperature"] = float(data["temperature"])
            if "max_turns" in data:
                cfg["max_turns"] = int(data["max_turns"])
            if "cli_theme" in data:
                cfg["cli_theme"] = str(data["cli_theme"]).lower()

            save_cfg(cfg)
            return {"status": "ok", "message": "Settings saved"}
        except Exception as e:
            logger.error("Settings save error: %s", e)
            return {"status": "error", "message": str(e)}


    def _fetch_models(self, provider_id: str) -> list[str]:
        """Fetch available models for a provider — static defaults, then async refresh."""
        # Static defaults for instant UI response
        defaults = {
            "opencode-zen": ["deepseek-v4-flash-free", "mimo-v2.5-free", "qwen3.6-plus-free",
                           "minimax-m3-free", "nemotron-3-ultra-free", "north-mini-code-free"],
            "deepseek": ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
            "ollama": [],
            "gguf": [],
        }
        # Try live fetch with 2s timeout for dynamic providers only
        if provider_id in ("opencode-zen", "ollama"):
            try:
                import threading
                from core.providers.providers import get_available_models
                result = []
                t = threading.Thread(target=lambda: result.extend(get_available_models(provider_id)))
                t.daemon = True
                t.start()
                t.join(timeout=2.0)
                if result:
                    return result[:50]
            except Exception:
                pass
        return defaults.get(provider_id, [])


    def get_provider_models(self, provider_id: str) -> dict:
        """Get models for a specific provider (for live refresh)."""
        result = []
        thread = threading.Thread(target=lambda: result.extend(self._fetch_models(provider_id)))
        thread.daemon = True
        thread.start()
        thread.join(timeout=8.0)
        return {"provider": provider_id, "models": result[:50] if result else []}

    # ── Sandbox Computer ──


