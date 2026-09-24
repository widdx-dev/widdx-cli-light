"""Pattern-aware task decomposer — plans REAL steps from a knowledge base.

Upgrades core/uil/planner.py from 3 decomposers + minimal_steps to 25+ real patterns.
Each pattern produces concrete steps with: what to do, which tools to use,
what files to create/modify.

When no pattern matches → falls back to minimal decomposition (still better
than "handle task" — at least gives tool hints).

Zero LLM calls. Zero network I/O. Pure deterministic pattern matching.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field

from . import patterns as _patterns_lib
from .classifier import ClassificationResult

logger = logging.getLogger("widdx.intelligence.planner")


@dataclass
class PlanStep:
    """A single step in an execution plan.

    v4.1: Added risk assessment + verification hints + alternative approaches.
    """
    step_id: int
    description: str
    tools: list[str] = field(default_factory=list)
    files_to_create: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    expected_output: str = ""
    tool_hints: list[str] = field(default_factory=list)

    # ── v4.1 Reasoning enhancements ──
    risk_score: float = 0.3        # 0.0 (safe) to 1.0 (risky) — likelihood of failure
    verification_hint: str = ""    # what to check after executing this step
    alternatives: list[str] = field(default_factory=list)  # alternative approaches
    reasoning: str = ""            # why this step exists in the plan


@dataclass
class Plan:
    """An execution plan with ordered steps and dependencies."""
    steps: list[PlanStep]
    pattern_name: str = ""
    is_minimal: bool = False
    estimated_time: str = ""
    total_steps: int = 0

    def __post_init__(self):
        self.total_steps = len(self.steps)


class PatternAwarePlanner:
    """Task planner that uses software patterns for real decomposition.

    For each task, it:
    1. Finds the best matching software pattern
    2. Converts pattern steps into PlanSteps with tool hints
    3. Adds dependencies between steps
    4. Falls back to keyword-based decomposition if no pattern matches
    """

    def __init__(self):
        self._pattern_index: dict[str, list[str]] = {}  # task_type → pattern names
        self._build_index()

    def _build_index(self):
        """Index patterns by task type for fast lookup."""
        for name, pattern in _patterns_lib.PATTERNS.items():
            for task_type in pattern.task_types:
                self._pattern_index.setdefault(task_type, []).append(name)

    def plan(self, classification: ClassificationResult,
             user_input: str = "") -> Plan:
        """Create an execution plan from task classification.

        v4.1: Adds reasoning, risk assessment, and verification hints.

        Args:
            classification: ClassificationResult from classifier.py
            user_input: Original user input (for context)

        Returns:
            Plan with concrete, actionable steps.
        """
        task_type = classification.task_type
        features = classification.detected_features
        languages = classification.detected_languages

        # ── v4.1 Smart complexity estimation ──
        complexity = 1
        if len(features) >= 3 or classification.is_confused:
            complexity = 3
        elif len(features) >= 2:
            complexity = 2

        # Apply confusion-aware planning: confused → fall through to LLM
        if classification.is_confused:
            logger.info(
                "Confused classification (%s vs %s, margin=%.3f) — "
                "using minimal safe plan",
                classification.task_type,
                classification.runner_up,
                classification.confusion_margin,
            )

        # ── 1. Try pattern-based planning ──
        matching = _patterns_lib.find_patterns(
            task_type=task_type,
            features=features,
            languages=languages,
            complexity=None,
        )

        if matching:
            pattern = matching[0]
            logger.debug("Pattern match: %s (score=best)", pattern.name)
            plan = self._plan_from_pattern(pattern)
            # v4.1: Add reasoning metadata
            plan = self._enrich_plan(plan, classification, user_input)
            return plan

        # ── 2. Try any pattern for this task type ──
        if task_type in self._pattern_index:
            pattern_names = self._pattern_index[task_type]
            for name in pattern_names:
                candidate = _patterns_lib.get_pattern(name)
                if candidate is None:
                    continue
                if candidate.complexity <= complexity:
                    logger.debug("Fallback pattern: %s", name)
                    plan = self._plan_from_pattern(candidate)
                    plan = self._enrich_plan(plan, classification, user_input)
                    return plan

        # ── 3. Keyword-based decomposition (still useful) ──
        plan = self._plan_from_keywords(classification, user_input)
        return self._enrich_plan(plan, classification, user_input)

    def _enrich_plan(self, plan: Plan, classification: ClassificationResult,
                     user_input: str) -> Plan:
        """v4.1: Add reasoning, risk scores, verification hints to each step."""
        risk_by_task = {
            "code_write": 0.4, "code_modify": 0.5, "complex": 0.7,
            "database": 0.3, "browser": 0.3, "system": 0.5,
            "research": 0.2, "code_read": 0.1, "code_review": 0.2,
            "file_ops": 0.3, "chat": 0.05, "reasoning": 0.15,
        }
        base_risk = risk_by_task.get(classification.task_type, 0.3)

        for i, step in enumerate(plan.steps):
            # Risk: base + complexity factors
            risk = base_risk
            if step.files_to_modify:
                risk += 0.1  # modifying existing code is riskier
            if step.files_to_create and not step.files_to_modify:
                risk -= 0.05  # creating new files is safer
            if "bash" in step.tools:
                risk += 0.05  # shell commands can fail
            if i == 0:
                risk -= 0.05  # first step is usually safe
            step.risk_score = round(min(1.0, max(0.05, risk)), 2)

            # Verification hints
            if "write" in step.tools or step.files_to_create:
                step.verification_hint = "Check file was created with correct content"
            elif "edit" in step.tools:
                step.verification_hint = "Verify edit was applied correctly"
            elif "bash" in step.tools:
                step.verification_hint = "Check exit code and output for errors"
            elif "read" in step.tools:
                step.verification_hint = "Confirm expected content was found"

            # Reasoning
            if i == 0:
                step.reasoning = f"First step: establish foundation for {classification.task_type}"
            elif i == len(plan.steps) - 1:
                step.reasoning = "Final step: verify and deliver results"
            else:
                step.reasoning = "Intermediate step building toward completion"

            # Alternatives for high-risk steps
            if step.risk_score >= 0.6:
                safe_tools = [t for t in step.tools if t != "bash"]
                if safe_tools and safe_tools != step.tools:
                    step.alternatives = [
                        f"Use {'/'.join(safe_tools)} instead of bash to reduce risk"
                    ]

        return plan

    def _plan_from_pattern(self, pattern: _patterns_lib.SoftwarePattern) -> Plan:
        """Convert a software pattern into an execution plan."""
        steps = []
        for i, pstep in enumerate(pattern.steps):
            step = PlanStep(
                step_id=i + 1,
                description=pstep.description,
                tools=list(pstep.tools),
                files_to_create=list(pstep.files_to_create),
                files_to_modify=list(pstep.files_to_modify),
                depends_on=[i] if i > 0 else [],
                expected_output="",
            )
            # If previous step created files that this step modifies,
            # note that dependency
            if i > 0 and pstep.files_to_modify:
                prev = pattern.steps[i - 1]
                overlap = set(pstep.files_to_modify) & set(prev.files_to_create)
                if overlap:
                    step.depends_on.append(i)

            steps.append(step)

        return Plan(
            steps=steps,
            pattern_name=pattern.name,
            estimated_time=pattern.estimated_time,
        )

    def _plan_from_keywords(self, classification: ClassificationResult,
                            user_input: str) -> Plan:
        """Keyword/rule-based decomposition when no pattern matches."""
        task_type = classification.task_type
        features = classification.detected_features
        steps: list[PlanStep] = []

        if task_type == "code_write":
            steps = self._decompose_code_write(features)
        elif task_type == "code_modify":
            steps = self._decompose_code_modify(features)
        elif task_type == "code_review":
            steps = self._decompose_code_review()
        elif task_type == "research":
            steps = self._decompose_research()
        elif task_type == "database":
            steps = self._decompose_database()
        elif task_type == "browser":
            steps = self._decompose_browser()
        elif task_type == "system":
            steps = self._decompose_system()
        elif task_type == "file_ops":
            steps = self._decompose_file_ops()
        elif task_type == "code_read":
            steps = self._decompose_code_read()
        elif task_type == "complex":
            steps = self._decompose_complex(features)
        else:
            steps = self._minimal_steps(task_type, user_input)

        return Plan(steps=steps, is_minimal=(len(steps) <= 1))

    # ── Decomposers ──────────────────────────────────────────────────

    def _decompose_code_write(self, features: list[str]) -> list[PlanStep]:
        steps = []
        has_api = "api" in features
        has_db = "database" in features
        has_web = "web" in features

        n = 1
        steps.append(PlanStep(n, "Set up project structure and dependencies",
                               tools=["write", "bash"],
                               files_to_create=["pyproject.toml", "README.md"]))
        n += 1

        if has_db:
            steps.append(PlanStep(n, "Create database models and schema",
                                   tools=["write"],
                                   files_to_create=["models.py"]))
            n += 1

        if has_api:
            steps.append(PlanStep(n, "Implement API routes and handlers",
                                   tools=["write"],
                                   files_to_create=["routes.py"],
                                   depends_on=[n - 1] if has_db else [1]))
            n += 1
        elif not has_web:
            steps.append(PlanStep(n, "Implement core logic",
                                   tools=["write"],
                                   files_to_create=["main.py"],
                                   depends_on=[1]))
            n += 1

        if has_web:
            steps.append(PlanStep(n, "Build frontend UI with HTML/CSS/JS",
                                   tools=["write"],
                                   files_to_create=["index.html", "style.css", "app.js"],
                                   depends_on=[1]))
            n += 1

        steps.append(PlanStep(n, "Add tests for all components",
                               tools=["write", "bash"],
                               files_to_create=["test_main.py"],
                               depends_on=[n - 1]))
        return steps

    def _decompose_code_modify(self, features: list[str]) -> list[PlanStep]:
        return [
            PlanStep(1, "Read and understand the current code",
                     tools=["read", "grep"]),
            PlanStep(2, "Apply changes with precise edits",
                     tools=["edit", "write"],
                     depends_on=[1]),
            PlanStep(3, "Verify changes with tests or validation",
                     tools=["bash"],
                     depends_on=[2]),
        ]

    def _decompose_code_review(self) -> list[PlanStep]:
        return [
            PlanStep(1, "Read the code to review thoroughly",
                     tools=["read", "glob"]),
            PlanStep(2, "Identify issues: bugs, style, performance, security",
                     tools=["grep"]),
            PlanStep(3, "Generate review with actionable recommendations",
                     tools=[]),
        ]

    def _decompose_research(self) -> list[PlanStep]:
        return [
            PlanStep(1, "Search and gather information",
                     tools=["web_fetch", "glob", "grep"]),
            PlanStep(2, "Analyze and synthesize findings",
                     tools=["read"]),
            PlanStep(3, "Generate research report with citations",
                     tools=[]),
        ]

    def _decompose_database(self) -> list[PlanStep]:
        return [
            PlanStep(1, "Analyze the database requirement",
                     tools=[]),
            PlanStep(2, "Write or execute the database query/migration",
                     tools=["bash", "write"]),
            PlanStep(3, "Validate the result",
                     tools=["bash"]),
        ]

    def _decompose_browser(self) -> list[PlanStep]:
        return [
            PlanStep(1, "Navigate to the target page",
                     tools=["mcp__playwright"]),
            PlanStep(2, "Interact with the page (click, fill, screenshot)",
                     tools=["mcp__playwright"]),
            PlanStep(3, "Extract and return results",
                     tools=[]),
        ]

    def _decompose_system(self) -> list[PlanStep]:
        return [
            PlanStep(1, "Run diagnostic/system commands",
                     tools=["bash"]),
            PlanStep(2, "Analyze command output",
                     tools=[]),
            PlanStep(3, "Take action or report findings",
                     tools=["bash", "write"]),
        ]

    def _decompose_file_ops(self) -> list[PlanStep]:
        return [
            PlanStep(1, "Find target files",
                     tools=["glob", "grep"]),
            PlanStep(2, "Perform file operations",
                     tools=["bash", "write", "edit"]),
        ]

    def _decompose_code_read(self) -> list[PlanStep]:
        return [
            PlanStep(1, "Locate relevant files and code sections",
                     tools=["glob", "grep"]),
            PlanStep(2, "Read and analyze the code",
                     tools=["read"]),
            PlanStep(3, "Provide explanation or answer",
                     tools=[]),
        ]

    def _decompose_complex(self, features: list[str]) -> list[PlanStep]:
        """Complex task decomposition with feature-aware steps."""
        steps = [PlanStep(1, "Analyze requirements and create project plan",
                          tools=["glob", "read"])]
        n = 2
        if "database" in features:
            steps.append(PlanStep(n, "Design and create database schema",
                                   tools=["write", "bash"],
                                   depends_on=[1]))
            n += 1
        if "api" in features:
            steps.append(PlanStep(n, "Build API layer with routes and controllers",
                                   tools=["write"],
                                   depends_on=[n - 1] if "database" in features else [1]))
            n += 1
        if "web" in features:
            steps.append(PlanStep(n, "Build frontend interface",
                                   tools=["write"],
                                   depends_on=[1]))
            n += 1
        if "cli" in features:
            steps.append(PlanStep(n, "Build CLI interface",
                                   tools=["write"],
                                   depends_on=[1]))
            n += 1
        if "testing" in features or "ci" in features:
            steps.append(PlanStep(n, "Add tests and CI configuration",
                                   tools=["write", "bash"],
                                   depends_on=[n - 1]))
            n += 1
        steps.append(PlanStep(n, "Integrate all components and finalize",
                               tools=["bash", "write"],
                               depends_on=[n - 1]))
        return steps

    def _minimal_steps(self, task_type: str, user_input: str = "") -> list[PlanStep]:
        """Absolute fallback — single step with best-guess tool hints."""
        tool_hints = {
            "chat": [],
            "unknown": [],
            "reasoning": [],
        }.get(task_type, ["read", "bash"])

        return [PlanStep(
            step_id=1,
            description=f"Handle {task_type} request{f': {user_input[:80]}' if user_input else ''}",
            tools=tool_hints,
        )]


# Module-level singleton
_planner: PatternAwarePlanner | None = None


def get_planner() -> PatternAwarePlanner:
    """Get or create the pattern-aware planner."""
    global _planner
    if _planner is None:
        _planner = PatternAwarePlanner()
    return _planner


def create_plan(classification: ClassificationResult, user_input: str = "") -> Plan:
    """Create a plan from a classification result."""
    return get_planner().plan(classification, user_input)
