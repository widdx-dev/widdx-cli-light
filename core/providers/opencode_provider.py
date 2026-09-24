"""OpenCode Provider — free LLM via OpenCode CLI.

Uses OpenCode CLI with free models (no account, no credit card).
Models available:
  - opencode/mimo-v2.5-free          ✅ working
  - opencode/nemotron-3.5-lightning-free  ✅ working
  - opencode/nemotron-3-ultra-free   ⚠️ slow/timeout
  - opencode/ling-3.0-flash-fin-free ⚠️ slow/timeout
  - opencode/muse-spark-1.3-contributor-free
  - opencode/muse-spark-1.2-contributor-free

Key insight: OpenCode free models ONLY work through the CLI, NOT via direct HTTP API.
The Zen API returns "OpenCode's free tier can only be used in OpenCode" for free models.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

from .base import Provider


logger = logging.getLogger("widdx.providers")


class OpenCodeProvider(Provider):
    """Provider that uses OpenCode CLI with free models (no API key needed)."""

    # Models verified to work via `opencode run --format json --pure`
    FREE_MODELS = [
        "opencode/mimo-v2.5-free",
        "opencode/nemotron-3.5-lightning-free",
        "opencode/nemotron-3-ultra-free",
        "opencode/ling-3.0-flash-fin-free",
        "opencode/muse-spark-1.3-contributor-free",
        "opencode/muse-spark-1.2-contributor-free",
    ]

    # Preferred models (fast, verified working)
    PREFERRED_MODELS = [
        "opencode/mimo-v2.5-free",
        "opencode/nemotron-3.5-lightning-free",
    ]

    # Timeout per model (seconds) — some free models are slow
    MODEL_TIMEOUTS = {
        "opencode/mimo-v2.5-free": 60,
        "opencode/nemotron-3.5-lightning-free": 180,
        "opencode/nemotron-3-ultra-free": 300,
        "opencode/ling-3.0-flash-fin-free": 300,
    }

    def __init__(
        self,
        name: str = "opencode",
        model: str = "opencode/mimo-v2.5-free",
        base_url: str = "",
        api_key: str = "",
        cfg: dict | None = None,
    ):
        resolved_model = model if model else "opencode/mimo-v2.5-free"
        super().__init__(name, resolved_model, base_url, api_key)
        self._cfg = cfg
        self._timeout = self.MODEL_TIMEOUTS.get(resolved_model, 120)
        self._opencode_path: str | None = None
        self._check_opencode()

    def _check_opencode(self) -> None:
        """Verify OpenCode CLI is installed and find its path."""
        # On Windows, opencode.cmd must be found via shell
        use_shell = sys.platform == "win32"
        possible_paths = [
            "opencode.cmd",  # Windows
            "opencode",
            os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm", "opencode.cmd"),
            os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm", "opencode"),
        ]
        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=use_shell,
                )
                if result.returncode == 0:
                    self._opencode_path = path
                    logger.info("OpenCode CLI found: %s (%s)", path, result.stdout.strip())
                    return
            except Exception:
                continue
        logger.warning("OpenCode CLI not found — install with: npm install -g opencode-ai")

    @property
    def is_available(self) -> bool:
        return self._opencode_path is not None

    def _build_cmd(self) -> list[str]:
        """Build the opencode CLI command with JSON output format."""
        cmd = self._opencode_path or "opencode.cmd"
        return [
            cmd, "run",
            "--model", self.model,
            "--format", "json",
            "--pure",
        ]

    def stream(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Stream response from OpenCode CLI (NDJSON format)."""
        if not self.is_available:
            yield {"type": "error", "data": "OpenCode CLI not found — install with: npm install -g opencode-ai"}
            return

        # Build prompt from messages
        system_prompt = ""
        user_messages = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_messages.append(content)
            elif role == "assistant":
                # Include assistant messages for context
                user_messages.append(f"[Assistant]: {content}")

        user_prompt = "\n\n".join(user_messages)
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
        else:
            full_prompt = user_prompt

        # Truncate very long prompts (free models have context limits)
        if len(full_prompt) > 8000:
            full_prompt = full_prompt[:8000] + "\n... [truncated]"

        cmd = self._build_cmd()
        logger.debug("OpenCode cmd: %s", " ".join(cmd))
        use_shell = sys.platform == "win32"

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                cwd=os.getcwd(),
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=use_shell,
            )

            content_parts: list[str] = []

            try:
                # Pipe the prompt via stdin (OpenCode reads it from there)
                stdout, _ = proc.communicate(input=full_prompt, timeout=self._timeout)

                # Parse NDJSON output line by line
                for line in stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")

                    if event_type == "text":
                        text = event.get("part", {}).get("text", "")
                        if text:
                            content_parts.append(text)
                            yield {"type": "content", "data": text}

                    elif event_type == "step_finish":
                        tokens = event.get("part", {}).get("tokens", {})
                        cost = event.get("part", {}).get("cost", 0)
                        logger.debug("OpenCode finished: tokens=%s cost=%s", tokens, cost)

                    elif event_type == "error":
                        error_msg = event.get("error", {}).get("data", {}).get("message", str(event))
                        yield {"type": "error", "data": f"OpenCode error: {error_msg}"}
                        return

            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                yield {"type": "error", "data": f"Timeout after {self._timeout}s"}
                return

            # Done
            content = "".join(content_parts)
            yield {"type": "done", "data": (content, [])}

        except FileNotFoundError:
            yield {"type": "error", "data": "OpenCode CLI not found — install with: npm install -g opencode-ai"}
        except subprocess.TimeoutExpired:
            yield {"type": "error", "data": f"Timeout after {self._timeout}s"}
        except Exception as e:
            yield {"type": "error", "data": f"Error: {e}"}

    def chat(self, messages: list, tool_defs: list, temperature: float = 0.7):
        """Non-streaming: consume stream() and return final result."""
        content = ""
        calls = []
        for event in self.stream(messages, tool_defs, temperature):
            if event["type"] == "error":
                return f"⚠️  {event['data']}", []
            if event["type"] == "done":
                content, calls = event["data"]
        return content, calls

    def build_tools_schema(self, tool_defs: list) -> list:
        """Build tools schema (simplified for OpenCode — not yet supported)."""
        return []


def create_opencode_provider(cfg: dict | None = None, **kwargs) -> OpenCodeProvider:
    """Factory function for OpenCode provider."""
    provider_cfg = cfg or {}
    model = provider_cfg.get("model", "opencode/mimo-v2.5-free")
    return OpenCodeProvider(
        name="opencode",
        model=model,
        cfg=cfg,
    )
