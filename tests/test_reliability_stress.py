"""Stress tests simulating provider failures and agent state interruptions."""
import time
import os
import shutil
import tempfile
from core.provider_reliability import (
    ReliableProvider, RateLimitError
)
from core.providers.base import Provider, ToolCall
from core.task_state import get_task_state, TaskState
from core.agents.agent import AutonomousAgent, AgentStep

class MockProvider(Provider):
    def __init__(self, name, responses=None, fail_count=0, fail_with=None):
        super().__init__(name, "mock-model", "")
        self.responses = responses or ["Response"]
        self.fail_count = fail_count
        self.fail_with = fail_with or Exception("Simulated failure")
        self.attempts = 0

    def chat(self, messages, tool_defs, temperature=0.7):
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise self.fail_with
        resp = self.responses[min(self.attempts - 1, len(self.responses) - 1)]
        if isinstance(resp, tuple):
            return resp
        return resp, []

    def stream(self, messages, tool_defs, temperature=0.7):
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise self.fail_with
        resp = self.responses[min(self.attempts - 1, len(self.responses) - 1)]
        if isinstance(resp, tuple):
            content, calls = resp
        else:
            content, calls = resp, []
        if content:
            yield {"type": "content", "data": content}
        for c in calls:
            yield {"type": "tool_call", "data": {"name": c.name, "args": c.args}}
        yield {"type": "done", "data": (content, calls)}


class TestReliabilityStress:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.tmp_dir)
        
        # Reset Singleton TaskState to use temp path
        import core.task_state
        core.task_state._task_state = TaskState(project_dir=self.tmp_dir)

    def teardown_method(self):
        os.chdir(self.orig_dir)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        
        # Reset TaskState singleton to original
        import core.task_state
        core.task_state._task_state = None

    def test_failover_and_exponential_backoff(self):
        # Setup pool with failing primary and successful fallback
        rp = ReliableProvider()
        rp._base_delay = 0.01  # accelerate delay for testing
        rp._pool._providers = [
            {"provider": MockProvider("primary", fail_count=2, fail_with=RateLimitError("Rate limit")), "priority": 1, "name": "primary"},
            {"provider": MockProvider("backup", responses=["Fallback success"]), "priority": 2, "name": "backup"}
        ]
        
        res = rp.chat_with_retry([{"role": "user", "content": "hello"}])
        assert res.provider_used == "backup"
        assert res.attempts == 2  # 1 fail on primary, 1 success on backup
        assert res.recovered is True
        assert res.content == "Fallback success"

    def test_least_unhealthy_fallback(self):
        # If all are in cooldown, pick the least unhealthy provider
        rp = ReliableProvider()
        rp._max_retries = 2
        rp._base_delay = 0.01
        
        # Mark failures to put both in cooldown
        p1 = MockProvider("p1")
        p2 = MockProvider("p2")
        rp._pool._providers = [
            {"provider": p1, "priority": 1, "name": "p1"},
            {"provider": p2, "priority": 2, "name": "p2"}
        ]
        rp._pool.mark_failure("p1", "error")
        time.sleep(0.01)
        rp._pool.mark_failure("p2", "error")
        
        # Cooldown of p1 started earlier, so its cooldown_until should be smaller/equal to p2's.
        # It should select p1 as the least unhealthy
        best = rp._pool.get_provider()
        assert best is not None
        assert best.name == "p1"

    def test_agent_checkpoint_and_deterministic_resume(self):
        # Simulate a crash: AutonomousAgent runs a tool, then crashes/interrupts.
        # On resume, the idempotency guard must bypass executing that tool again!
        
        tc = ToolCall("write", {"file_path": "a.py", "content": "x = 1"})
        responses = [
            ("", [tc]), # turn 1: tool call
            ("Successfully wrote code" , []) # turn 2: final summary
        ]
        
        prov = MockProvider("prov", responses=responses)
        cfg = {"agent_max_iterations": 5}
        state = {"model": "mock", "cost": 0.0}
        
        ts = get_task_state()
        ts.set_goal("test task")
        
        # Create agent and run it with a mock that throws exception after the first tool call
        agent = AutonomousAgent(prov, [{"name": "write"}], cfg, state)
        
        # Mock _execute_tool to trace execution count
        exec_count = 0
        def dummy_execute(tool_call):
            nonlocal exec_count
            exec_count += 1
            return f"Executed {tool_call.name}"
        agent._execute_tool = dummy_execute
        agent._auto_validate_file = lambda x: "Success"
        
        messages = [
            {"role": "system", "content": agent._build_prompt()},
            {"role": "user", "content": "test task"}
        ]
        content, tool_calls = prov.chat(messages, [{"name": "write"}])
        
        messages.append({"role": "assistant", "content": content or None, "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "write", "arguments": '{"file_path": "a.py", "content": "x = 1"}'}}
        ]})
        result = dummy_execute(tc)
        step = AgentStep(1, "write", tc.args, result)
        agent.steps.append(step)
        
        messages.append({
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "write",
            "content": result,
        })
        
        ts.set_messages(messages)
        ts.set_agent_steps([s.to_dict() for s in agent.steps])
        
        assert exec_count == 1
        assert len(ts.get_agent_steps()) == 1
        
        # 2. Start a fresh Agent instance representing the resumed process
        agent_resumed = AutonomousAgent(prov, [{"name": "write"}], cfg, state)
        exec_count_resumed = 0
        def dummy_execute_resumed(tool_call):
            nonlocal exec_count_resumed
            exec_count_resumed += 1
            return f"Executed {tool_call.name}"
        agent_resumed._execute_tool = dummy_execute_resumed
        agent_resumed._auto_validate_file = lambda x: "Success"
        
        prov.attempts = 0 # reset provider attempts to start from beginning
        
        steps, summary = agent_resumed.run("test task")
        
        assert exec_count_resumed == 0
        assert len(steps) >= 1
        assert steps[0].tool_name == "write"
        assert steps[0].result == "Executed write"
        assert "wrote code" in summary or "Task completed" in summary or summary == "Successfully wrote code"
        assert ts.is_active() is False
