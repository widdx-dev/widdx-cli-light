"""Tests for TDD-first planner additions in core/uil/planner.py."""

from __future__ import annotations


from core.uil.planner import (
    TaskPlanner,
    _code_write_tdd_steps,
    _code_modify_tdd_steps,
    _complex_tdd_steps,
)
from core.uil.contract import (
    TaskType, Domain, ClassificationResult,
    TaskStep,
)


def make_classification(
    task_type: TaskType = TaskType.CODE_WRITE,
    complexity: float = 0.5,
    features: dict | None = None,
) -> ClassificationResult:
    return ClassificationResult(
        task_type=task_type,
        domain=Domain.CODE,
        confidence=0.9,
        complexity=complexity,
        reasoning="test classification",
        detected_features=features or {},
    )


class TestTDDDecomposers:
    """TDD decomposers produce tests-before-code steps."""

    def test_code_write_tdd_has_three_steps(self):
        cl = make_classification(TaskType.CODE_WRITE)
        steps = _code_write_tdd_steps(cl)
        assert len(steps) == 3

    def test_code_write_tdd_first_step_is_tests(self):
        cl = make_classification(TaskType.CODE_WRITE)
        steps = _code_write_tdd_steps(cl)
        assert "test" in steps[0].description.lower()
        assert "implement" in steps[1].description.lower()
        assert "verifier" in steps[2].description.lower()

    def test_code_write_tdd_steps_have_correct_dependencies(self):
        cl = make_classification(TaskType.CODE_WRITE)
        steps = _code_write_tdd_steps(cl)
        assert steps[0].dependencies == []
        assert "step-1" in steps[1].dependencies
        assert "step-2" in steps[2].dependencies

    def test_code_modify_tdd_has_four_steps(self):
        cl = make_classification(TaskType.CODE_MODIFY)
        steps = _code_modify_tdd_steps(cl)
        assert len(steps) == 4

    def test_code_modify_tdd_reads_first(self):
        cl = make_classification(TaskType.CODE_MODIFY)
        steps = _code_modify_tdd_steps(cl)
        assert "read" in steps[0].description.lower()

    def test_complex_tdd_includes_integration_tests(self):
        cl = make_classification(
            TaskType.COMPLEX,
            features={"web": True, "api": True, "database": True},
        )
        steps = _complex_tdd_steps(cl)
        assert len(steps) >= 5
        descriptions = " ".join(s.description for s in steps)
        assert "test" in descriptions.lower()

    def test_complex_tdd_starts_with_project_structure(self):
        cl = make_classification(TaskType.COMPLEX)
        steps = _complex_tdd_steps(cl)
        assert "project" in steps[0].description.lower() or "structure" in steps[0].description.lower()

    def test_all_tdd_steps_are_taskstep_instances(self):
        cl = make_classification(TaskType.CODE_WRITE)
        for step in _code_write_tdd_steps(cl):
            assert isinstance(step, TaskStep)
            assert isinstance(step.id, str)
            assert isinstance(step.description, str)
            assert isinstance(step.dependencies, list)
            assert 0.0 <= step.estimated_difficulty <= 1.0


class TestTaskPlannerTDD:
    """TaskPlanner.plan() with use_tdd flag."""

    def test_normal_plan_minimal_for_chat(self):
        planner = TaskPlanner()
        cl = make_classification(TaskType.CHAT, complexity=0.1)
        plan = planner.plan(cl, "hello")
        assert plan.is_minimal is True

    def test_tdd_plan_decomposes_code_write(self):
        planner = TaskPlanner()
        cl = make_classification(TaskType.CODE_WRITE, complexity=0.5)
        plan = planner.plan(cl, "write a function", use_tdd=True)
        assert plan.is_minimal is False
        assert len(plan.steps) == 3

    def test_tdd_plan_has_test_first_step(self):
        planner = TaskPlanner()
        cl = make_classification(TaskType.CODE_WRITE, complexity=0.5)
        plan = planner.plan(cl, "write calculator", use_tdd=True)
        assert "test" in plan.steps[0].description.lower()

    def test_normal_plan_without_tdd_is_different(self):
        planner = TaskPlanner()
        cl = make_classification(TaskType.CODE_WRITE, complexity=0.5)
        tdd_plan = planner.plan(cl, "write calculator", use_tdd=True)
        normal_plan = planner.plan(cl, "write calculator", use_tdd=False)
        assert tdd_plan.steps[0].description != normal_plan.steps[0].description

    def test_tdd_decision_path_mentions_tdd(self):
        planner = TaskPlanner()
        cl = make_classification(TaskType.CODE_WRITE, complexity=0.5)
        plan = planner.plan(cl, "write app", use_tdd=True)
        path_text = " ".join(d.output for d in plan.decision_path)
        assert "TDD" in path_text or "tdd" in path_text

    def test_tdd_plan_has_valid_complexity(self):
        planner = TaskPlanner()
        cl = make_classification(TaskType.CODE_WRITE, complexity=0.7)
        plan = planner.plan(cl, "write complex app", use_tdd=True)
        assert 0.0 <= plan.estimated_complexity <= 1.0
