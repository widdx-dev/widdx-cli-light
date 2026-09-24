"""Universal Provider System — inspired by OpenCode's architecture.

Uses a unified interface for ALL providers:
- DeepSeek (via OpenAI-compatible API)
- OpenAI
- Anthropic
- Google
- OpenRouter
- Any OpenAI-compatible provider
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("widdx.universal_provider")


class UniversalProvider:
    """Unified provider that works with ANY LLM API."""

    def __init__(self, provider_name: str = "", model: str = "", api_key: str = "", base_url: str = ""):
        self._provider_name = provider_name
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._load_config()

    def _load_config(self):
        """Load configuration from .env and config."""
        from core.config.settings import load as load_config
        cfg = load_config()

        if not self._provider_name:
            self._provider_name = cfg.get("provider", {}).get("name", "deepseek")
        if not self._model:
            self._model = cfg.get("provider", {}).get("model", "deepseek-chat")
        if not self._api_key:
            self._api_key = self._load_api_key()
        if not self._base_url:
            self._base_url = self._get_default_base_url()

    def _load_api_key(self) -> str:
        """Load API key from .env or keychain — provider-specific."""
        # Try provider-specific key first
        env_path = Path('.env')
        if env_path.exists():
            content = env_path.read_bytes().decode('utf-8')
            for line in content.split('\n'):
                if '=' in line and not line.startswith('#'):
                    key, _, val = line.partition('=')
                    key = key.strip()
                    val = val.strip().strip('\r').strip('\n').strip('\x00')
                    # Match provider-specific key
                    if key.upper().endswith('_API_KEY'):
                        provider_part = key.upper().replace('_API_KEY', '')
                        if provider_part == self._provider_name.upper().replace('-', '_'):
                            return val

        # Try keychain
        try:
            from core.config.keychain import get_key
            return get_key(self._provider_name) or ""
        except Exception:
            return ""

    def _get_default_base_url(self) -> str:
        """Get default base URL for provider."""
        urls = {
            "deepseek": "https://api.deepseek.com",
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "openrouter": "https://openrouter.ai/api/v1",
            "together": "https://api.together.xyz/v1",
            "groq": "https://api.groq.com/openai/v1",
            "mistral": "https://api.mistral.ai/v1",
            "perplexity": "https://api.perplexity.ai",
        }
        return urls.get(self._provider_name, "https://api.openai.com/v1")

    def _get_valid_model(self) -> str:
        """Get valid model name for the provider."""
        valid_models = {
            "deepseek": ["deepseek-chat", "deepseek-v4-flash", "deepseek-v4-pro", "deepseek-v4-flash-vision-exp"],
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4-turbo", "gpt-3.5-turbo"],
            "anthropic": ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-haiku-4-20250514"],
            "openrouter": ["auto", "google/gemini-3-flash", "anthropic/claude-sonnet-4"],
            "together": ["meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"],
            "groq": ["llama-3.3-70b-versatile", "llama4-maverick-17b-128e"],
            "mistral": ["mistral-large-latest", "mistral-small-latest"],
            "perplexity": ["perplexity-sonar-large-online", "perplexity-sonar-small-online"],
        }

        models = valid_models.get(self._provider_name, [])
        if self._model in models:
            return self._model

        # If model not in valid list, use first valid one
        return models[0] if models else self._model

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Stream response from provider."""
        import httpx

        model = self._get_valid_model()

        # Build request
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4000,
            "stream": True,
        }

        # Add tools if provided
        if tool_defs:
            body["tools"] = self._build_tools_schema(tool_defs)

        try:
            with httpx.Client(timeout=120) as client:
                with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        err_body = resp.read().decode("utf-8", errors="replace")
                        yield {"type": "error", "data": f"{resp.status_code}: {err_body[:500]}"}
                        return

                    content_chunks = []
                    for line in resp.iter_lines():
                        if not line or line == "data: [DONE]":
                            continue
                        if not line.startswith("data: "):
                            continue
                        try:
                            chunk = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        choices = chunk.get("choices")
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        if not delta:
                            continue

                        if delta.get("content"):
                            content_chunks.append(delta["content"])
                            yield {"type": "content", "data": delta["content"]}

                    content = "".join(content_chunks)
                    yield {"type": "done", "data": (content, [])}

        except httpx.ConnectError:
            yield {"type": "error", "data": f"Cannot connect to {self._provider_name}"}
        except httpx.ReadTimeout:
            yield {"type": "error", "data": "Timeout"}
        except Exception as e:
            yield {"type": "error", "data": f"Error: {e}"}

    def chat(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Non-streaming chat."""
        content = ""
        for event in self.stream(messages, tool_defs, temperature):
            if event["type"] == "done":
                content, _ = event["data"]
            elif event["type"] == "error":
                return f"Error: {event['data']}", []
        return content, []

    def _build_tools_schema(self, tools: list) -> list:
        """Build OpenAI-compatible tools schema."""
        result = []
        for t in tools:
            params = t.get("parameters", {})
            if isinstance(params, dict) and params.get("type") == "object" and "properties" in params:
                props = params["properties"]
                required = params.get("required", [])
            else:
                props = {}
                required = []
                for k, v in params.items():
                    props[k] = {"type": v.get("type", "string"), "description": v.get("description", "")}
                    if v.get("required", False):
                        required.append(k)
            result.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": {"type": "object", "properties": props, "required": required},
                },
            })
        return result


def get_provider(provider_name: str = "", model: str = "") -> UniversalProvider:
    """Get or create a universal provider."""
    return UniversalProvider(provider_name=provider_name, model=model)
