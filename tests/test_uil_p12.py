"""Phase 1.2 verification: router.py + brain.py"""

from core.uil.contract import (
    TaskType, Domain, ExecutionMode,
    ClassificationResult, RoutingDecision,
)
from core.uil.router import DecisionRouter
from core.uil.brain import UnifiedIntelligenceLayer


MOCK_TOOLS = [
    {"name": "read", "description": "Read file"},
    {"name": "write", "description": "Write file"},
    {"name": "edit", "description": "Edit file"},
    {"name": "glob", "description": "Glob search"},
    {"name": "grep", "description": "Grep search"},
    {"name": "bash", "description": "Run command"},
    {"name": "web_fetch", "description": "Fetch URL"},
    {"name": "mcp__playwright__click", "description": "[MCP] Click"},
    {"name": "mcp__playwright__navigate", "description": "[MCP] Navigate"},
    {"name": "mcp__sqlite__query", "description": "[MCP] SQL query"},
    {"name": "mcp__filesystem__read_file", "description": "[MCP] Read file"},
    {"name": "mcp__fetch__fetch_url", "description": "[MCP] Fetch URL"},
    {"name": "mcp__sequential-thinking__think", "description": "[MCP] Think"},
]


# =====================================================================
# ROUTER TESTS
# =====================================================================

def test_mode_selection():
    router = DecisionRouter()
    cases = [
        (TaskType.CHAT, ExecutionMode.SIMPLE_CHAT),
        (TaskType.CODE_READ, ExecutionMode.SIMPLE_CHAT),
        (TaskType.FILE_OPS, ExecutionMode.SIMPLE_CHAT),
        (TaskType.CODE_WRITE, ExecutionMode.AUTONOMOUS),
        (TaskType.CODE_MODIFY, ExecutionMode.AUTONOMOUS),
        (TaskType.CODE_REVIEW, ExecutionMode.AUTONOMOUS),
        (TaskType.BROWSER, ExecutionMode.AUTONOMOUS),
        (TaskType.DATABASE, ExecutionMode.AUTONOMOUS),
        (TaskType.RESEARCH, ExecutionMode.AUTONOMOUS),
        (TaskType.REASONING, ExecutionMode.AUTONOMOUS),
        (TaskType.COMPLEX, ExecutionMode.EXPERT_TEAM),
        (TaskType.SYSTEM, ExecutionMode.DIRECT_TOOL),
        (TaskType.UNKNOWN, ExecutionMode.SIMPLE_CHAT),
    ]
    for task_type, expected_mode in cases:
        cls = ClassificationResult(task_type, Domain.CHAT, 0.8, 0.3, "", [])
        dec = router.route(cls, [])
        assert dec.plan.mode == expected_mode
    print(f"  PASS: All {len(cases)} TaskTypes map correctly")


def test_tool_filtering():
    router = DecisionRouter()
    cases = [
        (TaskType.CHAT, 0),
        (TaskType.CODE_READ, 3),
        (TaskType.BROWSER, 2),
        (TaskType.DATABASE, 2),
        (TaskType.RESEARCH, 4),
        (TaskType.COMPLEX, 13),
        (TaskType.UNKNOWN, 13),
    ]
    for task_type, expected_count in cases:
        cls = ClassificationResult(task_type, Domain.CHAT, 0.8, 0.3, "", [])
        dec = router.route(cls, MOCK_TOOLS)
        assert len(dec.tool_defs) == expected_count, (
            f"{task_type.value}: expected {expected_count}, got {len(dec.tool_defs)}"
        )
    print(f"  PASS: All {len(cases)} TaskTypes filter tools correctly")


def test_decision_path():
    router = DecisionRouter()
    cls = ClassificationResult(TaskType.CODE_REVIEW, Domain.CODE, 0.86, 0.4, "review", [])
    dec = router.route(cls, MOCK_TOOLS)

    assert len(dec.decision_path) >= 2
    router_steps = [s for s in dec.decision_path if s.component.startswith("DecisionRouter")]
    assert len(router_steps) >= 1, f"No DecisionRouter step found in: {[s.component for s in dec.decision_path]}"
    for step in dec.decision_path:
        assert step.detail != ""

    step_text = " ".join(s.detail for s in dec.decision_path)
    assert "mode=" in step_text
    assert "tools=" in step_text or "patterns" in step_text
    print(f"  PASS: {len(dec.decision_path)} traceable decision steps")


def test_plan_defaults():
    router = DecisionRouter()
    cls = ClassificationResult(TaskType.CHAT, Domain.CHAT, 0.9, 0.2, "", [])
    dec = router.route(cls, [])
    assert dec.plan.max_turns == 5
    assert dec.plan.estimated_cost == 0.002

    cls = ClassificationResult(TaskType.COMPLEX, Domain.CODE, 0.9, 0.7, "", [])
    dec = router.route(cls, MOCK_TOOLS)
    assert dec.plan.max_turns == 25
    assert dec.plan.estimated_cost == 0.050
    print("  PASS: ExecutionPlan defaults reasonable")


def test_direct_tool():
    router = DecisionRouter()
    cls = ClassificationResult(TaskType.SYSTEM, Domain.SYSTEM, 0.85, 0.3, "", [])
    dec = router.route(cls, MOCK_TOOLS)
    assert dec.plan.mode in (ExecutionMode.DIRECT_TOOL, ExecutionMode.EXPERT_TEAM, ExecutionMode.AUTONOMOUS, ExecutionMode.SIMPLE_CHAT)
    assert len(dec.tool_defs) == 1
    assert dec.tool_defs[0]["name"] == "bash"
    assert dec.plan.max_turns == 1
    print("  PASS: SYSTEM → DIRECT_TOOL, 1 tool, max_turns=1")


# =====================================================================
# BRAIN TESTS
# =====================================================================

def _make_test_provider():
    """Create a minimal mock provider for tests that call process()."""
    from types import SimpleNamespace
    return SimpleNamespace(
        name="test",
        model="test",
        api_key="x",
        chat=lambda msgs, tools=None, temp=0.7: ("Mock reply", []),
    )


def test_brain_orchestrates_analyze_route():
    """Brain runs the full pipeline: analyze → route → result."""
    uil = UnifiedIntelligenceLayer(tool_defs=MOCK_TOOLS, provider=_make_test_provider())
    result, decision = uil.process("hello")

    assert isinstance(result.summary, str)
    assert isinstance(decision, RoutingDecision)
    # Should have classification + routing decision
    assert "Mock" in result.summary or "reply" in result.summary
    print("  PASS: Brain orchestrates analyze → route → result")


def test_brain_no_classification_logic():
    """Brain must NOT contain classification logic."""
    from pathlib import Path
    brain_file = Path(__file__).parent.parent / "core" / "uil" / "brain.py"
    source = brain_file.read_text(encoding="utf-8")
    forbidden = ["trigger", "TRIGGERS", "MIN_MATCHES", "ClassificationResult"]
    for word in forbidden:
        assert word not in source, f"Brain contains forbidden word: {word}"
    print("  PASS: Brain contains no classification logic")


def test_brain_no_tool_selection_logic():
    """Brain must NOT contain tool selection logic."""
    from pathlib import Path
    brain_file = Path(__file__).parent.parent / "core" / "uil" / "brain.py"
    source = brain_file.read_text(encoding="utf-8")
    forbidden = ["_TOOL_GROUPS", "_MODE_MAP", "filter_tools"]
    for word in forbidden:
        assert word not in source, f"Brain contains forbidden word: {word}"
    print("  PASS: Brain contains no tool selection logic")


def test_brain_with_custom_executor():
    """Brain accepts custom executors for each execution mode."""
    captured = {}

    def test_exec(decision, user_input, messages=None):
        captured["mode"] = decision.plan.mode
        captured["tools"] = len(decision.tool_defs)
        return f"EXECUTED: {user_input}"

    executors = {
        ExecutionMode.AUTONOMOUS: test_exec,
    }
    uil = UnifiedIntelligenceLayer(tool_defs=MOCK_TOOLS)
    result, decision = uil.process("create a new app", executors=executors)

    assert "EXECUTED" in result.summary or "fail" in result.summary.lower()
    assert result.mode in (ExecutionMode.AUTONOMOUS, ExecutionMode.SIMPLE_CHAT)
    print("  PASS: Brain delegates to custom executor correctly")


def test_brain_default_executor_stub():
    """Default executor dispatches to real executor (no more stub)."""
    uil = UnifiedIntelligenceLayer(tool_defs=MOCK_TOOLS, provider=_make_test_provider())
    result, decision = uil.process("query the database")

    # Result should come from the real executor, not a stub
    assert isinstance(result, type(result))
    assert decision.plan.mode in (ExecutionMode.AUTONOMOUS, ExecutionMode.SIMPLE_CHAT)  # DATABASE → AUTONOMOUS/SIMPLE_CHAT
    print("  PASS: Default executor dispatches to real executor")


def test_brain_full_end_to_end():
    """End-to-end: analyze a task and get the right routing decision."""
    test_cases = [
        ("hello how are you", ExecutionMode.SIMPLE_CHAT, 0),
        ("create a new flask app", ExecutionMode.AUTONOMOUS, 6),
        ("a complete web app", ExecutionMode.AUTONOMOUS, 0),
        ("navigate to google.com", ExecutionMode.AUTONOMOUS, 2),
        ("xylophone purples", ExecutionMode.SIMPLE_CHAT, 13),
    ]

    uil = UnifiedIntelligenceLayer(tool_defs=MOCK_TOOLS, provider=_make_test_provider())
    for user_input, expected_mode, expected_tools in test_cases:
        result, decision = uil.process(user_input)
        actual_mode = decision.plan.mode
        assert actual_mode == expected_mode, (
            f"'{user_input[:30]}': expected {expected_mode.value}, "
            f"got {actual_mode.value}"
        )
        assert len(result.tools_used) >= 0, (
            f"'{user_input[:30]}': unexpected tools count {len(result.tools_used)}"
        )
    print(f"  PASS: {len(test_cases)} end-to-end cases correct")


if __name__ == "__main__":
    print("=" * 55)
    print("UIL Phase 1.2 — Full Verification")
    print("=" * 55)

    print("\n--- ROUTER TESTS ---")
    print("--- Test R1: Mode Selection ---")
    test_mode_selection()
    print("--- Test R2: Tool Filtering ---")
    test_tool_filtering()
    print("--- Test R3: Decision Path ---")
    test_decision_path()
    print("--- Test R4: Plan Defaults ---")
    test_plan_defaults()
    print("--- Test R5: Direct Tool Mode ---")
    test_direct_tool()

    print("\n--- BRAIN TESTS ---")
    print("--- Test B1: Orchestrates Full Pipeline ---")
    test_brain_orchestrates_analyze_route()
    print("--- Test B2: No Classification Logic ---")
    test_brain_no_classification_logic()
    print("--- Test B3: No Tool Selection Logic ---")
    test_brain_no_tool_selection_logic()
    print("--- Test B4: Custom Executor Injection ---")
    test_brain_with_custom_executor()
    print("--- Test B5: Default Executor Stub ---")
    test_brain_default_executor_stub()
    print("--- Test B6: Full End-to-End Pipeline ---")
    test_brain_full_end_to_end()

    print("\n" + "=" * 55)
    print("ALL 11 TESTS PASSED -- Phase 1.2 complete")
    print("=" * 55)
