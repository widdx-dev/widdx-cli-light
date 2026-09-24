"""Phase 1.4 — Planner Layer Tests.

Tests the TaskPlanner decomposition rules:
  - Full decomposition for COMPLEX, CODE_WRITE, CODE_MODIFY
  - Minimal 1-step plans for all other types
  - Dependency graph correctness
  - Traceability via DecisionStep
  - Brain integration (optional planner)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.uil import (
    TaskType, ClassificationResult,
    Domain, DecisionStep, TaskPlanner, UnifiedIntelligenceLayer, ExecutionMode,
)

# -------------------------------------------------------------------
# Helper: create a minimal ClassificationResult for a given TaskType
# -------------------------------------------------------------------

def _make_classification(task_type: TaskType,
                         confidence: float = 0.85,
                         complexity: float = 0.7,
                         features: dict | None = None) -> ClassificationResult:
    domain_map = {
        TaskType.COMPLEX: Domain.CODE,
        TaskType.CODE_WRITE: Domain.CODE,
        TaskType.CODE_MODIFY: Domain.CODE,
        TaskType.CODE_REVIEW: Domain.CODE,
        TaskType.CODE_READ: Domain.CODE,
        TaskType.RESEARCH: Domain.RESEARCH,
        TaskType.BROWSER: Domain.BROWSER,
        TaskType.DATABASE: Domain.DATABASE,
        TaskType.REASONING: Domain.REASONING,
        TaskType.CHAT: Domain.CHAT,
        TaskType.FILE_OPS: Domain.CHAT,
        TaskType.SYSTEM: Domain.SYSTEM,
        TaskType.UNKNOWN: Domain.CHAT,
    }
    return ClassificationResult(
        task_type=task_type,
        domain=domain_map.get(task_type, Domain.CHAT),
        confidence=confidence,
        complexity=complexity,
        reasoning=f"test: {task_type.value}",
        keywords=[],
        detected_features=features or {},
        decision_path=[DecisionStep("test", "input", task_type.value, 1.0, "")],
        is_fallback=False,
    )


# ===================================================================
# Full Decomposition Tests
# ===================================================================

def test_planner_complex():
    """COMPLEX produces 4-6 steps with dependencies."""
    planner = TaskPlanner()
    # Simulate what analyzer._detect_features() would produce for "build a web app with React and Flask"
    classification = _make_classification(TaskType.COMPLEX)
    classification.detected_features = {
        "web": True, "api": True, "database": False, "cli": False, "testing": False,
    }
    result = planner.plan(
        classification,
        "build a web app with React and Flask",
    )
    assert 4 <= len(result.steps) <= 6, f"Expected 4-6 steps, got {len(result.steps)}"
    assert not result.is_minimal
    # First step should have no dependencies
    assert result.steps[0].dependencies == []
    # Last step should have dependencies
    assert len(result.steps[-1].dependencies) > 0
    # Steps with dependencies reference earlier steps
    assert [s for s in result.steps if s.dependencies]


def test_planner_code_write():
    """CODE_WRITE produces 2 steps (+ testing if test keyword detected)."""
    planner = TaskPlanner()
    # Without testing feature → 2 steps
    result = planner.plan(
        _make_classification(TaskType.CODE_WRITE),
        "create a new Python script for data processing",
    )
    assert len(result.steps) == 2, f"Expected 2 steps without test, got {len(result.steps)}"
    assert not result.is_minimal
    assert "create" in result.steps[0].description.lower()
    assert "implement" in result.steps[1].description.lower()
    assert result.steps[1].dependencies == ["step-1"]

    # With detected testing feature → 3 steps
    cls = _make_classification(TaskType.CODE_WRITE, features={"testing": True})
    result2 = planner.plan(cls, "create a tool with tests")
    assert len(result2.steps) == 3, f"Expected 3 steps with test feature, got {len(result2.steps)}"
    assert result2.steps[2].dependencies == ["step-2"]


def test_planner_code_modify():
    """CODE_MODIFY produces 4 steps with read→analyze→modify→verify pattern."""
    planner = TaskPlanner()
    result = planner.plan(
        _make_classification(TaskType.CODE_MODIFY),
        "fix a bug in the authentication module",
    )
    assert len(result.steps) == 4, f"Expected 4 steps, got {len(result.steps)}"
    assert not result.is_minimal
    # Step order: read → analyze → modify → verify
    assert "read" in result.steps[0].description.lower()
    assert "modification" in result.steps[2].description.lower() or \
           "modif" in result.steps[2].description.lower()
    assert "verify" in result.steps[3].description.lower()


# ===================================================================
# Minimal Plan Tests (simple tasks → 1 step)
# ===================================================================

def test_planner_minimal_code_review():
    """CODE_REVIEW produces 1 step, is_minimal=True."""
    planner = TaskPlanner()
    result = planner.plan(
        _make_classification(TaskType.CODE_REVIEW),
        "review this code for best practices",
    )
    assert len(result.steps) == 1
    assert result.is_minimal


def test_planner_minimal_chat():
    """CHAT produces 1 step, is_minimal=True."""
    planner = TaskPlanner()
    result = planner.plan(
        _make_classification(TaskType.CHAT),
        "hello",
    )
    assert len(result.steps) == 1
    assert result.is_minimal
    assert "chat" in result.steps[0].description


def test_planner_minimal_research():
    """RESEARCH produces 1 step, is_minimal=True."""
    planner = TaskPlanner()
    result = planner.plan(
        _make_classification(TaskType.RESEARCH),
        "search for Python best practices",
    )
    assert len(result.steps) == 1
    assert result.is_minimal


def test_planner_minimal_browser():
    """BROWSER produces 1 step, is_minimal=True."""
    planner = TaskPlanner()
    result = planner.plan(
        _make_classification(TaskType.BROWSER),
        "navigate to example.com",
    )
    assert len(result.steps) == 1
    assert result.is_minimal


def test_planner_minimal_database():
    """DATABASE produces 1 step, is_minimal=True."""
    planner = TaskPlanner()
    result = planner.plan(
        _make_classification(TaskType.DATABASE),
        "query all users from the database",
    )
    assert len(result.steps) == 1
    assert result.is_minimal


def test_planner_minimal_file_ops():
    """FILE_OPS produces 1 step, is_minimal=True."""
    planner = TaskPlanner()
    result = planner.plan(
        _make_classification(TaskType.FILE_OPS),
        "copy all files to backup folder",
    )
    assert len(result.steps) == 1
    assert result.is_minimal
    assert "file" in result.steps[0].description or \
           "file_ops" in result.steps[0].description


def test_planner_minimal_unknown():
    """UNKNOWN produces 1 step, is_minimal=True."""
    planner = TaskPlanner()
    result = planner.plan(
        _make_classification(TaskType.UNKNOWN, confidence=0.3, complexity=0.3),
        "some random text",
    )
    assert len(result.steps) == 1
    assert result.is_minimal
    assert "unknown" in result.steps[0].description


# ===================================================================
# Traceability Tests
# ===================================================================

def test_planner_traceability():
    """Plan contains DecisionSteps with component='TaskPlanner'."""
    planner = TaskPlanner()
    # Test full decomposition trace
    complex_result = planner.plan(
        _make_classification(TaskType.COMPLEX),
        "build a web app",
    )
    assert len(complex_result.decision_path) >= 1
    assert any(
        step.component == "TaskPlanner" for step in complex_result.decision_path
    )
    assert any("decomposed" in step.output for step in complex_result.decision_path)

    # Test minimal plan trace
    chat_result = planner.plan(
        _make_classification(TaskType.CHAT),
        "hello",
    )
    assert any(
        step.component == "TaskPlanner" for step in chat_result.decision_path
    )
    assert any("minimal" in step.output for step in chat_result.decision_path)


# ===================================================================
# Brain Integration Tests
# ===================================================================

def test_planner_always_active():
    """brain always has a planner (Phase 2.1: dead-code removal)."""
    uil = UnifiedIntelligenceLayer()
    assert uil.planner is not None
    assert isinstance(uil.planner, TaskPlanner)

    def mock_exec(decision, inp, msgs):
        plan = getattr(getattr(decision, "plan", None), "decomposed", None)
        assert plan is not None  # always has a plan
        return f"steps={len(plan.steps)}, minimal={plan.is_minimal}"

    executors = {ExecutionMode.SIMPLE_CHAT: mock_exec}
    result, _ = uil.process("hi hello", executors=executors)
    assert "steps=" in result.summary


def test_planner_selective_in_brain():
    """COMPLEX triggers full plan; CHAT triggers minimal plan."""
    planner = TaskPlanner()
    uil = UnifiedIntelligenceLayer(planner=planner)

    def mock_exec(decision, inp, msgs):
        # Return info about the decomposed plan
        plan = decision.plan.decomposed
        assert plan is not None
        return f"steps={len(plan.steps)}, minimal={plan.is_minimal}"

    executors = {
        ExecutionMode.SIMPLE_CHAT: mock_exec,
        ExecutionMode.EXPERT_TEAM: mock_exec,
    }

    # Use input with NO explicit code/db keywords → features-only → COMPLEX → EXPERT_TEAM
    result_complex, decision_complex = uil.process(
        "a complete frontend application with user interface",
        executors=executors,
    )
    assert "minimal=False" in result_complex.summary or "steps=" in result_complex.summary

    # CHAT → minimal plan, 1 step
    result_chat, decision_chat = uil.process(
        "hello",
        executors=executors,
    )
    # Decision path should have TaskPlanner step
    planner_steps = [
        s for s in decision_chat.decision_path
        if s.component == "TaskPlanner"
    ]
    assert len(planner_steps) == 1
