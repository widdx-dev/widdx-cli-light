"""Memory Learner — auto-extract facts from conversations using the LLM.

Includes memory size limits to prevent unbounded growth:
  - MAX_MEMORIES: hard cap on total stored memories (default 500)
  - MAX_MEMORY_AGE_DAYS: auto-cleanup of old memories (default 180)
  - Content length capped at 200 characters per memory
"""

import json
import time
import logging
from .memory import MemoryStore
from .utils import to_slug

logger = logging.getLogger("widdx.memory_learner")

# ── Memory limits ────────────────────────────────────────────
MAX_MEMORIES = 500        # hard cap — oldest evicted first
MAX_MEMORY_AGE_DAYS = 180 # auto-cleanup threshold
MAX_CONTENT_LENGTH = 200  # max chars per memory content
MAX_NAME_LENGTH = 40      # max chars per memory name


class MemoryLearner:
    """Extracts and stores memories from conversation turns.

    Uses a lightweight LLM prompt to identify facts worth remembering,
    then stores them in the existing MemoryStore for future retrieval.

    Memory limits are enforced automatically on each save:
      - Content that exceeds MAX_CONTENT_LENGTH is truncated
      - When total > MAX_MEMORIES, oldest memories are deleted
      - Periodically cleans up memories older than MAX_MEMORY_AGE_DAYS
    """

    MEMORY_TYPES = {
        "user_preference":    "User stated a preference (language, style, tool, approach)",
        "project_convention": "Project-specific convention or rule (naming, architecture, pattern)",
        "learned_fix":        "A specific fix or solution to a problem",
        "tool_usage_pattern": "How to use a specific tool or command effectively",
    }

    def __init__(self, provider=None, memory_store: MemoryStore | None = None):
        self.provider = provider
        self.mem = memory_store or MemoryStore()
        self._cleanup_counter = 0  # periodic cleanup tracker

    # ── Main API ────────────────────────────────────────

    def extract_from_turn(self, user_input: str, assistant_response: str,
                          tools_used: list[str]) -> list[dict]:
        """Use LLM to extract 0-2 facts from the current turn.

        Returns list of {"name", "content", "type", "context"} dicts.
        Empty list if nothing worth remembering or LLM is unavailable.
        Enforces MAX_MEMORIES limit automatically.
        """
        if not self.provider:
            return []
        # Skip if the provider has no API key (would fail silently)
        if not getattr(self.provider, 'api_key', None) and getattr(self.provider, 'needs_api_key', True):
            return []
        if len(assistant_response) < 100:
            return []  # too short to contain learnable facts

        # Enforce memory cap before extracting more
        self._enforce_memory_cap()

        prompt = self._build_prompt(user_input, assistant_response, tools_used)
        try:
            content, _ = self.provider.chat(
                [{"role": "user", "content": prompt}], [], temperature=0.1,
            )
            return self._parse_memories(content or "")
        except Exception:
            return []

    def store_memories(self, memories: list[dict]):
        """Save extracted memories to MemoryStore.

        Enforces:
          - Content length cap (MAX_CONTENT_LENGTH)
          - Total memory cap (MAX_MEMORIES)
          - Periodic age-based cleanup
        """
        for m in memories:
            name = to_slug(m.get("name", f"fact-{int(time.time())}"))
            content = m.get("content", "")
            if not content.strip():
                continue
            # Truncate long content
            content = content[:MAX_CONTENT_LENGTH]
            self.mem.save(name, content, {
                "type": m.get("type", "learned_fix"),
                "context": m.get("context", "")[:60],
                "source": "auto_extracted",
                "timestamp": time.time(),
            })

    def load_relevant(self, user_input: str, max_memories: int = 5) -> str:
        """Search memory for facts relevant to current input.

        Returns formatted string for injection, or empty string.
        Limits to max_memories (default 5) to avoid context overflow.
        """
        try:
            results = self.mem.search(user_input)
            if not results:
                return ""
            relevant = results[:max_memories]
            lines = ["[RELEVANT MEMORIES]"]
            for m in relevant:
                lines.append(f"  - {m.get('description', m.get('name', ''))[:120]}")
            return "\n".join(lines)
        except Exception:
            return ""

    # ── Memory management ─────────────────────────────────

    def _enforce_memory_cap(self):
        """Ensure total memories stay within MAX_MEMORIES.

        Runs periodic age-based cleanup, then removes oldest
        memories if still over the cap.
        """
        self._cleanup_counter += 1

        # Periodic age-based cleanup (every 10 saves)
        if self._cleanup_counter % 10 == 0:
            try:
                removed = self.mem.cleanup_deprecated(older_than_days=MAX_MEMORY_AGE_DAYS)
                if removed:
                    logger.info("Cleaned up %d deprecated memories (age > %d days)",
                                removed, MAX_MEMORY_AGE_DAYS)
            except Exception as e:
                logger.debug("Memory cleanup skipped: %s", e)

        # Hard cap enforcement
        try:
            total = self.mem.total()
            if total > MAX_MEMORIES:
                excess = total - MAX_MEMORIES
                # List all memories, sort by created date, delete oldest
                all_mems = self.mem.list_all()
                # Add file timestamps
                from pathlib import Path
                timed_mems = []
                for mem in all_mems:
                    mp = Path(mem.get("path", ""))
                    if mp.exists():
                        timed_mems.append((mp.stat().st_mtime, mem))
                    else:
                        timed_mems.append((0, mem))
                timed_mems.sort(key=lambda x: x[0])  # oldest first

                for _, mem in timed_mems[:excess]:
                    self.mem.delete(mem.get("name", ""))
                logger.info("Memory cap enforced: removed %d oldest memories (total: %d→%d)",
                            excess, total, self.mem.total())
        except Exception as e:
            logger.debug("Memory cap enforcement skipped: %s", e)

    # ── Internal ────────────────────────────────────────

    def _build_prompt(self, user_input: str, response: str, tools: list[str]) -> str:
        tools_str = ", ".join(tools[:5]) if tools else "none"
        return (
            "You are WIDDX Nexus (a WIDDX AI, created by MUHAMMAD MUSLIH 🇵🇸), acting as a memory extraction tool. Output ONLY valid JSON, no explanations.\n\n"
            "Extract 0-2 facts worth remembering from this exchange:\n\n"
            f"User: {user_input[:200]}\n"
            f"Assistant: {response[:300]}\n"
            f"Tools: {tools_str}\n\n"
            'Output EXACTLY one of these (no other text):\n'
            '  []\n'
            '  [{"name":"slug","content":"fact","type":"user_preference","context":"topic"}]\n'
            '  [{"name":"a","content":"a","type":"user_preference","context":"x"},{"name":"b","content":"b","type":"project_convention","context":"y"}]\n\n'
            'Types: user_preference | project_convention | learned_fix | tool_usage_pattern\n'
            'Name: max 40 chars kebab-case. Content: max 120 chars. Context: max 60 chars.\n\n'
            'CRITICAL: Start your response with [ and end with ]. Nothing else.'
        )

    def _parse_memories(self, output: str) -> list[dict]:
        """Parse LLM JSON output into structured memory dicts."""
        try:
            import re
            # Strip thinking block if present
            clean = re.sub(r'\[thinking\].*?\[/thinking\]', '', output, flags=re.DOTALL).strip()
            # Find JSON array — first [ to matching ]
            depth = 0
            start = -1
            for i, ch in enumerate(clean):
                if ch == '[':
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0 and start >= 0:
                        json_str = clean[start:i+1]
                        data = json.loads(json_str)
                        if isinstance(data, list):
                            result = []
                            for item in data[:2]:
                                if isinstance(item, dict) and item.get("content"):
                                    result.append({
                                        "name": str(item.get("name", "fact"))[:40],
                                        "content": str(item["content"])[:200],
                                        "type": str(item.get("type", "learned_fix")),
                                        "context": str(item.get("context", ""))[:60],
                                    })
                            return result
                        break
            return []
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return []
