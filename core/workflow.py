"""Workflow Engine — spawn sub-agents in parallel/pipeline.

Inspired by WIDDX's Workflow system.

Three primitives:
  agent(prompt, tools=None)  → spawn a sub-agent, get its result
  parallel([thunk1, ...])    → run callables concurrently via threads
  pipeline(items, s1, s2)   → process items through staged transforms

Synchronous (no asyncio) — parallelism uses threading for I/O-bound LLM calls.
"""

import json
import logging
import threading
import time
import traceback
from typing import Any, Callable, Optional

logger = logging.getLogger("widdx.workflow")


class WorkflowEngine:
    """Orchestrates multiple sub-agents for complex tasks."""

    def __init__(
        self,
        provider: Any = None,
        tool_defs: list[dict[str, Any]] | None = None,
        cfg: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> None:
        """Initialize WorkflowEngine. If provider or tool_defs are not supplied,

        load the active defaults from settings and core.
        """
        from pathlib import Path
        if provider is None:
            from core.config.settings import load as load_cfg
            from core.providers.providers import create_provider
            self.cfg = load_cfg()
            self.provider = create_provider(self.cfg)
        else:
            self.provider = provider
            self.cfg = cfg or {}

        if tool_defs is None:
            from core import tools
            self.tool_defs = list(tools.TOOL_DEFINITIONS)
        else:
            self.tool_defs = tool_defs

        self.state = state or {}
        self._results: dict[str, Any] = {}
        self._workflows_dir = Path.cwd() / ".widdx" / "workflows"
        self._workflows_dir.mkdir(parents=True, exist_ok=True)

    def create(self, name: str, steps: list[dict[str, Any]]) -> Any:
        """Create and save a new workflow as a JSON file.

        Args:
            name: The human-readable name of the workflow.
            steps: The list of workflow step definitions.

        Returns:
            An object containing the workflow ID.
        """
        import uuid
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        workflow_data = {
            "id": workflow_id,
            "name": name,
            "steps": steps,
            "created_at": time.time(),
        }
        path = self._workflows_dir / f"{workflow_id}.json"
        path.write_text(json.dumps(workflow_data, indent=2), encoding="utf-8")
        return type("Workflow", (object,), {"id": workflow_id})()

    def list_workflows(self) -> list[dict[str, Any]]:
        """List all saved workflows from .widdx/workflows/.

        Returns:
            List of saved workflow dictionaries.
        """
        workflows = []
        if not self._workflows_dir.exists():
            return []
        for p in self._workflows_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                workflows.append(data)
            except Exception:
                pass
        return sorted(workflows, key=lambda x: x.get("created_at", 0), reverse=True)

    def run(self, workflow_id: str) -> str:
        """Execute the steps of a saved workflow.

        Args:
            workflow_id: The ID of the workflow to run.

        Returns:
            Status summary of the executed workflow.
        """
        path = self._workflows_dir / f"{workflow_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Workflow {workflow_id} not found")

        data = json.loads(path.read_text(encoding="utf-8"))
        steps = data.get("steps", [])

        try:
            from core.activity import add as add_event
            add_event("system", detail=f"Starting workflow: {data.get('name')}", icon="fa-play", agent="workflow", status="running")
        except Exception:
            pass

        results = []
        for i, step in enumerate(steps):
            step_type = step.get("type", "agent")
            prompt = step.get("prompt", "")

            try:
                from core.activity import add as add_event
                add_event("system", detail=f"Running step {i+1}/{len(steps)}: {prompt[:50]}", icon="fa-gears", agent="workflow", status="running")
            except Exception:
                pass

            if step_type == "agent":
                res = self.agent(prompt, label=f"step-{i+1}")
                results.append(res)
            elif step_type == "parallel":
                tasks = step.get("tasks", [])
                thunks = [lambda t=task: self.agent(t, label=f"step-{i+1}-p") for task in tasks]
                parallel_res: list[str] = self.parallel(thunks)  # type: ignore[arg-type]
                results.extend(parallel_res)

        try:
            from core.activity import add as add_event
            add_event("system", detail=f"Completed workflow: {data.get('name')}", icon="fa-check-double", agent="workflow", status="done")
        except Exception:
            pass

        return f"Workflow completed successfully. Executed {len(steps)} steps."


    # ── agent — run a single sub-agent ────────────────────────────────

    def agent(self, prompt: str,
              tool_defs: Optional[list] = None,
              label: str = "") -> str:
        """Run a sub-agent and return its summary.

        Args:
            prompt: The task description for the sub-agent.
            tool_defs: Optional subset of tools (defaults to all).
            label: Optional label for logging.

        Returns:
            The sub-agent's final summary string.
        """
        from core.agents.agent import AutonomousAgent

        tools = tool_defs or self.tool_defs
        ag = AutonomousAgent(self.provider, tools, self.cfg, self.state,
                             custom_prompt=self._agent_prompt(prompt))
        steps, summary = ag.run(prompt)
        key = label or prompt[:40]
        self._results[key] = {"steps": len(steps), "summary": summary[:200]}
        return summary

    # ── parallel — run multiple agents concurrently ───────────────────

    def parallel(self, thunks: list[Callable[[], str]],
                 timeout: int = 300) -> list[str]:
        """Run callables concurrently using threads.

        Args:
            thunks: List of zero-arg callables (usually lambdas).
            timeout: Max seconds per thunk.

        Returns:
            List of results in the same order as thunks.
            Failed thunks return an error string (never raise).
        """
        results: list[str] = [""] * len(thunks)
        errors: list[Optional[str]] = [None] * len(thunks)

        def _run(idx: int):
            try:
                results[idx] = thunks[idx]()
            except Exception as e:
                errors[idx] = f"{e}\n{traceback.format_exc()}"
                results[idx] = f"Error: {e}"

        threads = []
        for idx in range(len(thunks)):
            t = threading.Thread(target=_run, args=(idx,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=timeout)

        for idx, err in enumerate(errors):
            if err:
                results[idx] = f"⚠️ Sub-agent failed: {err[:200]}"

        return results

    # ── pipeline — staged processing ──────────────────────────────────

    def pipeline(self, items: list, *stages: Callable) -> list:
        """Process items through sequential stages.

        Each stage receives (prev_result, original_item, index)
        and returns a transformed result.

        Args:
            items: Input items to process.
            stages: One or more transform callables.

        Returns:
            List of final results (same order as items).
            Failed items return None (never raise).
        """
        results: list = list(items)
        for stage_idx, stage in enumerate(stages):
            new_results: list = []
            for idx, item in enumerate(results):
                prev = results[idx] if stage_idx > 0 else None
                original = items[idx] if idx < len(items) else item
                try:
                    new_results.append(stage(prev, original, idx))
                except Exception:
                    new_results.append(None)
            results = new_results
        return results

    # ── tools for AI to use workflow ──────────────────────────────────

    def get_tool_definitions(self) -> list[dict]:
        """Return workflow tool definitions for the AI to call."""
        return [
            {
                "name": "create_agent",
                "description": "Spawn a sub-agent to work on a subtask independently. "
                               "The sub-agent has its own tools and returns a summary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The exact task for the sub-agent",
                        },
                        "label": {
                            "type": "string",
                            "description": "Optional short label for tracking",
                        },
                    },
                    "required": ["prompt"],
                },
            },
            {
                "name": "run_parallel",
                "description": "Run multiple sub-agent tasks CONCURRENTLY. "
                               "All tasks start at once and run in parallel threads. "
                               "Returns results when ALL complete.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Array of task prompts, one per sub-agent",
                            "minItems": 1,
                            "maxItems": 8,
                        },
                    },
                    "required": ["tasks"],
                },
            },
        ]

    def execute_workflow_tool(self, name: str, args: dict) -> str:
        """Execute a workflow tool call from the AI."""
        if name == "create_agent":
            prompt = args.get("prompt", "")
            label = args.get("label", "")
            return self.agent(prompt, label=label)

        elif name == "run_parallel":
            tasks: list[str] = args.get("tasks", [])
            if not tasks:
                return "No tasks provided for parallel execution"

            thunks = [
                lambda t=task: self.agent(t, label=f"parallel-{i}")
                for i, task in enumerate(tasks)
            ]
            results = self.parallel(thunks)  # type: ignore[arg-type]
            parts = [f"=== Parallel Results ({len(results)} tasks) ==="]
            for i, (task, res) in enumerate(zip(tasks, results)):
                parts.append(f"\n--- Task {i+1}: {task[:60]} ---")
                parts.append(res[:500])
            return "\n".join(parts)

        return f"Unknown workflow tool: {name}"

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _agent_prompt(task: str) -> str:
        """Build a focused sub-agent system prompt."""
        return (
            "You are a focused sub-agent. Complete the following task.\n\n"
            "RULES:\n"
            "1. Use tools to accomplish the task\n"
            "2. Do not ask for clarification — make reasonable assumptions\n"
            "3. When done, provide a concise summary of what was accomplished\n"
            "4. If you hit errors, try a different approach before giving up\n\n"
            f"TASK:\n{task}"
        )

    def get_status(self) -> str:
        """Return a summary of completed workflow runs."""
        if not self._results:
            return "No workflow runs yet."
        parts = []
        for key, val in list(self._results.items())[:10]:
            parts.append(f"  {key}: {val['steps']} steps, summary: {val['summary'][:60]}")
        return "\n".join(parts)
