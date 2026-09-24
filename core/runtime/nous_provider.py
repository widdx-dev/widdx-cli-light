"""Nous Portal Provider — free models via Nous Research Inference API.

Nous Portal provides free models (tagged :free) that work with a free API key.
Endpoint: https://inference-api.nousresearch.com/v1
Base URL: OpenAI-compatible
"""

from __future__ import annotations

import json
import logging

from pathlib import Path


logger = logging.getLogger("widdx.nous")


class NousProvider:
    """Provider for Nous Portal free models."""

    BASE_URL = "https://inference-api.nousresearch.com/v1"
    
    # Free models available (as of 2026)
    FREE_MODELS = [
        "stepfun/step-3.7-flash:free",
        "inclusionai/ling-3.0-flash-sante:free",
        "inclusionai/ling-3.0-flash-fin:free",
        "poolside/laguna-s-2.1:free",
        "poolside/laguna-xs-2.1:free",
        "nemotron-3-ultra-free",
    ]

    def __init__(self, model: str = "stepfun/step-3.7-flash:free", api_key: str = ""):
        self._model = model
        self._api_key = api_key or self._load_api_key()
        self._timeout = 120

    def _load_api_key(self) -> str:
        """Load Nous API key from .env or keychain."""
        # Try .env first
        env_path = Path('.env')
        if env_path.exists():
            content = env_path.read_bytes().decode('utf-8')
            for line in content.split('\n'):
                if '=' in line and not line.startswith('#'):
                    key, _, val = line.partition('=')
                    key = key.strip()
                    val = val.strip().strip('\r').strip('\n').strip('\x00')
                    if key.upper() in ('NOUS_API_KEY', 'NOUS_API') and val:
                        return val

        # Try keychain
        try:
            from core.config.keychain import get_key
            return get_key("nous") or ""
        except Exception:
            return ""

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Stream response from Nous Portal."""
        import httpx

        if not self._api_key:
            yield {"type": "error", "data": "Nous API key not found. Get a free key at https://portal.nousresearch.com"}
            return

        url = f"{self.BASE_URL}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4000,
            "stream": True,
        }

        # Add tools if provided
        if tool_defs:
            body["tools"] = self._build_tools_schema(tool_defs)

        try:
            with httpx.Client(timeout=self._timeout) as client:
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


def get_nous_provider(model: str = "stepfun/step-3.7-flash:free") -> NousProvider:
    """Get Nous Portal provider — free models with free API key."""
    return NousProvider(model=model)
