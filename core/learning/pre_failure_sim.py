"""Pre-Failure Simulation + Strategy Shifter — Level 4 Adaptive Planning.

Predicts failure BEFORE execution by comparing the current plan against
historical failure patterns. When failure probability is high, proposes
alternative strategies before the first tool is called.

This is the difference between:
  L3: fail → learn → fix (reactive)
  L4: predict → change → avoid (proactive)

Usage:
    from core.learning.pre_failure_sim import PreFailureSim
    pfs = PreFailureSim()
    result = pfs.evaluate_plan(plan_steps, task_type)
    if result.risk_level == "high":
        # Use result.alternative_strategies instead
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("widdx.pre_failure")


@dataclass
class PlanRisk:
    """Risk assessment for a proposed plan."""
    risk_level: str = "low"          # "low" | "medium" | "high" | "critical"
    risk_score: float = 0.0          # 0.0-1.0
    matched_failures: list[str] = field(default_factory=list)
    alternative_strategies: list[str] = field(default_factory=list)
    reasoning: str = ""
    should_avoid: bool = False       # True → Planner should pick alternative


class PreFailureSim:
    """Predicts plan failure by comparing against historical patterns."""

    def __init__(self):
        self._failure_threshold: float = 0.6  # risk_score above this → avoid

    def evaluate_plan(self, plan_steps: list[str], task_type: str = "",
                      tools_to_use: list[str] | None = None) -> PlanRisk:
        """Evaluate a proposed plan against failure history.

        Returns PlanRisk with risk_level and alternative strategies if risk is high.
        """
        result = PlanRisk()
        if not plan_steps:
            return result

        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()

            # ── 1. Check each step against failure patterns ──
            failures_matched = []
            total_score = 0.0

            for step in plan_steps:
                step_lower = step.lower()
                # Search for debugging patterns that match this step
                matches = store.search(
                    query=step_lower, category="debugging",
                    tags=["failure"], min_confidence=0.3, limit=3,
                )
                for m in matches:
                    failures_matched.append(m.solution[:120])
                    total_score += (1.0 - m.confidence)  # Lower confidence = higher risk

            if tools_to_use:
                for tool in tools_to_use:
                    tool_matches = store.search(
                        query=tool, category="debugging",
                        tags=["failure"], min_confidence=0.3, limit=2,
                    )
                    for m in tool_matches:
                        if m.solution[:120] not in failures_matched:
                            failures_matched.append(m.solution[:120])
                            total_score += (1.0 - m.confidence) * 0.5

            # ── 2. Calculate risk ──
            plan_count = max(1, len(plan_steps))
            result.risk_score = min(1.0, total_score / plan_count)
            result.matched_failures = failures_matched[:5]

            if result.risk_score >= 0.8:
                result.risk_level = "critical"
                result.should_avoid = True
            elif result.risk_score >= self._failure_threshold:
                result.risk_level = "high"
                result.should_avoid = True
            elif result.risk_score >= 0.4:
                result.risk_level = "medium"
            else:
                result.risk_level = "low"

            # ── 3. Find alternative strategies ──
            if result.should_avoid:
                result.alternative_strategies = self._find_alternatives(
                    plan_steps, task_type, store,
                )

            # ── 4. Build reasoning ──
            if result.should_avoid:
                result.reasoning = (
                    f"Plan has {result.risk_level} risk (score={result.risk_score:.2f}). "
                    f"Matched {len(failures_matched)} historical failures. "
                    f"Consider alternatives: {', '.join(result.alternative_strategies[:3])}"
                )
            else:
                result.reasoning = f"Risk {result.risk_level} (score={result.risk_score:.2f})"

        except Exception as e:
            logger.debug("PreFailureSim error: %s", e)
            result.risk_level = "low"
            result.reasoning = f"Risk assessment unavailable: {e}"

        return result

    def _find_alternatives(self, plan_steps: list[str], task_type: str,
                           store: Any) -> list[str]:
        """Find alternative strategies from successful patterns."""
        alternatives = []

        # Search for high-confidence patterns in same task type
        success_patterns = store.search(
            category="planning", tags=["success"],
            min_confidence=0.6, limit=5,
        )
        for p in success_patterns:
            if p.solution not in alternatives:
                alternatives.append(p.solution[:200])

        # Search for architectural patterns as alternatives
        arch_patterns = store.search(
            category="architectural", min_confidence=0.7, limit=3,
        )
        for p in arch_patterns:
            alt = f"Try: {p.solution[:150]}"
            if alt not in alternatives:
                alternatives.append(alt)

        # If still empty, suggest generic alternatives
        if not alternatives:
            if "write" in " ".join(plan_steps).lower():
                alternatives = [
                    "Use template generation instead of manual file write",
                    "Generate the structure first, then fill content",
                    "Use a different tool combination (bash + template)",
                ]

        return alternatives[:5]

    # ── Creative Strategy Mode (Level 5) ──────────────────

    def needs_creative_mode(self, plan_risk: PlanRisk) -> bool:
        """Return True when all known strategies are exhausted and the LLM
        must invent a completely new approach."""
        return (
            plan_risk.risk_level in ("high", "critical")
            and len(plan_risk.alternative_strategies) == 0
        )

    def build_creative_prompt(self, plan_steps: list[str], task_type: str,
                              failures: list[str]) -> str:
        """Build a prompt asking the LLM to invent a novel strategy.

        This is Level 5 autonomy: when all known patterns fail,
        the system asks the LLM to create something entirely new.
        """
        return f"""<creative_strategy_mode>
ALL KNOWN STRATEGIES HAVE BEEN EXHAUSTED.

Task type: {task_type}
Proposed plan (HIGH RISK): {' → '.join(plan_steps)}
Historical failures with this approach:
{chr(10).join(f'- {f}' for f in failures[:5])}

INVENT A COMPLETELY NEW STRATEGY. Do NOT reuse any of the above.
Think differently:
- Can we solve this with a completely different architecture?
- Can we use a tool combination we haven't tried before?
- Can we break the problem into different sub-problems?
- Is there a simpler approach that bypasses the failing components entirely?

Describe your NEW strategy step by step.
</creative_strategy_mode>"""

    # ── Strategy Shifter ──────────────────────────────────

    def shift_strategy(self, plan_risk: PlanRisk) -> dict:
        """Given a high-risk plan, propose a completely different strategy."""
        if not plan_risk.should_avoid:
            return {"shift": False, "new_strategy": "", "reason": "Current plan acceptable"}

        strategy = {
            "shift": True,
            "risk_level": plan_risk.risk_level,
            "risk_score": plan_risk.risk_score,
            "current_plan_risks": plan_risk.matched_failures[:3],
            "alternatives": plan_risk.alternative_strategies[:3],
            "recommendation": (
                f"STRATEGY SHIFT: Current plan has {plan_risk.risk_level} failure risk. "
                f"Best alternative: {plan_risk.alternative_strategies[0] if plan_risk.alternative_strategies else 'none found'}"
            ),
        }
        logger.warning("StrategyShifter: %s", strategy["recommendation"])
        return strategy


# Singleton
_pfs: PreFailureSim | None = None


def get_pre_failure_sim() -> PreFailureSim:
    global _pfs
    if _pfs is None:
        _pfs = PreFailureSim()
    return _pfs
