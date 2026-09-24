"""Unified Decision Layer — Level 5.5.

Integrates KG, Memory, Plan progress, and ADR constraints into a
single weighted decision. Prevents the agent from suggesting
rejected alternatives or ignoring project structure.

Metric: القرارات لا تتعارض مع ADR. Agent لا يقترح حلولاً مرفوضة.

Usage:
    from core.decision_layer import DecisionLayer
    dl = DecisionLayer()
    score = dl.evaluate("Use Redis for caching")
    if score.blocked:
        print(f"Blocked by ADR: {score.reason}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("widdx.decision_layer")


@dataclass
class DecisionScore:
    suggestion: str = ""
    score: float = 0.0  # 0.0-1.0, higher = better
    blocked: bool = False
    reason: str = ""
    components: dict = field(default_factory=dict)


class DecisionLayer:
    """Weighs all knowledge sources to evaluate a suggestion."""

    def evaluate(self, suggestion: str) -> DecisionScore:
        """Score a suggestion against all knowledge sources."""
        result = DecisionScore(suggestion=suggestion)

        # ── PreDecisionForce: 3-tier influence (not hard block) ──
        try:
            from core.learning.pre_decision_force import get_pre_decision_force
            influence = get_pre_decision_force().evaluate(suggestion)
            result.components["pre_decision"] = influence["weight"]
            if influence["level"] == "warn":
                result.score *= 0.5  # Reduce but don't block
                result.reason = influence["reason"]
        except Exception:
            logger.debug("Exception suppressed (line 49)")

        s = suggestion.lower()

        # ── 1. ADR check (block if rejected) ──────────
        try:
            from core.adr import adr_manager
            for adr in adr_manager.list_all():
                title = adr.get("title", "").lower()
                # Check if suggestion matches a rejected alternative
                adr_text = ""
                adr_file = adr.get("file", "")
                if adr_file:
                    from pathlib import Path
                    fp = Path.cwd() / ".widdx" / adr_file
                    if fp.exists():
                        adr_text = fp.read_text(encoding="utf-8").lower()

                # Block if suggestion was explicitly rejected
                if "rejected:" in adr_text:
                    rejected_section = adr_text.split("rejected:")[-1].split("\n\n")[0]
                    if any(word in rejected_section for word in s.split() if len(word) > 3):
                        result.blocked = True
                        result.reason = f"ADR: '{suggestion[:60]}' was rejected in {title}"
                        result.components["adr"] = 0.0
                        return result
                result.components["adr"] = 0.8  # No conflict
        except Exception:
            result.components["adr"] = 0.5  # Unknown

        # ── 2. Memory check ──────────────────────────
        try:
            from core.memory import MemoryStore
            mem = MemoryStore()
            active = mem.search_active(suggestion)
            if active:
                confidences = [m.get("confidence", 0.5) for m in active]
                result.components["memory"] = sum(confidences) / len(confidences)
            else:
                result.components["memory"] = 0.3  # No prior knowledge
        except Exception:
            result.components["memory"] = 0.5

        # ── 2.5. Pattern Library check (new) ────────────
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()
            patterns = store.search(query=suggestion, min_confidence=0.5, limit=5)
            if patterns:
                confidences = [p.confidence for p in patterns]
                result.components["patterns"] = sum(confidences) / len(confidences)
                # Block if a pattern explicitly contradicts this suggestion
                for p in patterns:
                    if p.status == "deprecated" and p.superseded_by:
                        _check = suggestion.lower()
                        if p.name.replace("-", " ") in _check or p.solution[:30].lower() in _check:
                            result.blocked = True
                            result.reason = f"Pattern '{p.name}' was deprecated in favor of '{p.superseded_by}'"
                            result.components["patterns"] = 0.0
                            return result
            else:
                result.components["patterns"] = 0.3
        except Exception:
            result.components["patterns"] = 0.5

        # ── 3. KnowledgeGraph check ────────────────────
        try:
            from core.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            if not kg._built:
                kg.build()
            results = kg.query(suggestion)
            if results:
                # More connections = more relevant
                max_conn = max((r.get("connections", 0) for r in results), default=0)
                result.components["kg"] = min(1.0, max_conn / 10)
            else:
                result.components["kg"] = 0.1  # Not found in project
        except Exception:
            result.components["kg"] = 0.5

        # ── 4. Plan progress check ─────────────────────
        try:
            from core.task_state import get_task_state
            ts = get_task_state()
            progress = ts.get_progress()
            if progress["progress_pct"] > 50:
                # Late in project — be conservative
                result.components["plan"] = 0.6
            else:
                result.components["plan"] = 0.8  # Early — more flexibility
        except Exception:
            result.components["plan"] = 0.5

        # ── 5. Weighted sum ────────────────────────────
        weights = {"adr": 0.25, "memory": 0.2, "patterns": 0.2, "kg": 0.2, "plan": 0.15}
        result.score = sum(
            result.components.get(k, 0.5) * w for k, w in weights.items()
        )
        result.score = round(min(1.0, max(0.0, result.score)), 2)

        return result

    def get_context_for_prompt(self) -> str:
        """Return decision guidance for system prompt."""
        try:
            from core.task_state import get_task_state
            from core.adr import adr_manager
            ts = get_task_state()
            progress = ts.get_progress()

            lines = ["<decision_guidance>"]
            if progress["progress_pct"] > 0:
                lines.append(f"Project is {progress['progress_pct']}% complete.")
            if progress["progress_pct"] > 70:
                lines.append("Late stage: prefer small, safe changes. No major refactors.")

            adrs = adr_manager.list_all()
            if adrs:
                lines.append(f"{len(adrs)} architecture decisions recorded. Check before suggesting new tech.")
            lines.append("</decision_guidance>")
            return "\n".join(lines)
        except Exception:
            return ""


# Singleton
_decision_layer: DecisionLayer | None = None


def get_decision_layer() -> DecisionLayer:
    global _decision_layer
    if _decision_layer is None:
        _decision_layer = DecisionLayer()
    return _decision_layer
