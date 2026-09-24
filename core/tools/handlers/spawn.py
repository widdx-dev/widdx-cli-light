"""Agent spawning tool."""


def _handle_spawn_agent(task: str = "", role: str = "worker") -> str:
    try:
        from core.agents.agent import spawn_sub_agent
        result = spawn_sub_agent(task=task, role=role, depth=0)
        return (
            f"Sub-agent spawned: {result['agent_id']} ({result['role']})\n"
            f"Steps: {result['steps']}\n"
            f"Success: {result['success']}\n"
            f"Summary: {result['summary']}"
        )
    except Exception as e:
        return f"spawn_agent failed: {e}"
