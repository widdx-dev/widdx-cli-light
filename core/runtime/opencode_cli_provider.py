"""OpenCode CLI Provider — Free models without API key.

Uses OpenCode CLI as a subprocess to execute tasks.
OpenCode handles the auth internally via ~/.local/share/opencode/auth.json.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("widdx.opencode_cli")


@dataclass
class TaskResult:
    task_id: str
    description: str
    success: bool
    output: str
    code: str
    steps: int
    time_seconds: float


class OpenCodeCLIProvider:
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

    PROVIDER_NAME = "opencode"

    def __init__(self, model: str = ""):
        self.model = model or self.FREE_MODELS[0]
        self._opencode_path = self._find_opencode()

    def _find_opencode(self) -> str | None:
        """Find OpenCode CLI binary."""
        import shutil
        opencode_path = shutil.which("opencode")
        if opencode_path:
            return opencode_path
        # Check common locations
        for candidate in [
            "opencode",
            "/usr/local/bin/opencode",
            "/usr/bin/opencode",
        ]:
            if os.path.exists(candidate):
                return candidate
        return None

    def execute_task(self, task_description: str, task_id: str = "") -> TaskResult:
        """Execute a task using OpenCode CLI."""
        start_time = time.time()

        if not self._opencode_path:
            return TaskResult(
                task_id=task_id or f"task_{int(time.time())}",
                description=task_description,
                success=False,
                output="OpenCode CLI not found. Install: npm i -g opencode",
                code="",
                steps=0,
                time_seconds=time.time() - start_time,
            )

        prompt = f"""You are a coding assistant. Execute this task:

{task_description}

Write clean, correct code. Return ONLY the code inside a code block."""

        try:
            result = subprocess.run(
                [self._opencode_path, "run", "--format", "json", "--pure", "--model", self.model, prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout
            # Extract code from response
            code_blocks: list[str] = []
            in_code = False
            current_code: list[str] = []
            for line in output.split('\n'):
                if line.strip().startswith('```'):
                    if in_code:
                        code_blocks.append('\n'.join(current_code))
                        current_code = []
                        in_code = False
                    else:
                        in_code = True
                elif in_code:
                    current_code.append(line)
            code = '\n'.join(code_blocks) if code_blocks else output
            success = False
            try:
                compile(code, '<string>', 'exec')
                success = True
            except SyntaxError:
                if code.strip().startswith('<!DOCTYPE') or code.strip().startswith('<html') or '<html' in code[:100]:
                    success = True
                elif '<!DOCTYPE html>' in code:
                    success = True
                else:
                    success = False
            return TaskResult(
                task_id=task_id or f"task_{int(time.time())}",
                description=task_description,
                success=success,
                output=output,
                code=code,
                steps=1,
                time_seconds=time.time() - start_time,
            )
        except subprocess.TimeoutExpired:
            return TaskResult(
                task_id=task_id or f"task_{int(time.time())}",
                description=task_description,
                success=False,
                output="OpenCode CLI timed out after 120s",
                code="",
                steps=0,
                time_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"OpenCode CLI error: {e}")
            return TaskResult(
                task_id=task_id or f"task_{int(time.time())}",
                description=task_description,
                success=False,
                output=f"Error: {e}",
                code="",
                steps=0,
                time_seconds=time.time() - start_time,
            )

    def run_benchmark(self, tasks: list[dict[str, str]]) -> dict[str, Any]:
        """Run multiple tasks."""
        results: list[TaskResult] = []
        start_time = time.time()
        for task in tasks:
            task_id = task.get("id", f"task_{len(results)}")
            description = task.get("description", task.get("task", ""))
            print(f"  Running: {task_id}...")
            result = self.execute_task(description, task_id)
            results.append(result)
            status = "✅" if result.success else "❌"
            print(f"    {status} time={result.time_seconds:.1f}s")
        total_time = time.time() - start_time
        successes = sum(1 for r in results if r.success)
        return {
            "total_tasks": len(tasks),
            "completed": successes,
            "success_rate": round(successes / len(tasks), 3) if tasks else 0,
            "total_time": round(total_time, 1),
            "results": [
                {
                    "task_id": r.task_id,
                    "success": r.success,
                    "time": round(r.time_seconds, 1),
                }
                for r in results
            ],
        }
