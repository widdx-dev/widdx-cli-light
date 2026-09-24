"""OpenCode Zen provider — free models with proxy rotation."""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .openai_compatible import OpenAICompatibleProvider
from .base import _clean_surrogates, _DEFAULT_MAX_TOKENS
from .free_models import fetch_free_models
from ..proxy import proxy_manager

import logging as _logging
logger = _logging.getLogger("widdx.providers")

class OpenCodeZenProvider(OpenAICompatibleProvider):
    """
    Connects to opencode.ai/zen/v1 with:
    - full streaming
    - automatic proxy rotation on every 429
    - fallback across all free models on repeated failures
    - retry with exponential backoff
    """

    MAX_RETRIES = 5           # total retry attempts
    PROXY_ROTATIONS = 3       # how many proxy rotations before switching model

    def __init__(self, name: str, model: str,
                 base_url: str = "https://opencode.ai/zen/v1",
                 api_key: str = "public"):
        super().__init__(name, model, base_url, api_key)
        # Free model list for fallback -- populated on first use
        self._free_models: list[str] = []
        self._model_index: int = 0

    def _get_free_models(self) -> list[str]:
        if not self._free_models:
            self._free_models = fetch_free_models()
            # Put the current model first
            if self.model in self._free_models:
                self._free_models.remove(self.model)
            self._free_models.insert(0, self.model)
        return self._free_models

    def _next_model(self) -> str:
        models = self._get_free_models()
        self._model_index = (self._model_index + 1) % len(models)
        return models[self._model_index]

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Generator: yields content chunks + tool calls + done event."""
        url = f"{self.base_url}/chat/completions"
        schema = self.build_tools_schema(tool_defs)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": _DEFAULT_MAX_TOKENS,
            "stream": True,
        }
        if schema:
            body["tools"] = schema

        proxy_rotations_done = 0
        retries = self.MAX_RETRIES

        for attempt in range(retries):
            # Reset accumulators for each attempt
            content_chunks: list[str] = []
            reasoning_chunks: list[str] = []
            current_tool_calls: dict = {}
            transport = proxy_manager.get_transport()
            try:
                client_kwargs: dict[str, Any] = {"timeout": 300}
                if transport:
                    client_kwargs["transport"] = transport

                with httpx.Client(**client_kwargs) as client:
                    with client.stream("POST", url, json=body, headers=headers) as resp:

                        if resp.status_code == 429:
                            resp.read()
                            if proxy_rotations_done < self.PROXY_ROTATIONS:
                                proxy_manager.rotate()
                                proxy_rotations_done += 1
                                wait = 1
                            else:
                                new_model = self._next_model()
                                body["model"] = new_model
                                proxy_manager.rotate()
                                proxy_rotations_done = 0
                                wait = 2 ** attempt
                            time.sleep(wait)
                            continue

                        if resp.status_code != 200:
                            try:
                                err_body = resp.read().decode("utf-8", errors="replace")
                            except Exception:
                                err_body = f"HTTP {resp.status_code}"

                            # ── Retryable auth errors: switch model & proxy ──
                            retryable = (
                                "free promotion" in err_body.lower()
                                or "governor" in err_body.lower()
                                or "authentication fails" in err_body.lower()
                                or "rate limit" in err_body.lower()
                                or "too many requests" in err_body.lower()
                            )
                            if resp.status_code in (401, 403, 429) and retryable:
                                body["model"] = self._next_model()
                                proxy_manager.rotate()
                                proxy_rotations_done = 0
                                time.sleep(2 ** attempt)
                                continue

                            # ── Non-retryable error ──────────────────
                            hint = ""
                            if "governor" in err_body.lower() or "authentication fails" in err_body.lower():
                                hint = (
                                    "\n\n💡 OpenCode Zen is blocking this request.\n"
                                    "   Try: /provider → switch to 'deepseek' (needs API key)\n"
                                    "   Or:   /provider → switch to 'ollama' (local models)"
                                )
                            yield {"type": "error", "data": f"{resp.status_code}: {err_body[:500]}{hint}"}
                            return

                        # Read stream
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

                # --- Success ---
                content, calls = self._finalize_stream(
                    content_chunks, reasoning_chunks, current_tool_calls,
                )
                yield {"type": "done", "data": (content, calls)}
                return

            except (httpx.ProxyError, httpx.ConnectError):
                proxy_manager.rotate()
                proxy_rotations_done += 1
                time.sleep(1)
                continue
            except httpx.ReadTimeout:
                yield {"type": "error", "data": "Timeout (300 seconds)"}
                return
            except Exception as e:
                yield {"type": "error", "data": f"Unexpected error: {e}"}
                return

        yield {"type": "error", "data": "All attempts failed (proxies + models exhausted)"}

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


# ---------------------------------------------------------------------------
# DeepSeek Provider (OpenAI-compatible, with streaming)
# ---------------------------------------------------------------------------
