"""Tests for DelegationManager and SubAgent."""

from core.delegation import DelegationManager, SubAgentStatus, SubAgent


class _MockProvider:
    """Mock provider that returns a simple response."""
    def chat(self, messages, tool_defs, temperature=0.7):
        return ("Hello from mock!", [])

mock_provider = _MockProvider()

def test_delegation_run_and_status():
    mgr = DelegationManager()
    task_id = mgr.run("say hello", provider=mock_provider)
    assert task_id is not None
    assert len(task_id) > 0

    result = mgr.wait(task_id, timeout=10)
    assert result is not None
    assert result.status == SubAgentStatus.DONE
    assert "Hello from mock" in result.summary


def test_delegation_list_agents():
    mgr = DelegationManager()
    mgr.run("task1", provider=mock_provider)
    mgr.run("task2", provider=mock_provider)
    agents = mgr.list_agents()
    assert len(agents) >= 2


def test_delegation_status_not_found():
    mgr = DelegationManager()
    assert mgr.status("nonexistent") is None


def test_delegation_active_count():
    mgr = DelegationManager()
    mgr.run("task1", provider=mock_provider)
    mgr.run("task2", provider=mock_provider)
    agents = mgr.list_agents()
    assert len(agents) >= 2


def test_subagent_initial_state():
    agent = SubAgent(task="test", task_id="test_001", provider=None, tool_defs=[])
    assert agent.task_id == "test_001"
    assert agent.task == "test"
    assert agent.status == SubAgentStatus.PENDING
    assert agent.is_done is False


def test_delegation_run_parallel():
    mgr = DelegationManager()
    results = mgr.run_parallel(["task a", "task b"], provider=mock_provider)
    assert len(results) == 2
