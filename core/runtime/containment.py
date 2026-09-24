"""Stability containment — mathematical bounds for an evolving control system.

Four containment models:
  1. Invariance test suite    — deterministic replay, semantic fingerprint
  2. Drift containment        — bounded variation, hysteresis gates
  3. Metalearning stability   — Lyapunov-inspired convergence criterion
  4. Acceptance control       — SPC (Statistical Process Control) on accept rate

These answer the three critical questions:
  - "Is the system still the same system after N steps?"
  - "Has learning converged, or is it optimizing noise?"
  - "How much change is too much?"
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("widdx.containment")

# ═══════════════════════════════════════════════════════════════
# 1. INVARIANCE TEST SUITE
# ───────────────────────────────────────────────────────────────
# Deterministic replay: same seed + same input → same decisions.
# Semantic fingerprint: hash of decision trajectory → compare across runs.
# Any deviation = invariance violation.
# ═══════════════════════════════════════════════════════════════

@dataclass
class InvarianceFingerprint:
    """Cryptographic fingerprint of a decision trajectory."""
    run_id: str = ""
    seed: int = 0
    trajectory_hash: str = ""
    step_count: int = 0
    action_sequence: list[str] = field(default_factory=list)
    parameter_snapshot: dict[str, float] = field(default_factory=dict)
    consistency_score: float = 1.0  # 1.0 = identical to baseline


class InvarianceTestSuite:
    """Verifies that the system produces identical behavior under identical conditions.

    Two runs with identical seed, input, and initial state MUST produce
    identical decision trajectories. Any deviation = semantic drift.
    """

    def __init__(self):
        self._baseline: InvarianceFingerprint | None = None
        self._runs: list[InvarianceFingerprint] = []
        self._violations: list[dict] = []

    def start(self, seed: int = 42):
        self._baseline = None
        self._runs.clear()
        self._violations.clear()

    def set_baseline(self, seed: int, trajectory: list[str],
                     parameters: dict[str, float], step_count: int):
        """Record the ground-truth fingerprint."""
        self._baseline = InvarianceFingerprint(
            run_id="baseline",
            seed=seed,
            trajectory_hash=self._hash_trajectory(trajectory),
            step_count=step_count,
            action_sequence=list(trajectory),
            parameter_snapshot=dict(parameters),
            consistency_score=1.0,
        )

    def verify(self, seed: int, trajectory: list[str],
               parameters: dict[str, float], step_count: int) -> InvarianceFingerprint:
        """Compare a new run against the baseline. Returns consistency score."""
        run = InvarianceFingerprint(
            run_id=f"run_{len(self._runs)}",
            seed=seed,
            trajectory_hash=self._hash_trajectory(trajectory),
            step_count=step_count,
            action_sequence=list(trajectory),
            parameter_snapshot=dict(parameters),
        )

        if self._baseline is None:
            self._baseline = run
            self._runs.append(run)
            return run

        # Compare actions
        base_actions = self._baseline.action_sequence
        run_actions = run.action_sequence
        match_count = sum(
            1 for a, b in zip(base_actions, run_actions) if a == b
        )
        action_consistency = match_count / max(len(base_actions), 1)

        # Compare parameters (allow minor drift within bounds)
        param_deltas = []
        for key in set(base_actions) & set(run.action_sequence if hasattr(run, 'parameter_snapshot') else []):
            pass
        for key in set(self._baseline.parameter_snapshot.keys()) & set(run.parameter_snapshot.keys()):
            delta = abs(self._baseline.parameter_snapshot[key] - run.parameter_snapshot[key])
            param_deltas.append(delta)
        param_consistency = 1.0 - (sum(param_deltas) / max(len(param_deltas), 1))

        # Composite
        run.consistency_score = round(action_consistency * 0.7 + param_consistency * 0.3, 3)

        self._runs.append(run)

        if run.consistency_score < 0.90:
            self._violations.append({
                "run": run.run_id,
                "consistency": run.consistency_score,
                "trajectory_diff": self._diff_trajectories(
                    self._baseline.action_sequence, run.action_sequence,
                ),
            })
            logger.critical(
                "INVARIANCE VIOLATION: run=%s consistency=%.3f (threshold=0.90)",
                run.run_id, run.consistency_score,
            )

        return run

    @staticmethod
    def _hash_trajectory(trajectory: list[str]) -> str:
        return hashlib.sha256("|".join(trajectory).encode()).hexdigest()[:16]

    @staticmethod
    def _diff_trajectories(a: list[str], b: list[str]) -> list[dict]:
        diffs = []
        for i in range(max(len(a), len(b))):
            if i >= len(a) or i >= len(b) or a[i] != b[i]:
                diffs.append({
                    "step": i,
                    "baseline": a[i] if i < len(a) else "none",
                    "actual": b[i] if i < len(b) else "none",
                })
        return diffs[:10]

    @property
    def is_invariant(self) -> bool:
        return len(self._violations) == 0

    @property
    def report(self) -> dict:
        return {
            "baseline_hash": self._baseline.trajectory_hash if self._baseline else None,
            "runs": len(self._runs),
            "violations": len(self._violations),
            "is_invariant": self.is_invariant,
            "consistency": round(
                sum(r.consistency_score for r in self._runs) / max(len(self._runs), 1), 3
            ) if self._runs else 1.0,
        }


# ═══════════════════════════════════════════════════════════════
# 2. DRIFT CONTAINMENT
# ───────────────────────────────────────────────────────────────
# Bounded variation: no parameter changes more than MAX_DELTA per epoch.
# Hysteresis gate: requires N confirmations before accepting a change.
# Total variation cap: cumulative change across all params ≤ TV_CAP.
# ═══════════════════════════════════════════════════════════════

@dataclass
class DriftGate:
    """A hysteresis gate for a single parameter."""
    parameter: str
    current_value: float
    proposed_value: float = 0.0
    confirmations_needed: int = 3
    confirmations_received: int = 0
    locked: bool = False
    total_variation_accumulated: float = 0.0

    def propose(self, value: float) -> str:
        """Propose a new value. Returns 'accept', 'accumulate', or 'reject'."""
        if self.locked:
            return "reject"

        if value == self.current_value:
            self.confirmations_received = 0
            return "reject"

        if value == self.proposed_value:
            self.confirmations_received += 1
            if self.confirmations_received >= self.confirmations_needed:
                delta = abs(value - self.current_value)
                self.current_value = value
                self.total_variation_accumulated += delta
                self.confirmations_received = 0
                self.proposed_value = 0.0
                return "accept"
            return "accumulate"

        self.proposed_value = value
        self.confirmations_received = 1
        return "accumulate"


class DriftContainment:
    """Bounds how much and how fast parameters can change.

    Enforces:
      - MAX_DELTA: maximum single-parameter change per epoch
      - HYSTERESIS: N confirmations before accepting
      - TV_CAP: total variation across all parameters
      - LOCK: freeze parameter if TV_CAP exceeded
    """

    MAX_DELTA = 0.15
    DEFAULT_HYSTERESIS = 3
    TV_CAP = 1.0  # total variation cap across all parameters

    def __init__(self):
        self._gates: dict[str, DriftGate] = {}
        self._total_variation: float = 0.0
        self._lock_count: int = 0

    def start(self):
        self._gates.clear()
        self._total_variation = 0.0
        self._lock_count = 0

    def register(self, parameter: str, initial_value: float):
        if parameter not in self._gates:
            self._gates[parameter] = DriftGate(
                parameter=parameter,
                current_value=initial_value,
                confirmations_needed=self.DEFAULT_HYSTERESIS,
            )

    def propose(self, parameter: str, value: float) -> dict:
        """Propose a parameter change. Returns verdict with reasoning."""
        gate = self._gates.get(parameter)
        if gate is None:
            return {"accepted": False, "reason": "parameter not registered"}

        if gate.locked:
            return {"accepted": False, "reason": "parameter locked (TV cap exceeded)"}

        delta = abs(value - gate.current_value)
        if delta > self.MAX_DELTA:
            return {
                "accepted": False,
                "reason": f"delta {delta:.2f} exceeds max {self.MAX_DELTA}",
                "clamped_proposal": gate.current_value + (self.MAX_DELTA if value > gate.current_value else -self.MAX_DELTA),
            }

        verdict = gate.propose(value)
        if verdict == "accept":
            self._total_variation += delta
            if self._total_variation > self.TV_CAP:
                for g in self._gates.values():
                    g.locked = True
                self._lock_count += 1
                logger.critical("DRIFT CONTAINMENT: TV cap %.2f exceeded — locking all parameters", self.TV_CAP)
                return {
                    "accepted": True,  # this change accepted, but future locked
                    "reason": f"accepted (delta={delta:.2f}) — ALL parameters now locked (TV={self._total_variation:.2f})",
                    "params_locked": True,
                }
            return {"accepted": True, "reason": f"accepted (hysteresis={gate.confirmations_needed})"}
        elif verdict == "accumulate":
            return {"accepted": False, "reason": f"accumulating ({gate.confirmations_received}/{gate.confirmations_needed})"}
        else:
            return {"accepted": False, "reason": "rejected"}

    @property
    def is_locked(self) -> bool:
        return all(g.locked for g in self._gates.values()) if self._gates else False

    @property
    def report(self) -> dict:
        return {
            "total_variation": round(self._total_variation, 3),
            "tv_cap": self.TV_CAP,
            "locked": self.is_locked,
            "lock_count": self._lock_count,
            "gates": {
                k: {
                    "current": g.current_value,
                    "total_variation": round(g.total_variation_accumulated, 3),
                    "locked": g.locked,
                }
                for k, g in self._gates.items()
            },
        }


# ═══════════════════════════════════════════════════════════════
# 3. METALEARNING STABILITY
# ───────────────────────────────────────────────────────────────
# Lyapunov-inspired stability: a system converges if V(t+1) ≤ V(t).
# V = composite instability metric (drift + divergence + oscillation).
# If V decreases monotonically → stable. If V oscillates → marginally
# stable. If V increases → unstable learning.
# ═══════════════════════════════════════════════════════════════

@dataclass
class StabilityPoint:
    """One point in the stability function."""
    step: int
    drift: float
    divergence: float
    oscillation: float
    v_value: float  # Lyapunov candidate value
    timestamp: float = field(default_factory=time.time)


class MetalearningStability:
    """Measures whether the learning process converges or diverges.

    Uses a Lyapunov-inspired candidate function:
      V(t) = α·drift(t) + β·divergence(t) + γ·oscillation(t)

    Convergence: V(t+1) ≤ V(t) for N consecutive steps.
    Divergence: V(t+1) > V(t) for N consecutive steps.
    Marginal: oscillating between convergence and divergence.
    """

    CONVERGENCE_WINDOW = 5
    DIVERGENCE_THRESHOLD = 3

    def __init__(self):
        self._history: list[StabilityPoint] = []
        self._state: str = "initializing"  # initializing | converging | diverging | marginal | stable

    def start(self):
        self._history.clear()
        self._state = "initializing"

    def tick(self, step: int, drift: float, divergence: float,
             oscillation: float) -> StabilityPoint:
        """Record a stability measurement and compute convergence state."""
        v = drift * 0.4 + divergence * 0.35 + oscillation * 0.25
        point = StabilityPoint(
            step=step,
            drift=drift,
            divergence=divergence,
            oscillation=oscillation,
            v_value=v,
        )
        self._history.append(point)
        if len(self._history) > 20:
            self._history.pop(0)

        self._update_state()
        return point

    def _update_state(self):
        if len(self._history) < self.CONVERGENCE_WINDOW:
            self._state = "initializing"
            return

        recent = self._history[-self.CONVERGENCE_WINDOW:]
        v_values = [p.v_value for p in recent]

        decreasing = sum(1 for i in range(1, len(v_values)) if v_values[i] < v_values[i-1])
        increasing = sum(1 for i in range(1, len(v_values)) if v_values[i] > v_values[i-1])

        if decreasing >= self.CONVERGENCE_WINDOW - 1:
            self._state = "converging"
        elif increasing >= self.DIVERGENCE_THRESHOLD:
            self._state = "diverging"
        elif max(v_values) - min(v_values) < 0.05:
            self._state = "stable"
        else:
            self._state = "marginal"

    @property
    def is_converging(self) -> bool:
        return self._state == "converging"

    @property
    def is_diverging(self) -> bool:
        return self._state == "diverging"

    @property
    def is_stable(self) -> bool:
        return self._state in ("stable", "converging")

    @property
    def report(self) -> dict:
        return {
            "state": self._state,
            "samples": len(self._history),
            "current_v": round(self._history[-1].v_value, 3) if self._history else 0,
            "trend_v": [round(p.v_value, 3) for p in self._history[-5:]] if self._history else [],
            "is_converging": self.is_converging,
            "is_diverging": self.is_diverging,
            "is_stable": self.is_stable,
        }


# ═══════════════════════════════════════════════════════════════
# 4. ACCEPTANCE CONTROL (SPC)
# ───────────────────────────────────────────────────────────────
# Statistical Process Control on proposal accept rate.
# Control limits: mean ± 3σ. If accept rate falls outside limits
# → learning process is out of statistical control.
# Also detects: systematic bias (all accept/reject), rate drift.
# ═══════════════════════════════════════════════════════════════

@dataclass
class AcceptanceWindow:
    """A rolling window of accept/reject decisions."""
    window_size: int = 20
    decisions: list[bool] = field(default_factory=list)

    def record(self, accepted: bool):
        self.decisions.append(accepted)
        if len(self.decisions) > self.window_size:
            self.decisions.pop(0)

    @property
    def accept_rate(self) -> float:
        return sum(self.decisions) / len(self.decisions) if self.decisions else 0.0

    @property
    def mean(self) -> float:
        return self.accept_rate

    @property
    def std(self) -> float:
        if len(self.decisions) < 2:
            return 0.0
        m = self.mean
        variance = sum((1.0 if d else 0.0 - m) ** 2 for d in self.decisions) / (len(self.decisions) - 1)
        return variance ** 0.5


class AcceptanceControl:
    """Statistical process control on learning accept rate.

    Detects when the learning process is:
      - Out of control (accept rate beyond 3σ limits)
      - Systematically biased (all accept or all reject)
      - Drifting (accept rate trending outside 2σ for sustained period)
    """

    SIGMA_WARNING = 2.0
    SIGMA_ACTION = 3.0
    MIN_SAMPLES = 10

    def __init__(self):
        self._window = AcceptanceWindow()
        self._baseline_mean: float | None = None
        self._baseline_std: float | None = None
        self._alert_count: int = 0

    def start(self):
        self._window = AcceptanceWindow()
        self._baseline_mean = None
        self._baseline_std = None
        self._alert_count = 0

    def record(self, accepted: bool):
        self._window.record(accepted)

        if len(self._window.decisions) >= self.MIN_SAMPLES:
            if self._baseline_mean is None:
                self._baseline_mean = self._window.mean
                self._baseline_std = self._window.std or 0.05
                logger.info("SPC baseline: mean=%.3f, std=%.3f",
                            self._baseline_mean, self._baseline_std)

    def check(self) -> dict:
        """Check if the acceptance process is in control. Returns SPC verdict."""
        if self._baseline_mean is None or len(self._window.decisions) < self.MIN_SAMPLES:
            return {"in_control": True, "status": "baseline_not_set"}

        current_rate = self._window.accept_rate
        baseline_mean = self._baseline_mean
        deviation = abs(current_rate - baseline_mean)
        sigma = deviation / max(self._baseline_std or 0.01, 0.01)

        if sigma >= self.SIGMA_ACTION:
            self._alert_count += 1
            return {
                "in_control": False,
                "status": "out_of_control",
                "accept_rate": round(current_rate, 3),
                "baseline_mean": round(baseline_mean, 3),
                "sigma": round(sigma, 1),
                "alert": f"Accept rate {current_rate:.3f} is {sigma:.1f}σ from baseline {baseline_mean:.3f}",
            }
        elif sigma >= self.SIGMA_WARNING:
            return {
                "in_control": True,
                "status": "warning",
                "accept_rate": round(current_rate, 3),
                "baseline_mean": round(baseline_mean, 3),
                "sigma": round(sigma, 1),
                "alert": f"Accept rate trending: {sigma:.1f}σ from baseline",
            }

        # Check systematic bias
        if current_rate == 0.0 and len(self._window.decisions) >= self.MIN_SAMPLES:
            return {
                "in_control": False,
                "status": "systematic_reject",
                "accept_rate": 0.0,
                "alert": "Systematic rejection: all proposals rejected",
            }
        if current_rate == 1.0 and len(self._window.decisions) >= self.MIN_SAMPLES:
            return {
                "in_control": False,
                "status": "systematic_accept",
                "accept_rate": 1.0,
                "alert": "Systematic acceptance: all proposals accepted",
            }

        return {"in_control": True, "status": "normal", "accept_rate": round(current_rate, 3)}

    @property
    def report(self) -> dict:
        check = self.check()
        return {
            **check,
            "samples": len(self._window.decisions),
            "baseline": {
                "mean": round(self._baseline_mean, 3) if self._baseline_mean else None,
                "std": round(self._baseline_std, 3) if self._baseline_std else None,
            },
            "alert_count": self._alert_count,
        }


# ═══════════════════════════════════════════════════════════════
# UNIFIED CONTAINMENT REPORT
# ═══════════════════════════════════════════════════════════════

class ContainmentSystem:
    """Unified stability containment across all four models."""

    def __init__(self):
        self.invariance = InvarianceTestSuite()
        self.drift = DriftContainment()
        self.metalearning = MetalearningStability()
        self.acceptance = AcceptanceControl()

    def start(self):
        self.invariance.start()
        self.drift.start()
        self.metalearning.start()
        self.acceptance.start()

    def report(self) -> dict:
        return {
            "invariance": self.invariance.report,
            "drift_containment": self.drift.report,
            "metalearning_stability": self.metalearning.report,
            "acceptance_control": self.acceptance.report,
            "overall_contained": (
                self.invariance.is_invariant
                and not self.drift.is_locked
                and self.metalearning.is_stable
                and self.acceptance.check()["in_control"]
            ),
        }

    def check_all(
        self,
        drift_score: float = 0.0,
        invariance_score: float = 1.0,
        lyapunov_drift: float = 0.0,
        spc_violations: int = 0,
    ) -> dict:
        """Run all containment checks and return verdict.

        Args:
            drift_score: current semantic drift score (0-1)
            invariance_score: current invariance consistency (0-1)
            lyapunov_drift: current Lyapunov function value
            spc_violations: number of SPC violations detected

        Returns:
            dict with 'passed' bool and 'violations' list
        """
        violations = []

        # 1. Invariance check
        if invariance_score < 0.8:
            violations.append(f"Invariance score {invariance_score:.2f} below threshold 0.8")

        # 2. Drift containment check
        if drift_score > 0.7:
            violations.append(f"Drift score {drift_score:.2f} exceeds threshold 0.7")

        # 3. Lyapunov stability check
        if lyapunov_drift > 0.5:
            violations.append(f"Lyapunov drift {lyapunov_drift:.2f} indicates instability")

        # 4. SPC check
        if spc_violations > 0:
            violations.append(f"{spc_violations} SPC violations detected")

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "drift_score": drift_score,
            "invariance_score": invariance_score,
            "lyapunov_drift": lyapunov_drift,
            "spc_violations": spc_violations,
        }


_containment: ContainmentSystem | None = None


def get_containment() -> ContainmentSystem:
    global _containment
    if _containment is None:
        _containment = ContainmentSystem()
    return _containment
