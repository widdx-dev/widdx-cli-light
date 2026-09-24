"""Task Planner — Execution Decomposition Layer.

Decomposes classified tasks into structured, ordered,
dependency-aware execution plans.

Pure logic. Zero LLM. Zero MCP. Zero external dependencies.
Rule-based decomposition only (Phase 1).

Usage:
    planner = TaskPlanner()
    plan = planner.plan(classification, user_input)
    if plan.is_minimal:
        # Simple 1-step task
    else:
        # Full decomposition with dependency graph
"""

import logging

from .contract import (
    TaskType, TaskStep, Plan, DecisionStep,
    ClassificationResult,
)

logger = logging.getLogger("widdx.uil.planner")


# -------------------------------------------------------------------
# Step Factories — each produces a list of TaskStep for a specific TaskType
# -------------------------------------------------------------------

def _complex_steps(classification: ClassificationResult) -> list[TaskStep]:
    """Decompose a complex project request into ordered steps.

    Uses classification.detected_features (populated by analyzer)
    instead of re-scanning the raw input text.
    """
    features = classification.detected_features
    has_web = features.get("web", False)
    has_api = features.get("api", False)
    has_db = features.get("database", False)
    has_cli = features.get("cli", False)

    steps: list[TaskStep] = []

    # Step 1: always project setup
    steps.append(TaskStep(
        id="step-1",
        description="create project structure and initialize dependencies",
        dependencies=[],
        tool_hints=["bash", "write"],
        estimated_difficulty=0.3,
    ))

    # Step 2: backend / core logic
    if has_api:
        steps.append(TaskStep(
            id="step-2",
            description="implement backend API and core logic",
            dependencies=["step-1"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.7,
        ))
    elif has_cli:
        steps.append(TaskStep(
            id="step-2",
            description="implement core CLI logic and argument parsing",
            dependencies=["step-1"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.6,
        ))
    else:
        steps.append(TaskStep(
            id="step-2",
            description="implement core application logic",
            dependencies=["step-1"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.6,
        ))

    # Step 3: database (if applicable)
    if has_db:
        steps.append(TaskStep(
            id="step-3",
            description="create database schema and data layer",
            dependencies=["step-1"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.5,
        ))
        db_step_id = "step-3"
        next_step = 4
    else:
        db_step_id = None
        next_step = 3

    # Step 4 (or 3): frontend (if applicable)
    if has_web:
        steps.append(TaskStep(
            id=f"step-{next_step}",
            description="build frontend UI components",
            dependencies=["step-1"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.6,
        ))
        frontend_dep = f"step-{next_step}"
        next_step += 1
    else:
        frontend_dep = None

    # Integration step
    integration_deps = ["step-2"]
    if db_step_id:
        integration_deps.append(db_step_id)
    if frontend_dep:
        integration_deps.append(frontend_dep)

    steps.append(TaskStep(
        id=f"step-{next_step}",
        description="connect components and verify integration",
        dependencies=integration_deps,
        tool_hints=["bash", "write"],
        estimated_difficulty=0.5,
    ))
    next_step += 1

    # Testing step
    steps.append(TaskStep(
        id=f"step-{next_step}",
        description="test the full application and fix issues",
        dependencies=[f"step-{next_step - 1}"],
        tool_hints=["bash"],
        estimated_difficulty=0.4,
    ))

    return steps


def _code_write_steps(classification: ClassificationResult) -> list[TaskStep]:
    """Decompose a code-write request into ordered steps.

    Receives ClassificationResult with detected_features from the analyzer,
    allowing feature-aware step generation (future use).
    """
    features = classification.detected_features
    has_tests = features.get("testing", False)
    steps = [
        TaskStep(id="step-1", description="create new file(s) with skeleton structure",
                 dependencies=[], tool_hints=["write"], estimated_difficulty=0.2),
        TaskStep(id="step-2", description="implement the full logic and functionality",
                 dependencies=["step-1"], tool_hints=["write"], estimated_difficulty=0.7),
    ]
    if has_tests:
        steps.append(TaskStep(id="step-3", description="write tests and verify correctness",
                              dependencies=["step-2"], tool_hints=["bash", "write"],
                              estimated_difficulty=0.4))
    return steps


def _code_write_tdd_steps(classification: ClassificationResult) -> list[TaskStep]:
    """TDD-first decomposition: tests BEFORE implementation.

    Small models benefit from writing tests first because tests:
      1. Define the contract precisely (reducing ambiguity)
      2. Provide immediate pass/fail feedback
      3. Prevent hallucinated features not in the spec
    """
    return [
        TaskStep(
            id="step-1",
            description="write failing tests first — define expected behavior and edge cases",
            dependencies=[],
            tool_hints=["write"],
            estimated_difficulty=0.4,
        ),
        TaskStep(
            id="step-2",
            description="implement minimal code to pass the tests — no extra features",
            dependencies=["step-1"],
            tool_hints=["write"],
            estimated_difficulty=0.6,
        ),
        TaskStep(
            id="step-3",
            description="run tests with verifier — all must pass before proceeding",
            dependencies=["step-2"],
            tool_hints=["bash"],
            estimated_difficulty=0.3,
        ),
    ]


def _code_modify_steps(classification: ClassificationResult) -> list[TaskStep]:
    """Decompose a code-modify request into ordered steps."""
    return [
        TaskStep(id="step-1", description="read and understand the existing code",
                 dependencies=[], tool_hints=["read"], estimated_difficulty=0.3),
        TaskStep(id="step-2", description="analyze the issue and plan the change",
                 dependencies=["step-1"], tool_hints=[], estimated_difficulty=0.4),
        TaskStep(id="step-3", description="implement the modification",
                 dependencies=["step-1", "step-2"], tool_hints=["write"],
                 estimated_difficulty=0.5),
        TaskStep(id="step-4", description="verify the change works correctly",
                 dependencies=["step-3"], tool_hints=["bash"], estimated_difficulty=0.3),
    ]


def _code_modify_tdd_steps(classification: ClassificationResult) -> list[TaskStep]:
    """TDD-first decomposition for modifications: update tests first."""
    return [
        TaskStep(
            id="step-1",
            description="read existing code and tests to understand current behavior",
            dependencies=[],
            tool_hints=["read"],
            estimated_difficulty=0.3,
        ),
        TaskStep(
            id="step-2",
            description="update or write new tests that reflect the desired change",
            dependencies=["step-1"],
            tool_hints=["write"],
            estimated_difficulty=0.4,
        ),
        TaskStep(
            id="step-3",
            description="implement the modification to make the updated tests pass",
            dependencies=["step-1", "step-2"],
            tool_hints=["write"],
            estimated_difficulty=0.5,
        ),
        TaskStep(
            id="step-4",
            description="run all tests with verifier — old + new must pass",
            dependencies=["step-3"],
            tool_hints=["bash"],
            estimated_difficulty=0.3,
        ),
    ]


def _complex_tdd_steps(classification: ClassificationResult) -> list[TaskStep]:
    """TDD-first decomposition for complex multi-file projects."""
    features = classification.detected_features
    has_web = features.get("web", False)
    has_api = features.get("api", False)
    has_db = features.get("database", False)
    has_cli = features.get("cli", False)

    steps: list[TaskStep] = []

    steps.append(TaskStep(
        id="step-1",
        description="create project structure and initialize dependencies",
        dependencies=[], tool_hints=["bash", "write"],
        estimated_difficulty=0.3,
    ))

    steps.append(TaskStep(
        id="step-2",
        description="write integration tests first — define all endpoints and expected responses",
        dependencies=["step-1"],
        tool_hints=["write"],
        estimated_difficulty=0.5,
    ))

    if has_api:
        steps.append(TaskStep(
            id="step-3",
            description="implement backend API to pass integration tests",
            dependencies=["step-1", "step-2"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.7,
        ))
    elif has_cli:
        steps.append(TaskStep(
            id="step-3",
            description="implement CLI logic to pass integration tests",
            dependencies=["step-1", "step-2"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.6,
        ))
    else:
        steps.append(TaskStep(
            id="step-3",
            description="implement core logic to pass integration tests",
            dependencies=["step-1", "step-2"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.6,
        ))

    next_step = 4
    if has_db:
        steps.append(TaskStep(
            id="step-4",
            description="implement database schema and data layer",
            dependencies=["step-1"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.5,
        ))
        next_step = 5

    if has_web:
        steps.append(TaskStep(
            id=f"step-{next_step}",
            description="build frontend UI components",
            dependencies=["step-1"],
            tool_hints=["bash", "write"],
            estimated_difficulty=0.6,
        ))
        next_step += 1

    steps.append(TaskStep(
        id=f"step-{next_step}",
        description="run all tests and verify end-to-end",
        dependencies=["step-2", "step-3"],
        tool_hints=["bash"],
        estimated_difficulty=0.4,
    ))

    return steps


# Map TaskType → decomposition factory
# All factories accept ClassificationResult (populated by analyzer)
_DECOMPOSERS = {
    TaskType.COMPLEX: _complex_steps,
    TaskType.CODE_WRITE: _code_write_steps,
    TaskType.CODE_MODIFY: _code_modify_steps,
}

# TDD variants — tests before implementation
_TDD_DECOMPOSERS = {
    TaskType.COMPLEX: _complex_tdd_steps,
    TaskType.CODE_WRITE: _code_write_tdd_steps,
    TaskType.CODE_MODIFY: _code_modify_tdd_steps,
}


def _minimal_steps(classification: ClassificationResult) -> list[TaskStep]:
    """Generate a single-step minimal plan for simple tasks."""
    desc = f"handle {classification.task_type.value} request"
    return [
        TaskStep(
            id="step-1",
            description=desc,
            dependencies=[],
            tool_hints=None,
            estimated_difficulty=classification.complexity,
        ),
    ]


# -------------------------------------------------------------------
# TaskPlanner
# -------------------------------------------------------------------

class TaskPlanner:
    """Rule-based execution planner.

    Decomposes classified tasks into structured step plans.
    Full decomposition for COMPLEX / CODE_WRITE / CODE_MODIFY.
    Minimal 1-step plan for all other task types.

    Supports TDD-first mode: tests are written BEFORE implementation,
    giving small models a precise contract to satisfy.

    Pure logic. No LLM. No MCP. No I/O.
    """

    def plan(self, classification: ClassificationResult,
             user_input: str,
             context: dict | None = None,
             use_tdd: bool = False) -> Plan:
        """Generate an execution plan from a classification result.

        Args:
            classification: Result of TaskAnalyzer.analyze().
            user_input: Raw user input text.
            context: Optional context (reserved for future use).
            use_tdd: When True, use TDD-first decomposition (tests before code).

        Returns:
            Plan with steps, dependencies, and decision trace.
        """
        task_type = classification.task_type
        steps: list[TaskStep]
        is_minimal: bool
        decision_steps: list[DecisionStep] = []

        # ── Architecture Intelligence Layer: generate + select architecture ──
        try:
            from core.architecture.generator import ArchitectureGenerator
            from core.architecture.scorer import ArchitectureScorer
            from core.architecture.compiler import ArchitectureCompiler
            gen = ArchitectureGenerator()
            scorer = ArchitectureScorer()
            compiler = ArchitectureCompiler()

            # Detect domain from user input
            domain = "web"
            if "api" in user_input.lower() or "rest" in user_input.lower():
                domain = "api"
            elif "cli" in user_input.lower() or "terminal" in user_input.lower():
                domain = "cli"

            architectures = gen.generate(goal=user_input, domain=domain)
            if architectures:
                best = scorer.select_best(architectures, goal=user_input, domain=domain)
                if best:
                    compiler.compile(best, goal=user_input)
                    decision_steps.append(DecisionStep(
                        component="ArchitectureLayer",
                        input_summary=f"generated {len(architectures)} candidates",
                        output=f"selected: {best.name} (score={scorer.score(best).get('total', 0):.2f})",
                        score=scorer.score(best).get("total", 0.5),
                        detail=f"Architecture: {best.components}, {best.communication}, {best.storage}",
                    ))
        except Exception as e:
            logger.debug("ArchitectureLayer unavailable: %s", e)

        # ── PreDecisionForce: actively constrain planning ──
        try:
            from core.learning.pre_decision_force import get_pre_decision_force
            pdf = get_pre_decision_force()
            constraints = pdf.get_planner_constraints(task_type.value)
            # Block deprecated patterns
            for avoided in constraints.get("avoided_patterns", [])[:3]:
                decision_steps.append(DecisionStep(
                    component="PreDecisionForce",
                    input_summary=f"avoided={avoided[:60]}",
                    output="BLOCKED",
                    score=0.0,
                    detail=f"PreDecisionForce blocked deprecated pattern: {avoided[:100]}",
                ))
            # Prefer proven patterns
            for pref in constraints.get("preferred_patterns", [])[:2]:
                decision_steps.append(DecisionStep(
                    component="PreDecisionForce",
                    input_summary=f"prefer={pref['name']}",
                    output=f"preferred (conf={pref['confidence']:.2f})",
                    score=pref['confidence'],
                    detail=f"PreDecisionForce prefers: {pref['solution'][:100]}",
                ))
        except Exception as e:
            logger.debug("PreDecisionForce unavailable: %s", e)

        # ── Learning: query proven planning patterns ──
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()
            patterns = store.search(category="planning", min_confidence=0.5, limit=2)
            if patterns:
                pattern = patterns[0]
                decision_steps.append(DecisionStep(
                    component="PatternLibrary",
                    input_summary="query=planning,conf>0.5",
                    output=f"found: {pattern.name} (conf={pattern.confidence:.2f}, used={pattern.usage_count}x)",
                    score=pattern.confidence,
                    detail=f"Pattern: {pattern.solution[:120]}",
                ))
        except Exception as e:
            logger.debug("PatternLibrary unavailable: %s", e)

        if use_tdd and task_type in _TDD_DECOMPOSERS:
            decomposer = _TDD_DECOMPOSERS[task_type]
            steps = decomposer(classification)
            is_minimal = False
            decision_steps.append(DecisionStep(
                component="TaskPlanner",
                input_summary=f"type={task_type.value}, tdd=True",
                output=f"tdd-decomposed: {len(steps)} step(s)",
                score=1.0,
                detail=f"TDD-first decomposition into {len(steps)} steps "
                       f"(tests before implementation)",
            ))
        elif task_type in _DECOMPOSERS:
            decomposer = _DECOMPOSERS[task_type]
            steps = decomposer(classification)
            is_minimal = False
            decision_steps.append(DecisionStep(
                component="TaskPlanner",
                input_summary=f"type={task_type.value}",
                output=f"decomposed: {len(steps)} step(s)",
                score=1.0,
                detail=f"Full decomposition into {len(steps)} steps "
                       f"with dependency graph",
            ))
        else:
            steps = _minimal_steps(classification)
            is_minimal = True
            decision_steps.append(DecisionStep(
                component="TaskPlanner",
                input_summary=f"type={task_type.value}",
                output="minimal: 1 step",
                score=1.0,
                detail=f"Minimal plan (simple task type: {task_type.value})",
            ))

        # Estimate overall complexity
        if steps:
            avg_diff = sum(s.estimated_difficulty for s in steps) / len(steps)
        else:
            avg_diff = 0.0

        # ── PreFailureSim: evaluate plan risk BEFORE returning ──
        try:
            from core.learning.pre_failure_sim import get_pre_failure_sim
            pfs = get_pre_failure_sim()
            step_descs = [s.description for s in steps]
            tool_hints = [h for s in steps if s.tool_hints for h in s.tool_hints]
            plan_risk = pfs.evaluate_plan(step_descs, task_type.value, tool_hints)
            decision_steps.append(DecisionStep(
                component="PreFailureSim",
                input_summary=f"evaluated plan with {len(steps)} steps",
                output=f"risk={plan_risk.risk_level} (score={plan_risk.risk_score:.2f})",
                score=1.0 - plan_risk.risk_score,
                detail=plan_risk.reasoning[:200],
            ))
            if plan_risk.should_avoid:
                strategy = pfs.shift_strategy(plan_risk)
                decision_steps.append(DecisionStep(
                    component="StrategyShifter",
                    input_summary=f"risk={plan_risk.risk_level}",
                    output=f"shift recommended: {strategy['shift']}",
                    score=0.5,
                    detail=strategy["recommendation"][:200],
                ))
                # Level 5: Creative Strategy Mode
                if pfs.needs_creative_mode(plan_risk):
                    creative_prompt = pfs.build_creative_prompt(
                        step_descs, task_type.value, plan_risk.matched_failures,
                    )
                    decision_steps.append(DecisionStep(
                        component="CreativeStrategyMode",
                        input_summary="ALL strategies exhausted",
                        output="triggering creative invention mode (Level 5)",
                        score=0.3,
                        detail=creative_prompt[:200],
                    ))
        except Exception as e:
            logger.debug("PreFailureSim unavailable: %s", e)

        return Plan(
            steps=steps,
            estimated_complexity=round(avg_diff, 2),
            is_minimal=is_minimal,
            decision_path=decision_steps,
        )
