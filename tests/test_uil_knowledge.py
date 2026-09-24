"""Phase 2 — Knowledge Base Tests (Phase 1.5 stable, knowledge.py first).

Acceptance criteria:
  After 5 executions, the system can answer "What is the average
  execution time for CODE_WRITE tasks?"
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.uil.knowledge import KnowledgeBase, ExecutionRecord
from core.uil.router import DecisionRouter
from core.uil.contract import (
    TaskType, Domain, ExecutionMode,
    ClassificationResult, ExecutionResult, RoutingDecision,
    ExecutionPlan,
)
from core.uil.brain import UnifiedIntelligenceLayer


# =====================================================================
# K1 — Unit: direct record → get_similar → get_stats
# =====================================================================

def test_knowledge_record_and_query():
    """Record 3 records, get_similar returns them, get_stats computes."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        kb = KnowledgeBase(project_dir=tmpdir)

    rec1 = ExecutionRecord(
        task_type="code_write",
        execution_mode="autonomous",
        steps_planned=3, steps_completed=3,
        execution_time=2.5, success=True, timestamp=time.time(),
    )
    rec2 = ExecutionRecord(
        task_type="code_write",
        execution_mode="autonomous",
        steps_planned=3, steps_completed=2,
        execution_time=5.0, success=False, timestamp=time.time(),
        steps_failed=1,
    )
    rec3 = ExecutionRecord(
        task_type="chat",
        execution_mode="simple_chat",
        steps_planned=1, steps_completed=1,
        execution_time=0.5, success=True, timestamp=time.time(),
    )

    # Manual insert using record()
    for rec in [rec1, rec2, rec3]:
        cls = ClassificationResult(
            TaskType(rec.task_type), Domain.CHAT, 0.9, 0.3,
            "test", [], detected_features={},
        )
        res = ExecutionResult(
            success=rec.success, summary="test",
            mode=ExecutionMode(rec.execution_mode),
            steps_planned=rec.steps_planned,
            steps_completed=rec.steps_completed,
            steps_failed=rec.steps_failed,
            execution_time=rec.execution_time,
        )
        dec = RoutingDecision(
            classification=cls,
            plan=ExecutionPlan(
                mode=ExecutionMode(rec.execution_mode),
            ),
        )
        kb.record(classification=cls, result=res, decision=dec)

    assert kb.total_records == 3
    assert kb.task_types == ["code_write", "chat"]

    # get_similar
    code_records = kb.get_similar("code_write")
    assert len(code_records) == 2

    # get_stats — the acceptance criteria
    stats = kb.get_stats("code_write")
    assert stats["count"] == 2
    assert stats["avg_execution_time"] == 3.75  # (2.5 + 5.0) / 2
    assert stats["min_time"] == 2.5
    assert stats["max_time"] == 5.0
    assert stats["success_rate"] == 0.5
    assert stats["avg_steps_planned"] == 3.0
    assert stats["avg_steps_completed"] == 2.5

    # Empty case
    empty = kb.get_stats("browser")
    assert empty["count"] == 0
    assert empty["avg_execution_time"] is None


# =====================================================================
# K2 — Integration: brain auto-records via process()
# =====================================================================

def test_knowledge_brain_auto_records():
    """UIL process() automatically records execution to knowledge."""
    uil = UnifiedIntelligenceLayer()
    assert hasattr(uil, "knowledge")
    assert isinstance(uil.knowledge, KnowledgeBase)
    assert uil.knowledge.total_records == 0

    # Each process() call should auto-record
    uil.set_tool_defs([{"name": "bash"}])
    executors = {ExecutionMode.SIMPLE_CHAT: lambda d, i, m: "ok"}
    uil.process("hello", executors=executors)
    assert uil.knowledge.total_records == 1

    uil.process("how are you", executors=executors)
    assert uil.knowledge.total_records == 2


# =====================================================================
# K3 — Acceptance: 5 code_write executions, get avg time
# =====================================================================

def test_knowledge_five_executions_answer_avg_time():
    """After 5 executions of CODE_WRITE, get_stats gives avg time."""
    kb = KnowledgeBase()
    times = [1.2, 3.8, 2.1, 4.5, 0.9]
    expected_avg = round(sum(times) / len(times), 4)

    for t in times:
        cls = ClassificationResult(
            TaskType.CODE_WRITE, Domain.CODE, 0.85, 0.5,
            "write code", ["write"], detected_features={},
        )
        res = ExecutionResult(
            success=True, summary="done",
            mode=ExecutionMode.AUTONOMOUS,
            steps_planned=3, steps_completed=3,
            execution_time=t,
        )
        dec = RoutingDecision(
            classification=cls,
            plan=ExecutionPlan(mode=ExecutionMode.AUTONOMOUS),
        )
        kb.record(classification=cls, result=res, decision=dec)

    # ACCEPTANCE: "ما متوسط وقت تنفيذ مهام CODE_WRITE؟"
    stats = kb.get_stats("code_write")
    assert stats["count"] == 5
    assert stats["avg_execution_time"] == expected_avg, (
        f"Expected avg {expected_avg}, got {stats['avg_execution_time']}"
    )


# =====================================================================
# K4 — Unit: suggest_mode with < 3 records → None
# =====================================================================

def test_knowledge_suggest_insufficient_data():
    """suggest_mode returns None when fewer than 3 records."""
    kb = KnowledgeBase()
    # Record 1 execution (not enough)
    cls = ClassificationResult(
        TaskType.CODE_WRITE, Domain.CODE, 0.85, 0.5,
        "test", [], detected_features={},
    )
    res = ExecutionResult(
        success=False, summary="fail",
        mode=ExecutionMode.AUTONOMOUS,
        steps_planned=3, steps_completed=0,
        steps_failed=3, execution_time=10.0,
    )
    dec = RoutingDecision(
        classification=cls,
        plan=ExecutionPlan(mode=ExecutionMode.AUTONOMOUS),
    )
    kb.record(classification=cls, result=res, decision=dec)

    assert kb.get_stats("code_write")["count"] == 1
    # 1 record only (< 2) → insufficient data → None (Phase 2.3: min=2)
    assert kb.suggest_mode("code_write") is None

    # 2 records — still None
    cls2 = ClassificationResult(
        TaskType.CODE_WRITE, Domain.CODE, 0.85, 0.5,
        "test", [], detected_features={},
    )
    res2 = ExecutionResult(
        success=False, summary="fail",
        mode=ExecutionMode.AUTONOMOUS,
        steps_planned=3, steps_completed=0,
        steps_failed=3, execution_time=10.0,
    )
    kb.record(classification=cls2, result=res2, decision=dec)

    assert kb.get_stats("code_write")["count"] == 2
    # 2 failures out of 2 → success_rate=0 < 0.5 → escalate
    assert kb.suggest_mode("code_write") == ExecutionMode.EXPERT_TEAM


# =====================================================================
# K5 — Acceptance: 3 failed AUTONOMOUS → suggest_mode returns EXPERT_TEAM
# =====================================================================

def test_knowledge_suggest_expert_team_after_failures():
    """After 3 failed AUTONOMOUS execs, suggest_mode returns EXPERT_TEAM."""
    kb = KnowledgeBase()

    for _ in range(3):
        cls = ClassificationResult(
            TaskType.CODE_WRITE, Domain.CODE, 0.85, 0.5,
            "write code", ["write"], detected_features={},
        )
        res = ExecutionResult(
            success=False, summary="failed",
            mode=ExecutionMode.AUTONOMOUS,
            steps_planned=3, steps_completed=1,
            steps_failed=2, execution_time=15.0,
        )
        dec = RoutingDecision(
            classification=cls,
            plan=ExecutionPlan(mode=ExecutionMode.AUTONOMOUS),
        )
        kb.record(classification=cls, result=res, decision=dec)

    # Now count=3, success_rate=0.0 → should suggest EXPERT_TEAM
    stats = kb.get_stats("code_write")
    assert stats["count"] == 3
    assert stats["success_rate"] == 0.0

    suggestion = kb.suggest_mode("code_write")
    assert suggestion == ExecutionMode.EXPERT_TEAM, (
        f"Expected EXPERT_TEAM for 3 failures, got {suggestion}"
    )


# =====================================================================
# K6 — Unit: slow + incomplete → suggest_mode returns AUTONOMOUS
# =====================================================================

def test_knowledge_suggest_autonomous_for_slow():
    """When avg time > 30s and steps_completed < steps_planned, suggest AUTONOMOUS."""
    kb = KnowledgeBase()

    # 3 successful but slow + incomplete executions
    # Currently using EXPERT_TEAM mode; avg_time > 30
    for _ in range(3):
        cls = ClassificationResult(
            TaskType.COMPLEX, Domain.CODE, 0.9, 0.8,
            "complex task", [], detected_features={},
        )
        res = ExecutionResult(
            success=True, summary="done but slow",
            mode=ExecutionMode.EXPERT_TEAM,
            steps_planned=10, steps_completed=6,
            execution_time=35.0,
        )
        dec = RoutingDecision(
            classification=cls,
            plan=ExecutionPlan(mode=ExecutionMode.EXPERT_TEAM),
        )
        kb.record(classification=cls, result=res, decision=dec)

    stats = kb.get_stats("complex")
    assert stats["count"] == 3
    assert stats["avg_execution_time"] > 30.0
    assert stats["avg_steps_completed"] < stats["avg_steps_planned"]

    suggestion = kb.suggest_mode("complex")
    assert suggestion == ExecutionMode.AUTONOMOUS, (
        f"Expected AUTONOMOUS for slow+incomplete, got {suggestion}"
    )


# =====================================================================
# K7 — Integration: Router uses knowledge.suggest_mode for override
# =====================================================================

def test_router_knowledge_mode_override():
    """DecisionRouter overrides mode when knowledge suggests it."""
    kb = KnowledgeBase()

    # Record 3 FAILED AUTONOMOUS code_write executions
    for _ in range(3):
        cls = ClassificationResult(
            TaskType.CODE_WRITE, Domain.CODE, 0.85, 0.5,
            "write code", ["write"], detected_features={},
        )
        res = ExecutionResult(
            success=False, summary="failed",
            mode=ExecutionMode.AUTONOMOUS,
            steps_planned=3, steps_completed=0,
            steps_failed=3, execution_time=15.0,
        )
        dec = RoutingDecision(
            classification=cls,
            plan=ExecutionPlan(mode=ExecutionMode.AUTONOMOUS),
        )
        kb.record(classification=cls, result=res, decision=dec)

    # Router with knowledge → should override AUTONOMOUS → EXPERT_TEAM
    router = DecisionRouter()
    cls = ClassificationResult(
        TaskType.CODE_WRITE, Domain.CODE, 0.85, 0.5,
        "write code", ["write"], detected_features={},
    )
    decision = router.route(cls, [{"name": "bash"}], knowledge=kb)

    assert decision.plan.mode == ExecutionMode.EXPERT_TEAM, (
        f"Expected EXPERT_TEAM override, got {decision.plan.mode}"
    )

    # Decision path must contain the KnowledgeRouter step
    components = [s.component for s in decision.decision_path]
    assert "KnowledgeRouter" in components, (
        f"KnowledgeRouter not in decision_path: {components}"
    )


# =====================================================================
# K8 — Backward compatibility: knowledge=None = no change
# =====================================================================

def test_router_knowledge_backward_compat():
    """Router without knowledge behaves exactly as before."""
    router = DecisionRouter()
    cls = ClassificationResult(
        TaskType.CODE_WRITE, Domain.CODE, 0.85, 0.5,
        "write code", ["write"], detected_features={},
    )

    # Without knowledge (backward compat)
    decision_no_knowledge = router.route(cls, [{"name": "bash"}])

    # With knowledge=None (explicit)
    decision_explicit_none = router.route(
        cls, [{"name": "bash"}], knowledge=None,
    )

    assert decision_no_knowledge.plan.mode == ExecutionMode.AUTONOMOUS
    assert decision_explicit_none.plan.mode == ExecutionMode.AUTONOMOUS

    # No KnowledgeRouter component without knowledge
    components_explicit = [s.component for s in decision_explicit_none.decision_path]
    assert "KnowledgeRouter" not in components_explicit, (
        f"KnowledgeRouter should NOT appear without knowledge: {components_explicit}"
    )


# =====================================================================
# K9 — VERIFY feedback: repeated criticals → EXPERT_TEAM
# =====================================================================

def test_knowledge_suggest_expert_team_after_verify_failures():
    """Repeated verification critical failures escalate to EXPERT_TEAM."""
    kb = KnowledgeBase()

    for _ in range(3):
        cls = ClassificationResult(
            TaskType.CODE_WRITE, Domain.CODE, 0.85, 0.5,
            "write html", ["write"], detected_features={},
        )
        res = ExecutionResult(
            success=False, summary="verify failed",
            mode=ExecutionMode.AUTONOMOUS,
            steps_planned=2, steps_completed=2,
            execution_time=1.0,
        )
        from core.uil.contract import VerificationReport, VerificationFinding, VerificationSeverity
        res.verification = VerificationReport(
            findings=[
                VerificationFinding(
                    check_name="html_structure",
                    severity=VerificationSeverity.CRITICAL,
                    message="broken",
                    passed=False,
                )
            ],
            verifier_name="html",
        )
        dec = RoutingDecision(
            classification=cls,
            plan=ExecutionPlan(mode=ExecutionMode.AUTONOMOUS),
        )
        kb.record(classification=cls, result=res, decision=dec)

    stats = kb.get_stats("code_write")
    assert stats["verify_failure_rate"] == 1.0
    assert kb.suggest_mode("code_write") == ExecutionMode.EXPERT_TEAM


# =====================================================================
# K10 — Direct tool executor picks filtered tools
# =====================================================================

def test_direct_tool_executor_prefers_bash():
    from core.uil.executors import pick_direct_tool, run_direct_tool

    assert pick_direct_tool([{"name": "read"}, {"name": "bash"}]) == "bash"
    assert pick_direct_tool([{"name": "read"}]) == "read"
    assert pick_direct_tool([]) is None

    class FakeCtx:
        tool_defs = [{"name": "bash"}]

    result = run_direct_tool(FakeCtx(), "echo direct-tool-test")
    assert isinstance(result, str)
    assert result.strip()

    class EmptyCtx:
        tool_defs = []

    assert "No tools available" in run_direct_tool(EmptyCtx(), "test")


def _clean_knowledge_cache():
    """Remove cached knowledge.json to prevent state leakage between tests."""
    cache = Path(".widdx/knowledge.json")
    if cache.exists():
        cache.unlink()


if __name__ == "__main__":
    _clean_knowledge_cache()

    print("=" * 55)
    print("Phase 2 — Knowledge Base Tests")
    print("=" * 55)
    test_knowledge_record_and_query()
    print("  PASS: K1 — record, get_similar, get_stats")
    _clean_knowledge_cache()
    test_knowledge_brain_auto_records()
    print("  PASS: K2 — brain auto-record integration")
    _clean_knowledge_cache()
    test_knowledge_five_executions_answer_avg_time()
    print("  PASS: K3 — 5 CODE_WRITE execs → avg_time")
    _clean_knowledge_cache()
    test_knowledge_suggest_insufficient_data()
    print("  PASS: K4 — suggest_mode with <3 records → None")
    _clean_knowledge_cache()
    test_knowledge_suggest_expert_team_after_failures()
    print("  PASS: K5 — 3 failed AUTONOMOUS → EXPERT_TEAM")
    _clean_knowledge_cache()
    test_knowledge_suggest_autonomous_for_slow()
    print("  PASS: K6 — slow+incomplete → AUTONOMOUS")
    _clean_knowledge_cache()
    test_router_knowledge_mode_override()
    print("  PASS: K7 — Router overrides mode via knowledge")
    _clean_knowledge_cache()
    test_router_knowledge_backward_compat()
    print("  PASS: K8 — Router knowledge=None backward compat")
    _clean_knowledge_cache()
    test_knowledge_suggest_expert_team_after_verify_failures()
    print("  PASS: K9 — Verify failures → EXPERT_TEAM")
    _clean_knowledge_cache()
    test_direct_tool_executor_prefers_bash()
    print("  PASS: K10 — Direct tool prefers bash")
    print("\n" + "=" * 55)
    print("ALL 10 TESTS PASSED — Phase 2.1 complete")
    print("=" * 55)
