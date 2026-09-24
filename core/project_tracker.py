"""Project Tracker — persistent project plan, design, tasks, and roadmap.

Stores four markdown files in ``.widdx/``:
  - **PLAN.md**    — current implementation plan (what's being worked on now)
  - **DESIGN.md**  — architecture decisions, design patterns, rationale
  - **TASKS.md**   — task list with status (todo / in-progress / done)
  - **ROADMAP.md** — milestones, progress, what's next

On startup these are loaded into system context so WIDDX always knows
where it is and what it's doing.  An ``update_project_doc`` tool lets the
AI update them as work progresses.
"""

from pathlib import Path
import logging

logger = logging.getLogger("widdx.project_tracker")

_DOC_NAMES = ("PLAN.md", "DESIGN.md", "TASKS.md", "ROADMAP.md")

_TEMPLATES: dict[str, str] = {
    "PLAN.md": """# Project Plan

> Auto-managed by WIDDX. Updated as the project evolves.

## Current Goal

*Describe what you're working on right now.*

## Implementation Steps

1. *Step 1 — description*
2. *Step 2 — description*
3. *Step 3 — description*

## Completed Milestones

- *Milestone 1*
""",
    "DESIGN.md": """# Design Decisions

> Architecture and design rationale, automatically tracked.

## Architecture

*Overall architecture description.*

## Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| *choice* | *why* | *date* |

## Data Flow

*How data moves through the system.*
""",
    "TASKS.md": """# Tasks

> Auto-managed by WIDDX. Update via `update_project_doc` tool.

## In Progress

- [ ] *Task description*

## Todo

- [ ] *Task description*

## Done

- [x] *Task description*
""",
    "ROADMAP.md": """# Roadmap

> Project milestones and progress, automatically tracked.

## Current Status

- **Phase:** *current phase*
- **Progress:** *0%*

## Milestones

- [ ] *Milestone 1*
- [ ] *Milestone 2*

## Completed

- *What was done*
""",
}


def _widdx_dir(project_dir: Path) -> Path:
    p = project_dir.resolve() / ".widdx"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ─── Initialisation ────────────────────────────────────────────────────────

def _detect_project_info(project_dir: Path) -> dict:
    """Auto-detect project name, type, dependencies from project files."""
    info = {
        "name": project_dir.name,
        "type": "unknown",
        "language": "unknown",
        "dependencies": [],
        "description": "",
    }

    pyproject = project_dir / "pyproject.toml"
    package_json = project_dir / "package.json"
    cargo = project_dir / "Cargo.toml"
    go_mod = project_dir / "go.mod"
    readme = project_dir / "README.md"

    if pyproject.exists():
        try:
            import tomllib
            data = tomllib.loads(pyproject.read_text("utf-8"))
            proj = data.get("project", {})
            info["name"] = proj.get("name", info["name"])
            info["description"] = proj.get("description", "")
            info["type"] = "python"
            info["language"] = "Python"
            info["dependencies"] = list(proj.get("dependencies", []))
        except Exception:
            logger.debug("Exception suppressed (line 129)")

    if package_json.exists():
        try:
            import json
            data = json.loads(package_json.read_text("utf-8"))
            info["name"] = data.get("name", info["name"])
            info["description"] = data.get("description", info["description"])
            info["type"] = "node"
            info["language"] = "JavaScript/TypeScript"
            deps = list(data.get("dependencies", {}).keys())
            dev_deps = list(data.get("devDependencies", {}).keys())
            info["dependencies"] = deps + dev_deps
        except Exception:
            logger.debug("Exception suppressed (line 143)")

    if cargo.exists():
        try:
            import tomllib
            data = tomllib.loads(cargo.read_text("utf-8"))
            pkg = data.get("package", {})
            info["name"] = pkg.get("name", info["name"])
            info["description"] = pkg.get("description", info["description"])
            info["type"] = "rust"
            info["language"] = "Rust"
        except Exception:
            logger.debug("Exception suppressed (line 155)")

    if go_mod.exists():
        for line in go_mod.read_text("utf-8").splitlines():
            if line.startswith("module "):
                info["name"] = line[7:].strip()
                info["type"] = "go"
                info["language"] = "Go"
                break

    if readme.exists():
        try:
            text = readme.read_text("utf-8", errors="ignore")[:500]
            if not info["description"]:
                info["description"] = text.split("\n")[0].strip("# \n\t\r")[:200]
        except Exception:
            logger.debug("Exception suppressed (line 171)")

    return info


def _populate_docs(project_dir: Path, info: dict):
    """Fill newly created docs with auto-detected project info."""
    wd = _widdx_dir(project_dir)
    name = info["name"]
    desc = info["description"] or f"A {info['language']} project"

    plan_path = wd / "PLAN.md"
    if plan_path.exists() and "Current Goal" in plan_path.read_text("utf-8"):
        plan_path.write_text(
            f"# Project Plan — {name}\n\n"
            f"> {desc}\n\n"
            f"## Current Goal\n\n"
            f"*Describe what you're working on right now.*\n\n"
            f"## Project Type\n\n"
            f"- Language: {info['language']}\n"
            f"- Type: {info['type']}\n"
            f"- Dependencies: {', '.join(info['dependencies'][:10]) or 'none detected yet'}\n\n"
            f"## Implementation Steps\n\n"
            f"1. *Step 1 — description*\n"
            f"2. *Step 2 — description*\n"
            f"3. *Step 3 — description*\n\n"
            f"## Completed Milestones\n\n"
            f"- *Milestone 1*\n",
            encoding="utf-8",
        )

    design_path = wd / "DESIGN.md"
    if design_path.exists() and "Key Decisions" in design_path.read_text("utf-8"):
        design_path.write_text(
            f"# Design Decisions — {name}\n\n"
            f"> {desc}\n\n"
            f"## Architecture\n\n"
            f"*Overall architecture description.*\n\n"
            f"## Key Decisions\n\n"
            f"| Decision | Rationale | Date |\n"
            f"|----------|-----------|------|\n"
            f"| *Initial project setup* | *Auto-detected from project files* | {__import__('datetime').datetime.now().strftime('%Y-%m-%d')} |\n\n"
            f"## Tech Stack\n\n"
            f"- Language: {info['language']}\n"
            f"- Dependencies: {', '.join(info['dependencies'][:15]) or 'none detected'}\n",
            encoding="utf-8",
        )

    tasks_path = wd / "TASKS.md"
    if tasks_path.exists() and "In Progress" in tasks_path.read_text("utf-8"):
        tasks_path.write_text(
            f"# Tasks — {name}\n\n"
            f"## In Progress\n\n"
            f"- [ ] *Task description*\n\n"
            f"## Todo\n\n"
            f"- [ ] *Task description*\n\n"
            f"## Done\n\n"
            f"- [x] *Initial project setup*\n",
            encoding="utf-8",
        )

    roadmap_path = wd / "ROADMAP.md"
    if roadmap_path.exists() and "Current Status" in roadmap_path.read_text("utf-8"):
        roadmap_path.write_text(
            f"# Roadmap — {name}\n\n"
            f"## Current Status\n\n"
            f"- **Phase:** Initial development\n"
            f"- **Progress:** 0%\n\n"
            f"## Milestones\n\n"
            f"- [ ] *Milestone 1*\n"
            f"- [ ] *Milestone 2*\n\n"
            f"## Completed\n\n"
            f"- *Project initialized*\n",
            encoding="utf-8",
        )


def ensure_docs(project_dir: Path) -> list[str]:
    """Create any missing doc files from templates and auto-populate them.

    Returns a list of doc names that were created (empty if all existed).
    """
    created: list[str] = []
    wd = _widdx_dir(project_dir)
    for name in _DOC_NAMES:
        path = wd / name
        if not path.exists():
            template = _TEMPLATES.get(name, f"# {name.replace('.md', '')}\n\n"
                                             f"Auto-managed by WIDDX.\n")
            path.write_text(template, encoding="utf-8")
            created.append(name)
    if created:
        logger.info("Created project docs: %s", ", ".join(created))
        info = _detect_project_info(project_dir)
        _populate_docs(project_dir, info)
        logger.info("Auto-populated project docs from detected project info")
    return created


# ─── Read ──────────────────────────────────────────────────────────────────

def load_docs(project_dir: Path) -> dict[str, str]:
    """Load all four doc files as a dict of ``{name: content}``.

    Missing files are silently skipped.
    """
    result: dict[str, str] = {}
    wd = _widdx_dir(project_dir)
    for name in _DOC_NAMES:
        path = wd / name
        if path.exists():
            try:
                result[name] = path.read_text(encoding="utf-8")
            except Exception as e:
                logger.debug("Failed to read %s: %s", name, e)
    return result


def build_context_block(project_dir: Path) -> str | None:
    """Build a ``[PROJECT DOCS]`` string for injection as system message.

    Returns None if no docs exist yet.
    Augmented with RAG-relevant project context when available.
    """
    docs = load_docs(project_dir)
    if not docs:
        return None

    lines: list[str] = []
    for name in _DOC_NAMES:
        content = docs.get(name, "").strip()
        if not content:
            continue
        # Use first line (title) as heading, next few non-empty lines as preview
        title_line = content.split("\n")[0].lstrip("#").strip()
        lines.append(f"\n=== {title_line} ===")
        # Keep the full content (it's all relevant context)
        body = content.strip()
        lines.append(body)

    # ── RAG augmentation: search project docs ─────────────────
    try:
        from core.rag import RAGStore
        rag = RAGStore(str(project_dir))
        # Build a query from the concatenated docs
        query = " ".join(docs.get(n, "")[:200] for n in _DOC_NAMES if docs.get(n, "").strip())
        if query:
            rags = rag.search(query, top_k=3)
            if rags:
                lines.append("\n=== RAG Context ===")
                for _score, doc in rags:
                    snippet = doc.get("content", "")[:300]
                    if snippet:
                        lines.append(f"  • {snippet}")
    except Exception:
        logger.debug("Exception suppressed (line 326)")

    if not lines:
        return None
    return "\n".join(lines)


# ─── Write ─────────────────────────────────────────────────────────────────

def update_doc(project_dir: Path, doc_name: str, content: str) -> bool:
    """Update one of the project docs.

    Args:
        project_dir: Project root.
        doc_name: One of ``PLAN.md``, ``DESIGN.md``, ``TASKS.md``, ``ROADMAP.md``.
        content: New markdown content.

    Returns:
        True on success, False if the doc name is invalid.
    """
    name = doc_name.strip()
    if name not in _DOC_NAMES:
        return False
    path = _widdx_dir(project_dir) / name
    try:
        path.write_text(content.strip() + "\n", encoding="utf-8")
        logger.info("Updated %s (%d chars)", name, len(content))
        return True
    except Exception as e:
        logger.warning("Failed to update %s: %s", name, e)
        return False


# ─── Tool definition for the AI ────────────────────────────────────────────

TOOL_DEFINITION = {
    "name": "update_project_doc",
    "description": (
        "Update the project's PLAN, DESIGN, TASKS, or ROADMAP. "
        "Use this when you make progress, change direction, complete tasks, "
        "or make design decisions — so WIDDX never loses track of the project."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doc": {
                "type": "string",
                "enum": ["PLAN.md", "DESIGN.md", "TASKS.md", "ROADMAP.md"],
                "description": "Which document to update",
            },
            "content": {
                "type": "string",
                "description": "Full new markdown content for the document",
            },
        },
        "required": ["doc", "content"],
    },
}


def handle_update_project_doc(doc: str, content: str) -> str:
    """Handler for the ``update_project_doc`` tool."""
    from pathlib import Path
    ok = update_doc(Path.cwd().resolve(), doc, content)
    if ok:
        return f"✅ Updated {doc}"
    return f"❌ Invalid doc name: {doc}. Use one of: {', '.join(_DOC_NAMES)}"
