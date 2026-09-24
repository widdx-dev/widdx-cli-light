"""Pattern learner — extracts new patterns from successful executions.

Analyzes successful execution records from knowledge.json and:
1. Identifies novel project structures that succeeded
2. Extracts reusable patterns (file layout, tool sequences)
3. Promotes patterns after 3+ similar successes
4. Stores learned patterns to .widdx/patterns.json

Zero LLM calls. Pure statistical pattern extraction.
"""

from __future__ import annotations
import json
import logging
from collections import Counter
from pathlib import Path

from .patterns import SoftwarePattern, PatternStep, PATTERNS

logger = logging.getLogger("widdx.intelligence.learner")


class PatternLearner:
    """Learns new patterns and improves existing ones from execution history."""

    def __init__(self, data_dir: Path | str | None = None):
        """Initialize the pattern learner.

        Args:
            data_dir: Directory for storing learned patterns.
                      Defaults to .widdx/ in the current directory.
        """
        self._data_dir = Path(data_dir) if data_dir else Path.cwd() / ".widdx"
        self._patterns_path = self._data_dir / "patterns.json"
        self._observations: list[dict] = []
        self._load()

    def _load(self):
        """Load learned patterns and observations from disk."""
        if not self._patterns_path.exists():
            return
        try:
            data = json.loads(self._patterns_path.read_text(encoding="utf-8"))
            self._observations = data.get("observations", [])
            # Load user patterns into the global PATTERNS dict
            for pdata in data.get("patterns", []):
                pattern = SoftwarePattern(**pdata)
                if pattern.name not in PATTERNS:
                    PATTERNS[pattern.name] = pattern
                    logger.debug("Loaded learned pattern: %s", pattern.name)
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.warning("Failed to load learned patterns: %s", e)

    def _save(self):
        """Persist learned patterns to disk."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        # Only save user-learned patterns (not the built-in ones)
        builtin = {
            "python_fastapi_api", "flask_web_app", "django_project",
            "node_express_api", "python_cli_tool", "bash_script_tool",
            "html_css_js_page", "react_component", "python_data_pipeline",
            "sql_database_schema", "mongodb_collection_design",
            "python_test_suite", "javascript_test_suite", "docker_setup",
            "github_actions_ci", "python_project_setup", "api_documentation",
            "code_refactor", "bug_fix", "code_review", "codebase_analysis",
            "system_monitoring", "flutter_app", "react_native_app",
            "security_audit",
        }
        user_patterns = [
            p for name, p in PATTERNS.items() if name not in builtin
        ]
        data = {
            "observations": self._observations[-100:],  # keep last 100
            "patterns": [
                {
                    "name": p.name,
                    "category": p.category,
                    "task_types": p.task_types,
                    "features": p.features,
                    "languages": p.languages,
                    "steps": [
                        {
                            "description": s.description,
                            "tools": s.tools,
                            "files_to_create": s.files_to_create,
                            "files_to_modify": s.files_to_modify,
                        }
                        for s in p.steps
                    ],
                    "description": p.description,
                    "estimated_time": p.estimated_time,
                    "complexity": p.complexity,
                }
                for p in user_patterns
            ],
        }
        self._patterns_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def observe(self, task_type: str, features: list[str],
                files_created: list[str], tools_used: list[str],
                success: bool, quality_score: float):
        """Record an execution observation for pattern learning.

        Args:
            task_type: Task type that was executed
            features: Detected features
            files_created: Files that were created during execution
            tools_used: Tools that were used
            success: Whether execution succeeded
            quality_score: Quality score (0.0-1.0)
        """
        if not success or quality_score < 0.5:
            return  # only learn from good outcomes

        obs = {
            "task_type": task_type,
            "features": features,
            "files_created": files_created,
            "tools_used": tools_used,
        }
        self._observations.append(obs)

        # Keep only last 200 observations
        if len(self._observations) > 200:
            self._observations = self._observations[-200:]

    def extract_patterns(self):
        """Analyze observations and extract new patterns.

        Looks for clusters of similar observations (same task_type +
        similar files_created pattern) that succeeded 3+ times.
        """
        if len(self._observations) < 3:
            return

        # Group by task_type + features signature
        groups: dict[str, list[dict]] = {}
        for obs in self._observations:
            feat_key = "+".join(sorted(obs["features"])) if obs["features"] else "none"
            key = f"{obs['task_type']}:{feat_key}"
            groups.setdefault(key, []).append(obs)

        for key, observations in groups.items():
            if len(observations) < 3:
                continue

            # Find common files created across observations
            file_counter: Counter = Counter()
            tool_counter: Counter = Counter()
            for obs in observations:
                for f in obs["files_created"]:
                    file_counter[f] += 1
                for t in obs["tools_used"]:
                    tool_counter[t] += 1

            # Files that appear in >= 60% of observations
            common_files = [
                f for f, count in file_counter.items()
                if count >= len(observations) * 0.6
            ]
            # Tools that appear in >= 60% of observations
            common_tools = [
                t for t, count in tool_counter.items()
                if count >= len(observations) * 0.6
            ]

            if not common_files and not common_tools:
                continue

            # Create a new pattern
            task_type = observations[0]["task_type"]
            features = observations[0]["features"]
            pattern_name = f"learned_{task_type}_{key.replace(':', '_').replace('+', '_')}"

            if pattern_name in PATTERNS:
                continue  # already have this one

            step_list = []
            if common_files:
                step_list.append(PatternStep(
                    description=f"Create files: {', '.join(common_files[:5])}",
                    tools=[t for t in common_tools if t in {"write", "bash"}],
                    files_to_create=common_files[:5],
                ))
            if common_tools:
                step_list.append(PatternStep(
                    description=f"Requested execution using: {', '.join(common_tools[:5])}",
                    tools=common_tools[:5],
                ))

            if step_list:
                PATTERNS[pattern_name] = SoftwarePattern(
                    name=pattern_name,
                    category="learned",
                    task_types=[task_type],
                    features=features,
                    languages=[],
                    steps=step_list,
                    description=f"Auto-learned pattern from {len(observations)} successful executions",
                    estimated_time="varies",
                    complexity=2,
                )
                logger.info("Learned new pattern: %s (%d observations)",
                           pattern_name, len(observations))

        # Save learned patterns
        self._save()

    def get_stats(self) -> dict:
        """Get pattern learning statistics."""
        return {
            "total_observations": len(self._observations),
            "learned_patterns": sum(
                1 for name in PATTERNS
                if name.startswith("learned_")
            ),
        }


# Module-level singleton
_learner: PatternLearner | None = None


def get_learner(data_dir: Path | str | None = None) -> PatternLearner:
    """Get or create the pattern learner."""
    global _learner
    if _learner is None:
        _learner = PatternLearner(data_dir)
    return _learner
