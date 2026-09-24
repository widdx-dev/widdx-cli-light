"""Tests for VerifyLoop."""
from core.verification.loop import VerifyLoop, LoopResult, get_verify_loop
from core.uil.contract import TaskType


def test_verify_loop_creates():
    loop = VerifyLoop(max_retries=3)
    assert loop._max_retries == 3


def test_verify_loop_result_dataclass():
    r = LoopResult(passed_all=True, iterations=1, total_time=0.5)
    assert r.passed_all is True
    assert r.iterations == 1


def test_get_verify_loop_singleton():
    a = get_verify_loop()
    b = get_verify_loop()
    assert a is b


def test_verify_loop_no_fixer_passes():
    """Without a fixer function, verify once and return."""
    from core.uil.contract import ExecutionResult
    loop = VerifyLoop(max_retries=1)
    class MockClassification:
        task_type = TaskType.CODE_WRITE
    output = ExecutionResult(success=True, summary="print('hello world')")
    result = loop.run(
        output=output,
        task_type=MockClassification(),
        fixer_fn=None,
    )
    assert isinstance(result, LoopResult)
    assert result.iterations >= 1
