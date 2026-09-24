"""DeepSeek provider — reasoning_content + tool calls."""
from __future__ import annotations

import json
import httpx

from .openai_compatible import OpenAICompatibleProvider
from .base import _DEFAULT_MAX_TOKENS, Provider

import logging as _logging
logger = _logging.getLogger("widdx.providers")

class DeepSeekProvider(OpenAICompatibleProvider):
    """
    Connects to api.deepseek.com with:
    - full streaming
    - reasoning_content support
    - tool calls support
    - optional thinking / reasoning_effort parameters (controlled via config)
    """

    def __init__(self, name: str, model: str,
                 base_url: str = "https://api.deepseek.com",
                 api_key: str = "",
                 cfg: dict | None = None):
        self._api_key_internal = api_key
        self._thinking_enabled = True if cfg is None else cfg.get("thinking", True)
        Provider.__init__(self, name, model, base_url, api_key)

    @property
    def api_key(self) -> str:
        """Lazy-load API key from keychain if not set."""
        if not self._api_key_internal:
            from core.config.keychain import get_key
            self._api_key_internal = get_key("deepseek") or ""
        return self._api_key_internal

    @api_key.setter
    def api_key(self, value: str):
        self._api_key_internal = value

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Generator with reasoning_content + tool calls support."""
        url = f"{self.base_url}/chat/completions"
        schema = self.build_tools_schema(tool_defs)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": _DEFAULT_MAX_TOKENS,
            "stream": True,
        }
        # Official DeepSeek API does not support thinking/reasoning_effort request parameters (throws 400).
        # We only add them if we are using a third-party proxy that supports it.
        if self._thinking_enabled and ".deepseek.com" not in self.base_url and "api.deepseek" not in self.base_url:
            body["thinking"] = {"type": "enabled"}
            body["reasoning_effort"] = "high"
        if schema:
            body["tools"] = schema

        try:
            with httpx.Client(timeout=300) as client:
                with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        err_body = resp.read().decode("utf-8", errors="replace")
                        yield {"type": "error",
                               "data": f"{resp.status_code}: {err_body[:500]}"}
                        return

                    content_chunks: list[str] = []
                    reasoning_chunks: list[str] = []
                    current_tool_calls: dict = {}

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
                        if delta.get("reasoning_content"):
                            reasoning_chunks.append(delta["reasoning_content"])
                            yield {"type": "reasoning",
                                   "data": delta["reasoning_content"]}
                        tc = delta.get("tool_calls")
                        if tc:
                            for t in tc:
                                self._accumulate_tool_call(current_tool_calls, t)

                    # --- Build final result ---
                    content, calls = self._finalize_stream(
                        content_chunks, reasoning_chunks, current_tool_calls,
                    )
                    yield {"type": "done", "data": (content, calls)}

        except httpx.ConnectError:
            yield {"type": "error",
                   "data": f"Cannot connect to DeepSeek at {self.base_url}"}
        except httpx.ReadTimeout:
            yield {"type": "error", "data": "Timeout (300 seconds)"}
        except Exception as e:
            yield {"type": "error", "data": f"Error: {e}"}

    def chat(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Non-streaming: consume stream() and return final result."""
        content = ""
        calls = []
        for event in self.stream(messages, tool_defs, temperature):
            if event["type"] == "error":
                return f"\u26a0\ufe0f  {event['data']}", []
            if event["type"] == "done":
                content, calls = event["data"]
        return content, calls


