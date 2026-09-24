"""Architecture Generator — generates 2-5 candidate architectures per goal."""

from __future__ import annotations
import logging
from .pattern_store import ArchitecturePattern, ArchitecturePatternStore

logger = logging.getLogger("widdx.arch.gen")

# Predefined architecture templates when no patterns exist
_DEFAULT_ARCHITECTURES = [
    ArchitecturePattern(name="monolith-sqlite", components=["app.py", "database.py", "templates/"],
                        communication="REST", storage="SQLite",
                        complexity="simple", domains=["web", "api"], risk_profile="low",
                        estimated_files=3, estimated_modules=2),
    ArchitecturePattern(name="api-sqlite", components=["server.py", "models.py", "routes.py"],
                        communication="REST", storage="SQLite",
                        complexity="simple", domains=["api"], risk_profile="low",
                        estimated_files=3, estimated_modules=3),
    ArchitecturePattern(name="fullstack-flask", components=["server.py", "models.py", "static/", "templates/", "test_api.py"],
                        communication="REST", storage="SQLite",
                        complexity="moderate", domains=["web", "api"], risk_profile="medium",
                        estimated_files=5, estimated_modules=4),
    ArchitecturePattern(name="microservices-basic", components=["gateway.py", "service_a/", "service_b/", "shared/", "docker-compose.yml"],
                        communication="REST", storage="PostgreSQL",
                        complexity="complex", domains=["api", "microservice"], risk_profile="high",
                        estimated_files=8, estimated_modules=6),
    ArchitecturePattern(name="static-site", components=["index.html", "style.css", "script.js"],
                        communication="none", storage="none",
                        complexity="simple", domains=["web"], risk_profile="low",
                        estimated_files=3, estimated_modules=1),
]


class ArchitectureGenerator:
    """Generates candidate architectures using World Model + patterns."""

    def __init__(self):
        self._store = ArchitecturePatternStore()

    def generate(self, goal: str, domain: str = "web", max_count: int = 5) -> list[ArchitecturePattern]:
        """Generate candidate architectures for a goal."""
        candidates = []

        # 1. Search existing patterns
        existing = self._store.search(domain=domain, limit=3)
        candidates.extend(existing)

        # 2. Add default templates that match the domain
        for tmpl in _DEFAULT_ARCHITECTURES:
            if domain in tmpl.domains and tmpl.name not in [c.name for c in candidates]:
                candidates.append(tmpl)

        # 3. World Model filtering: remove architectures that historically failed
        try:
            from core.world_model import get_world_model
            wm = get_world_model()
            for c in list(candidates):
                # Check causal graph for failure patterns
                for comp in c.components[:3]:
                    will_fail, reason = wm.causal.will_likely_fail(comp)
                    if will_fail and c.risk_profile != "high":
                        c.risk_profile = "high"
                        logger.info("Architecture %s risk upgraded: %s", c.name, reason[:80])
        except Exception:
            logger.debug("Exception suppressed (line 64)")

        # 4. Sort by: complexity (simple first) + success_rate (high first)
        complexity_order = {"simple": 0, "moderate": 1, "complex": 2}
        candidates.sort(key=lambda c: (
            complexity_order.get(c.complexity, 1),
            -c.success_rate,
            -c.usage_count,
        ))

        return candidates[:max_count]
