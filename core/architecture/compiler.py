"""Architecture Compiler — converts selected architecture into execution plan."""

from __future__ import annotations
import logging
from typing import Any
from .pattern_store import ArchitecturePattern

logger = logging.getLogger("widdx.arch.compiler")


class ArchitectureCompiler:
    """Converts an architecture into a structured execution plan."""

    def compile(self, arch: ArchitecturePattern, goal: str = "") -> dict:
        """Convert architecture → execution plan.

        Returns {"modules": [...], "tasks": [...], "dependencies": {...}, "order": [...]}
        """
        plan: dict[str, Any] = {
            "architecture": arch.name,
            "components": arch.components,
            "communication": arch.communication,
            "storage": arch.storage,
            "modules": [],
            "tasks": [],
            "dependencies": {},
            "execution_order": [],
        }

        # Generate modules from components
        for comp in arch.components:
            module = {
                "name": comp.replace("/", "").replace(".py", "").replace(".html", "").replace(".css", "").replace(".js", ""),
                "file": comp,
                "type": self._classify_file(comp),
            }
            plan["modules"].append(module)

        # Generate tasks based on architecture type
        plan["tasks"] = self._generate_tasks(arch, goal)

        # Build dependency graph
        for i, task in enumerate(plan["tasks"]):
            if i > 0:
                plan["dependencies"][task["id"]] = [plan["tasks"][i-1]["id"]]
            else:
                plan["dependencies"][task["id"]] = []

        # Execution order
        plan["execution_order"] = [t["id"] for t in plan["tasks"]]

        return plan

    def _classify_file(self, filename: str) -> str:
        ext = filename.split(".")[-1] if "." in filename else ""
        mapping = {"py": "backend", "html": "frontend", "css": "style", "js": "script",
                   "sql": "database", "yml": "config", "yaml": "config", "json": "config",
                   "md": "documentation"}
        return mapping.get(ext, "file")

    def _generate_tasks(self, arch: ArchitecturePattern, goal: str) -> list[dict]:
        tasks = []
        tid = 1

        # 1. Project structure
        tasks.append({"id": f"task_{tid}", "step": tid, "description": f"Create project structure for {arch.name}",
                      "tool": "bash", "depends_on": []})
        tid += 1

        # 2. Storage setup
        if arch.storage and arch.storage != "none":
            tasks.append({"id": f"task_{tid}", "step": tid,
                          "description": f"Initialize {arch.storage} database schema",
                          "tool": "write", "depends_on": [f"task_{tid-1}"]})
            tid += 1

        # 3. Core modules
        for comp in arch.components:
            if comp.endswith(".py") and comp not in ("test_api.py",):
                tasks.append({"id": f"task_{tid}", "step": tid,
                              "description": f"Implement {comp}",
                              "tool": "write", "depends_on": [f"task_{tid-1}"]})
                tid += 1

        # 4. Frontend
        has_frontend = any(c.endswith((".html", ".css", ".js")) for c in arch.components)
        if has_frontend:
            tasks.append({"id": f"task_{tid}", "step": tid,
                          "description": "Build frontend files", "tool": "write",
                          "depends_on": [f"task_{tid-1}"]})
            tid += 1

        # 5. Communication setup
        if arch.communication in ("REST", "GraphQL"):
            tasks.append({"id": f"task_{tid}", "step": tid,
                          "description": f"Configure {arch.communication} endpoints",
                          "tool": "write", "depends_on": [f"task_{tid-1}"]})
            tid += 1

        # 6. Tests
        tasks.append({"id": f"task_{tid}", "step": tid,
                      "description": "Create tests for all modules",
                      "tool": "write", "depends_on": [f"task_{tid-1}"]})
        tid += 1

        # 7. Validate
        tasks.append({"id": f"task_{tid}", "step": tid,
                      "description": "Validate all files — syntax + runtime checks",
                      "tool": "validate", "depends_on": [f"task_{tid-1}"]})

        return tasks
