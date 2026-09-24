"""Atria provider — api.atria-asi.ai (OpenAI Chat Completions compatible).

Endpoint: POST {base_url}/chat/completions
Auth:     Authorization: Bearer <ATRIA_API_KEY>   (keys are prefixed ``atr_``)
Model:    Atria-Dawn-Preview (single model; capitalization is significant)
Context:  256K tokens, text input only
Limits:   output capped at 65,536 tokens via max_completion_tokens

Rate limits are account-wide per minute and shared across every key and API.
A 429 carries ``Retry-After`` plus ``x-rpm-limit`` / ``x-rpm-remaining``; this
provider surfaces the retry hint and the remaining budget to the agent.
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from .base import _clean_surrogates, _DEFAULT_MAX_TOKENS
from .openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger("widdx.providers")


class AtriaProvider(OpenAICompatibleProvider):
    """Atria Dawn Preview — 256K context, text-only, OpenAI-compatible."""

    BASE_URL = "https://api.atria-asi.ai/v1"
    MODEL = "Atria-Dawn-Preview"
    CONTEXT_WINDOW = 256_000
    MAX_OUTPUT_TOKENS = 65_536
    KEY_PREFIX = "atr_"
    DEFAULT_TIMEOUT = 300

    # Atria wraps its scratchpad in literal <think>/<thinking> markers inside
    # the assistant text. Route it to the reasoning channel instead of showing
    # it to the user as part of the answer.
    _THINK_BLOCKS = (
        re.compile(r"<(thinking|think|reasoning)>(.*?)</\1>", re.DOTALL | re.IGNORECASE),
        re.compile(r"\[(thinking|think|reasoning)\](.*?)\[/\1\]", re.DOTALL | re.IGNORECASE),
    )
    _THINK_TAG = re.compile(r"</?(?:thinking|think|reasoning)>|\[/?(?:thinking|think|reasoning)\]", re.IGNORECASE)

    @classmethod
    def _split_thinking(cls, text: str) -> tuple[list[str], str]:
        """Separate reasoning blocks from the user-facing answer.

        Returns (reasoning_fragments, cleaned_text). If the whole message is
        reasoning, the cleaned text is empty rather than whitespace.
        """
        if not text:
            return [], ""
        reasoning: list[str] = []

        def _keep(m: re.Match) -> str:
            inner = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
            if inner.strip():
                reasoning.append(inner.strip())
            return ""

        cleaned = text
        for pattern in cls._THINK_BLOCKS:
            cleaned = pattern.sub(_keep, cleaned)
        return reasoning, cls._THINK_TAG.sub("", cleaned).strip()

    def __init__(self, name: str = "atria", model: str = "", base_url: str = "",
                 api_key: str = "", cfg: dict | None = None):
        super().__init__(
            name or "atria",
            model or self.MODEL,
            base_url or self.BASE_URL,
            api_key,
        )
        self._cfg = cfg

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Stream a completion, translating Atria status codes into hints."""
        url = f"{self.base_url}/chat/completions"
        schema = self.build_tools_schema(tool_defs)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": _DEFAULT_MAX_TOKENS,
            "stream": True,
        }
        if schema:
            body["tools"] = schema

        try:
            with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as client:
                with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        yield {"type": "error", "data": self._describe_error(resp)}
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
                        for t in delta.get("tool_calls") or []:
                            self._accumulate_tool_call(current_tool_calls, t)

                    # Atria emits its scratchpad inline as literal
                    # [thinking]...[/thinking] inside the assistant text.
                    # Route it to the reasoning channel and keep the answer clean.
                    joined = "".join(content_chunks)
                    if any(p.search(joined) for p in self._THINK_BLOCKS):
                        fragments, cleaned = self._split_thinking(joined)
                        for frag in fragments:
                            reasoning_chunks.append(frag + "\n")
                        content_chunks = [cleaned]

                    # Build the final result without _finalize_stream's
                    # [thinking] re-wrapping: reasoning is already delivered on
                    # the reasoning channel, and the user-facing answer must
                    # not repeat it.
                    content = _clean_surrogates("".join(content_chunks)).strip()
                    calls = self._collect_tool_calls(current_tool_calls)
                    yield {"type": "done", "data": (content, calls)}

        except httpx.ConnectError:
            yield {"type": "error", "data": f"Cannot connect to {self.base_url}"}
        except httpx.ReadTimeout:
            yield {"type": "error", "data": f"Timeout ({self.DEFAULT_TIMEOUT}s)"}
        except Exception as e:
            yield {"type": "error", "data": f"Error: {e}"}

    # ── Error translation ────────────────────────────────────

    def _describe_error(self, resp: httpx.Response) -> str:
        """Turn a non-200 response into an actionable message.

        Atria reports 401 for a bad/revoked key and 429 for a rate limit with
        Retry-After / x-rpm-* headers; a bare status code is not actionable on
        its own.
        """
        try:
            err_body = resp.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""

        if resp.status_code == 401:
            detail = "API key is invalid or revoked. Store a new one with /apikey."
            if not self.api_key:
                detail = "No API key set. Run /apikey to store your ATRIA key."
            elif not self.api_key.startswith(self.KEY_PREFIX):
                detail = (
                    f"Key does not start with '{self.KEY_PREFIX}' — Atria keys are "
                    "issued from the Atria console."
                )
            return f"401: {detail}"

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            remaining = resp.headers.get("x-rpm-remaining")
            limit = resp.headers.get("x-rpm-limit")
            parts = ["Rate limit exceeded (per-minute quota is account-wide)."]
            if retry_after:
                parts.append(f"retry after {retry_after}s")
            if limit and remaining:
                parts.append(f"{remaining}/{limit} requests left this minute")
            return f"429: {' — '.join(parts[1:])}. {parts[0]}"

        if resp.status_code >= 500:
            return f"{resp.status_code}: Atria service temporarily unavailable — retry later. {err_body[:300]}"

        return f"{resp.status_code}: {err_body[:500]}"
