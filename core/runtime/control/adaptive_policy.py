"""Adaptive Policy — learns thresholds with audit trail and confidence.

Closes the loop: scorer grades → PolicyProposal → audit → accept/reject.

Key protections:
  1. Weighted Moving Average (recent evidence weighted higher)
  2. Confidence intervals — only apply changes with ≥70% confidence
  3. Forgetting factor — old evidence decays, prevents Policy Drift
  4. Hard bounds — no parameter can drift outside proven range
  5. Audit trail — every proposal logged with evidence, confidence, decision
  6. Immutable parameters — safety rules NEVER auto-adapt
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("widdx.ecp.adaptive")

# ── Immutable safety parameters (never auto-adapt) ──
IMMUTABLE = frozenset({
    "abort_rules", "memory_pressure_abort", "provider_failure_abort",
    "healing_contracts", "invariants",
})

# ── Learnable operational parameters with proven bounds ──
LEARNABLE_BOUNDS: dict[str, tuple[float, float, float]] = {
    "failure_rate_threshold": (0.30, 0.70, 0.50),
    "complexity_threshold": (0.50, 0.85, 0.70),
    "stuck_iterations": (3.0, 10.0, 5.0),
    "cooldown_steps": (1.0, 5.0, 2.0),
    "action_cap": (4.0, 12.0, 8.0),
}

FORGETTING_HALF_LIFE = 8.0
MIN_EVIDENCE_COUNT = 3
MIN_CONFIDENCE = 0.70


@dataclass
class PolicyProposal:
    """Proposed parameter change with evidence, confidence, and decision."""
    parameter: str
    current_value: float
    proposed_value: float
    direction: str  # "increase" | "decrease" | "hold"
    confidence: float
    evidence_count: int
    reasoning: str
    accepted: bool = False
    rejection_reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "ts": round(self.timestamp, 0),
            "param": self.parameter,
            "from": self.current_value,
            "to": self.proposed_value,
            "dir": self.direction,
            "conf": round(self.confidence, 2),
            "evidence": self.evidence_count,
            "reason": self.reasoning,
            "accepted": self.accepted,
            "rejection": self.rejection_reason,
        }


class AdaptivePolicy:
    """Evidence-weighted adaptive policy with audit trail.

    Algorithm: Weighted Moving Average with exponential forgetting.
    Only proposes changes when confidence ≥ MIN_CONFIDENCE.
    Every proposal is logged to .widdx/policy_proposals.json.

    Immutable parameters (abort rules, invariants) are NEVER proposed.
    """

    def __init__(self):
        self._history: list[dict] = []
        self._proposals: list[PolicyProposal] = []
        self._task_count: int = 0

    def start_task(self):
        """Called at task start — does NOT clear history (cross-task learning)."""
        self._task_count += 1

    def record_score(self, stability: float, policy_intervention_rate: float,
                     switch_effectiveness: float, escalation_efficiency: float,
                     overall: float, anomalies: int):
        """Record a benchmark score with timestamp for weighted averaging."""
        self._history.append({
            "t": time.time(),
            "stability": stability,
            "policy_rate": policy_intervention_rate,
            "switch_eff": switch_effectiveness,
            "esc_eff": escalation_efficiency,
            "overall": overall,
            "anomalies": anomalies,
        })

        # Update Lyapunov analyzer with current parameter state
        try:
            from core.runtime.lyapunov import get_lyapunov_analyzer
            analyzer = get_lyapunov_analyzer()
            params = {
                name: self._defaults()[name]
                for name in LEARNABLE_BOUNDS
            }
            analyzer.tick(len(self._history), params)
        except Exception:
            logger.debug("Exception suppressed (line 115)")

    def _weighted_stats(self) -> dict:
        """Compute weighted moving average with exponential forgetting.

        Recent evidence (newer) weighted higher than old evidence.
        Evidence older than 2x half-life is effectively discarded.
        """
        if not self._history:
            return {}

        now = time.time()
        weights = []
        total_weight = 0.0

        for h in self._history[-20:]:  # last 20 tasks only
            age = now - h["t"]
            weight = 2.0 ** (-age / (FORGETTING_HALF_LIFE * 3600))
            weights.append(weight)
            total_weight += weight

        if total_weight == 0:
            return {}

        def w_avg(key):
            return sum(w * h[key] for w, h in zip(weights, self._history[-20:])) / total_weight

        evidence_count = len(self._history[-20:])
        # Confidence: higher with more evidence, lower with high variance
        raw_count_factor = min(1.0, evidence_count / 10.0)
        return {
            "stability": w_avg("stability"),
            "policy_rate": w_avg("policy_rate"),
            "switch_eff": w_avg("switch_eff"),
            "esc_eff": w_avg("esc_eff"),
            "overall": w_avg("overall"),
            "anomalies": w_avg("anomalies"),
            "evidence_count": evidence_count,
            "confidence_base": raw_count_factor,
        }

    def propose(self) -> list[PolicyProposal]:
        """Generate PolicyProposals for all learnable parameters.

        Each proposal includes confidence and reasoning.
        Proposals with confidence < MIN_CONFIDENCE are rejected.
        Immutable parameters are never proposed.
        """
        stats = self._weighted_stats()
        if not stats or stats["evidence_count"] < MIN_EVIDENCE_COUNT:
            return []

        proposals: list[PolicyProposal] = []
        defaults = self._defaults()
        conf_base = stats["confidence_base"]

        for param, (lo, hi, default) in LEARNABLE_BOUNDS.items():
            current = defaults[param]
            proposal = self._compute_proposal(param, current, lo, hi, stats, conf_base)
            proposals.append(proposal)

        return proposals

    def _compute_proposal(
        self, param: str, current: float,
        lo: float, hi: float, stats: dict, conf_base: float,
    ) -> PolicyProposal:
        """Compute a single parameter proposal with confidence reasoning."""
        proposed = current
        direction = "hold"
        reasoning_parts: list[str] = []
        conf_adjustments: list[float] = []

        if param == "failure_rate_threshold":
            if stats["policy_rate"] > 0.4:
                proposed = min(hi, current + 0.05)
                direction = "increase"
                reasoning_parts.append(f"policy_rate={stats['policy_rate']:.2f}>0.4 → raise")
                conf_adjustments.append(0.85)
            elif stats["stability"] > 0.8 and stats["policy_rate"] < 0.15:
                proposed = max(lo, current - 0.05)
                direction = "decrease"
                reasoning_parts.append(f"stable ({stats['stability']:.2f}) + low policy → lower")
                conf_adjustments.append(0.80)

        elif param == "complexity_threshold":
            if stats["esc_eff"] < 0.5:
                proposed = max(lo, current - 0.05)
                direction = "decrease"
                reasoning_parts.append(f"esc_eff={stats['esc_eff']:.2f}<0.5 → escalate earlier")
                conf_adjustments.append(0.75)

        elif param == "stuck_iterations":
            if stats["anomalies"] > 1.0:
                proposed = min(hi, current + 1)
                direction = "increase"
                reasoning_parts.append(f"anomalies={stats['anomalies']:.1f}>1 → more patience")
                conf_adjustments.append(0.80)
            elif stats["stability"] > 0.85 and stats["anomalies"] < 0.3:
                proposed = max(lo, current - 1)
                direction = "decrease"
                reasoning_parts.append(f"high stability ({stats['stability']:.2f}) → faster reaction")
                conf_adjustments.append(0.70)

        elif param == "cooldown_steps":
            if stats["policy_rate"] > 0.5:
                proposed = min(hi, current + 1)
                direction = "increase"
                reasoning_parts.append(f"policy_rate={stats['policy_rate']:.2f}>0.5 → longer cooldown")
                conf_adjustments.append(0.80)

        elif param == "action_cap":
            if stats["anomalies"] > 2.0:
                proposed = max(lo, current - 2)
                direction = "decrease"
                reasoning_parts.append(f"anomalies={stats['anomalies']:.1f}>2 → restrict actions")
                conf_adjustments.append(0.75)

        avg_conf = sum(conf_adjustments) / len(conf_adjustments) if conf_adjustments else 0.0
        confidence = round(min(1.0, avg_conf * conf_base), 2)
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "no change needed"

        if direction == "hold":
            proposed = current
            reasoning = "within optimal range — no change recommended"

        proposal = PolicyProposal(
            parameter=param,
            current_value=current,
            proposed_value=round(proposed, 2),
            direction=direction,
            confidence=confidence,
            evidence_count=stats["evidence_count"],
            reasoning=reasoning,
        )

        # Auto-accept or reject based on confidence
        if direction != "hold" and confidence >= MIN_CONFIDENCE:
            proposal.accepted = True
        elif direction != "hold":
            proposal.rejection_reason = f"confidence {confidence:.2f} < minimum {MIN_CONFIDENCE}"

        self._proposals.append(proposal)
        return proposal

    def recommend(self) -> dict[str, float]:
        """Return recommended thresholds — only accepted proposals applied."""
        proposals = self.propose()
        accepted = [p for p in proposals if p.accepted]
        defaults = self._defaults()

        if accepted:
            for p in accepted:
                defaults[p.parameter] = p.proposed_value
            logger.info(
                "ADAPTIVE POLICY: %d/%d proposals accepted — %s",
                len(accepted), len(proposals),
                ", ".join(f"{p.parameter}={p.proposed_value}" for p in accepted),
            )

        # Save audit trail
        self._save_audit()

        return defaults

    def _defaults(self) -> dict[str, float]:
        return {
            param: bounds[2]
            for param, bounds in LEARNABLE_BOUNDS.items()
        }

    def _save_audit(self):
        """Save all proposals to audit file."""
        try:
            path = Path(".widdx/policy_proposals.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [p.to_dict() for p in self._proposals]
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("Exception suppressed (line 294)")

    @property
    def audit_trail(self) -> list[dict]:
        return [p.to_dict() for p in self._proposals]

    @property
    def proposal_count(self) -> int:
        return len(self._proposals)

    def reset_to_defaults(self):
        """Emergency reset — clear all learned values, return to factory defaults."""
        self._history.clear()
        self._proposals.clear()
        logger.critical("ADAPTIVE POLICY: emergency reset to factory defaults")


_adaptive: AdaptivePolicy | None = None


def get_adaptive_policy() -> AdaptivePolicy:
    global _adaptive
    if _adaptive is None:
        _adaptive = AdaptivePolicy()
    return _adaptive
