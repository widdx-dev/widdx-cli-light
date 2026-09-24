"""OpenCode Zen — Free Models Provider.

HOW IT WORKS:
1. OpenCode Zen is a gateway that provides free LLM access
2. When no API key is provided, OpenCode uses "public" as the key
3. Models with cost.input === 0 are kept as "free models"
4. The Zen gateway authenticates the "public" key and returns responses

This provider uses the same mechanism to access free models without individual API keys.
"""

from __future__ import annotations

import json
import logging


logger = logging.getLogger("widdx.opencode_zen")


class OpenCodeZenProvider:
    """Provider for OpenCode Zen free models — no API key required."""

    BASE_URL = "https://opencode.ai/zen/v1"
    
    # Free models (cost.input === 0)
    FREE_MODELS = [
        "deepseek-v4-flash-free",
        "mimo-v2.5-free",
        "nemotron-3-ultra-free",
        "nemotron-3.5-lightning-free",
        "muse-spark-1.2-contributor-free",
        "muse-spark-1.3-contributor-free",
        "ling-3.0-flash-fin-free",
    ]

    def __init__(self, model: str = "deepseek-v4-flash-free"):
        self._model = model
        self._api_key = "public"  # The secret: "public" key for free models
        self._timeout = 120

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Stream response from OpenCode Zen free models."""
        import httpx

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


def get_opencode_zen_provider(model: str = "deepseek-v4-flash-free") -> OpenCodeZenProvider:
    """Get OpenCode Zen provider — no API key needed."""
    return OpenCodeZenProvider(model=model)
