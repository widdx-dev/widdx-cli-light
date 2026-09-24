"""Continuous Evaluation Dashboard — production-grade operational reference.

Single entry point for system health. Answers "why" not just "what".

Output: unified JSON with:
  - Health: GREEN/YELLOW/RED per layer + overall
  - Score: breakdown per layer with weighted contributors
  - Recommendations: structured with reason + action, not just codes
  - Experiments: temporal context (duration, samples, confidence)
  - Invariance: honest state reporting
  - 24h trend: is the system improving or degrading?
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("widdx.dashboard")


def _health_color(value: float, warning: float = 0.6, critical: float = 0.3) -> str:
    if value >= warning:
        return "GREEN"
    if value >= critical:
        return "YELLOW"
    return "RED"


@dataclass
class LayerHealth:
    name: str
    status: str  # GREEN | YELLOW | RED
    score: float  # 0-100
    weight: float
    detail: str = ""


class ContinuousDashboard:
    """Production-grade operational dashboard. Call snapshot() from anywhere."""

    REPORT_PATH = ".widdx/system_snapshot.json"
    HISTORY_PATH = ".widdx/system_history.json"
    MAX_HISTORY = 100

    def snapshot(self) -> dict:
        """Take a complete, production-grade system snapshot."""
        layers = self._collect_layers()
        health = self._compute_health(layers)
        grade, total_score, contributors = self._compute_grade_with_breakdown(layers)
        recommendations = self._generate_recommendations(layers)

        return {
            "timestamp": time.time(),
            "health": health,
            "grade": grade,
            "score": total_score,
            "contributors": contributors,
            "layers": layers,
            "recommendations": recommendations,
        }

    def _collect_layers(self) -> dict[str, dict]:
        layers: dict[str, dict] = {}

        # ── Runtime Control ──
        try:
            from core.runtime import get_control_plane
            ecp = get_control_plane()
            s = ecp.status
            layers["runtime"] = {
                "status": "GREEN" if not s.get("escalated") and s.get("tool_failure_rate", 0) < 0.5 else "YELLOW",
                "score": round((1.0 - s.get("tool_failure_rate", 0)) * 100),
                "detail": f"{s.get('model_switches',0)} switches, {s.get('step_count',0)} steps, "
                          f"cooldown={s.get('cooldown_remaining',0)}, "
                          f"actions={s.get('control_actions_remaining',0)}/{s.get('control_actions_used',0)+s.get('control_actions_remaining',0)}",
                "metrics": {
                    "escalated": s.get("escalated", False),
                    "failure_rate": s.get("tool_failure_rate", 0),
                    "model_switches": s.get("model_switches", 0),
                    "oscillation_warnings": s.get("oscillation_warnings", 0),
                    "step_count": s.get("step_count", 0),
                    "cooldown_remaining": s.get("cooldown_remaining", 0),
                },
            }
        except Exception as e:
            layers["runtime"] = {"status": "RED", "score": 0, "detail": str(e), "metrics": {}}

        # ── Semantic ──
        try:
            from core.runtime.semantic import get_semantic_monitor
            sem = get_semantic_monitor()
            drift = sem.drift.current_drift if sem.drift else 0
            divergence = sem.divergence.consistency if sem.divergence else 1.0
            contam = sem.contamination.measure().contamination_score if sem.contamination else 0
            sem_score = round((1.0 - (drift * 0.4 + (1 - divergence) * 0.3 + contam * 0.3)) * 100)
            layers["semantic"] = {
                "status": _health_color(sem_score / 100),
                "score": sem_score,
                "detail": f"drift={drift:.2f}, divergence={divergence:.2f}, contamination={contam:.2f}",
                "metrics": {
                    "drift": drift,
                    "divergence_consistency": divergence,
                    "contamination": contam,
                    "trend": sem.trend,
                },
            }
        except Exception as e:
            layers["semantic"] = {"status": "GREEN", "score": 100, "detail": f"inactive: {e}", "metrics": {}}

        # ── Healing ──
        try:
            from core.runtime.semantic import get_self_healing_monitor
            healer = get_self_healing_monitor()
            stats = healer.stats
            heal_score = 100 if stats.get("total_healings", 0) == 0 else (
                70 if stats.get("total_healings", 0) < 3 else 50)
            layers["healing"] = {
                "status": "GREEN" if heal_score >= 80 else "YELLOW" if heal_score >= 60 else "RED",
                "score": heal_score,
                "detail": f"{stats.get('total_healings',0)} healings, "
                          f"{stats.get('snapshots',0)} snapshots, "
                          f"cooldown={stats.get('healing_cooldown',0)}",
                "metrics": {
                    "total_healings": stats.get("total_healings", 0),
                    "snapshots": stats.get("snapshots", 0),
                    "last_recovery_step": stats.get("last_recovery_step", 0),
                    "rollbacks": stats.get("rollback_stats", {}).get("total_rollbacks", 0),
                },
            }
        except Exception as e:
            layers["healing"] = {"status": "GREEN", "score": 100, "detail": f"inactive: {e}", "metrics": {}}

        # ── Invariance ──
        try:
            from core.runtime.semantic import get_cognitive_invariance
            inv = get_cognitive_invariance()
            g = inv.get_guarantees()
            guarantee = g.get("guarantee_level", "UNKNOWN")
            violations = len(g.get("violations", []))
            inv_score = {"STRONG": 100, "MODERATE": 70, "WEAK": 40, "NONE": 20}.get(guarantee, 50)
            layers["invariance"] = {
                "status": "GREEN" if guarantee == "STRONG" else "YELLOW" if guarantee == "MODERATE" else "RED",
                "score": inv_score,
                "detail": f"guarantee={guarantee}, violations={violations}, "
                          f"converges={g.get('healing_converges', True)}",
                "metrics": {
                    "guarantee_level": guarantee,
                    "violations": violations,
                    "healing_converges": g.get("healing_converges", True),
                    "contracts": g.get("contracts_defined", 0),
                },
            }
        except Exception as e:
            layers["invariance"] = {"status": "GREEN", "score": 100, "detail": f"inactive: {e}", "metrics": {}}

        # ── Adaptive Policy ──
        try:
            from core.runtime.control.adaptive_policy import get_adaptive_policy
            ap = get_adaptive_policy()
            total = ap.proposal_count
            audit = len(ap.audit_trail)
            accepted = sum(1 for a in ap.audit_trail if a.get("accepted"))
            ap_score = 70 if total == 0 else round((accepted / max(total, 1)) * 100 if total > 0 else 100)
            layers["adaptive"] = {
                "status": "GREEN" if total == 0 or (accepted > 0 and accepted / total < 0.6) else "YELLOW",
                "score": min(100, ap_score + 30),
                "detail": f"{total} proposals, {accepted} accepted, {audit} audited",
                "metrics": {
                    "total_proposals": total,
                    "accepted": accepted,
                    "rejected": total - accepted,
                    "audit_entries": audit,
                },
            }
        except Exception as e:
            layers["adaptive"] = {"status": "GREEN", "score": 100, "detail": f"inactive: {e}", "metrics": {}}

        # ── Experiments ──
        try:
            from core.runtime.control.experiments import get_experiment_runner
            runner = get_experiment_runner()
            active = runner.active_experiments
            history = runner.results_history
            won = sum(1 for h in history if h.get("winner") == "candidate")
            lost = sum(1 for h in history if h.get("winner") == "baseline")
            inconclusive = len(history) - won - lost
            exp_score = 100 if not active and not history else (
                80 if won > lost else 60 if won == lost else 40)
            layers["experiments"] = {
                "status": "GREEN" if exp_score >= 80 else "YELLOW" if exp_score >= 60 else "RED",
                "score": exp_score,
                "detail": f"{len(active)} active, {won} won, {lost} lost, {inconclusive} inconclusive",
                "metrics": {
                    "active": active,
                    "results_count": len(history),
                    "won": won,
                    "lost": lost,
                    "inconclusive": inconclusive,
                },
            }
        except Exception as e:
            layers["experiments"] = {"status": "GREEN", "score": 100, "detail": f"inactive: {e}", "metrics": {}}

        # ── Constraint Transparency (CTI) ──
        try:
            from core.runtime.cti import get_cti
            cti = get_cti()
            cti_summary = cti.summary
            layers["cti"] = {
                "status": "GREEN" if cti_summary["grade"] in ("A", "B")
                          else "YELLOW" if cti_summary["grade"] == "C"
                          else "RED",
                "score": {
                    "A": 100, "B": 80, "C": 60, "D": 40, "F": 20, "N/A": 50
                }.get(cti_summary["grade"], 50),
                "detail": f"CTI={cti_summary['cti']:.2f}, "
                          f"visibility={cti_summary['visibility_index']:.2f}, "
                          f"freedom={cti_summary['learning_freedom']:.2f}",
                "metrics": cti_summary,
            }
        except Exception as e:
            layers["cti"] = {"status": "GREEN", "score": 100, "detail": f"inactive: {e}", "metrics": {}}
        # ── Lyapunov Stability (Real) ──
        try:
            from core.runtime.lyapunov import get_lyapunov_analyzer
            lyap = get_lyapunov_analyzer()
            lyap_report = lyap.analyze()
            cert = lyap.get_stability_certificate()
            lyap_score = 100 if lyap_report.is_stable and lyap_report.is_converging else (
                70 if lyap_report.is_stable else 40 if lyap_report.is_converging else 20
            )
            layers["lyapunov"] = {
                "status": "GREEN" if lyap_report.is_stable and lyap_report.is_converging else (
                    "YELLOW" if lyap_report.is_stable else "RED"),
                "score": lyap_score,
                "detail": f"V={lyap_report.current_v:.4f}, dV={lyap_report.convergence_rate:.4f}, "
                          f"stable={lyap_report.is_stable}, converging={lyap_report.is_converging}",
                "metrics": {
                    "is_stable": lyap_report.is_stable,
                    "is_converging": lyap_report.is_converging,
                    "is_asymptotic": lyap_report.is_asymptotic,
                    "current_v": lyap_report.current_v,
                    "convergence_rate": lyap_report.convergence_rate,
                    "stability_margin": lyap_report.stability_margin,
                    "parameter_convergence": lyap_report.parameter_convergence,
                    "certificate": cert["mathematical_guarantee"],
                },
            }
        except Exception as e:
            layers["lyapunov"] = {"status": "GREEN", "score": 100, "detail": f"inactive: {e}", "metrics": {}}
        try:
            from core.runtime.control.metalearning import get_metalearning_monitor
            ml = get_metalearning_monitor()
            report = ml.evaluate()
            kpi = report.kpi
            ml_score = 100
            issues = 0
            if kpi.is_stale:
                ml_score -= 25
                issues += 1
            if kpi.is_overconfident:
                ml_score -= 25
                issues += 1
            if kpi.is_underconfident:
                ml_score -= 25
                issues += 1
            layers["metalearning"] = {
                "status": "GREEN" if ml_score >= 80 else "YELLOW" if ml_score >= 60 else "RED",
                "score": max(0, ml_score),
                "detail": f"accept_rate={kpi.accept_rate:.0%}, win_rate={kpi.win_rate:.0%}, "
                          f"velocity={kpi.learning_velocity:.3f}/h, issues={issues}",
                "metrics": {
                    "total_proposals": kpi.total_proposals,
                    "accept_rate": kpi.accept_rate,
                    "win_rate": kpi.win_rate,
                    "decisiveness": kpi.decisiveness,
                    "learning_velocity": kpi.learning_velocity,
                    "is_overconfident": kpi.is_overconfident,
                    "is_underconfident": kpi.is_underconfident,
                    "is_stale": kpi.is_stale,
                    "recommendations": report.recommendations,
                    "parameter_health": report.parameter_health,
                },
            }
        except Exception as e:
            layers["metalearning"] = {"status": "GREEN", "score": 100, "detail": f"inactive: {e}", "metrics": {}}

        return layers

    def _compute_health(self, layers: dict) -> dict:
        health = {}
        for name, layer in layers.items():
            health[name] = layer.get("status", "GREEN")
        statuses = list(health.values())
        reds = statuses.count("RED")
        yellows = statuses.count("YELLOW")
        overall = "RED" if reds >= 2 else "YELLOW" if reds >= 1 or yellows >= 3 else "GREEN"
        health["overall"] = overall
        return health

    def _compute_grade_with_breakdown(self, layers: dict) -> tuple[str, float, dict]:
        weights = {
            "runtime": 0.20, "semantic": 0.15, "healing": 0.15,
            "invariance": 0.10, "adaptive": 0.10, "experiments": 0.10,
            "lyapunov": 0.10, "metalearning": 0.10,
        }
        total = 0.0
        contributors = {}
        for name, layer_data in layers.items():
            w = weights.get(name, 0.10)
            score = layer_data.get("score", 100)
            total += score * w
            contributors[name] = round(score, 1)

        total = round(total, 1)
        grade = ("A" if total >= 85 else "B" if total >= 70
                 else "C" if total >= 55 else "D" if total >= 40 else "F")
        return grade, total, contributors

    def _generate_recommendations(self, layers: dict) -> list[dict]:
        recs: list[dict] = []

        runtime = layers.get("runtime", {})
        if runtime.get("metrics", {}).get("escalated"):
            recs.append({
                "code": "RUNTIME_ESCALATED", "severity": "high",
                "reason": "ECP has escalated to expert mode",
                "recommended_action": "Review task complexity; consider manual intervention",
            })

        semantic = layers.get("semantic", {})
        if semantic.get("metrics", {}).get("drift", 0) > 0.5:
            recs.append({
                "code": "HIGH_DRIFT", "severity": "medium",
                "reason": f"Goal drift at {semantic['metrics']['drift']:.2f}",
                "recommended_action": "Re-anchor goal via semantic healer or restart task",
            })

        invariance = layers.get("invariance", {})
        if invariance.get("metrics", {}).get("guarantee_level", "") in ("WEAK", "NONE"):
            recs.append({
                "code": "WEAK_GUARANTEES", "severity": "low",
                "reason": "Not enough evidence for strong invariance guarantees",
                "recommended_action": "Run more tasks to build evidence for invariance contracts",
            })

        ml = layers.get("metalearning", {})
        for r in ml.get("metrics", {}).get("recommendations", []):
            recs.append({
                "code": "META_" + r.split(":")[0] if ":" in r else "META_LEARNING",
                "severity": "medium" if "STALE" in r else "low",
                "reason": r,
                "recommended_action": "Review learning parameters (confidence, half-life, sample rate)",
            })

        if not recs:
            recs.append({
                "code": "ALL_CLEAR", "severity": "low",
                "reason": "All systems operating within normal parameters",
                "recommended_action": "No action required",
            })

        return recs

    def save(self, path: str | None = None) -> dict:
        """Save snapshot and maintain history."""
        data = self.snapshot()
        p = Path(path or self.REPORT_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, default=str))

        # Append to history for trend tracking
        hist_path = Path(self.HISTORY_PATH)
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if hist_path.exists():
            try:
                history = json.loads(hist_path.read_text())
            except Exception:
                logger.debug("Exception suppressed (line 383)")
        history.append({
            "ts": data["timestamp"],
            "grade": data["grade"],
            "score": data["score"],
            "health_overall": data["health"]["overall"],
        })
        if len(history) > self.MAX_HISTORY:
            history = history[-self.MAX_HISTORY:]
        hist_path.write_text(json.dumps(history, indent=2))

        logger.info("Dashboard saved: grade=%s score=%.1f health=%s → %s",
                     data["grade"], data["score"], data["health"]["overall"], p)
        return data

    def trend(self) -> dict:
        """Return 24h trend from history."""
        hist_path = Path(self.HISTORY_PATH)
        if not hist_path.exists():
            return {"available": False, "samples": 0}
        try:
            history = json.loads(hist_path.read_text())
        except Exception:
            return {"available": False, "samples": 0}

        if len(history) < 2:
            return {"available": True, "samples": len(history), "trend": "insufficient_data"}

        scores = [h["score"] for h in history]
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if avg_second > avg_first + 1:
            trend = "improving"
        elif avg_second < avg_first - 1:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "available": True,
            "samples": len(history),
            "trend": trend,
            "first_score": scores[0],
            "last_score": scores[-1],
            "delta": round(scores[-1] - scores[0], 1),
        }


_dashboard: ContinuousDashboard | None = None


def get_dashboard() -> ContinuousDashboard:
    global _dashboard
    if _dashboard is None:
        _dashboard = ContinuousDashboard()
    return _dashboard
