"""Knowledge Graph — 4.0 #4.

Builds a graph of project entities (files, classes, functions, tables, APIs)
and their relationships (imports, calls, inherits, references).

Reuses RepoMapper's file scanning and symbol extraction.
Adds cross-file relationship tracking and graph queries.

Usage:
    from core.knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph()
    kg.build()
    related = kg.query("UserModel")
    path = kg.find_path("auth.py", "database.py")
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger("widdx.kg")


class KnowledgeGraph:
    """Project entity graph with nodes and edges."""

    def __init__(self, project_dir: str | Path | None = None):
        self._root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        self._nodes: dict[str, dict] = {}     # name → {type, file, line}
        self._edges: list[dict] = []           # {from, to, relation}
        self._built = False
        self._last_build: float = 0.0           # timestamp of last build
        self._cache_ttl: float = 30.0            # seconds before rebuild needed

    def build(self, force: bool = False) -> int:
        """Scan project and build the graph. Returns node count.

        Uses 30-second cache to avoid expensive rebuilds on rapid calls.
        Pass force=True to bypass cache.
        """
        import time as _time
        now = _time.time()
        if self._built and not force and (now - self._last_build < self._cache_ttl):
            return len(self._nodes)

        self._nodes.clear()
        self._edges.clear()

        try:
            # Walk project files directly (max depth 5 for performance)
            ignore = {".git", "__pycache__", ".pytest_cache", ".widdx",
                      "node_modules", ".venv", "venv", "env",
                      ".idea", ".vscode", ".mypy_cache", "build", "dist"}
            code_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
                         ".html", ".css", ".scss", ".sql", ".md", ".json",
                         ".yaml", ".yml", ".toml", ".sh", ".java", ".c", ".cpp", ".h"}

            for fp in self._root.rglob("*"):
                # Limit depth to avoid excessive traversal
                try:
                    rel = fp.relative_to(self._root)
                    if len(rel.parts) > 5:
                        continue
                except ValueError:
                    continue
                if fp.is_dir() or any(p in ignore for p in fp.parts):
                    continue
                if fp.suffix not in code_exts:
                    continue
                try:
                    fname = str(fp.relative_to(self._root))
                except ValueError:
                    continue
                self._nodes[fname] = {"type": "file", "file": fname}

                # Extract imports as edges for Python files
                if fp.suffix == ".py":
                    deps = self._get_python_imports(fp)
                    for dep in deps:
                        self._edges.append({"from": fname, "to": dep, "relation": "imports"})
                        if dep not in self._nodes:
                            self._nodes[dep] = {"type": "module", "file": dep}

                # Extract symbols
                symbols = self._get_symbols(str(fp))
                for sym in symbols:
                    node_id = f"{fname}::{sym['name']}"
                    self._nodes[node_id] = {"type": sym["type"], "file": fname, "name": sym["name"], "line": sym.get("line", 0)}
                    self._edges.append({"from": fname, "to": node_id, "relation": "contains"})

            self._built = True
            self._last_build = _time.time()
            logger.info("KnowledgeGraph built: %d nodes, %d edges", len(self._nodes), len(self._edges))
        except Exception as e:
            logger.warning("KnowledgeGraph build failed: %s", e)

        return len(self._nodes)

    def query(self, name: str) -> list[dict]:
        """Find all nodes and relations matching a name."""
        if not self._built:
            self.build()
        results = []
        q = name.lower()
        for node_id, data in self._nodes.items():
            if q in node_id.lower():
                # Find connected edges
                connected = [e for e in self._edges if e["from"] == node_id or e["to"] == node_id]
                results.append({"node": node_id, "data": data, "connections": len(connected), "edges": connected[:10]})
        return results

    def find_path(self, from_entity: str, to_entity: str) -> list[dict]:
        """BFS to find shortest path between two entities."""
        if not self._built:
            self.build()

        # Build adjacency list
        adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for e in self._edges:
            adj[e["from"]].append((e["to"], e["relation"]))
            adj[e["to"]].append((e["from"], f"reverse_{e['relation']}"))

        # Find matching nodes
        start_nodes = [n for n in self._nodes if from_entity.lower() in n.lower()]
        end_nodes = [n for n in self._nodes if to_entity.lower() in n.lower()]
        if not start_nodes or not end_nodes:
            return []

        # BFS from first matching start node
        from collections import deque
        start = start_nodes[0]
        end = end_nodes[0]
        visited = {start}
        queue: deque = deque([(start, [])])
        while queue:
            current, path = queue.popleft()
            if current == end:
                return path + [{"node": current, "relation": "target"}]
            for neighbor, relation in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [{"node": current, "relation": relation}]))
        return []

    def get_context_snippet(self, max_items: int = 20) -> str:
        """Return a compact graph summary for system prompt injection."""
        if not self._built:
            self.build()
        if not self._nodes:
            return ""

        lines = ["<knowledge_graph>"]
        lines.append(f"Project: {self._root.name}")
        lines.append(f"Files: {len([n for n in self._nodes.values() if n['type'] == 'file'])}")

        # Top files by connections
        conn_counts: defaultdict[str, int] = defaultdict(int)
        for e in self._edges:
            conn_counts[e["from"]] += 1
            conn_counts[e["to"]] += 1
        top_files = sorted(conn_counts.items(), key=lambda x: -x[1])[:10]
        for fname, count in top_files:
            if "/" in fname or "\\" in fname:
                lines.append(f"  {fname} ({count} connections)")

        lines.append("</knowledge_graph>")
        return "\n".join(lines)

    def _get_python_imports(self, fp: Path) -> list[str]:
        """Extract imported module names from a Python file."""
        imports = []
        try:
            import re
            text = fp.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'^(?:from|import)\s+(\w+)', text, re.MULTILINE):
                imports.append(m.group(1))
        except Exception:
            logger.debug("Exception suppressed (line 179)")
        return list(set(imports))

    def _get_symbols(self, file_path: str) -> list[dict]:
        """Extract class/function names from a file."""
        symbols: list[dict] = []
        fp = self._root / file_path
        if not fp.exists():
            return symbols
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
            import re
            for i, line in enumerate(text.split("\n"), 1):
                # Python: class/def
                m = re.match(r'^\s*(?:export\s+)?(?:async\s+)?(?:def|class)\s+(\w+)', line)
                if m:
                    symbols.append({"name": m.group(1), "type": "function" if "def" in line else "class", "line": i})
                # JS/TS: function/class/const
                m = re.match(r'^\s*(?:export\s+)?(?:function|class|const)\s+(\w+)', line)
                if m:
                    symbols.append({"name": m.group(1), "type": "function", "line": i})
        except Exception:
            logger.debug("Exception suppressed (line 201)")
        return symbols


# Singleton
_kg: KnowledgeGraph | None = None


def get_knowledge_graph() -> KnowledgeGraph:
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph()
    return _kg
