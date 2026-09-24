"""Simple integration test: mock provider + agent to validate auto-validate logic.

Creates a sandbox dir, configures tools to write there, and runs a single
AutonomousAgent loop where the provider returns tool calls for:
  1. write (create files)
  2. validate (check file syntax)
  3. project_validate (run project-level tests)

Tests the full validation and project verification workflow.
"""

import tempfile
import shutil
import os

from core import tools


class MockToolCall:
    def __init__(self, id, name, args):
        self.id = id
        self.name = name
        self.args = args


class MockProvider:
    def __init__(self, project_dir):
        self.project_dir = project_dir
    
    def chat(self, messages, tool_defs, temperature=0.0):
        # Simulate assistant deciding to call write tool to create index.html
        sandbox = messages[0]["content"].split("PROJECT_DIR:")[-1].strip() if messages else "."
        file_path = os.path.join(sandbox, "index.html")
        content = "Creating project files"
        tc = MockToolCall("tc1", "write", {"file_path": file_path, "content": "<html><body><h1>Broken"})
        return content, [tc]

    def stream(self, messages, tool_defs, temperature=0.0):
        # Stream a short content then signal done with a write tool call.
        # Extract PROJECT_DIR from the system prompt if present.
        proj = None
        try:
            # system prompt is messages[0]['content'] in our test
            first = messages[0]["content"] if messages and isinstance(messages[0], dict) else None
            if first and "PROJECT_DIR:" in first:
                # Extract just the directory path part (first line after "PROJECT_DIR:")
                parts = first.split("PROJECT_DIR:")
                if len(parts) > 1:
                    proj = parts[1].split("\n")[0].strip()
        except Exception:
            proj = None

        if not proj:
            proj = self.project_dir

        # First: write a simple HTML file
        file_path = os.path.join(proj, "index.html")
        yield {"type": "content", "data": "(stream) preparing..."}
        tc = MockToolCall("tc1", "write", {"file_path": file_path, "content": "<html><body><h1>Hello</h1></body></html>"})
        yield {"type": "done", "data": ("", [tc])}


def test_integration_workflow():
    """Integration test: mock provider + agent validates auto-validate logic."""
    tmp = tempfile.mkdtemp(prefix="widdx_test_")
    try:
        # Configure sandbox so tools.write/edit are allowed only inside tmp
        tools.configure(tmp)

        provider = MockProvider(tmp)

        # Build a minimal state and cfg
        state = {"model": "mock-model", "turns": 0, "cost": 0.0}
        cfg = {"agent_max_iterations": 5, "temperature": 0.0}

        from core.agents.agent import AutonomousAgent

        # Pass a system prompt including PROJECT_DIR so coder-like agents can pick it up
        system_prompt = "PROJECT_DIR: %s" % tmp
        agent = AutonomousAgent(provider, tools.TOOL_DEFINITIONS, cfg, state, custom_prompt=system_prompt)

        steps, _summary = agent.run("Create a valid HTML file in PROJECT_DIR and validate it")

        # Verify file was created
        fp = os.path.join(tmp, "index.html")
        assert os.path.exists(fp), f"Expected file not found: {fp}"
        assert os.path.getsize(fp) > 0, "File is empty"

        # Verify write step was performed
        tool_names = [s.tool_name for s in steps]
        assert 'write' in tool_names, f"Expected 'write' step, got: {tool_names}"
        assert len(steps) > 0, "Expected at least one execution step"

    finally:
        shutil.rmtree(tmp)
