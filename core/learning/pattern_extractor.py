"""Pattern Extractor — learns patterns from both successes and failures.

Watches execution results and extracts reusable patterns:
  - From success: what worked, how long it took, what tools were used
  - From failure: what broke, what fixed it, what to avoid

Usage:
    from core.learning.pattern_extractor import PatternExtractor
    pe = PatternExtractor()
    pe.extract_from_execution(exec_result, task_type, user_input)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("widdx.learning")


class PatternExtractor:
    """Extracts patterns from execution results."""

    def __init__(self):
        from .pattern_library import PatternLibrary
        self.local_lib = PatternLibrary(global_scope=False)

    def extract_from_execution(self, result: Any, task_type: Any, user_input: str = "",
                               steps: list | None = None, success: bool = True,
                               project_name: str = "") -> list[str]:
        """Extract patterns from a completed execution. Returns list of pattern IDs."""
        task_type_str = str(getattr(task_type, 'value', task_type))
        extracted = []
        summary = getattr(result, "summary", "") or str(result)
        tools_used = getattr(result, "tools_used", []) or []

        # 1. Extract tool usage patterns
        if tools_used:
            tool_names = [t if isinstance(t, str) else getattr(t, "name", str(t)) for t in tools_used]
            if "validate" in tool_names:
                extracted.append(self._add("validate-after-write", "workflow",
                    "Run validate after every write/edit", "Call validate tool after write tool",
                    tools="write,validate", success=success, project=project_name))
            if len(tool_names) >= 3:
                extracted.append(self._add("multi-tool-workflow", "workflow",
                    f"Multi-step workflow with {len(tool_names)} tools",
                    f"Execute in sequence: {' → '.join(tool_names[:5])}",
                    tools=", ".join(tool_names[:5]), success=success, project=project_name))

        # 2. Extract coding patterns from success
        if success and "CODE" in task_type_str.upper():
            # Detect framework usage
            if "flask" in summary.lower() or "fastapi" in summary.lower():
                extracted.append(self._add("use-python-web-framework", "architectural",
                    "Use Flask/FastAPI for Python web projects",
                    "Start with minimal app, add routes incrementally",
                    tags=["python", "web"], success=True, project=project_name))
            if "react" in summary.lower() or "vue" in summary.lower() or "next" in summary.lower():
                extracted.append(self._add("use-component-framework", "architectural",
                    "Use component-based framework for frontend",
                    "Build components in isolation, compose at page level",
                    tags=["frontend", "components"], success=True, project=project_name))

        # 3. Extract debugging patterns from failures
        if not success:
            errors = re.findall(r'(?:Error|Failed|❌|⚠️):?\s*(.+?)(?:\n|$)', summary, re.IGNORECASE)
            for err in errors[:3]:
                if "import" in err.lower() or "module" in err.lower():
                    extracted.append(self._add("check-imports-first", "debugging",
                        "Check imports before debugging logic", f"Error: {err[:80]}",
                        tags=["debug", "import"], success=False, project=project_name))
                elif "syntax" in err.lower():
                    extracted.append(self._add("validate-syntax-first", "debugging",
                        "Validate syntax before runtime testing", f"Error: {err[:80]}",
                        tags=["debug", "syntax"], success=False, project=project_name))

        # 4. Extract planning patterns
        if steps and len(steps) > 1:
            step_names = [s.get("description", "")[:100] if isinstance(s, dict) else str(s)[:100] for s in steps]
            extracted.append(self._add("sequential-execution-plan", "planning",
                f"Break task into {len(steps)} sequential steps",
                "Execute: " + " → ".join(step_names[:5]),
                tags=["planning", "sequential"], success=success, project=project_name))

        return [e for e in extracted if e]

    def _add(self, name: str, category: str, desc: str, solution: str,
             tools: str = "", tags: list[str] | None = None,
             success: bool = True, project: str = "") -> str:
        """Add a pattern with appropriate confidence based on success/failure."""
        confidence = 0.7 if success else 0.3
        tags = (tags or []) + (["success"] if success else ["failure"])
        p = self.local_lib.add(
            name=name, category=category, description=desc,
            solution=solution, tags=tags, confidence=confidence,
            source_project=project or "current",
        )
        return p.id


class UserPreferenceLearner:
    """Learns user preferences from project patterns."""

    def __init__(self):
        from .pattern_library import PatternLibrary
        self.global_lib = PatternLibrary(global_scope=True)

    def learn_from_project(self, project_dir: str):
        """Scan a project for user preferences."""
        p = Path(project_dir)
        prefs = {}

        # Detect language
        py_count = len(list(p.rglob("*.py")))
        js_count = len(list(p.rglob("*.js"))) + len(list(p.rglob("*.ts")))
        if py_count > js_count:
            prefs["primary_language"] = "python"
        elif js_count > 0:
            prefs["primary_language"] = "javascript"

        # Detect framework
        if (p / "package.json").exists():
            import json as _j
            try:
                pkg = _j.loads((p / "package.json").read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "react" in deps:
                    prefs["frontend"] = "react"
                if "vue" in deps:
                    prefs["frontend"] = "vue"
                if "next" in deps:
                    prefs["framework"] = "nextjs"
            except Exception as e:
                logger.debug("Failed to parse package.json: %s", e)
        if (p / "pyproject.toml").exists():
            try:
                import tomllib as _t
                cfg = _t.loads((p / "pyproject.toml").read_text())
                deps = cfg.get("project", {}).get("dependencies", [])
                deps_str = " ".join(deps)
                if "fastapi" in deps_str:
                    prefs["framework"] = "fastapi"
                if "flask" in deps_str:
                    prefs["framework"] = "flask"
                if "django" in deps_str:
                    prefs["framework"] = "django"
            except Exception as e:
                logger.debug("Failed to parse pyproject.toml: %s", e)

        # Store as patterns
        for key, value in prefs.items():
            self.global_lib.add(
                name=f"pref-{key}", category="preference",
                description=f"User prefers {value} for {key}",
                solution=f"Default to {value} when {key} is relevant",
                tags=[key, value], confidence=0.8, source_project=str(p),
            )

    def get_preferences(self) -> dict:
        """Get all learned user preferences."""
        patterns = self.global_lib.search(category="preference", min_confidence=0.5)
        prefs = {}
        for p in patterns:
            key = p.name.replace("pref-", "")
            prefs[key] = p.solution
        return prefs

    def get_context_for_prompt(self) -> str:
        prefs = self.get_preferences()
        if not prefs:
            return ""
        lines = ["<user_preferences>"]
        for k, v in prefs.items():
            lines.append(f"- {k}: {v}")
        lines.append("</user_preferences>")
        return "\n".join(lines)
