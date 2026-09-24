"""OpenAI-compatible provider — base for OpenAI-like APIs."""
from __future__ import annotations

import json
import uuid
import httpx

from .base import Provider, ToolCall, _clean_surrogates, _DEFAULT_MAX_TOKENS

import logging as _logging
logger = _logging.getLogger("widdx.providers")

class OpenAICompatibleProvider(Provider):
    def chat(self, messages: list, tool_defs: list, temperature: float = 0.7):
        content = ""
        calls = []
        for event in self.stream(messages, tool_defs, temperature):
            if event["type"] == "error":
                return f"\u26a0\ufe0f  {event['data']}", []
            if event["type"] == "done":
                content, calls = event["data"]
        return content, calls

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Generator: yields content chunks + tool calls + done event."""
        url = f"{self.base_url}/chat/completions"
        # Auto-append /v1 if base_url ends with openai.com but missing /v1
        if "/openai.com" in url and not url.endswith("/v1/chat/completions"):
            url = f"{self.base_url}/v1/chat/completions"
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
        if schema:
            body["tools"] = schema

        try:
            with httpx.Client(timeout=300) as client:
                with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        err_body = resp.read().decode("utf-8", errors="replace")
                        yield {"type": "error", "data": f"{resp.status_code}: {err_body[:500]}"}
                        return

                    content_chunks: list[str] = []
                    reasoning_chunks: list[str] = []
                    current_tool_calls: dict = {}

                    for line in resp.iter_lines():
                        if not line or line == "data: [DONE]" or line.startswith(":keepalive"):
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
                            clean = _clean_surrogates(delta["content"])
                            content_chunks.append(clean)
                            yield {"type": "content", "data": clean}
                        if delta.get("reasoning_content"):
                            clean = _clean_surrogates(delta["reasoning_content"])
                            reasoning_chunks.append(clean)
                            yield {"type": "reasoning", "data": clean}
                        tc = delta.get("tool_calls")
                        if tc:
                            for t in tc:
                                self._accumulate_tool_call(current_tool_calls, t)

                    # Build final result
                    content, calls = self._finalize_stream(
                        content_chunks, reasoning_chunks, current_tool_calls,
                    )
                    yield {"type": "done", "data": (content, calls)}

        except httpx.ConnectError:
            yield {"type": "error", "data": f"Cannot connect to {self.base_url}"}
        except httpx.ReadTimeout:
            yield {"type": "error", "data": "Timeout (300 seconds)"}
        except Exception as e:
            yield {"type": "error", "data": f"Error: {e}"}

    def _parse(self, data: dict) -> tuple:
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content") or ""
        calls = []
        for tc in msg.get("tool_calls") or []:
            func = tc.get("function", {})
            raw = func.get("arguments", "{}")
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    raw = {}
            call_id = tc.get("id") or f"call_{uuid.uuid4().hex[:12]}"
            calls.append(ToolCall(name=func.get("name", ""), args=raw, id=call_id))
        return content, calls


# ---------------------------------------------------------------------------
# OpenCode Zen Provider -- with automatic proxy rotation
# ---------------------------------------------------------------------------
