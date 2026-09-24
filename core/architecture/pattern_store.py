"""Architecture Pattern Store — stores full system designs, their success rates, and domain applicability."""

from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("widdx.arch")


@dataclass
class ArchitecturePattern:
    name: str = ""
    components: list[str] = field(default_factory=list)       # ["API server", "Database", "Cache"]
    communication: str = ""                                     # "REST" | "GraphQL" | "gRPC" | "Event-driven"
    storage: str = ""                                           # "SQLite" | "PostgreSQL" | "MongoDB" | "File"
    risk_profile: str = ""                                      # "low" | "medium" | "high"
    complexity: str = ""                                        # "simple" | "moderate" | "complex"
    estimated_files: int = 0
    estimated_modules: int = 0
    success_rate: float = 0.0
    usage_count: int = 0
    domains: list[str] = field(default_factory=list)            # ["web", "cli", "api", "mobile"]
    source_projects: list[str] = field(default_factory=list)
    created_at: str = ""


class ArchitecturePatternStore:
    """Stores and retrieves full system architecture patterns."""

    def __init__(self):
        self._dir = Path.cwd() / ".widdx" / "architectures"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._global_dir = Path.home() / ".widdx" / "architectures"
        self._global_dir.mkdir(parents=True, exist_ok=True)
        self._patterns: dict[str, ArchitecturePattern] = {}
        self._load()

    def _load(self):
        for d in (self._dir, self._global_dir):
            for f in sorted(d.glob("*.json")):
                try:
                    data = json.loads(f.read_text())
                    ap = ArchitecturePattern(**data)
                    self._patterns[ap.name] = ap
                except Exception:
                    logger.debug("Exception suppressed (line 48)")

    def _save(self, pattern: ArchitecturePattern):
        fpath = self._dir / f"{pattern.name}.json"
        fpath.write_text(json.dumps(pattern.__dict__, indent=2, ensure_ascii=False))

    def add(self, name: str, components: list[str], communication: str, storage: str,
            complexity: str, domains: list[str], risk: str = "medium",
            files: int = 0, modules: int = 0, source: str = "") -> ArchitecturePattern:
        if name in self._patterns:
            existing = self._patterns[name]
            existing.usage_count += 1
            existing.source_projects.append(source)
            self._save(existing)
            return existing
        ap = ArchitecturePattern(name=name, components=components, communication=communication,
                                 storage=storage, complexity=complexity, domains=domains,
                                 risk_profile=risk, estimated_files=files, estimated_modules=modules,
                                 usage_count=1, success_rate=0.5, source_projects=[source],
                                 created_at=time.strftime("%Y-%m-%d"))
        self._patterns[name] = ap
        self._save(ap)
        return ap

    def search(self, domain: str = "", complexity: str = "", limit: int = 10) -> list[ArchitecturePattern]:
        results = list(self._patterns.values())
        if domain:
            results = [r for r in results if domain in r.domains]
        if complexity:
            results = [r for r in results if r.complexity == complexity]
        results.sort(key=lambda x: -(x.success_rate * 0.6 + x.usage_count * 0.4))
        return results[:limit]

    def record_outcome(self, name: str, success: bool):
        if name in self._patterns:
            p = self._patterns[name]
            p.success_rate = (p.success_rate * p.usage_count + (1 if success else 0)) / (p.usage_count + 1)
            self._save(p)
