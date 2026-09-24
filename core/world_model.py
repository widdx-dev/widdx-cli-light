"""World Model Layer — understands WHY things happen, not just THAT they happen.

Sits ABOVE ESC. Feeds causal understanding into layer transitions.
Transforms WIDDX from "agent that learns from experience" to
"system that understands experience before repeating it."

4 subsystems:
  1. CausalGraph — links cause → effect → failure → success
  2. TaskSemantics — classifies failure as architecture/implementation/tool
  3. StrategyMemory — remembers strategies + context + WHY they worked
  4. HypothesisEngine — predicts "if I use X, what will happen?"

Usage:
    from core.world_model import WorldModel
    wm = WorldModel()
    diagnosis = wm.diagnose_failure("WebSocket timeout", recent_steps)
    if diagnosis.root_cause == "architecture":
        # Skip retry — redesign needed
"""

from __future__ import annotations

import logging
import time
import json
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("widdx.world_model")


# ═══════════════════════════════════════════════════════════════
# 1. Causal Graph
# ═══════════════════════════════════════════════════════════════

@dataclass
class CausalLink:
    cause: str = ""
    effect: str = ""
    count: int = 0
    confidence: float = 0.0
    first_seen: str = ""
    last_seen: str = ""


class CausalGraph:
    """Links causes to effects across execution history."""

    def __init__(self):
        self._links: dict[str, CausalLink] = {}
        self._load()

    def record(self, cause: str, effect: str):
        key = f"{cause[:80]}→{effect[:80]}"
        if key in self._links:
            link = self._links[key]
            link.count += 1
            link.confidence = min(1.0, link.confidence + 0.1)
            link.last_seen = time.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            self._links[key] = CausalLink(
                cause=cause[:120], effect=effect[:120],
                count=1, confidence=0.5,
                first_seen=time.strftime("%Y-%m-%dT%H:%M:%S"),
                last_seen=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        self._save()

    def query_effect(self, cause: str) -> list[CausalLink]:
        """What usually happens when this cause occurs?"""
        results = []
        for key, link in self._links.items():
            if cause[:40].lower() in link.cause.lower():
                results.append(link)
        results.sort(key=lambda x: -x.confidence)
        return results[:5]

    def query_cause(self, effect: str) -> list[CausalLink]:
        """What usually causes this effect?"""
        results = []
        for key, link in self._links.items():
            if effect[:40].lower() in link.effect.lower():
                results.append(link)
        results.sort(key=lambda x: -x.confidence)
        return results[:5]

    def will_likely_fail(self, action: str) -> tuple[bool, str]:
        """Predict if an action will fail based on causal history."""
        effects = self.query_effect(action)
        if effects and effects[0].confidence > 0.7 and effects[0].count >= 2:
            return True, f"'{action}' → '{effects[0].effect}' (conf={effects[0].confidence:.2f}, {effects[0].count}x)"
        return False, ""

    def _load(self):
        p = Path.cwd() / ".widdx" / "causal_graph.json"
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._links = {k: CausalLink(**v) for k, v in data.items()}
            except Exception:
                logger.debug("Exception suppressed (line 100)")

    def _save(self):
        p = Path.cwd() / ".widdx" / "causal_graph.json"
        data = {k: v.__dict__ for k, v in self._links.items()}
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @property
    def stats(self) -> dict:
        return {"total_links": len(self._links)}


# ═══════════════════════════════════════════════════════════════
# 2. Task Semantics Analyzer
# ═══════════════════════════════════════════════════════════════

@dataclass
class FailureDiagnosis:
    root_cause: str = ""          # "architecture" | "implementation" | "tool" | "environment" | "unknown"
    confidence: float = 0.0
    reasoning: str = ""
    suggested_action: str = ""    # "redesign" | "retry" | "change_tool" | "fix_env" | "ask_human"
    skip_retry: bool = False      # If True, ESC jumps directly to L4/L5


class TaskSemantics:
    """Understands what kind of problem this is, not just that it happened."""

    # Patterns that indicate each failure type
    _ARCH_SIGNALS = [
        "protocol", "architecture", "design", "pattern", "event loop",
        "blocking", "race condition", "deadlock", "scalability",
        "not compatible", "incompatible", "wrong approach",
    ]
    _IMPL_SIGNALS = [
        "syntax", "import", "undefined", "missing", "typo", "null",
        "type error", "attribute", "key error", "index",
    ]
    _TOOL_SIGNALS = [
        "timeout", "connection refused", "rate limit", "quota",
        "disk full", "memory", "permission denied", "not found",
    ]

    def diagnose(self, error_msg: str, recent_steps: list[str]) -> FailureDiagnosis:
        """Classify what kind of failure this is."""
        msg = error_msg.lower()
        steps = " ".join(recent_steps).lower() if recent_steps else ""

        arch_score = sum(1 for s in self._ARCH_SIGNALS if s in msg or s in steps)
        impl_score = sum(1 for s in self._IMPL_SIGNALS if s in msg or s in steps)
        tool_score = sum(1 for s in self._TOOL_SIGNALS if s in msg or s in steps)

        d = FailureDiagnosis()

        if arch_score > impl_score and arch_score > tool_score and arch_score >= 2:
            d.root_cause = "architecture"
            d.confidence = min(0.9, arch_score * 0.25)
            d.reasoning = f"Architecture-level issue detected ({arch_score} signals): {error_msg[:150]}"
            d.suggested_action = "redesign"
            d.skip_retry = True  # Retry won't fix an architecture problem
        elif tool_score > impl_score and tool_score >= 1:
            d.root_cause = "tool"
            d.confidence = min(0.9, tool_score * 0.3)
            d.reasoning = f"Tool/environment issue ({tool_score} signals): {error_msg[:150]}"
            d.suggested_action = "change_tool"
            d.skip_retry = False
        elif impl_score >= 2:
            d.root_cause = "implementation"
            d.confidence = min(0.9, impl_score * 0.2)
            d.reasoning = f"Implementation error ({impl_score} signals): {error_msg[:150]}"
            d.suggested_action = "retry"
            d.skip_retry = False
        else:
            d.root_cause = "unknown"
            d.confidence = 0.3
            d.reasoning = f"Unclassified failure: {error_msg[:150]}"
            d.suggested_action = "retry"
            d.skip_retry = False

        logger.info("TaskSemantics: %s (conf=%.2f) → %s",
                    d.root_cause, d.confidence, d.suggested_action)
        return d


# ═══════════════════════════════════════════════════════════════
# 3. Strategy Memory Graph
# ═══════════════════════════════════════════════════════════════

@dataclass
class StrategyMemory:
    name: str = ""
    context: str = ""          # What project/task was this used in
    outcome: str = ""          # "success" | "failure" | "mixed"
    why: str = ""              # WHY it succeeded or failed
    when_to_use: str = ""      # Conditions where this works
    when_to_avoid: str = ""    # Conditions where this fails


class StrategyMemoryGraph:
    """Remembers strategies + context + causal reasoning."""

    def __init__(self):
        self._strategies: list[StrategyMemory] = []
        self._load()

    def record(self, name: str, context: str, outcome: str, why: str,
               when_to_use: str = "", when_to_avoid: str = ""):
        sm = StrategyMemory(name=name, context=context, outcome=outcome,
                           why=why, when_to_use=when_to_use, when_to_avoid=when_to_avoid)
        self._strategies.append(sm)
        if len(self._strategies) > 100:
            self._strategies = self._strategies[-50:]
        self._save()

    def find_similar(self, context: str) -> list[StrategyMemory]:
        """Find strategies used in similar contexts."""
        ctx = context.lower()
        results = [s for s in self._strategies if any(
            w in s.context.lower() or w in s.name.lower()
            for w in ctx.split() if len(w) > 2
        )]
        results.sort(key=lambda s: 1 if s.outcome == "success" else 0, reverse=True)
        return results[:5]

    def get_context_for_prompt(self, current_task: str) -> str:
        """Build strategic guidance for the LLM."""
        similar = self.find_similar(current_task)
        if not similar:
            return ""
        lines = ["<strategy_memory>"]
        for s in similar[:3]:
            icon = {"success": "✅", "failure": "❌", "mixed": "⚠️"}.get(s.outcome, "❓")
            lines.append(f"- {icon} {s.name}: {s.why[:150]}")
            if s.when_to_avoid:
                lines.append(f"  ⚠ Avoid when: {s.when_to_avoid[:100]}")
        lines.append("</strategy_memory>")
        return "\n".join(lines)

    def _load(self):
        p = Path.home() / ".widdx" / "strategy_memory.json"
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self._strategies = [StrategyMemory(**d) for d in data[-50:]]
            except Exception:
                logger.debug("Exception suppressed (line 245)")

    def _save(self):
        p = Path.home() / ".widdx" / "strategy_memory.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([s.__dict__ for s in self._strategies], indent=2, ensure_ascii=False))


# ═══════════════════════════════════════════════════════════════
# 4. Hypothesis Engine
# ═══════════════════════════════════════════════════════════════

@dataclass
class Hypothesis:
    action: str = ""
    predicted_outcome: str = ""
    confidence: float = 0.0
    based_on: str = ""          # "causal_graph" | "strategy_memory" | "pattern_library"
    risk_assessment: str = ""   # "likely safe" | "moderate risk" | "high risk"


class HypothesisEngine:
    """Predicts "if I use X, what will happen?" based on causal history."""

    def __init__(self):
        self._causal = CausalGraph()

    def evaluate(self, action: str) -> Hypothesis:
        """Predict the outcome of an action."""
        h = Hypothesis(action=action)

        # Check causal graph
        will_fail, reason = self._causal.will_likely_fail(action)
        if will_fail:
            h.predicted_outcome = reason
            h.confidence = 0.8
            h.based_on = "causal_graph"
            h.risk_assessment = "high risk"
        else:
            # Check strategy memory
            try:
                sm = StrategyMemoryGraph()
                similar = sm.find_similar(action)
                if similar:
                    best = similar[0]
                    h.predicted_outcome = f"Similar strategy '{best.name}' had outcome: {best.outcome} — {best.why[:100]}"
                    h.confidence = 0.6
                    h.based_on = "strategy_memory"
                    h.risk_assessment = "moderate risk" if best.outcome == "mixed" else "likely safe"
            except Exception:
                logger.debug("Exception suppressed (line 295)")

        if not h.predicted_outcome:
            h.predicted_outcome = "No historical data — will explore"
            h.confidence = 0.3
            h.based_on = "none"
            h.risk_assessment = "unknown"

        return h


# ═══════════════════════════════════════════════════════════════
# Unified World Model
# ═══════════════════════════════════════════════════════════════

class WorldModel:
    """Unified world model — understands WHY, not just WHAT."""

    def __init__(self):
        self.causal = CausalGraph()
        self.semantics = TaskSemantics()
        self.strategies = StrategyMemoryGraph()
        self.hypothesis = HypothesisEngine()

    def diagnose_failure(self, error_msg: str, recent_steps: list[str],
                         tool_used: str = "") -> FailureDiagnosis:
        """Diagnose a failure — returns root cause classification.

        This feeds into ESC: if skip_retry=True, ESC jumps to L4/L5 directly.
        """
        # 1. Semantic classification
        diagnosis = self.semantics.diagnose(error_msg, recent_steps)

        # 2. Record causal link
        if tool_used:
            self.causal.record(
                cause=f"{tool_used}: {error_msg[:100]}",
                effect=diagnosis.root_cause,
            )

        # 3. Predict if retry will help
        if diagnosis.skip_retry:
            logger.warning("WorldModel: skipping retry — %s requires redesign", diagnosis.root_cause)

        return diagnosis

    def before_execution(self, plan_steps: list[str], task_type: str) -> dict:
        """Evaluate a plan BEFORE execution using world model.

        Returns {"risks": [...], "recommendations": [...], "skip_retry_hints": [...]}
        """
        risks = []
        recommendations = []
        skip_hints = []

        for step in plan_steps:
            h = self.hypothesis.evaluate(step)
            if h.risk_assessment == "high risk":
                risks.append(f"Step '{step[:60]}': {h.predicted_outcome[:100]}")
                skip_hints.append(step)

        # Check strategy memory for similar tasks
        similar = self.strategies.find_similar(task_type)
        for s in similar[:3]:
            if s.outcome == "failure":
                recommendations.append(f"Avoid: {s.name} — {s.why[:100]}")
            else:
                recommendations.append(f"Consider: {s.name} — {s.why[:100]}")

        return {
            "risks": risks[:5],
            "recommendations": recommendations[:5],
            "skip_retry_hints": skip_hints[:3],
        }

    def learn_from_outcome(self, strategy_name: str, context: str,
                           outcome: str, why: str):
        """Record what happened and WHY."""
        self.strategies.record(
            name=strategy_name, context=context,
            outcome=outcome, why=why,
            when_to_use=context if outcome == "success" else "",
            when_to_avoid=context if outcome == "failure" else "",
        )


# Singleton
_wm: WorldModel | None = None


def get_world_model() -> WorldModel:
    global _wm
    if _wm is None:
        _wm = WorldModel()
    return _wm
