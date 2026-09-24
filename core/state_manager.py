"""Global State Manager — Level 5.2.

Unifies all context sources (Memory, KG, Plan, ADR, TaskState)
into a single coherent view for the agent.

Metric: Agent gets unified context < 100ms instead of 5 separate sources.

Usage:
    from core.state_manager import StateManager
    sm = StateManager()
    context = sm.get_full_context("Build a REST API")
    progress = sm.get_progress()
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger("widdx.state_manager")


class StateManager:
    """Unified state: Memory + KG + Plan + ADR + TaskState."""

    def __init__(self, project_dir: str | Path | None = None):
        self._root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        self._last_build: float = 0.0
        self._cached_context: str = ""

    def get_full_context(self, goal: str = "", max_chars: int = 4000) -> str:
        """Build complete unified context for agent. Returns in < 100ms."""
        t0 = time.perf_counter()

        # Cache for 10 seconds to avoid rebuild on rapid calls
        if self._cached_context and (time.perf_counter() - self._last_build < 10):
            return self._cached_context[:max_chars]

        parts = []

        # 1. Goal
        if goal:
            parts.append(f"<goal>\n{goal}\n</goal>")

        # 2. TaskState (current progress)
        try:
            from core.task_state import get_task_state
            ts = get_task_state()
            ctx = ts.get_context_for_prompt()
            if ctx:
                parts.append(ctx)
        except Exception:
            logger.debug("Exception suppressed (line 53)")

        # 3. KnowledgeGraph (quick)
        try:
            from core.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            if not kg._built:
                kg.build()
            snippet = kg.get_context_snippet(max_items=10)
            if snippet:
                parts.append(snippet)
        except Exception:
            logger.debug("Exception suppressed (line 65)")

        # 4. Active memories
        try:
            from core.memory import MemoryStore
            mem = MemoryStore()
            active = mem.search_active(goal or "project")
            if active:
                lines = ["<active_memories>"]
                for m in active[:5]:
                    lines.append(
                        f"- [{m.get('type', 'fact')}] v{m.get('version', 1)} "
                        f"c={m.get('confidence', 0.5):.1f}: {m.get('description', '')}"
                    )
                lines.append("</active_memories>")
                parts.append("\n".join(lines))
        except Exception:
            logger.debug("Exception suppressed (line 82)")

        # 5. ADR
        try:
            from core.adr import adr_manager
            adr_ctx = adr_manager.get_context_for_prompt(max_adrs=5)
            if adr_ctx:
                parts.append(adr_ctx)
        except Exception:
            logger.debug("Exception suppressed (line 91)")

        # 6. Project docs
        try:
            from core.project_tracker import build_context_block
            ctx = build_context_block(self._root) or ""
            if ctx:
                parts.append(f"<project_docs>\n{ctx[:800]}\n</project_docs>")
        except Exception:
            logger.debug("Exception suppressed (line 100)")

        # 7. SelfImprove rules
        try:
            from core.self_improve import get_improver
            suggestions = get_improver().suggest_prompt_improvements()
            if suggestions:
                lines = ["<learned_rules>"]
                for s in suggestions[:5]:
                    lines.append(f"- {s}")
                lines.append("</learned_rules>")
                parts.append("\n".join(lines))
        except Exception:
            logger.debug("Exception suppressed (line 113)")

        self._cached_context = "\n\n".join(parts)
        self._last_build = time.perf_counter()
        elapsed = (self._last_build - t0) * 1000
        logger.debug("StateManager context built in %.1fms", elapsed)
        return self._cached_context[:max_chars]

    def get_progress(self) -> dict:
        """Return unified progress snapshot."""
        try:
            from core.task_state import get_task_state
            ts = get_task_state()
            progress = ts.get_progress()
            progress["kg_nodes"] = 0
            progress["active_memories"] = 0
            progress["adr_count"] = 0

            try:
                from core.knowledge_graph import get_knowledge_graph
                kg = get_knowledge_graph()
                if kg._built:
                    progress["kg_nodes"] = len(kg._nodes)
            except Exception:
                logger.debug("Exception suppressed (line 137)")

            try:
                from core.memory import MemoryStore
                progress["active_memories"] = MemoryStore().total()
            except Exception:
                logger.debug("Exception suppressed (line 143)")

            try:
                from core.adr import adr_manager
                progress["adr_count"] = len(adr_manager.list_all())
            except Exception:
                logger.debug("Exception suppressed (line 149)")

            return progress
        except Exception:
            return {"goal": "", "progress_pct": 0}


# Singleton
_state_manager: StateManager | None = None


def get_state_manager() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
