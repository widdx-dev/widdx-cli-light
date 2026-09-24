"""Pre-Decision Influence Engine — learning that influences (not dictates) decisions.

3-tier influence system:
  🟢 BOOST   (confidence > 0.7) → increase weight, prefer this pattern
  🟡 SUGGEST (confidence 0.4-0.7) → recommend but don't force
  🔴 WARN    (confidence < 0.3 or deprecated) → caution, reduce weight

Key principle: Learning INFLUENCES decision probability — never DECIDES instead of LLM.
The LLM remains free to choose, but with adjusted weights based on history.

Usage:
    from core.learning.pre_decision_force import PreDecisionForce
    pdf = PreDecisionForce()
    influence = pdf.evaluate('Use raw WebSocket')
    # → {"level": "warn", "weight": 0.15, "reason": "Deprecated: use Socket.io"}
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("widdx.pre_decision")


class PreDecisionForce:
    """Learning that actively constrains future decisions."""

    def __init__(self):
        self._blocked_patterns: set[str] = set()       # Never suggest these
        self._penalized_tools: dict[str, float] = {}    # tool → penalty multiplier
        self._preferred_patterns: dict[str, float] = {} # pattern → preference weight
        self._mode_success_rates: dict[str, dict] = {}  # task_type → {mode: success_rate}
        self._refresh()

    def _refresh(self):
        """Reload all constraints from PatternLibrary."""
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()

            # ── Block deprecated patterns ──
            all_patterns = store.local.list_all() + store.global_.list_all()
            for p in all_patterns:
                if p.status == "deprecated":
                    self._blocked_patterns.add(p.name)
                    self._blocked_patterns.add(p.solution[:60].lower())
                elif p.status == "active":
                    if p.confidence < 0.3:
                        self._penalized_tools[p.name] = p.confidence
                    elif p.confidence > 0.7:
                        self._preferred_patterns[p.name] = p.confidence

            logger.debug("PreDecisionForce refreshed: %d blocked, %d penalized, %d preferred",
                        len(self._blocked_patterns), len(self._penalized_tools),
                        len(self._preferred_patterns))
        except Exception as e:
            logger.debug("PreDecisionForce refresh failed: %s", e)

    # ── Planner Constraints ───────────────────────────────

    def get_planner_constraints(self, task_type: str = "") -> dict:
        """Return constraints that modify the Planner's step generation.

        The Planner SHOULD use these to prefer proven patterns and
        avoid deprecated/low-confidence approaches.
        """
        self._refresh()
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()

            constraints: dict[str, Any] = {
                "preferred_patterns": [],
                "avoided_patterns": list(self._blocked_patterns)[:10],
                "suggested_steps": [],
            }

            # Find high-confidence planning patterns for this task type
            planning_patterns = store.search(category="planning", min_confidence=0.6, limit=5)
            for p in planning_patterns:
                constraints["preferred_patterns"].append({
                    "name": p.name,
                    "confidence": p.confidence,
                    "solution": p.solution,
                })
                # Extract step suggestions from the solution
                steps = [s.strip() for s in p.solution.split("→")]
                if len(steps) >= 2:
                    constraints["suggested_steps"].extend(steps)

            # Find debugging patterns to actively avoid
            failed_patterns = store.search(category="debugging", tags=["failure"], min_confidence=0.3, limit=5)
            for p in failed_patterns:
                if p.solution.lower() not in [a.lower() for a in constraints["avoided_patterns"]]:
                    constraints["avoided_patterns"].append(p.solution[:100])

            return constraints
        except Exception as e:
            logger.debug("get_planner_constraints failed: %s", e)
            return {"preferred_patterns": [], "avoided_patterns": [], "suggested_steps": []}

    # ── Router Weight Modification ─────────────────────────

    def get_router_weights(self, task_type: str = "") -> dict[str, float]:
        """Return modified mode weights based on learning history.

        Default weights are modified by pattern success rates.
        Lower weight = less likely to be chosen.
        """
        self._refresh()
        from core.uil.contract import ExecutionMode
        weights = {
            ExecutionMode.SIMPLE_CHAT.value: 1.0,
            ExecutionMode.AUTONOMOUS.value: 1.0,
            ExecutionMode.EXPERT_TEAM.value: 0.5,
            ExecutionMode.DIRECT_TOOL.value: 0.8,
        }

        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()

            # Penalize modes that have high failure patterns
            for mode_key in weights:
                failure_patterns = store.search(
                    query=mode_key, tags=["failure"], min_confidence=0.3, limit=5,
                )
                if failure_patterns:
                    # Each failure reduces mode weight by 10%
                    penalty = min(0.5, len(failure_patterns) * 0.1)
                    weights[mode_key] = max(0.1, weights[mode_key] - penalty)
                    logger.debug("Router weight: %s penalized from %.1f to %.1f (%d failures)",
                                mode_key, weights[mode_key] + penalty, weights[mode_key],
                                len(failure_patterns))

            # Boost modes with high success patterns
            for mode_key in weights:
                success_patterns = store.search(
                    query=mode_key, tags=["success"], min_confidence=0.6, limit=5,
                )
                if success_patterns:
                    boost = min(0.3, len(success_patterns) * 0.05)
                    weights[mode_key] = min(1.0, weights[mode_key] + boost)

        except Exception as e:
            logger.debug("get_router_weights failed: %s", e)

        return weights

    # ── 3-Tier Influence Engine ─────────────────────────────

    INFLUENCE_LEVELS = {"boost": 0.9, "suggest": 0.5, "warn": 0.15, "none": 0.0}

    def evaluate(self, suggestion: str) -> dict:
        """Evaluate a suggestion using 3-tier influence.

        Returns {"level": "boost"|"suggest"|"warn"|"none",
                 "weight": 0.0-1.0,
                 "reason": str,
                 "patterns": [...]}
        """
        self._refresh()
        s = suggestion.lower()

        # Check for matching patterns
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()
            patterns = store.search(query=s[:80], min_confidence=0.2, limit=5)
        except Exception as e:
            logger.debug("Pattern search in evaluate failed: %s", e)
            patterns = []

        if not patterns:
            return {"level": "none", "weight": 1.0, "reason": "No matching patterns — free to explore",
                    "patterns": []}

        best = patterns[0]
        matched = [{"name": p.name, "confidence": p.confidence, "status": p.status} for p in patterns[:3]]

        # 🔴 WARN: deprecated or very low confidence
        if best.status == "deprecated":
            return {"level": "warn", "weight": 0.15,
                    "reason": f"Pattern '{best.name}' was deprecated: {best.superseded_by or 'no replacement'}",
                    "patterns": matched}
        if best.confidence < 0.3:
            return {"level": "warn", "weight": 0.2,
                    "reason": f"Pattern '{best.name}' has low confidence ({best.confidence:.2f}) — caution advised",
                    "patterns": matched}

        # 🟢 BOOST: high confidence, proven success
        if best.confidence > 0.7 and best.usage_count >= 2:
            return {"level": "boost", "weight": 1.0,
                    "reason": f"Pattern '{best.name}' is proven (conf={best.confidence:.2f}, used={best.usage_count}x)",
                    "patterns": matched}

        # 🟡 SUGGEST: moderate confidence
        return {"level": "suggest", "weight": 0.6,
                "reason": f"Pattern '{best.name}' has moderate confidence ({best.confidence:.2f})",
                "patterns": matched}

    # ── Expert Selection ───────────────────────────────────

    def get_preferred_experts(self) -> list[str]:
        """Return experts with proven success, ordered by preference."""
        self._refresh()
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()
            expert_patterns = store.search(category="architectural", tags=["success"], min_confidence=0.6, limit=10)
            preferred = []
            for p in expert_patterns:
                if "orchestrator" in p.solution.lower():
                    preferred.append("orchestrator")
                if "coder" in p.solution.lower():
                    preferred.append("coder")
                if "reviewer" in p.solution.lower():
                    preferred.append("reviewer")
                if "researcher" in p.solution.lower():
                    preferred.append("researcher")
                if "debugger" in p.solution.lower():
                    preferred.append("debugger")
            return list(dict.fromkeys(preferred))  # unique, preserve order
        except Exception as e:
            logger.debug("get_preferred_experts failed: %s", e)
            return []


# Singleton
_pdf: PreDecisionForce | None = None


def get_pre_decision_force() -> PreDecisionForce:
    global _pdf
    if _pdf is None:
        _pdf = PreDecisionForce()
    return _pdf
