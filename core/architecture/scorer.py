"""Architecture Scorer — scores and ranks candidate architectures."""

from __future__ import annotations
import logging
from .pattern_store import ArchitecturePattern

logger = logging.getLogger("widdx.arch.scorer")


class ArchitectureScorer:
    """Scores architectures on complexity, performance, risk, and similarity."""

    def score(self, arch: ArchitecturePattern, goal: str = "", domain: str = "") -> dict:
        """Score a single architecture. Returns score breakdown + total."""
        scores = {}

        # 1. Complexity score (simple = better for small tasks)
        complexity_map = {"simple": 1.0, "moderate": 0.7, "complex": 0.4}
        scores["complexity"] = complexity_map.get(arch.complexity, 0.5)

        # 2. Performance estimate (based on components + communication)
        perf = 1.0
        if arch.communication == "gRPC":
            perf += 0.2
        elif arch.communication == "Event-driven":
            perf += 0.1
        if arch.storage in ("PostgreSQL", "MongoDB"):
            perf += 0.1
        if len(arch.components) > 5:
            perf -= 0.2
        scores["performance"] = min(1.0, max(0.1, perf))

        # 3. Failure risk (from World Model + historical success)
        risk = 1.0 - arch.success_rate
        if arch.risk_profile == "high":
            risk += 0.2
        elif arch.risk_profile == "low":
            risk -= 0.1
        # World Model check
        try:
            from core.world_model import get_world_model
            wm = get_world_model()
            for comp in arch.components[:3]:
                will_fail, _ = wm.causal.will_likely_fail(comp)
                if will_fail:
                    risk += 0.15
        except Exception:
            logger.debug("Exception suppressed (line 47)")
        scores["risk"] = min(1.0, max(0.0, risk))
        scores["safety"] = 1.0 - scores["risk"]

        # 4. Similarity to successful patterns
        if arch.usage_count > 0:
            scores["similarity"] = min(1.0, arch.success_rate * 0.7 + min(arch.usage_count / 10, 1) * 0.3)
        else:
            scores["similarity"] = 0.3  # New template — moderate trust

        # 5. Domain match
        scores["domain_match"] = 1.0 if domain in arch.domains else 0.5

        # Total weighted score
        weights = {"complexity": 0.25, "performance": 0.2, "safety": 0.25, "similarity": 0.2, "domain_match": 0.1}
        total = sum(scores.get(k, 0.5) * w for k, w in weights.items())
        scores["total"] = round(total, 2)

        return scores

    def rank(self, architectures: list[ArchitecturePattern],
             goal: str = "", domain: str = "") -> list[tuple[ArchitecturePattern, dict]]:
        """Score and rank architectures. Returns sorted (arch, scores) pairs."""
        ranked = [(arch, self.score(arch, goal, domain)) for arch in architectures]
        ranked.sort(key=lambda x: -x[1]["total"])
        return ranked

    def select_best(self, architectures: list[ArchitecturePattern],
                    goal: str = "", domain: str = "") -> ArchitecturePattern | None:
        """Select the best architecture. Returns None if none viable."""
        ranked = self.rank(architectures, goal, domain)
        if not ranked:
            return None
        best, scores = ranked[0]
        if scores["total"] < 0.3:
            return None  # All too risky
        return best
