"""File tree — display project structure as a tree."""

import json
from pathlib import Path
from typing import Any

from ..safety import is_safe_path


def _file_tree(path: str | None = None, depth: int = 3,
               include: str | None = None, format: str = "text") -> str:
    """Display project file tree structure."""
    root = Path(path) if path else Path(".")
    if not is_safe_path(root):
        return f"Sandbox: tree in {path} denied"

    if format == "json":
        return json.dumps(_build_tree(root, depth, include), indent=2, ensure_ascii=False)

    lines = [f"📁 {root.name}/"]
    _render_tree(root, "", depth, include, lines)
    return "\n".join(lines)


def _build_tree(dirpath: Path, max_depth: int, include: str | None) -> dict:
    """Build a JSON tree structure."""
    result: dict[str, Any] = {"name": dirpath.name, "type": "directory", "children": []}
    if max_depth <= 0:
        return result
    try:
        for entry in sorted(dirpath.iterdir()):
            if entry.name.startswith(".") and entry.name not in (".git", ".github"):
                continue
            if entry.name == "__pycache__":
                continue
            if entry.name.startswith("node_modules"):
                continue
            if entry.is_dir():
                child = _build_tree(entry, max_depth - 1, include)
                result["children"].append(child)
            elif entry.is_file():
                if include and not entry.match(include):
                    continue
                result["children"].append({
                    "name": entry.name,
                    "type": "file",
                    "size": entry.stat().st_size,
                })
    except PermissionError:
        pass
    return result


def _render_tree(dirpath: Path, prefix: str, max_depth: int, include: str | None, lines: list):
    if max_depth <= 0:
        lines.append(f"{prefix}  └── ...")
        return
    try:
        entries = sorted(dirpath.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        entries = [e for e in entries if not e.name.startswith(".") or e.name == ".git"]
        entries = [e for e in entries if e.name not in ("__pycache__", "node_modules")]
        if include:
            entries = [e for e in entries if e.is_dir() or e.match(include)]
    except PermissionError:
        return

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        if entry.is_dir():
            lines.append(f"{prefix}{connector}📁 {entry.name}/")
            extension = "    " if is_last else "│   "
            _render_tree(entry, prefix + extension, max_depth - 1, include, lines)
        else:
            try:
                size = entry.stat().st_size
                size_str = f" ({size} bytes)" if size < 1024 else f" ({size//1024} KB)" if size < 1048576 else f" ({size//1048576} MB)"
            except Exception:
                size_str = ""
            lines.append(f"{prefix}{connector}📄 {entry.name}{size_str}")
