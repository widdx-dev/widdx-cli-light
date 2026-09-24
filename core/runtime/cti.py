"""Constraint Transparency Index (CTI) — measures learning potential lost to constraints.

Answers: "How much learning that should have happened, didn't happen
because of the constraints?"

Core metrics:
  CTI           — ratio of blocked learning to total potential learning (0=transparent, 1=opaque)
  Information Loss — cumulative knowledge lost per constraint
  Visibility Index — what % of the learning landscape is visible to the system
  Learning Freedom — inverse of total constraint suppression
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("widdx.cti")


@dataclass
class CTIReport:
    """Complete constraint transparency assessment."""
    cti: float                     # 0.0 = fully transparent, 1.0 = fully opaque
    information_loss: dict[str, float]  # per-constraint learning potential lost
    visibility_index: float        # % of learning landscape visible
    learning_freedom: float        # 1.0 = unconstrained, 0.0 = fully constrained
    dominant_occluder: str         # which constraint blocks learning visibility the most
    constraint_efficiency: float   # how many constraints are actually needed vs active
    recommendations: list[str]
    grade: str                     # A (transparent) → F (opaque learning shutdown)
    timestamp: float = field(default_factory=time.time)


class ConstraintTransparencyIndex:
    """Quantifies learning potential lost to constraint occlusion.

    A constraint does two things: blocks learning (direct suppression)
    AND blocks other constraints from seeing learning (occlusion).

    CTI measures both — distinguishing between "system is stable"
    and "system is stable because it can no longer learn."
    """

    OCCLUSION_THRESHOLD = 0.40     # >40% blocked = significant occlusion
    EFFICIENCY_TARGET = 0.50       # at most 50% of active constraints should fire

    def __init__(self):
        self._proposals: list[dict] = []
        self._constraint_fires: dict[str, int] = {}
        self._proposals_that_would_succeed: int = 0  # estimated
        self._total_potential_learning: int = 0

    def start(self):
        self._proposals.clear()
        for k in ["drift", "spc", "invariance", "lyapunov"]:
            self._constraint_fires[k] = 0
        self._proposals_that_would_succeed = 0
        self._total_potential_learning = 0

    def record(self, parameter: str, accepted: bool, blocked_by: str = "",
               would_have_succeeded: bool = False, confidence: float = 0.0):
        """Record a proposal outcome.

        would_have_succeeded: True if the proposal had merit but was
        blocked by a constraint (estimated via confidence or expert judgment).
        """
        self._proposals.append({
            "param": parameter,
            "accepted": accepted,
            "blocked_by": blocked_by,
            "would_succeed": would_have_succeeded,
            "confidence": confidence,
        })

        if blocked_by and blocked_by in self._constraint_fires:
            self._constraint_fires[blocked_by] += 1

        self._total_potential_learning += 1
        if would_have_succeeded and not accepted:
            self._proposals_that_would_succeed += 1

    def evaluate(self) -> CTIReport:
        """Compute the Constraint Transparency Index and related metrics."""
        total = len(self._proposals)
        if total < 5:
            return CTIReport(
                cti=0.0, information_loss={},
                visibility_index=1.0, learning_freedom=1.0,
                dominant_occluder="none", constraint_efficiency=1.0,
                recommendations=["Insufficient data"], grade="N/A",
            )

        blocked = sum(1 for p in self._proposals if not p["accepted"])
        accepted = total - blocked

        # ── CTI: ratio of blocked learning to total potential ──
        # If there's zero learning happening at all, CTI = N/A
        if blocked == 0:
            cti = 0.0
        else:
            # CTI = (proposals that would have succeeded but were blocked) / (all blocked proposals)
            # Estimate: blocked proposals with confidence > 0.6 = "would have succeeded"
            blocked_with_merit = sum(
                1 for p in self._proposals
                if not p["accepted"] and p["confidence"] > 0.6
            )
            cti = round(blocked_with_merit / max(blocked, 1), 3)

        # ── Per-constraint information loss ──
        info_loss: dict[str, float] = {}
        for constraint, fire_count in self._constraint_fires.items():
            if fire_count > 0:
                info_loss[constraint] = round(
                    fire_count / max(total, 1), 3
                )
            else:
                info_loss[constraint] = 0.0

        # ── Visibility Index: 1.0 - (total blocked / total proposals) ──
        visibility = round(1.0 - (blocked / max(total, 1)), 3)

        # ── Learning Freedom: accepted / total ──
        freedom = round(accepted / max(total, 1), 3)

        # ── Dominant occluder ──
        if info_loss:
            dominant = max(info_loss, key=lambda k: info_loss[k])
        else:
            dominant = "none"

        # ── Constraint efficiency: active constraints / total constraints ──
        active_constraints = sum(1 for v in info_loss.values() if v > 0)
        efficiency = round(
            active_constraints / max(len(info_loss), 1), 3
        )

        # ── Recommendations ──
        recs: list[str] = []
        if cti > self.OCCLUSION_THRESHOLD:
            recs.append(
                f"CTI={cti:.2f}: Significant learning occlusion — "
                f"{cti:.0%} of blocked proposals had merit. "
                f"Dominant occluder: {dominant}."
            )
        if visibility < 0.5:
            recs.append(
                f"VISIBILITY={visibility:.2f}: Constraint system blocking "
                f"over half of all proposals. Learning landscape largely invisible."
            )
        if freedom < 0.3:
            recs.append(
                f"FREEDOM={freedom:.2f}: System approaching learning shutdown. "
                f"Consider emergency constraint relaxation."
            )
        if efficiency > 0.8:
            recs.append(
                f"EFFICIENCY={efficiency:.2f}: Most constraints active — "
                f"possible over-constraint. Review which constraints are essential."
            )
        if not recs:
            recs.append("CTI healthy: constraints are not occluding learning.")

        # ── Grade ──
        grade = (
            "A" if cti < 0.15 and visibility > 0.8
            else "B" if cti < 0.25 and visibility > 0.6
            else "C" if cti < 0.40 and visibility > 0.4
            else "D" if cti < 0.60
            else "F"
        )

        return CTIReport(
            cti=cti,
            information_loss=info_loss,
            visibility_index=visibility,
            learning_freedom=freedom,
            dominant_occluder=dominant,
            constraint_efficiency=efficiency,
            recommendations=recs,
            grade=grade,
        )

    @property
    def summary(self) -> dict:
        r = self.evaluate()
        return {
            "cti": r.cti,
            "grade": r.grade,
            "visibility_index": r.visibility_index,
            "learning_freedom": r.learning_freedom,
            "dominant_occluder": r.dominant_occluder,
            "information_loss": r.information_loss,
            "recommendations": r.recommendations,
            "optimal_pressure": self.optimal_pressure(),
        }

    def optimal_pressure(self) -> dict:
        """Compute the equilibrium point between safety and learning.

        The Optimal Constraint Pressure is the balance where:
          - Constraints are tight enough to prevent chaos
          - But loose enough to allow learning at a minimum viable rate

        Returns:
          pressure_ratio   — current constraint pressure vs. optimal
          learning_headroom — how much learning capacity remains unused
          is_at_equilibrium — whether system is at the optimal balance
          requires_relaxation — whether any constraint needs relaxing
          minimum_viable_change — smallest adjustment needed to reach equilibrium
        """
        r = self.evaluate()
        total = len(self._proposals)
        if total < 5:
            return {"status": "insufficient_data"}

        blocked = sum(1 for p in self._proposals if not p["accepted"])
        total - blocked
        blocked_with_merit = sum(
            1 for p in self._proposals
            if not p["accepted"] and p["confidence"] > 0.6
        )

        passed_merit = sum(
            1 for p in self._proposals
            if p["accepted"] and p["confidence"] > 0.6
        )
        total_merit = sum(1 for p in self._proposals if p["confidence"] > 0.6)
        learning_headroom = round(passed_merit / max(total_merit, 1), 3)

        if blocked > 0:
            pressure_ratio = round(blocked_with_merit / blocked, 3)
        else:
            pressure_ratio = 0.0

        # ── Confidence: based on sample size and distribution ──
        sample_factor = min(1.0, total / 50.0)
        variance = pressure_ratio * (1 - pressure_ratio) if 0 < pressure_ratio < 1 else 0.05
        confidence = round(sample_factor * (1.0 - variance), 2)
        ci_half = round(1.96 * (variance ** 0.5) / max(total ** 0.5, 1), 3) if total > 0 else 0.10
        confidence_interval = [
            round(max(0.0, pressure_ratio - ci_half), 3),
            round(min(1.0, pressure_ratio + ci_half), 3),
        ]

        # ── Sensitivity: which constraints matter most? ──
        sensitivities: dict[str, float] = {}
        for constraint, loss in r.information_loss.items():
            if loss > 0:
                sens = round(loss / max(1.0 - r.learning_freedom, 0.01), 3)
                sensitivities[constraint] = min(1.0, sens)
            else:
                sensitivities[constraint] = 0.0

        # ── Equilibrium zone (not a single point) ──
        equilibrium_zone = {"pressure_ratio_max": 0.10, "learning_headroom_min": 0.80}
        distance_pressure = max(0.0, pressure_ratio - equilibrium_zone["pressure_ratio_max"])
        distance_headroom = max(0.0, equilibrium_zone["learning_headroom_min"] - learning_headroom)
        distance_to_center = round((distance_pressure + distance_headroom) / 2, 3)
        is_in_zone = distance_to_center <= 0.02

        # ── Relaxation targets ──
        relax_targets: list[str] = []
        if r.dominant_occluder != "none" and r.cti > 0.15:
            relax_targets.append(r.dominant_occluder)
        for constraint, loss in r.information_loss.items():
            if loss > 0.25:
                relax_targets.append(constraint)
        relax_targets = list(set(relax_targets))[:3]

        # ── Minimum viable change with CI ──
        if relax_targets:
            mv_change = (
                f"Relax {relax_targets[0]} by reducing its "
                f"block rate by ~{int(pressure_ratio * 100)}% "
                f"(CI: {int(confidence_interval[0]*100)}%-{int(confidence_interval[1]*100)}%) "
                f"to reach equilibrium zone"
            )
        elif distance_to_center > 0.02:
            mv_change = (
                f"System near equilibrium zone — minor adjustment. "
                f"Distance to zone center: {distance_to_center:.2f}"
            )
        else:
            mv_change = "At optimal equilibrium zone — no adjustment needed"

        return {
            "pressure_ratio": pressure_ratio,
            "learning_headroom": learning_headroom,
            "recommended_relaxation": pressure_ratio,
            "confidence": confidence,
            "confidence_interval": confidence_interval,
            "evidence_tasks": total,
            "equilibrium_zone": equilibrium_zone,
            "distance_to_center": distance_to_center,
            "is_in_zone": is_in_zone,
            "requires_relaxation": len(relax_targets) > 0,
            "relax_targets": relax_targets,
            "sensitivity": {
                k: {"value": v, "level": "HIGH" if v > 0.7 else "MEDIUM" if v > 0.3 else "LOW"}
                for k, v in sorted(sensitivities.items(), key=lambda x: -x[1])[:4]
            },
            "minimum_viable_change": mv_change,
            "status": (
                "optimal" if is_in_zone
                else "over_constrained" if pressure_ratio > 0.20
                else "approaching_equilibrium" if pressure_ratio <= 0.15
                else "under_constrained"
            ),
        }


_cti: ConstraintTransparencyIndex | None = None


def get_cti() -> ConstraintTransparencyIndex:
    global _cti
    if _cti is None:
        _cti = ConstraintTransparencyIndex()
    return _cti
