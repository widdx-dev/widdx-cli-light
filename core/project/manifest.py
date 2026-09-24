"""MANIFEST.json generator — describes project structure for humans and AI."""
import logging


import re
import json
import ast
from pathlib import Path
logger = logging.getLogger("widdx.manifest")


ROOT = Path(__file__).parent.parent.parent

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".venv",
               "venv", "env", ".pytest_cache", ".widdx",
               ".idea", ".vscode", ".DS_Store"}
SKIP_FILES = {"__init__.py"}


def _extract_docstring(filepath: Path) -> str:
    """Extract the module-level docstring from a .py file."""
    try:
        text = filepath.read_text(encoding="utf-8")
        tree = ast.parse(text)
        doc = ast.get_docstring(tree)
        if doc:
            return doc.split("\n")[0].strip()
    except Exception:
        pass
    return ""


def _extract_frontmatter_desc(filepath: Path) -> str:
    """Extract description from markdown frontmatter."""
    try:
        text = filepath.read_text(encoding="utf-8")
        m = re.search(r"^description:\s*(.+)", text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""


def _walk() -> tuple[list[dict], list[dict]]:
    """Walk the project and return a list of file records."""
    files = []
    skills = []

    for child in sorted(ROOT.iterdir()):
        if child.name.startswith(".") or child.name in EXCLUDE_DIRS:
            continue
        rel = child.relative_to(ROOT)

        if child.is_dir() and child.name in ("core", "tui", "cli"):
            for f in sorted(child.rglob("*.py")):
                if f.name in SKIP_FILES or "__pycache__" in f.parts:
                    continue
                desc = _extract_docstring(f)
                files.append({
                    "path": str(f.relative_to(ROOT)).replace("\\", "/"),
                    "description": desc or "\u2014",
                })

        elif child.is_dir() and child.name == "skills":
            for skill_dir in sorted(child.iterdir()):
                if skill_dir.is_dir():
                    md = skill_dir / "skill.md"
                    if md.exists():
                        desc = _extract_frontmatter_desc(md)
                        skills.append({
                            "name": skill_dir.name,
                            "description": desc or "\u2014",
                        })

        elif child.suffix == ".py":
            desc = _extract_docstring(child)
            files.insert(0, {
                "path": str(rel).replace("\\", "/"),
                "description": desc or "\u2014",
            })

    files.sort(key=lambda x: x["path"])
    skills.sort(key=lambda x: x["name"])
    return files, skills


def generate_manifest():
    """Scan the project and write MANIFEST.json to the root."""
    files, skills = _walk()
    manifest = {
        "project": "WIDDX Nexus",
        "language": "Python 3.12",
        "files": files,
        "skills": skills,
    }
    dest = ROOT / "MANIFEST.json"
    dest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest
