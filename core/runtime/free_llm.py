"""Free LLM Integration — no account, no subscription, no credit card.

Uses BlockRun API: https://blockrun.ai/
- No API key required
- No account creation
- OpenAI-compatible endpoint
- Free tier available
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("widdx.free_llm")


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    success: bool
    error: str = ""


class BlockRunLLM:
    """Free LLM via BlockRun — no account required."""

    ENDPOINT = "https://blockrun.ai/api/v1/chat/completions"
    MODELS_ENDPOINT = "https://blockrun.ai/api/v1/models"

    # Free models available without key
    FREE_MODELS = [
        "nvidia/gpt-oss-120b",
        "nvidia/mistral-nemotron",
        "nvidia/nemotron-nano-9b-v2",
    ]

    def __init__(self, model: str = "nvidia/gpt-oss-120b"):
        self._model = model
        self._timeout = 120  # seconds

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> LLMResponse:
        """Generate response using free LLM."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.ENDPOINT,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                result = json.loads(response.read().decode("utf-8"))

            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"]["content"]
                return LLMResponse(
                    content=content,
                    model=self._model,
                    success=True,
                )
            else:
                return LLMResponse(
                    content="",
                    model=self._model,
                    success=False,
                    error=f"Unexpected response format: {result}",
                )

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return LLMResponse(
                content="",
                model=self._model,
                success=False,
                error=f"HTTP {e.code}: {error_body}",
            )
        except Exception as e:
            return LLMResponse(
                content="",
                model=self._model,
                success=False,
                error=str(e),
            )

    def list_models(self) -> list[dict[str, Any]]:
        """List available free models."""
        try:
            req = urllib.request.Request(self.MODELS_ENDPOINT, method="GET")
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []


class FreeLLMProvider:
    """Provider that uses free LLM for code generation tasks."""

    def __init__(self):
        self._llm = BlockRunLLM()
        self._system_prompt = """You are a helpful coding assistant.
Write clean, correct Python code.
Always include proper error handling.
Return ONLY the code, no explanations."""

    def generate_code(self, task_description: str) -> str:
        """Generate code for a task."""
        response = self._llm.generate(
            system_prompt=self._system_prompt,
            user_prompt=f"Write Python code for: {task_description}",
        )
        return response.content if response.success else ""

    def fix_code(self, code: str, error: str) -> str:
        """Fix code based on error message."""
        response = self._llm.generate(
            system_prompt=self._system_prompt,
            user_prompt=f"Fix this error in the code:\nError: {error}\n\nCode:\n{code}",
        )
        return response.content if response.success else ""

    def explain_code(self, code: str) -> str:
        """Explain what code does."""
        response = self._llm.generate(
            system_prompt="You are a code explainer. Explain clearly and concisely.",
            user_prompt=f"Explain this code:\n{code}",
        )
        return response.content if response.success else ""


# Singleton
_free_llm: FreeLLMProvider | None = None


def get_free_llm() -> FreeLLMProvider:
    global _free_llm
    if _free_llm is None:
        _free_llm = FreeLLMProvider()
    return _free_llm
