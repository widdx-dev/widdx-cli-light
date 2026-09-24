"""Meta-Constraint Layer (MCL) — constraint reflexivity for bounded learning.

Monitors whether the four containment models are themselves healthy:
  - Rigidity detection: is any constraint too strict?
  - Suppression detection: are constraints blocking all learning?
  - Conflict detection: are two constraints fighting each other?
  - Coupling matrix: how do constraints affect each other?

Does NOT auto-adjust constraints — produces a reflexivity report
with recommendations for human review.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("widdx.mcl")


@dataclass
class ConstraintHealth:
    """Health assessment of a single constraint."""
    name: str
    rigidity: float       # 0.0 = too loose, 1.0 = too tight
    suppression_rate: float  # % of learning blocked by this constraint
    conflict_count: int     # detected conflicts with other constraints
    recommendation: str
    status: str            # HEALTHY | RIGID | SUPPRESSIVE | CONFLICTING


@dataclass
class CouplingEdge:
    """Directed edge: constraint A affects constraint B."""
    source: str
    target: str
    strength: float  # 0.0 = no effect, 1.0 = strong coupling
    direction: str   # "amplifies" | "suppresses" | "independent"


@dataclass
class MCLReport:
    """Complete meta-constraint health report."""
    constraints: dict[str, ConstraintHealth]
    coupling_matrix: list[CouplingEdge]
    suppression_chain: list[str]  # chain of constraints blocking learning
    overall_health: str           # FREE | BALANCED | CONSTRAINED | STAGNANT
    recommendations: list[str]
    timestamp: float = field(default_factory=time.time)


class MetaConstraintLayer:
    """Monitors the health of the containment system itself.

    Answers: "Are my constraints too tight, conflicting, or suppressing learning?"
    """

    # Thresholds for rigidity detection
    RIGIDITY_LOW_THRESHOLD = 0.1   # too loose — nearly no constraint
    RIGIDITY_HIGH_THRESHOLD = 0.8  # too tight — constraint dominates
    SUPPRESSION_HIGH_THRESHOLD = 0.6  # >60% of proposals blocked = suppressive

    def __init__(self):
        self._proposal_history: list[dict] = []
        self._constraint_actions: dict[str, list[dict]] = {
            "drift": [],
            "spc": [],
            "invariance": [],
            "lyapunov": [],
        }
        self._start_time: float = 0.0

    def start(self):
        self._proposal_history.clear()
        for k in self._constraint_actions:
            self._constraint_actions[k].clear()
        self._start_time = time.time()

    # ── Data collection ────────────────────────────────

    def record_proposal(self, parameter: str, accepted: bool, blocked_by: str = ""):
        """Record a proposal outcome and which constraint blocked it (if any)."""
        self._proposal_history.append({
            "t": time.time(),
            "param": parameter,
            "accepted": accepted,
            "blocked_by": blocked_by,
        })
        if blocked_by and blocked_by in self._constraint_actions:
            self._constraint_actions[blocked_by].append({
                "t": time.time(),
                "param": parameter,
                "action": "blocked",
            })

    def record_constraint_action(self, constraint: str, action: str,
                                  parameter: str = ""):
        """Record when a constraint takes action (block/reject/clamp)."""
        if constraint in self._constraint_actions:
            self._constraint_actions[constraint].append({
                "t": time.time(),
                "param": parameter,
                "action": action,
            })

    # ── Analysis ───────────────────────────────────────

    def evaluate(self) -> MCLReport:
        """Analyze constraint health and coupling. Produces an MCLReport."""
        total = len(self._proposal_history)
        if total < 5:
            return MCLReport(
                constraints={},
                coupling_matrix=[],
                suppression_chain=[],
                overall_health="FREE",
                recommendations=["Insufficient data for constraint analysis"],
            )

        accepted = sum(1 for p in self._proposal_history if p["accepted"])
        blocked = total - accepted

        # Per-constraint health
        constraints: dict[str, ConstraintHealth] = {}

        # Drift: rigidity = % of proposals clamped/rejected by drift
        len(self._constraint_actions["drift"])
        drift_blocked = sum(1 for p in self._proposal_history if p["blocked_by"] == "drift")
        drift_rigidity = drift_blocked / max(total, 1)
        drift_suppression = drift_blocked / max(blocked, 1) if blocked > 0 else 0
        drift_status = self._assess_status(drift_rigidity, drift_suppression)
        constraints["drift"] = ConstraintHealth(
            name="drift",
            rigidity=round(drift_rigidity, 3),
            suppression_rate=round(drift_suppression, 3),
            conflict_count=0,
            recommendation=self._recommend(drift_rigidity, "drift"),
            status=drift_status,
        )

        # SPC: rigidity = % rejected by acceptance control
        spc_blocked = sum(1 for p in self._proposal_history if p["blocked_by"] == "spc")
        spc_rigidity = spc_blocked / max(total, 1)
        spc_suppression = spc_blocked / max(blocked, 1) if blocked > 0 else 0
        spc_status = self._assess_status(spc_rigidity, spc_suppression)
        constraints["spc"] = ConstraintHealth(
            name="spc",
            rigidity=round(spc_rigidity, 3),
            suppression_rate=round(spc_suppression, 3),
            conflict_count=0,
            recommendation=self._recommend(spc_rigidity, "SPC acceptance control"),
            status=spc_status,
        )

        # Invariance: only counts if it blocked proposals
        inv_blocked = sum(1 for p in self._proposal_history if p["blocked_by"] == "invariance")
        inv_rigidity = inv_blocked / max(total, 1)
        inv_status = self._assess_status(inv_rigidity, inv_blocked / max(blocked, 1) if blocked > 0 else 0)
        constraints["invariance"] = ConstraintHealth(
            name="invariance",
            rigidity=round(inv_rigidity, 3),
            suppression_rate=round(inv_blocked / max(blocked, 1), 3) if blocked > 0 else 0,
            conflict_count=0,
            recommendation=self._recommend(inv_rigidity, "invariance"),
            status=inv_status,
        )

        # Lyapunov: rigidity = % of proposals rejected due to diverging V(t)
        lyap_blocked = sum(1 for p in self._proposal_history if p["blocked_by"] == "lyapunov")
        lyap_rigidity = lyap_blocked / max(total, 1)
        lyap_status = self._assess_status(lyap_rigidity, lyap_blocked / max(blocked, 1) if blocked > 0 else 0)
        constraints["lyapunov"] = ConstraintHealth(
            name="lyapunov",
            rigidity=round(lyap_rigidity, 3),
            suppression_rate=round(lyap_blocked / max(blocked, 1), 3) if blocked > 0 else 0,
            conflict_count=0,
            recommendation=self._recommend(lyap_rigidity, "Lyapunov stability"),
            status=lyap_status,
        )

        # Coupling matrix
        coupling = self._compute_coupling(constraints)

        # Suppression chain: which constraints are the dominant blockers?
        chain = sorted(
            [k for k, v in constraints.items() if v.suppression_rate > 0.3],
            key=lambda k: constraints[k].suppression_rate, reverse=True,
        )

        # Conflict detection
        conflicts = self._detect_conflicts(constraints)
        for c in conflicts:
            if c[0] in constraints:
                constraints[c[0]].conflict_count += 1
            if c[1] in constraints:
                constraints[c[1]].conflict_count += 1

        # Overall health
        n_constrained = sum(1 for v in constraints.values() if v.status in ("RIGID", "SUPPRESSIVE"))
        sum(1 for v in constraints.values() if v.status == "HEALTHY")
        overall = (
            "STAGNANT" if n_constrained >= 3
            else "CONSTRAINED" if n_constrained >= 2
            else "BALANCED" if n_constrained == 1
            else "FREE"
        )

        # Recommendations
        recs: list[str] = []
        for v in constraints.values():
            if v.status == "SUPPRESSIVE":
                recs.append(f"RELAX_{v.name.upper()}: blocking {v.suppression_rate:.0%} of learning. "
                           f"Consider raising threshold or reducing hysteresis.")
            elif v.status == "RIGID":
                recs.append(f"TUNE_{v.name.upper()}: rigidity={v.rigidity:.2f}. "
                           f"{v.recommendation}")
        if overall == "STAGNANT":
            recs.append("CRITICAL: System in stagnation equilibrium — "
                       "constraints are blocking nearly all adaptation. "
                       "Emergency relaxation recommended.")
        if overall == "FREE":
            recs.append("System constraints are healthy — no excessive blocking detected.")

        return MCLReport(
            constraints=constraints,
            coupling_matrix=coupling,
            suppression_chain=chain,
            overall_health=overall,
            recommendations=recs,
        )

    def _assess_status(self, rigidity: float, suppression: float) -> str:
        if suppression > self.SUPPRESSION_HIGH_THRESHOLD:
            return "SUPPRESSIVE"
        if rigidity > self.RIGIDITY_HIGH_THRESHOLD:
            return "RIGID"
        if rigidity < self.RIGIDITY_LOW_THRESHOLD and suppression > 0:
            return "HEALTHY"  # low rigidity is fine if not suppressing
        return "HEALTHY"

    def _recommend(self, rigidity: float, name: str) -> str:
        if rigidity > self.RIGIDITY_HIGH_THRESHOLD:
            return f"{name} is too strict — relax thresholds"
        if rigidity < self.RIGIDITY_LOW_THRESHOLD:
            return f"{name} is very loose — may not provide adequate protection"
        return f"{name} is operating within healthy bounds"

    def _compute_coupling(self, constraints: dict) -> list[CouplingEdge]:
        """Detect coupling between constraints.

        Drift rejecting → less for SPC to reject → SPC appears looser.
        SPC rejecting → fewer accepted proposals → less drift accumulated.
        """
        edges: list[CouplingEdge] = []

        drift = constraints.get("drift")
        spc = constraints.get("spc")

        if drift and spc:
            # If drift blocks more, SPC sees fewer proposals → coupling
            if drift.rigidity > 0.3 and spc.rigidity < 0.1:
                edges.append(CouplingEdge(
                    source="drift", target="spc",
                    strength=round(drift.rigidity * 0.7, 2),
                    direction="suppresses",
                ))

        # SPC rejecting → drift accumulates less
        if spc and drift:
            if spc.rigidity > 0.3 and drift.rigidity < 0.1:
                edges.append(CouplingEdge(
                    source="spc", target="drift",
                    strength=round(spc.rigidity * 0.7, 2),
                    direction="suppresses",
                ))

        # Invariance blocking → fewer proposals reach drift/SPC
        inv = constraints.get("invariance")
        if inv and inv.rigidity > 0.2:
            edges.append(CouplingEdge(
                source="invariance", target="drift",
                strength=round(inv.rigidity * 0.5, 2),
                direction="suppresses",
            ))
            edges.append(CouplingEdge(
                source="invariance", target="spc",
                strength=round(inv.rigidity * 0.5, 2),
                direction="suppresses",
            ))

        return edges

    def _detect_conflicts(self, constraints: dict) -> list[tuple[str, str]]:
        """Detect conflicting constraints.

        Conflict: two constraints are both highly rigid but pulling in
        opposite directions (e.g., drift allows change but SPC rejects it).
        """
        rigid_pairs = []
        names = list(constraints.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = constraints[names[i]]
                b = constraints[names[j]]
                if a.rigidity > 0.5 and b.rigidity > 0.5:
                    # Both rigid → potential conflict
                    rigid_pairs.append((names[i], names[j]))

        return rigid_pairs

    @property
    def summary(self) -> dict:
        report = self.evaluate()
        return {
            "overall": report.overall_health,
            "constraints": {
                k: v.status for k, v in report.constraints.items()
            },
            "suppression_chain": report.suppression_chain,
            "coupling_edges": len(report.coupling_matrix),
            "recommendations": report.recommendations[:3],
        }


_mcl: MetaConstraintLayer | None = None


def get_mcl() -> MetaConstraintLayer:
    global _mcl
    if _mcl is None:
        _mcl = MetaConstraintLayer()
    return _mcl
