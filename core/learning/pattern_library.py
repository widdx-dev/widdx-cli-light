"""Pattern Library — Core of the Learning Architecture.

Stores reusable patterns extracted from project executions.
Supports CRUD, search, confidence, versioning, promotion, and lifecycle management.

A pattern is a proven approach to a recurring problem:
  - Architectural: "Use context+provider for state management"
  - Coding: "Use async/await for DB queries"
  - Debugging: "Check for None before accessing dict keys"
  - Planning: "Break API task into: models→routes→tests"
  - Workflow: "Always run validate after write"

Usage:
    from core.learning.pattern_library import PatternLibrary
    pl = PatternLibrary()
    pl.add("use-async-db", pattern_data)
    results = pl.search("database", category="coding")
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("widdx.learning")


@dataclass
class Pattern:
    """A single reusable pattern."""
    id: str = ""
    name: str = ""
    category: str = ""          # architectural | coding | debugging | planning | workflow | preference
    description: str = ""
    solution: str = ""          # What to do
    context: str = ""           # When to apply
    examples: list[str] = field(default_factory=list)
    confidence: float = 0.5     # 0.0-1.0
    success_rate: float = 0.0   # % of times this worked
    usage_count: int = 0
    version: int = 1
    status: str = "active"      # active | deprecated | superseded
    superseded_by: str = ""
    source_projects: list[str] = field(default_factory=list)
    source_task_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    promoted_to_global: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Pattern":
        defaults = {
            "id": "", "name": "", "category": "", "description": "", "solution": "",
            "context": "", "examples": [], "confidence": 0.5, "success_rate": 0.0,
            "usage_count": 0, "version": 1, "status": "active", "superseded_by": "",
            "source_projects": [], "source_task_types": [], "tags": [],
            "created_at": "", "updated_at": "", "promoted_to_global": False,
        }
        return cls(**{k: d.get(k, defaults.get(k)) for k in cls.__dataclass_fields__})


class PatternLibrary:
    """Searchable library of proven patterns."""

    def __init__(self, project_dir: str | Path | None = None, global_scope: bool = False):
        root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        base = root / ".widdx" / "patterns"
        if global_scope:
            base = Path.home() / ".widdx" / "patterns"
        self._dir = base
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "_index.json"
        self._patterns: dict[str, Pattern] = {}
        self._load()

    def _load(self):
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text())
                self._patterns = {k: Pattern.from_dict(v) for k, v in data.items()}
            except (json.JSONDecodeError, OSError):
                self._patterns = {}

    def _save(self):
        data = {k: v.to_dict() for k, v in self._patterns.items()}
        self._index_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ── CRUD ─────────────────────────────────────────────────

    def add(self, name: str, category: str, description: str, solution: str,
            context: str = "", examples: list[str] | None = None,
            tags: list[str] | None = None, confidence: float = 0.5,
            source_project: str = "", source_task_type: str = "") -> Pattern:
        """Add a new pattern or update existing one with higher confidence."""
        pid = f"pat_{name.lower().replace(' ', '-')[:40]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%S")

        # Check existing
        if pid in self._patterns:
            existing = self._patterns[pid]
            existing.confidence = min(1.0, max(existing.confidence, confidence))
            existing.success_rate = (existing.success_rate * existing.usage_count + 1) / (existing.usage_count + 1)
            existing.usage_count += 1
            existing.version += 1
            existing.updated_at = now
            if source_project and source_project not in existing.source_projects:
                existing.source_projects.append(source_project)
            self._save()
            logger.debug("Pattern updated: %s (v%d, conf=%.2f)", name, existing.version, existing.confidence)
            return existing

        pattern = Pattern(
            id=pid, name=name, category=category,
            description=description, solution=solution,
            context=context, examples=examples or [], tags=tags or [],
            confidence=confidence, success_rate=1.0, usage_count=1,
            version=1, status="active",
            source_projects=[source_project] if source_project else [],
            source_task_types=[source_task_type] if source_task_type else [],
            created_at=now, updated_at=now, promoted_to_global=False,
        )
        self._patterns[pid] = pattern
        self._save()
        logger.info("Pattern added: %s (cat=%s, conf=%.2f)", name, category, confidence)
        return pattern

    def get(self, pattern_id: str) -> Pattern | None:
        return self._patterns.get(pattern_id)

    def search(self, query: str = "", category: str = "", tags: list[str] | None = None,
               min_confidence: float = 0.3, limit: int = 20) -> list[Pattern]:
        """Search patterns by query, category, tags, and minimum confidence."""
        results = []
        q = query.lower()
        for p in self._patterns.values():
            if p.status != "active":
                continue
            if p.confidence < min_confidence:
                continue
            if category and p.category != category:
                continue
            if tags and not any(t in p.tags for t in tags):
                continue
            if q and q not in p.name.lower() and q not in p.description.lower() and q not in p.solution.lower():
                continue
            results.append(p)
        results.sort(key=lambda x: (x.confidence * 0.5 + x.success_rate * 0.3 + min(x.usage_count / 10, 1) * 0.2), reverse=True)
        return results[:limit]

    def deprecate(self, pattern_id: str, reason: str = "", superseded_by: str = ""):
        if p := self._patterns.get(pattern_id):
            p.status = "deprecated"
            p.superseded_by = superseded_by
            p.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._save()
            logger.info("Pattern deprecated: %s → %s", pattern_id, superseded_by or reason)

    def merge_duplicates(self) -> int:
        """Detect and merge duplicate patterns. Returns count of merges."""
        merged = 0
        names = list(self._patterns.keys())
        for i, k1 in enumerate(names):
            for k2 in names[i+1:]:
                p1, p2 = self._patterns.get(k1), self._patterns.get(k2)
                if not p1 or not p2:
                    continue
                if p1.solution.strip().lower() == p2.solution.strip().lower():
                    # Merge p2 into p1
                    p1.confidence = max(p1.confidence, p2.confidence)
                    p1.usage_count += p2.usage_count
                    p1.examples.extend(p2.examples)
                    p1.source_projects.extend(p2.source_projects)
                    p2.status = "superseded"
                    p2.superseded_by = p1.id
                    merged += 1
        if merged:
            self._save()
        return merged

    # ── Promotion ────────────────────────────────────────────

    def get_promotable(self, min_projects: int = 2, min_confidence: float = 0.7) -> list[Pattern]:
        """Find patterns ready for promotion from project→global scope."""
        return [p for p in self._patterns.values()
                if not p.promoted_to_global
                and p.status == "active"
                and len(p.source_projects) >= min_projects
                and p.confidence >= min_confidence]

    def promote_to_global(self, pattern_id: str) -> bool:
        """Promote a project pattern to global knowledge."""
        p = self._patterns.get(pattern_id)
        if not p or p.promoted_to_global:
            return False
        try:
            global_lib = PatternLibrary(global_scope=True)
            global_lib.add(
                name=p.name, category=p.category,
                description=p.description, solution=p.solution,
                context=p.context, examples=p.examples,
                tags=p.tags, confidence=p.confidence * 0.9,  # slight reduction for safety
                source_project="global",
            )
            p.promoted_to_global = True
            p.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._save()
            logger.info("Pattern promoted to global: %s", pattern_id)
            return True
        except Exception as e:
            logger.warning("Promotion failed: %s", e)
            return False

    def promote_all_ready(self) -> int:
        """Promote all ready patterns. Returns count."""
        ready = self.get_promotable()
        count = 0
        for p in ready:
            if self.promote_to_global(p.id):
                count += 1
        return count

    # ── Stats ─────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        ps = list(self._patterns.values())
        active = [p for p in ps if p.status == "active"]
        return {
            "total": len(ps),
            "active": len(active),
            "deprecated": sum(1 for p in ps if p.status == "deprecated"),
            "promoted": sum(1 for p in ps if p.promoted_to_global),
            "avg_confidence": sum(p.confidence for p in active) / len(active) if active else 0,
            "avg_usage": sum(p.usage_count for p in active) / len(active) if active else 0,
            "categories": {c: sum(1 for p in active if p.category == c)
                           for c in set(p.category for p in active)},
        }

    @property
    def count(self) -> int:
        return len(self._patterns)

    def list_all(self) -> list[Pattern]:
        return list(self._patterns.values())


# ═══════════════════════════════════════════════════════════════
# Unified access: project + global
# ═══════════════════════════════════════════════════════════════

class UnifiedPatternStore:
    """Queries both project-local and global pattern libraries."""

    def __init__(self, project_dir: str | Path | None = None):
        self.local = PatternLibrary(project_dir, global_scope=False)
        self.global_ = PatternLibrary(global_scope=True)

    def search(self, query: str = "", category: str = "", tags: list[str] | None = None,
               min_confidence: float = 0.3, limit: int = 20) -> list[Pattern]:
        """Search both stores, local first (higher priority)."""
        local_results = self.local.search(query, category, tags, min_confidence, limit)
        global_results = self.global_.search(query, category, tags, min_confidence, limit)
        seen = {p.id for p in local_results}
        combined = list(local_results)
        for p in global_results:
            if p.id not in seen:
                combined.append(p)
                seen.add(p.id)
        combined.sort(key=lambda x: (x.confidence * 0.5 + x.success_rate * 0.5), reverse=True)
        return combined[:limit]

    def get_context_for_prompt(self, query: str = "", max_patterns: int = 10) -> str:
        """Build a context snippet for system prompt injection."""
        patterns = self.search(query=query, min_confidence=0.5, limit=max_patterns)
        if not patterns:
            return ""
        lines = ["<proven_patterns>"]
        for p in patterns:
            source = "🌍" if p.promoted_to_global else "📁"
            lines.append(f"- [{p.category}] {p.name}: {p.solution[:120]} "
                         f"({source} conf={p.confidence:.2f}, used={p.usage_count}x)")
        lines.append("</proven_patterns>")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Project Template Scaffolding
# ═══════════════════════════════════════════════════════════════

@dataclass
class ProjectTemplate:
    """A reusable project scaffold with files, dependencies, and instructions.

    Small models benefit from templates because they:
      1. Eliminate boilerplate decisions (folder layout, config files)
      2. Provide a validated starting point that always compiles
      3. Include known-good dependency versions and patterns
    """
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)  # path -> content
    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    post_init_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectTemplate":
        field_names = list(cls.__dataclass_fields__)
        kwargs: dict[str, Any] = {}
        for key in field_names:
            if key in d:
                kwargs[key] = d[key]
        return cls(**kwargs)


class TemplateRegistry:
    """Registry of project templates for scaffolding new projects."""

    def __init__(self):
        self._templates: dict[str, ProjectTemplate] = {}
        self._register_builtins()

    def _register_builtins(self):
        """Register built-in templates."""
        self.register(self._fastapi_sqlalchemy_template())
        self.register(self._nextjs_prisma_template())
        self.register(self._python_cli_template())

    def register(self, template: ProjectTemplate):
        self._templates[template.name] = template

    def get(self, name: str) -> ProjectTemplate | None:
        return self._templates.get(name)

    def search(self, query: str = "", tags: list[str] | None = None) -> list[ProjectTemplate]:
        results = []
        q = query.lower()
        for t in self._templates.values():
            if q and q not in t.name.lower() and q not in t.description.lower():
                continue
            if tags and not any(tag in t.tags for tag in tags):
                continue
            results.append(t)
        return results

    @property
    def list_all(self) -> list[ProjectTemplate]:
        return list(self._templates.values())

    # ── Built-in templates ─────────────────────────────────

    def _fastapi_sqlalchemy_template(self) -> ProjectTemplate:
        return ProjectTemplate(
            name="fastapi-sqlalchemy",
            description="FastAPI + SQLAlchemy async with Alembic migrations",
            tags=["api", "web", "database", "python"],
            dependencies=[
                "fastapi>=0.110.0", "uvicorn[standard]>=0.27.0",
                "sqlalchemy[asyncio]>=2.0.25", "alembic>=1.13.0",
                "pydantic>=2.5.0", "pydantic-settings>=2.1.0",
            ],
            dev_dependencies=[
                "pytest>=8.0.0", "pytest-asyncio>=0.23.0",
                "httpx>=0.26.0", "ruff>=0.1.0",
            ],
            files={
                "app/__init__.py": "",
                "app/main.py": (
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI(title=\"My API\")\n\n\n"
                    "@app.get(\"/health\")\n"
                    "async def health():\n"
                    '    return {"status": "ok"}\n'
                ),
                "app/database.py": (
                    "from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker\n\n"
                    "DATABASE_URL = \"sqlite+aiosqlite:///./db.sqlite3\"\n"
                    "engine = create_async_engine(DATABASE_URL)\n"
                    "AsyncSessionLocal = async_sessionmaker(engine)\n"
                ),
                "app/models.py": (
                    "from sqlalchemy.orm import DeclarativeBase\n\n\n"
                    "class Base(DeclarativeBase):\n"
                    "    pass\n"
                ),
                "app/schemas.py": (
                    "from pydantic import BaseModel\n\n\n"
                    "class Message(BaseModel):\n"
                    "    content: str\n"
                ),
                "tests/__init__.py": "",
                "tests/test_health.py": (
                    "from httpx import AsyncClient, ASGITransport\n"
                    "from app.main import app\n\n\n"
                    "async def test_health():\n"
                    "    transport = ASGITransport(app=app)\n"
                    "    async with AsyncClient(transport=transport, base_url=\"http://test\") as cl:\n"
                    "        r = await cl.get(\"/health\")\n"
                    "    assert r.status_code == 200\n"
                    '    assert r.json() == {"status": "ok"}\n'
                ),
                "alembic.ini": (
                    "[alembic]\n"
                    "script_location = alembic\n"
                    "sqlalchemy.url = sqlite+aiosqlite:///./db.sqlite3\n"
                ),
                "pyproject.toml": (
                    "[project]\n"
                    'name = "my-api"\n'
                    'version = "0.1.0"\n'
                    'requires-python = ">=3.11"\n'
                ),
            },
            post_init_commands=[
                "alembic init alembic",
                "alembic revision --autogenerate -m init",
                "alembic upgrade head",
            ],
        )

    def _nextjs_prisma_template(self) -> ProjectTemplate:
        return ProjectTemplate(
            name="nextjs-prisma",
            description="Next.js 14 App Router + Prisma ORM + Tailwind CSS",
            tags=["web", "frontend", "database", "typescript"],
            dependencies=[
                "next@14", "react@18", "react-dom@18",
                "@prisma/client@5", "prisma@5",
            ],
            dev_dependencies=[
                "typescript@5", "@types/react@18", "@types/node@20",
                "tailwindcss@3", "postcss", "autoprefixer",
            ],
            files={
                "prisma/schema.prisma": (
                    "generator client {\n"
                    "  provider = \"prisma-client-js\"\n"
                    "}\n\n"
                    "datasource db {\n"
                    "  provider = \"sqlite\"\n"
                    "  url      = env(\"DATABASE_URL\")\n"
                    "}\n\n"
                    'model User {\n'
                    '  id        String   @id @default(cuid())\n'
                    '  email     String   @unique\n'
                    '  name      String?\n'
                    '  createdAt DateTime @default(now())\n'
                    "}\n"
                ),
                "src/app/page.tsx": (
                    "export default function Home() {\n"
                    "  return <main><h1>Hello World</h1></main>\n"
                    "}\n"
                ),
                "src/app/api/health/route.ts": (
                    "import { NextResponse } from 'next/server'\n\n"
                    "export async function GET() {\n"
                    '  return NextResponse.json({ status: "ok" })\n'
                    "}\n"
                ),
                "package.json": (
                    '{\n'
                    '  "name": "my-app",\n'
                    '  "version": "0.1.0",\n'
                    '  "scripts": {\n'
                    '    "dev": "next dev",\n'
                    '    "build": "next build",\n'
                    '    "start": "next start"\n'
                    '  }\n'
                    '}\n'
                ),
                "tsconfig.json": (
                    '{\n'
                    '  "compilerOptions": {\n'
                    '    "target": "es2017",\n'
                    '    "lib": ["dom", "dom.iterable", "esnext"],\n'
                    '    "module": "esnext",\n'
                    '    "moduleResolution": "bundler",\n'
                    '    "jsx": "preserve",\n'
                    '    "strict": true\n'
                    '  },\n'
                    '  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"]\n'
                    '}\n'
                ),
            },
            post_init_commands=[
                "npx prisma generate",
                "npx prisma db push",
            ],
        )

    def _python_cli_template(self) -> ProjectTemplate:
        return ProjectTemplate(
            name="python-cli",
            description="Python CLI app with argparse, structured logging, and tests",
            tags=["cli", "python", "tool"],
            dependencies=[],
            dev_dependencies=["pytest>=8.0.0", "ruff>=0.1.0"],
            files={
                "src/cli.py": (
                    "import argparse\n\n\n"
                    "def main():\n"
                    '    parser = argparse.ArgumentParser(description="My CLI")\n'
                    '    parser.add_argument("--name", default="world")\n'
                    "    args = parser.parse_args()\n"
                    '    print(f"Hello, {args.name}!")\n\n\n'
                    'if __name__ == "__main__":\n'
                    "    main()\n"
                ),
                "src/__init__.py": "",
                "tests/test_cli.py": (
                    "from src.cli import main\n\n\n"
                    "def test_main():\n"
                    "    assert main() is None\n"
                ),
                "pyproject.toml": (
                    "[project]\n"
                    'name = "my-cli"\n'
                    'version = "0.1.0"\n'
                    'requires-python = ">=3.11"\n'
                    '[project.scripts]\n'
                    'my-cli = "src.cli:main"\n'
                ),
            },
        )
