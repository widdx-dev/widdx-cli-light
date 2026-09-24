"""GGUF direct provider — run .gguf files via llama-cpp-python."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from .base import Provider, ToolCall, _clean_surrogates, _DEFAULT_MAX_TOKENS

import logging as _logging
logger = _logging.getLogger("widdx.providers")

_LLAMA_CPP_AVAILABLE = False
try:
    from llama_cpp import Llama
    _LLAMA_CPP_AVAILABLE = True
except ImportError:
    pass


def _auto_install_llama_cpp() -> bool:
    """Try to pip install llama-cpp-python with user consent. Returns True on success."""
    global _LLAMA_CPP_AVAILABLE
    if _LLAMA_CPP_AVAILABLE:
        return True
    import subprocess
    import sys
    # Ask user before installing
    answer = input(
        "GGUF support requires llama-cpp-python. Install now? [y/N]: "
    ).strip().lower()
    if answer not in ("y", "yes"):
        return False
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "llama-cpp-python", "-q"],
            timeout=120,
        )
        _LLAMA_CPP_AVAILABLE = True
        return True
    except Exception:
        return False


class GGUFDirectProvider(Provider):
    """Load & run a .gguf file directly via llama-cpp-python.

    No Ollama required — the model runs in-process.
    Install:  pip install llama-cpp-python
    """

    # Known prompt templates for GGUF models
    _PROMPT_TEMPLATES = {
        "chatml":   ("<|im_start|>{role}\n{content}<|im_end|>\n", ["<|im_start|>", "<|im_end|>"]),
        "llama3":   ("<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>\n", ["<|start_header_id|>", "<|eot_id|>"]),
        "mistral":  ("<s>[INST] {content} [/INST]\n", ["[INST]", "[/INST]"]),
        "phi3":     ("<|{role}|>\n{content}<|end|>\n", ["<|user|>", "<|system|>"]),
        "gemma":    ("<start_of_turn>{role}\n{content}<end_of_turn>\n", ["<start_of_turn>", "<end_of_turn>"]),
        "deepseek": ("<｜{role}｜>{content}\n", ["<｜User｜>", "<｜Assistant｜>"]),
    }

    def __init__(self, name: str, model: str,
                 base_url: str = "", api_key: str = ""):
        super().__init__(name, model, base_url or "local://gguf", api_key)
        self._llm = None
        self._loaded = False
        self._template = "chatml"  # default, can be overridden via cfg
        self._n_ctx = 8192
        self._n_threads: int | None = None  # auto: os.cpu_count() or 4

    def _ensure_loaded(self):
        if self._loaded:
            return
        if not _LLAMA_CPP_AVAILABLE:
            if not _auto_install_llama_cpp():
                raise RuntimeError(
                    "Could not install llama-cpp-python automatically.\n"
                    "Please install manually: pip install llama-cpp-python\n"
                    "Or download a wheel from: https://github.com/abetlen/llama-cpp-python/releases"
                )
        path = Path(self.model)
        if not path.exists():
            # Try resolving from import log
            from .gguf import list_imports
            for entry in list_imports():
                if entry.get("model_name") == self.model:
                    candidate = Path(entry.get("metadata", {}).get("path", ""))
                    if candidate and candidate.exists():
                        path = candidate
                        break
            if not path.exists():
                raise FileNotFoundError(f"GGUF file not found: {self.model}")
        # Auto-detect threads
        if self._n_threads is None:
            import os
            self._n_threads = max(1, (os.cpu_count() or 4) - 1)
        # Read GGUF metadata for context if available
        try:
            from .gguf import read_gguf_metadata
            meta = read_gguf_metadata(str(path))
            self._n_ctx = meta.get("context_length", 8192)
            # Auto-detect template from architecture
            arch = meta.get("architecture", "").lower()
            template_map = {"llama": "llama3", "mistral": "mistral", "phi": "phi3",
                          "phi3": "phi3", "phi4": "phi3", "gemma": "gemma",
                          "gemma2": "gemma", "deepseek": "deepseek", "deepseek2": "deepseek"}
            for arch_key, tmpl in template_map.items():
                if arch_key in arch:
                    self._template = tmpl
                    break
        except Exception:
            logger.debug("Exception suppressed (line 111)")
        self._llm = Llama(
            model_path=str(path),
            n_ctx=self._n_ctx,
            n_threads=self._n_threads,
            verbose=False,
        )
        self._loaded = True

    def chat(self, messages: list, tool_defs: list,
             temperature: float = 0.7) -> tuple[str, list]:
        content = ""
        calls = []
        for event in self.stream(messages, tool_defs, temperature):
            if event["type"] == "error":
                return f"⚠️  {event['data']}", []
            if event["type"] == "done":
                content, calls = event["data"]
        return content, calls

    def stream(self, messages: list, tool_defs: list,
              temperature: float = 0.7):
        try:
            self._ensure_loaded()

            # Build prompt using the selected template
            tmpl, stops = self._PROMPT_TEMPLATES.get(
                self._template,
                self._PROMPT_TEMPLATES["chatml"],
            )

            prompt_parts = []
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "") or ""
                if role == "system":
                    prompt_parts.append(tmpl.format(role="system", content=content))
                elif role == "user":
                    prompt_parts.append(tmpl.format(role="user", content=content))
                elif role == "assistant":
                    prompt_parts.append(tmpl.format(role="assistant", content=content))
                elif role == "tool":
                    # Tools results as user context
                    prompt_parts.append(f"[Tool result: {m.get('name', '?')}]\n{content}\n")
            prompt_parts.append(tmpl.format(role="assistant", content=""))

            full_prompt = "".join(prompt_parts)

            # Inject tool descriptions if needed
            if tool_defs:
                tool_desc = "\n".join(
                    f"- {t['name']}: {t.get('description', '')}"
                    for t in tool_defs[:10]
                )
                tool_content = (
                    "Available tools:\n" + tool_desc + "\n"
                    'To call a tool, output EXACTLY: '
                    '{"tool": "tool_name", "arguments": {...}}'
                )
                tool_prefix = tmpl.format(role='system', content=tool_content)
                full_prompt = tool_prefix + full_prompt

            content_chunks: list[str] = []
            if self._llm is None:
                raise RuntimeError("Model failed to load")
            stream = self._llm.create_completion(
                full_prompt,
                max_tokens=_DEFAULT_MAX_TOKENS,
                temperature=temperature,
                stop=[s for s in stops if s],
                stream=True,
            )
            try:
                for token in stream:
                    chunk = _clean_surrogates(token["choices"][0]["text"])
                    content_chunks.append(chunk)
                    yield {"type": "content", "data": chunk}
            finally:
                try:
                    stream.close()
                except Exception:
                    logger.debug("Exception suppressed (line 192)")

            full_content = "".join(content_chunks).strip()
            cleaned, calls = self._parse_tool_calls_from_text(full_content)
            yield {"type": "done", "data": (cleaned, calls)}
        except Exception as e:
            yield {"type": "error", "data": f"GGUF error: {e}"}

    @staticmethod
    def _parse_tool_calls_from_text(content: str) -> tuple[str, list]:
        """Parse JSON tool calls from model text output."""
        import re
        tool_calls = []
        cleaned = content
        # Pattern: {"tool": "name", "arguments": {...}} with nested braces support
        for m in re.finditer(
            r'\{\s*"tool"\s*:\s*"(\w[\w.-]*)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}',
            content,
        ):
            name = m.group(1)
            try:
                args = json.loads(m.group(2))
                call_id = f"call_{uuid.uuid4().hex[:12]}"
                tool_calls.append(ToolCall(name=name, args=args, id=call_id))
                cleaned = cleaned.replace(m.group(0), "", 1)
            except (json.JSONDecodeError, TypeError):
                pass
        # Also try the Ollama text-based tool format
        if not tool_calls:
            # ```tool\n{...}\n```
            for m in re.finditer(r'```tool\s*\n(\{.+?\})\s*\n```', content, re.DOTALL):
                try:
                    data = json.loads(m.group(1))
                    name = data.get("tool", "")
                    args = data.get("arguments", {})
                    if name:
                        call_id = f"call_{uuid.uuid4().hex[:12]}"
                        tool_calls.append(ToolCall(name=name, args=args, id=call_id))
                        cleaned = cleaned.replace(m.group(0), "", 1)
                except (json.JSONDecodeError, TypeError):
                    pass
        return cleaned.strip(), tool_calls


_DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434",
    "gguf": "http://localhost:11434",
    "opencode-zen": "https://opencode.ai/zen/v1",
    "opencode": "https://opencode.ai/zen/v1",
}

_DEFAULT_MODELS: dict[str, list[str]] = {
    "opencode-zen": [],       # تُجلب ديناميكياً من fetch_free_models()
    "deepseek": ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
    "ollama": [],             # تُجلب ديناميكياً من fetch_ollama_models()
    "gguf": [],               # تُجلب ديناميكياً من fetch_gguf_models()
}


