"""Self-Reflection Module — WIDDX reviews its own work and saves lessons learned."""
import logging


import time
from typing import Optional, List
from core.memory import MemoryStore
from core.utils import get_last_turn
logger = logging.getLogger("widdx.self_reflection")




def generate_reflection_prompt(user_input: str, assistant_response: str, tools_used: List[str]) -> str:
    """Build a prompt to let the AI reflect on its own work."""
    return f"""You are WIDDX Nexus (a WIDDX AI, created by MUHAMMAD MUSLIH 🇵🇸), reviewing your own work. Your task is to extract 1-2 key lessons or improvements you can use in the future.

USER'S REQUEST:
{user_input}

YOUR RESPONSE:
{assistant_response}

TOOLS USED:
{', '.join(tools_used) if tools_used else 'None'}

---

INSTRUCTIONS:
1. Identify what you did well in this interaction
2. Identify 1-2 things you could improve for next time
3. Extract concrete, actionable lessons you can remember
4. Keep each lesson short and specific

EXAMPLE LESSONS:
- "When asked to refactor code, always run `validate` tool after making changes"
- "When user mentions 'bugs', ask for more details about error messages first"
- "Prefer `glob` over `bash ls` for file searching for reliability"

RESPONSE FORMAT:
Return a list of 1-2 lessons, each as a single line of text. Do not include any explanations or extra text.
"""


def extract_lessons(provider, user_input: str, assistant_response: str, tools_used: List[str]) -> List[str]:
    """Extract lessons learned using the LLM."""
    prompt = generate_reflection_prompt(user_input, assistant_response, tools_used)
    try:
        response, _ = provider.chat([{"role": "user", "content": prompt}], [], temperature=0.3)
        if response:
            lessons = [line.strip() for line in response.strip().splitlines() if line.strip()]
            return lessons[:2]  # Limit to 2 lessons per turn
    except Exception:
        pass
    return []


def save_reflection_lessons(lessons: List[str], project_dir: Optional[str] = None) -> None:
    """Save reflection lessons to memory store."""
    if not lessons:
        return
    memory = MemoryStore(project_dir=project_dir)
    for idx, lesson in enumerate(lessons):
        memory.save(
            f"lesson-{int(time.time())}-{idx}",
            lesson,
            {
                "type": "self-reflection",
                "timestamp": time.time(),
            }
        )


def reflect_on_last_turn(provider, messages: List[dict], state: dict, project_dir: Optional[str] = None) -> None:
    """Orchestrate self-reflection on the last conversation turn."""
    turn = get_last_turn(messages)
    if not turn:
        return

    last_user = turn["user"]
    last_assistant = turn["assistant"]
    
    # Get tools used from state
    tools_used = list(state.get("tools_used", []))
    
    # Extract and save lessons
    lessons = extract_lessons(provider, last_user, last_assistant, tools_used)
    save_reflection_lessons(lessons, project_dir=project_dir)
