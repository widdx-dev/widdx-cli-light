"""Dependency graph — analyze imports and dependencies across the project."""
import logging


import ast
import re
import json
from pathlib import Path

from ..safety import is_safe_path
logger = logging.getLogger("widdx.dep_graph")


_PY_IMPORT_RE = re.compile(r'^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))')
_TS_IMPORT_RE = re.compile(r'(?:import|from)\s+["\']([^"\']+)["\']')
_C_IMPORT_RE = re.compile(r'#\s*include\s*[<"]([^>"]+)[>"]')


def _extract_imports(filepath: Path) -> list[str]:
    imports = []
    try:
        text = filepath.read_text("utf-8", errors="ignore")

        if filepath.suffix == ".py":
            try:
                tree = ast.parse(text, filename=str(filepath))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module.split(".")[0])
            except SyntaxError:
                for m in _PY_IMPORT_RE.finditer(text):
                    imports.append(m.group(1) or m.group(2))

        elif filepath.suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
            for m in _TS_IMPORT_RE.finditer(text):
                imp = m.group(1)
                if imp.startswith("."):
                    imp = str(filepath.parent / imp)
                imports.append(imp)

        elif filepath.suffix in (".c", ".h", ".cpp", ".hpp"):
            for m in _C_IMPORT_RE.finditer(text):
                imports.append(m.group(1))

        elif filepath.suffix == ".rs":
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("use ") or line.startswith("mod "):
                    imports.append(line.split()[1].split("::")[0])

        elif filepath.suffix == ".go":
            for m in re.finditer(r'"(?:[\w/]+/)?(\w+)"', text):
                imports.append(m.group(1))

    except Exception:
        pass

    return list(dict.fromkeys(imports))


def _dep_graph(path: str | None = None, include: str | None = None,
               depth: int = 2, format: str = "text") -> str:
    """Analyze import dependencies in the project."""
    root = Path(path) if path else Path(".")
    if not is_safe_path(root):
        return f"Sandbox: dep_graph in {path} denied"

    project_files = []
    files_iter = root.rglob(include) if include else root.rglob("*")
    for f in files_iter:
        if not f.is_file() or f.stat().st_size > 102400:
            continue
        if f.suffix in (".pyc", ".pyo", ".so", ".dll", ".dylib", ".bin", ".png", ".jpg", ".svg"):
            continue
        project_files.append(f)

    dep_map: dict[str, list[str]] = {}
    for f in sorted(project_files):
        try:
            rel = str(f.relative_to(root))
        except ValueError:
            continue
        imports = _extract_imports(f)
        if imports:
            dep_map[rel] = imports

    if format == "json":
        return json.dumps(dep_map, indent=2, ensure_ascii=False)

    buf = [f"📊 Dependency Graph — {len(dep_map)} file(s) with imports", ""]
    for filepath in sorted(dep_map, key=lambda x: -len(dep_map[x])):
        imports = dep_map[filepath]
        internal = [i for i in imports if any(str(f).replace(".py", "").endswith(i.replace("/", ".")) for f in project_files)]
        external = [i for i in imports if i not in internal]
        buf.append(f"  📄 {filepath}")
        if internal:
            buf.append(f"     └─ internal: {', '.join(internal[:5])}")
        if external:
            buf.append(f"     └─ external: {', '.join(external[:8])}")
        if len(imports) > 13:
            buf.append(f"     └─ ... and {len(imports) - 13} more")
        buf.append("")

    circular = _find_circular(dep_map)
    if circular:
        buf.append(f"⚠️  {len(circular)} circular dependency(ies) detected:")
        for cycle in circular[:5]:
            buf.append(f"  {' -> '.join(cycle)}")
        buf.append("")

    return "\n".join(buf)


def _find_circular(dep_map: dict[str, list[str]]) -> list[list[str]]:
    """Find circular dependencies using DFS."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    path_stack: list[str] = []

    def dfs(node: str, path_set: set):
        if node in path_set:
            idx = path_stack.index(node)
            cycles.append(path_stack[idx:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        path_stack.append(node)
        path_set.add(node)
        for neighbor in dep_map.get(node, []):
            dfs(neighbor, path_set)
        path_stack.pop()
        path_set.discard(node)

    for node in dep_map:
        dfs(node, set())
    return cycles
