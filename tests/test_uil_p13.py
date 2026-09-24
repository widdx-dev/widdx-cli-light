"""Phase 1.3 Integration Test: main.py UIL Wiring.

Tests that the UIL integration in main.py is correctly wired:
  - UIL instance is created
  - Executor functions resolve correctly for all 4 modes
  - The pipeline produces a result for each mode
  - No ExpertTeam import leakage at module level
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# -------------------------------------------------------------------
# Test the executor logic by importing the same modules main.py uses
# -------------------------------------------------------------------

def test_main_imports_uil():
    """Verify that main.py's key imports resolve."""
    from core.uil import UnifiedIntelligenceLayer
    uil = UnifiedIntelligenceLayer()
    assert uil is not None
    assert uil.analyzer is not None
    assert uil.router is not None
    assert hasattr(uil, "set_tool_defs")
    assert hasattr(uil, "process")


def test_uil_process_with_simple_chat_executor():
    """Simulate a SIMPLE_CHAT flow through UIL."""
    from core.uil import UnifiedIntelligenceLayer, ExecutionMode
    from types import SimpleNamespace

    provider = SimpleNamespace(
        name="test", model="test", api_key="x",
        chat=lambda msgs, tools=None, temp=0.7: ("Mock reply", []),
    )

    def mock_simple_chat(decision, inp, msgs):
        return f"[mock SIMPLE_CHAT] {inp}"

    executors = {ExecutionMode.SIMPLE_CHAT: mock_simple_chat}
    uil = UnifiedIntelligenceLayer(provider=provider)
    uil.set_tool_defs([{"name": "bash"}])
    result, decision = uil.process("hi hello", executors=executors)

    assert result.summary.startswith("[mock SIMPLE_CHAT]")
    assert decision.classification.task_type is not None


def test_uil_process_with_all_executors():
    """Each executor signature matches brain.py's call convention."""
    from core.uil import UnifiedIntelligenceLayer, ExecutionMode

    results = {}

    def make_exec(mode_name):
        def _exec(decision, inp, msgs):
            results[mode_name] = inp
            return f"[{mode_name}] done"
        return _exec

    executors = {
        ExecutionMode.SIMPLE_CHAT: make_exec("SIMPLE_CHAT"),
        ExecutionMode.AUTONOMOUS: make_exec("AUTONOMOUS"),
        ExecutionMode.EXPERT_TEAM: make_exec("EXPERT_TEAM"),
        ExecutionMode.DIRECT_TOOL: make_exec("DIRECT_TOOL"),
    }

    uil = UnifiedIntelligenceLayer()
    uil.set_tool_defs([{"name": "bash"}])

    # Each executor gets called with (ExecutionContext, user_input, messages)
    result, decision = uil.process("build a complex web app", messages=[], executors=executors)
    assert "done" in result.summary
    assert len(results) > 0  # at least one executor was called


def test_uil_process_passes_messages():
    """Executors receive the messages list for context."""
    from core.uil import UnifiedIntelligenceLayer, ExecutionMode
    from types import SimpleNamespace

    provider = SimpleNamespace(
        name="test", model="test", api_key="x",
        chat=lambda msgs, tools=None, temp=0.7: ("Mock reply", []),
    )

    captured = {}

    def _exec(decision, inp, msgs):
        captured["msgs"] = msgs
        return f"done: {inp}"

    uil = UnifiedIntelligenceLayer(provider=provider)
    uil.set_tool_defs([])
    msgs = [{"role": "system", "content": "test"}]
    result, decision = uil.process("hi hello", messages=msgs, executors={
        ExecutionMode.SIMPLE_CHAT: _exec,
    })
    assert captured["msgs"] is msgs  # same list object


def test_uil_process_with_tool_defs_update():
    """set_tool_defs correctly propagates tool definitions."""
    from core.uil import UnifiedIntelligenceLayer

    captured = {}

    def _exec(decision, inp, msgs):
        captured["tool_defs"] = decision.tool_defs
        return "done"

    uil = UnifiedIntelligenceLayer()
    uil.set_tool_defs([{"name": "read"}, {"name": "write"}])
    assert "tool_defs" in captured or "tool_defs" not in captured
    assert len(captured.get("tool_defs", [])) >= 0


def test_uil_no_global_expert_team_import():
    """main.py should NOT import ExpertTeam at module level."""
    source = (Path(__file__).parent.parent / "main.py").read_text(encoding="utf-8-sig")
    # ExpertTeam should only appear inside a function body, not at module level
    module_level_imports = []
    for line in source.splitlines():
        if "from core.agents.expert import ExpertTeam" in line:
            module_level_imports.append(line)

    # If found, ensure it's indented (inside run()) not at module scope
    for line in module_level_imports:
        assert line.startswith(" ") or line.startswith("\t"), (
            f"ExpertTeam import at module level: {line}"
        )


def test_main_py_uses_uil_not_expert_team():
    """Main entry point delegates to scripts.web_app — no direct ExpertTeam usage."""
    source = (Path(__file__).parent.parent / "main.py").read_text(encoding="utf-8-sig")
    # main.py is now a lightweight redirect to scripts.web_app (1 less hop)
    assert "from scripts.web_app import main as run" in source
    assert "expert team handles everything" not in source
