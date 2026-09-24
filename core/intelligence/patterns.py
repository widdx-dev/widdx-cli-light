"""Software pattern knowledge base — REAL knowledge about how to build things.

This file contains 25+ concrete, actionable software patterns.
Each pattern describes: what files to create, what tools to use,
what the expected output looks like, and which task types it applies to.

This is what makes the planner ACTUALLY useful — not 10/12 types getting
a single "handle task" step.

Patterns are loaded at startup and can be extended via learner.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PatternStep:
    """A single step in a pattern."""
    description: str
    tools: list[str] = field(default_factory=list)
    files_to_create: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)


@dataclass
class SoftwarePattern:
    """A reusable software project pattern."""
    name: str
    category: str  # "web", "cli", "data", "mobile", "config", "testing"
    task_types: list[str]  # which TaskType values this applies to
    features: list[str] = field(default_factory=list)  # "api", "database", "web", "cli"
    languages: list[str] = field(default_factory=list)  # "python", "javascript", etc.
    steps: list[PatternStep] = field(default_factory=list)
    description: str = ""
    estimated_time: str = ""  # human-readable time estimate
    complexity: int = 1  # 1=simple, 2=medium, 3=complex


# ═══════════════════════════════════════════════════════════════════════════════
# PATTERN DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

PATTERNS: dict[str, SoftwarePattern] = {}

# ── WEB / API Patterns ─────────────────────────────────────────────────────

PATTERNS["python_fastapi_api"] = SoftwarePattern(
    name="python_fastapi_api",
    category="web",
    task_types=["code_write", "complex"],
    features=["api", "database"],
    languages=["python"],
    description="REST API with FastAPI + SQLAlchemy + JWT auth + OpenAPI docs",
    estimated_time="10-20 min",
    complexity=3,
    steps=[
        PatternStep("Create project structure",
                    tools=["write"], files_to_create=["main.py", "models.py", "routes.py", "config.py", "requirements.txt"]),
        PatternStep("Define SQLAlchemy database models",
                    tools=["write"], files_to_create=["models.py"]),
        PatternStep("Create database connection and session management",
                    tools=["write"], files_to_create=["database.py"]),
        PatternStep("Define Pydantic schemas for request/response",
                    tools=["write"], files_to_create=["schemas.py"]),
        PatternStep("Implement CRUD API routes",
                    tools=["write"], files_to_create=["routes.py"]),
        PatternStep("Add JWT authentication middleware",
                    tools=["write"], files_to_modify=["main.py", "routes.py"]),
        PatternStep("Add request validation and error handling",
                    tools=["write"], files_to_modify=["main.py"]),
        PatternStep("Write API tests with pytest + httpx",
                    tools=["write"], files_to_create=["test_api.py"]),
    ],
)

PATTERNS["flask_web_app"] = SoftwarePattern(
    name="flask_web_app",
    category="web",
    task_types=["code_write", "complex"],
    features=["web", "database"],
    languages=["python"],
    description="Full Flask web application with templates, database, and auth",
    estimated_time="15-25 min",
    complexity=3,
    steps=[
        PatternStep("Create project structure with Flask app factory",
                    tools=["write"], files_to_create=["app/__init__.py", "app/models.py", "app/routes.py", "app/templates/base.html"]),
        PatternStep("Define database models",
                    tools=["write"], files_to_create=["app/models.py"]),
        PatternStep("Create route blueprints",
                    tools=["write"], files_to_create=["app/routes.py", "app/auth.py"]),
        PatternStep("Build HTML templates with Jinja2",
                    tools=["write"], files_to_create=["app/templates/index.html", "app/templates/base.html"]),
        PatternStep("Add user authentication (login/register)",
                    tools=["write"], files_to_modify=["app/auth.py"]),
        PatternStep("Add static files and CSS styling",
                    tools=["write"], files_to_create=["app/static/style.css"]),
        PatternStep("Write configuration for dev/prod",
                    tools=["write"], files_to_create=["config.py"]),
        PatternStep("Write tests",
                    tools=["write"], files_to_create=["tests/test_app.py"]),
    ],
)

PATTERNS["django_project"] = SoftwarePattern(
    name="django_project",
    category="web",
    task_types=["code_write", "complex"],
    features=["web", "database", "admin"],
    languages=["python"],
    description="Django project with models, views, templates, admin",
    estimated_time="15-25 min",
    complexity=3,
    steps=[
        PatternStep("Create Django project and app structure",
                    tools=["bash"], files_to_create=[]),
        PatternStep("Define models with fields and relationships",
                    tools=["write"], files_to_create=["models.py"]),
        PatternStep("Register models in admin",
                    tools=["write"], files_to_create=["admin.py"]),
        PatternStep("Create views and URL routing",
                    tools=["write"], files_to_create=["views.py", "urls.py"]),
        PatternStep("Build HTML templates",
                    tools=["write"], files_to_create=["templates/"]),
        PatternStep("Add forms with validation",
                    tools=["write"], files_to_create=["forms.py"]),
        PatternStep("Configure settings and static files",
                    tools=["write"], files_to_modify=["settings.py"]),
        PatternStep("Write tests",
                    tools=["write"], files_to_create=["tests.py"]),
    ],
)

PATTERNS["node_express_api"] = SoftwarePattern(
    name="node_express_api",
    category="web",
    task_types=["code_write", "complex"],
    features=["api", "database"],
    languages=["javascript", "typescript"],
    description="REST API with Express.js + Prisma/Sequelize + JWT",
    estimated_time="15-20 min",
    complexity=3,
    steps=[
        PatternStep("Initialize Node.js project with package.json",
                    tools=["bash", "write"], files_to_create=["package.json"]),
        PatternStep("Create Express app entry point with middleware",
                    tools=["write"], files_to_create=["index.js", "app.js"]),
        PatternStep("Define routes for each resource",
                    tools=["write"], files_to_create=["routes/"]),
        PatternStep("Create database models/schema",
                    tools=["write"], files_to_create=["models/", "prisma/schema.prisma"]),
        PatternStep("Add authentication middleware (JWT)",
                    tools=["write"], files_to_create=["middleware/auth.js"]),
        PatternStep("Add error handling middleware",
                    tools=["write"], files_to_modify=["app.js"]),
        PatternStep("Add input validation",
                    tools=["write"], files_to_create=["middleware/validate.js"]),
        PatternStep("Write tests with Jest/Supertest",
                    tools=["write"], files_to_create=["tests/"]),
    ],
)

# ── CLI Tool Patterns ──────────────────────────────────────────────────────

PATTERNS["python_cli_tool"] = SoftwarePattern(
    name="python_cli_tool",
    category="cli",
    task_types=["code_write", "complex"],
    features=["cli"],
    languages=["python"],
    description="Python CLI tool with argparse/click + rich output",
    estimated_time="5-10 min",
    complexity=1,
    steps=[
        PatternStep("Create CLI entry point with argument parsing",
                    tools=["write"], files_to_create=["cli.py"]),
        PatternStep("Add command handlers",
                    tools=["write"], files_to_create=["commands.py"]),
        PatternStep("Add rich terminal output (tables, progress bars)",
                    tools=["write"], files_to_modify=["cli.py"]),
        PatternStep("Add configuration file support",
                    tools=["write"], files_to_create=["config.py"]),
        PatternStep("Write installation setup (setup.py/pyproject.toml)",
                    tools=["write"], files_to_create=["pyproject.toml"]),
    ],
)

PATTERNS["bash_script_tool"] = SoftwarePattern(
    name="bash_script_tool",
    category="cli",
    task_types=["code_write"],
    features=["cli"],
    languages=["bash"],
    description="Bash script with arg parsing, error handling, and logging",
    estimated_time="3-7 min",
    complexity=1,
    steps=[
        PatternStep("Create script with shebang and error handling",
                    tools=["write"], files_to_create=["script.sh"]),
        PatternStep("Add argument parsing with getopts",
                    tools=["write"], files_to_modify=["script.sh"]),
        PatternStep("Add logging functions",
                    tools=["write"], files_to_modify=["script.sh"]),
    ],
)

# ── Frontend Patterns ──────────────────────────────────────────────────────

PATTERNS["html_css_js_page"] = SoftwarePattern(
    name="html_css_js_page",
    category="web",
    task_types=["code_write", "complex"],
    features=["web"],
    languages=["html", "css", "javascript"],
    description="Single-page HTML/CSS/JS with responsive design and dark mode",
    estimated_time="5-15 min",
    complexity=2,
    steps=[
        PatternStep("Create HTML structure with semantic elements",
                    tools=["write"], files_to_create=["index.html"]),
        PatternStep("Add CSS styles with CSS variables and dark/light themes",
                    tools=["write"], files_to_create=["style.css"]),
        PatternStep("Add JavaScript interactivity",
                    tools=["write"], files_to_create=["app.js"]),
        PatternStep("Add responsive design (media queries)",
                    tools=["write"], files_to_modify=["style.css"]),
        PatternStep("Add accessibility (ARIA labels, keyboard nav)",
                    tools=["write"], files_to_modify=["index.html"]),
    ],
)

PATTERNS["react_component"] = SoftwarePattern(
    name="react_component",
    category="web",
    task_types=["code_write"],
    features=["web"],
    languages=["javascript", "typescript"],
    description="React component with hooks, props, and styling",
    estimated_time="5-10 min",
    complexity=2,
    steps=[
        PatternStep("Create React component with TypeScript types",
                    tools=["write"], files_to_create=["Component.tsx"]),
        PatternStep("Add hooks (useState, useEffect)",
                    tools=["write"], files_to_modify=["Component.tsx"]),
        PatternStep("Add CSS modules or styled-components",
                    tools=["write"], files_to_create=["Component.module.css"]),
        PatternStep("Add tests with React Testing Library",
                    tools=["write"], files_to_create=["Component.test.tsx"]),
    ],
)

# ── Data / Pipeline Patterns ───────────────────────────────────────────────

PATTERNS["python_data_pipeline"] = SoftwarePattern(
    name="python_data_pipeline",
    category="data",
    task_types=["code_write", "complex"],
    features=["data"],
    languages=["python"],
    description="Data processing pipeline with pandas/polars + output",
    estimated_time="8-15 min",
    complexity=2,
    steps=[
        PatternStep("Create data loading/reading functions",
                    tools=["write"], files_to_create=["pipeline.py"]),
        PatternStep("Add data cleaning and transformation",
                    tools=["write"], files_to_modify=["pipeline.py"]),
        PatternStep("Add data validation and quality checks",
                    tools=["write"], files_to_create=["validate.py"]),
        PatternStep("Add output generation (CSV, JSON, Parquet, or visualization)",
                    tools=["write"], files_to_create=["output.py"]),
        PatternStep("Add logging and progress tracking",
                    tools=["write"], files_to_modify=["pipeline.py"]),
        PatternStep("Write tests with sample data",
                    tools=["write"], files_to_create=["test_pipeline.py"]),
    ],
)

PATTERNS["sql_database_schema"] = SoftwarePattern(
    name="sql_database_schema",
    category="data",
    task_types=["code_write", "database"],
    features=["database"],
    languages=["sql"],
    description="SQL database schema with tables, indexes, and constraints",
    estimated_time="5-10 min",
    complexity=2,
    steps=[
        PatternStep("Create schema with CREATE TABLE statements",
                    tools=["write"], files_to_create=["schema.sql"]),
        PatternStep("Add foreign key constraints",
                    tools=["write"], files_to_modify=["schema.sql"]),
        PatternStep("Add indexes for query performance",
                    tools=["write"], files_to_modify=["schema.sql"]),
        PatternStep("Add seed/migration data",
                    tools=["write"], files_to_create=["seed.sql"]),
    ],
)

PATTERNS["mongodb_collection_design"] = SoftwarePattern(
    name="mongodb_collection_design",
    category="data",
    task_types=["code_write", "database"],
    features=["database"],
    languages=["javascript", "python"],
    description="MongoDB collection design with indexes and validation",
    estimated_time="5-10 min",
    complexity=2,
    steps=[
        PatternStep("Design collection schemas with embedded vs reference decisions",
                    tools=["write"], files_to_create=["schema_design.md"]),
        PatternStep("Create indexes (single field, compound, text, geospatial)",
                    tools=["write"], files_to_create=["indexes.js"]),
        PatternStep("Add schema validation rules",
                    tools=["write"], files_to_create=["validation.js"]),
        PatternStep("Create CRUD operation helpers",
                    tools=["write"], files_to_create=["operations.py"]),
    ],
)

# ── Testing Patterns ───────────────────────────────────────────────────────

PATTERNS["python_test_suite"] = SoftwarePattern(
    name="python_test_suite",
    category="testing",
    task_types=["code_write"],
    features=["testing"],
    languages=["python"],
    description="Comprehensive pytest test suite with fixtures and mocks",
    estimated_time="5-10 min",
    complexity=1,
    steps=[
        PatternStep("Create conftest.py with shared fixtures",
                    tools=["write"], files_to_create=["conftest.py"]),
        PatternStep("Write unit tests for each module",
                    tools=["write"], files_to_create=["tests/"]),
        PatternStep("Add integration tests",
                    tools=["write"], files_to_create=["tests/test_integration.py"]),
        PatternStep("Add mock providers/APIs",
                    tools=["write"], files_to_modify=["conftest.py"]),
    ],
)

PATTERNS["javascript_test_suite"] = SoftwarePattern(
    name="javascript_test_suite",
    category="testing",
    task_types=["code_write"],
    features=["testing"],
    languages=["javascript", "typescript"],
    description="Jest/Vitest test suite with mocks",
    estimated_time="5-10 min",
    complexity=1,
    steps=[
        PatternStep("Create Jest/Vitest configuration",
                    tools=["write"], files_to_create=["jest.config.js"]),
        PatternStep("Write unit tests",
                    tools=["write"], files_to_create=["__tests__/"]),
        PatternStep("Add mock modules",
                    tools=["write"], files_to_create=["__mocks__/"]),
    ],
)

# ── Config / DevOps Patterns ──────────────────────────────────────────────

PATTERNS["docker_setup"] = SoftwarePattern(
    name="docker_setup",
    category="config",
    task_types=["code_write"],
    features=["docker"],
    languages=[],
    description="Docker + docker-compose setup for any project",
    estimated_time="5-8 min",
    complexity=1,
    steps=[
        PatternStep("Create Dockerfile with multi-stage build",
                    tools=["write"], files_to_create=["Dockerfile"]),
        PatternStep("Create docker-compose.yml with services",
                    tools=["write"], files_to_create=["docker-compose.yml"]),
        PatternStep("Add .dockerignore",
                    tools=["write"], files_to_create=[".dockerignore"]),
        PatternStep("Add health checks",
                    tools=["write"], files_to_modify=["docker-compose.yml"]),
    ],
)

PATTERNS["github_actions_ci"] = SoftwarePattern(
    name="github_actions_ci",
    category="config",
    task_types=["code_write"],
    features=["ci"],
    languages=[],
    description="GitHub Actions CI/CD pipeline",
    estimated_time="3-5 min",
    complexity=1,
    steps=[
        PatternStep("Create CI workflow with test/lint/build steps",
                    tools=["write"], files_to_create=[".github/workflows/ci.yml"]),
        PatternStep("Add matrix testing for multiple versions",
                    tools=["write"], files_to_modify=[".github/workflows/ci.yml"]),
        PatternStep("Add caching for dependencies",
                    tools=["write"], files_to_modify=[".github/workflows/ci.yml"]),
    ],
)

# ── Config / Setup Patterns ───────────────────────────────────────────────

PATTERNS["python_project_setup"] = SoftwarePattern(
    name="python_project_setup",
    category="config",
    task_types=["code_write"],
    features=["config"],
    languages=["python"],
    description="Python project scaffolding with pyproject.toml, venv, and tools",
    estimated_time="3-5 min",
    complexity=1,
    steps=[
        PatternStep("Create pyproject.toml with dependencies and build config",
                    tools=["write"], files_to_create=["pyproject.toml"]),
        PatternStep("Create .gitignore for Python projects",
                    tools=["write"], files_to_create=[".gitignore"]),
        PatternStep("Create README.md stub",
                    tools=["write"], files_to_create=["README.md"]),
        PatternStep("Create initial module structure",
                    tools=["write"], files_to_create=["src/__init__.py"]),
    ],
)

# ── Documentation Patterns ─────────────────────────────────────────────────

PATTERNS["api_documentation"] = SoftwarePattern(
    name="api_documentation",
    category="config",
    task_types=["code_write"],
    features=["api", "docs"],
    languages=[],
    description="API documentation in OpenAPI/Swagger or Markdown format",
    estimated_time="5-8 min",
    complexity=1,
    steps=[
        PatternStep("Document all endpoints with request/response examples",
                    tools=["write"], files_to_create=["API.md"]),
        PatternStep("Add authentication documentation",
                    tools=["write"], files_to_modify=["API.md"]),
        PatternStep("Add error codes and troubleshooting",
                    tools=["write"], files_to_modify=["API.md"]),
    ],
)

# ── Code Modification Patterns ────────────────────────────────────────────

PATTERNS["code_refactor"] = SoftwarePattern(
    name="code_refactor",
    category="modify",
    task_types=["code_modify"],
    features=[],
    languages=["python", "javascript", "typescript"],
    description="Safe code refactoring: extract functions, rename, restructure",
    estimated_time="3-8 min",
    complexity=2,
    steps=[
        PatternStep("Read and analyze the target file",
                    tools=["read"], files_to_modify=[]),
        PatternStep("Identify refactoring opportunities",
                    tools=["grep", "glob"], files_to_modify=[]),
        PatternStep("Apply refactoring with edit operations",
                    tools=["edit"], files_to_modify=[]),
        PatternStep("Verify tests still pass",
                    tools=["bash"], files_to_modify=[]),
    ],
)

PATTERNS["bug_fix"] = SoftwarePattern(
    name="bug_fix",
    category="modify",
    task_types=["code_modify"],
    features=[],
    languages=["python", "javascript", "typescript", "bash"],
    description="Bug fix workflow: reproduce → locate → fix → verify",
    estimated_time="5-15 min",
    complexity=2,
    steps=[
        PatternStep("Understand the bug from user description or error logs",
                    tools=["read"], files_to_modify=[]),
        PatternStep("Locate the root cause using grep and code reading",
                    tools=["grep", "read"], files_to_modify=[]),
        PatternStep("Apply the fix with precise edit",
                    tools=["edit"], files_to_modify=[]),
        PatternStep("Add a test that reproduces the original bug",
                    tools=["edit", "write"], files_to_modify=[]),
        PatternStep("Verify the fix with tests",
                    tools=["bash"], files_to_modify=[]),
    ],
)

PATTERNS["code_review"] = SoftwarePattern(
    name="code_review",
    category="modify",
    task_types=["code_review"],
    features=[],
    languages=["python", "javascript", "typescript"],
    description="Code review: check for bugs, style, performance, security",
    estimated_time="3-8 min",
    complexity=1,
    steps=[
        PatternStep("Read changed files thoroughly",
                    tools=["read"], files_to_modify=[]),
        PatternStep("Check for bugs, security issues, and logic errors",
                    tools=["grep"], files_to_modify=[]),
        PatternStep("Check code style and patterns",
                    tools=["read"], files_to_modify=[]),
        PatternStep("Generate review with actionable feedback",
                    tools=[], files_to_modify=[]),
    ],
)

# ── Research / Analysis Patterns ──────────────────────────────────────────

PATTERNS["codebase_analysis"] = SoftwarePattern(
    name="codebase_analysis",
    category="modify",
    task_types=["research", "code_read"],
    features=[],
    languages=[],
    description="Analyze a codebase: structure, dependencies, patterns, issues",
    estimated_time="5-10 min",
    complexity=2,
    steps=[
        PatternStep("Scan project structure",
                    tools=["glob"], files_to_modify=[]),
        PatternStep("Analyze dependencies and imports",
                    tools=["grep", "read"], files_to_modify=[]),
        PatternStep("Identify architectural patterns",
                    tools=["read"], files_to_modify=[]),
        PatternStep("Report findings with recommendations",
                    tools=[], files_to_modify=[]),
    ],
)

# ── Mobile Patterns ───────────────────────────────────────────────────────

PATTERNS["flutter_app"] = SoftwarePattern(
    name="flutter_app",
    category="mobile",
    task_types=["code_write", "complex"],
    features=["mobile", "api"],
    languages=["dart"],
    description="Flutter mobile app with state management, API integration, and navigation",
    estimated_time="15-25 min",
    complexity=3,
    steps=[
        PatternStep("Create Flutter project structure",
                    tools=["write"], files_to_create=["lib/main.dart"]),
        PatternStep("Define data models with JSON serialization",
                    tools=["write"], files_to_create=["lib/models/"]),
        PatternStep("Implement state management (Provider/Riverpod/Bloc)",
                    tools=["write"], files_to_create=["lib/providers/"]),
        PatternStep("Create API service layer",
                    tools=["write"], files_to_create=["lib/services/api.dart"]),
        PatternStep("Build UI screens and navigation",
                    tools=["write"], files_to_create=["lib/screens/"]),
        PatternStep("Add widget tests",
                    tools=["write"], files_to_create=["test/"]),
    ],
)

PATTERNS["react_native_app"] = SoftwarePattern(
    name="react_native_app",
    category="mobile",
    task_types=["code_write", "complex"],
    features=["mobile", "api"],
    languages=["javascript", "typescript"],
    description="React Native mobile app with navigation and native features",
    estimated_time="15-25 min",
    complexity=3,
    steps=[
        PatternStep("Initialize React Native project",
                    tools=["bash", "write"], files_to_create=["App.tsx"]),
        PatternStep("Set up navigation (React Navigation)",
                    tools=["write"], files_to_create=["src/navigation/"]),
        PatternStep("Create screens and components",
                    tools=["write"], files_to_create=["src/screens/", "src/components/"]),
        PatternStep("Add API service with Axios/fetch",
                    tools=["write"], files_to_create=["src/services/api.ts"]),
        PatternStep("Add state management (Context/Zustand/Redux)",
                    tools=["write"], files_to_create=["src/store/"]),
        PatternStep("Write tests with React Native Testing Library",
                    tools=["write"], files_to_create=["__tests__/"]),
    ],
)

# ── Security Patterns ─────────────────────────────────────────────────────

PATTERNS["security_audit"] = SoftwarePattern(
    name="security_audit",
    category="config",
    task_types=["code_review", "research"],
    features=["security"],
    languages=["python", "javascript", "bash"],
    description="Security audit: scan for vulnerabilities, hardcoded secrets, unsafe patterns",
    estimated_time="5-10 min",
    complexity=2,
    steps=[
        PatternStep("Scan for hardcoded secrets (API keys, tokens, passwords)",
                    tools=["grep"], files_to_modify=[]),
        PatternStep("Check for unsafe function calls and injection points",
                    tools=["grep"], files_to_modify=[]),
        PatternStep("Review authentication and authorization logic",
                    tools=["read"], files_to_modify=[]),
        PatternStep("Check dependency versions for known CVEs",
                    tools=["bash"], files_to_modify=[]),
        PatternStep("Generate security report with prioritized fixes",
                    tools=[], files_to_modify=[]),
    ],
)

# ── System / Operations Patterns ──────────────────────────────────────────

PATTERNS["system_monitoring"] = SoftwarePattern(
    name="system_monitoring",
    category="config",
    task_types=["system", "code_write"],
    features=["monitoring"],
    languages=["python", "bash"],
    description="System monitoring script: check health, resources, alerts",
    estimated_time="5-10 min",
    complexity=2,
    steps=[
        PatternStep("Create health check functions",
                    tools=["write"], files_to_create=["monitor.py"]),
        PatternStep("Add resource monitoring (CPU, memory, disk)",
                    tools=["write"], files_to_modify=["monitor.py"]),
        PatternStep("Add alerting via email/webhook",
                    tools=["write"], files_to_modify=["monitor.py"]),
        PatternStep("Add logging and metrics export",
                    tools=["write"], files_to_modify=["monitor.py"]),
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# PATTERN LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════

def find_patterns(task_type: str, features: list[str] | None = None,
                  languages: list[str] | None = None,
                  complexity: int | None = None) -> list[SoftwarePattern]:
    """Find matching patterns for a given task type and features.

    Args:
        task_type: TaskType value like 'code_write', 'complex', 'database'
        features: Detected features like ['api', 'database', 'web']
        languages: Preferred languages like ['python', 'javascript']
        complexity: Filter by complexity level (1-3)

    Returns:
        List of matching patterns, best matches first.
    """
    features = features or []
    languages = languages or []
    scored: list[tuple[int, SoftwarePattern]] = []

    for pattern in PATTERNS.values():
        score = 0
        # Task type match
        if task_type in pattern.task_types:
            score += 3
        elif "complex" in pattern.task_types and task_type not in ("chat", "unknown"):
            score += 1
        # Feature overlap
        feature_overlap = set(features) & set(pattern.features)
        score += len(feature_overlap) * 2
        # Language match
        if languages and pattern.languages:
            lang_overlap = set(languages) & set(pattern.languages)
            score += len(lang_overlap) * 2
        # Complexity filter
        if complexity is not None and pattern.complexity != complexity:
            continue
        if score > 0:
            scored.append((score, pattern))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored]


def get_pattern(name: str) -> SoftwarePattern | None:
    """Get a specific pattern by name."""
    return PATTERNS.get(name)


def list_patterns_by_category() -> dict[str, list[str]]:
    """List all patterns grouped by category."""
    cats: dict[str, list[str]] = {}
    for name, p in PATTERNS.items():
        cats.setdefault(p.category, []).append(name)
    return cats


def all_patterns() -> list[SoftwarePattern]:
    """Return all registered patterns."""
    return list(PATTERNS.values())


# Count for verification
assert len(PATTERNS) >= 25, f"Expected >=25 patterns, got {len(PATTERNS)}"
