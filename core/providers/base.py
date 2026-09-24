"""AI Provider implementations — OpenCode Zen, Ollama, DeepSeek, OpenAI.

Each provider wraps the LLM API with a consistent interface:
  - chat()         → streaming generator of content/reasoning chunks
  - chat_sync()    → blocking call, returns full response
  - list_models()  → fetch available models from the API

Includes fallback logic: if one provider fails, the router tries the next.
"""

import json
import uuid
from abc import ABC, abstractmethod
from typing import Optional

import logging as _logging
logger = _logging.getLogger("widdx.providers")


# ── Surrogate sanitizer ───────────────────────────────────────────────
_SURROGATE_RE = None  # lazy-compiled


def _clean_surrogates(text: str) -> str:
    """Remove lone surrogate characters (U+D800–U+DFFF) from a string.

    Surrogates are invalid in UTF-8 and crash ``json.dumps`` /
    ``websocket.send_json``. They can enter the system when a provider
    API returns JSON that contains ``\\uD800``-style escapes.
    """
    if not isinstance(text, str):
        return text
    global _SURROGATE_RE
    if _SURROGATE_RE is None:
        import re
        _SURROGATE_RE = re.compile(r'[\ud800-\udfff]')
    return _SURROGATE_RE.sub('\ufffd', text)


# ── Constants ─────────────────────────────────────────────
_DEFAULT_MAX_TOKENS = 32768

# ---------------------------------------------------------------------------
# ToolCall
# ---------------------------------------------------------------------------

class ToolCall:
    def __init__(self, name: str, args: dict, id: str = ""):
        self.name = name
        self.args = args
        self.id = id


# ---------------------------------------------------------------------------
# Base Provider
# ---------------------------------------------------------------------------

class Provider(ABC):
    def __init__(self, name: str, model: str, base_url: str, api_key: Optional[str] = None) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key  # Use internal attribute directly

    @property
    def api_key(self) -> str:
        return self._api_key or ""

    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value

    def build_tools_schema(self, tools: list[dict]) -> list[dict]:
        result = []
        for t in tools:
            params = t.get("parameters", {})
            # Support both flat format and OpenAI-compatible format
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

    @abstractmethod
    def chat(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Send a chat completion request. Must be implemented by subclasses."""
        ...

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Generator that yields events for live streaming.
        Calls chat() and yields the final result as a single event.
        Subclasses override this for true token-by-token streaming."""
        content, tool_calls = self.chat(messages, tool_defs, temperature)
        if content:
            yield {"type": "content", "data": content}
        for tc in (tool_calls or []):
            tc_name = tc.name if hasattr(tc, 'name') else str(tc)
            tc_args = tc.args if hasattr(tc, 'args') else {}
            yield {"type": "tool_call", "data": {"name": tc_name, "args": tc_args}}
        yield {"type": "done", "data": (content, tool_calls)}

    # ── Shared streaming helpers (used by subclasses) ──────────────

    @staticmethod
    def _accumulate_tool_call(current_tool_calls: dict, t: dict):
        """Accumulate a single streaming tool_call delta into current_tool_calls.

        Called for each chunk in the SSE stream that carries tool_calls.
        Modifies current_tool_calls in place.
        """
        idx = t.get("index", 0)
        if idx not in current_tool_calls:
            current_tool_calls[idx] = {
                "id": t.get("id", ""),
                "function": {"name": "", "arguments": ""},
            }
        func = t.get("function", {})
        if func.get("name"):
            current_tool_calls[idx]["function"]["name"] += func["name"]
        if func.get("arguments"):
            current_tool_calls[idx]["function"]["arguments"] += _clean_surrogates(func["arguments"])
        if t.get("id"):
            current_tool_calls[idx]["id"] = t["id"]

    @staticmethod
    def _finalize_stream(content_chunks: list[str],
                         reasoning_chunks: list[str],
                         current_tool_calls: dict) -> tuple[str, list]:
        """Build the final content string and ToolCall list from streamed chunks.

        Args:
            content_chunks: Accumulated content delta strings.
            reasoning_chunks: Accumulated reasoning delta strings.
            current_tool_calls: Accumulated tool_call deltas (index → dict).

        Returns:
            (content, list_of_ToolCall).
        """
        content = _clean_surrogates("".join(content_chunks))
        full_reasoning = _clean_surrogates("".join(reasoning_chunks))
        if full_reasoning:
            content = f"[thinking]\n{full_reasoning}\n[/thinking]\n\n" + (content or "")
        calls = []
        for idx in sorted(current_tool_calls):
            tc = current_tool_calls[idx]
            raw = tc["function"]["arguments"]
            try:
                args = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                args = {}
            # ── Ensure every tool call has a valid ID ────────────────
            # DeepSeek (& other strict providers) reject empty tool_call_id.
            # Streaming APIs may send the id in a separate chunk, or not at
            # all — generate a UUID fallback so the tool response is valid.
            call_id = tc.get("id") or f"call_{uuid.uuid4().hex[:12]}"
            calls.append(ToolCall(
                name=tc["function"]["name"], args=args, id=call_id,
            ))
        return content, calls


# ---------------------------------------------------------------------------
# Ollama Provider \u2014 with automatic capability detection & fallback
# ---------------------------------------------------------------------------

# Models known to support native function calling (tool use)
_TOOL_CAPABLE_PATTERNS = [
    "llama3.1", "llama3.2", "llama3.3", "llama3.", "llama4.",
    "qwen2.5", "qwen2.", "qwen3", "qwen3.5", "qwq",
    "mistral", "mixtral", "codestral",
    "command-r", "command-r-plus",
    "nemotron",
    "granite3.1", "granite3.", "granite4.",
    "phi3", "phi4", "phi4.5",
    "gemma3", "gemma2", "gemma3.5",
    "deepseek-coder", "deepseek-v4", "deepseek-v3", "deepseek-r1",
    "minicpm",
    "dbrx",
    "hermes",
    "nousresearch",
]

# Models known to return reasoning / thinking (either native or in-content)
_REASONING_PATTERNS = [
    "deepseek-r1", "deepseek-r1-",
    "qwq", "qwen3-", "qwen3.5-",
    "openthinker",
    "phi4-", "phi4.5-",
    "llama3.3-",
    "minicpm-",
]

