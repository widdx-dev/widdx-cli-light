"""Universal Agent — works with ANY provider via UniversalProvider."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("widdx.universal_agent")


@dataclass
class TaskResult:
    """Result of executing a task."""
    task_id: str
    description: str
    success: bool
    output: str
    code: str
    steps: int
    time_seconds: float
    healing_applied: int = 0
    signals: dict[str, int] = field(default_factory=dict)


class UniversalAgent:
    """Universal agent that works with ANY provider."""

    def __init__(self, provider_name: str = "", model: str = ""):
        self._provider_name = provider_name
        self._model = model
        self._provider = self._create_provider()

    def _create_provider(self):
        """Create provider using UniversalProvider."""
        try:
            from core.runtime.universal_provider import UniversalProvider
            return UniversalProvider(
                provider_name=self._provider_name,
                model=self._model
            )
        except Exception as e:
            logger.error(f"Failed to create provider: {e}")
            return None

    def execute_task(self, task_description: str, task_id: str = "") -> TaskResult:
        """Execute a task using the configured provider."""
        start_time = time.time()

        prompt = f"""You are a coding assistant. Execute this task:

{task_description}

Write clean, correct code. Return ONLY the code inside a code block."""

        messages = [{'role': 'user', 'content': prompt}]

        content = ""
        if self._provider:
            for event in self._provider.stream(messages, [], temperature=0.7):
                if event.get("type") == "content":
                    content += event.get("data", "")
                elif event.get("type") == "error":
                    logger.warning(f"Provider error: {event.get('data', '')}")
                    break

        if not content:
            return TaskResult(
                task_id=task_id or f"task_{int(time.time())}",
                description=task_description,
                success=False,
                output="No response from provider",
                code="", steps=0,
                time_seconds=time.time() - start_time,
            )

        # Extract code from response
        code_blocks: list[str] = []
        in_code = False
        current_code: list[str] = []
        for line in content.split('\n'):
            if line.strip().startswith('```'):
                if in_code:
                    code_blocks.append('\n'.join(current_code))
                    current_code = []
                    in_code = False
                else:
                    in_code = True
            elif in_code:
                current_code.append(line)

        code = '\n'.join(code_blocks) if code_blocks else content

        # Verify code
        success = False
        try:
            compile(code, '<string>', 'exec')
            success = True
        except SyntaxError:
            # HTML/CSS/JS files are valid but not Python
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
            output=content,
            code=code,
            steps=1,
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


def get_real_agent(provider: str = "", model: str = "") -> UniversalAgent:
    """Get or create the universal agent."""
    return UniversalAgent(provider_name=provider, model=model)
