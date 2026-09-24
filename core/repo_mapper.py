"""Smart Repo Map — Dependency graph + context selector.

Builds a lightweight map of the repository: files, symbols, imports,
and dependencies.  Uses this to select the most relevant context for
a given task query.

Architecture:
  RepoMapper       — scan, index, query
  FileNode         — a file with its symbols and dependencies
  ContextSelector  — rank files by relevance to a query

Usage:
    from core.repo_mapper import RepoMapper

    mapper = RepoMapper()
    mapper.scan()                                  # build the map
    files = mapper.select("login authentication")  # top-5 relevant files
    # → ["src/auth/login.py", "src/models/user.py", ...]
"""

from __future__ import annotations
import logging

import ast
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
logger = logging.getLogger("widdx.repo_mapper")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAP_FILE = ".widdx/repo_map.json"
IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", ".widdx",
               "node_modules", ".venv", "venv", "env", "dist",
               ".mypy_cache", "build", ".idea", ".vscode", ".DS_Store",
               "backups", ".test_workdir"}
MAX_FILES = 500
RELEVANCE_BOOST_KEYWORDS = 2.0    # multiplier for keyword match in path
RELEVANCE_BOOST_IMPORT = 1.5      # multiplier for import relationship
RELEVANCE_BOOST_RECENT = 1.3      # multiplier for recently modified


# ---------------------------------------------------------------------------
# File Node
# ---------------------------------------------------------------------------

class FileNode:
    """A file in the repository map."""

    __slots__ = ("path", "size", "mtime", "ext", "symbols", "imports",
                 "exports", "keywords")

    def __init__(self, path: Path, root: Path):
        self.path = str(path.relative_to(root)).replace("\\", "/")
        self.size = 0
        self.mtime = 0.0
        self.ext = path.suffix.lower()
        self.symbols: list[str] = []
        self.imports: list[str] = []
        self.exports: list[str] = []
        self.keywords: set[str] = set()

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "ext": self.ext,
            "symbols": self.symbols[:30],
            "imports": self.imports[:30],
            "exports": self.exports[:30],
            "keywords": sorted(self.keywords)[:50],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FileNode":
        node = cls.__new__(cls)
        node.path = d["path"]
        node.size = d.get("size", 0)
        node.mtime = d.get("mtime", 0.0)
        node.ext = d.get("ext", "")
        node.symbols = d.get("symbols", [])
        node.imports = d.get("imports", [])
        node.exports = d.get("exports", [])
        node.keywords = set(d.get("keywords", []))
        return node


# ---------------------------------------------------------------------------
# Repo Mapper
# ---------------------------------------------------------------------------

class RepoMapper:
    """Scan, index, and query a repository structure."""

    def __init__(self, root: str | Path | None = None):
        self._root = Path(root) if root else Path.cwd()
        self._files: dict[str, FileNode] = {}
        self._import_index: dict[str, set[str]] = defaultdict(set)
        self._stem_index: dict[str, list[str]] = {}
        self._loaded = False

    # ── Scanning ────────────────────────────────────────

    def scan(self, force: bool = False) -> int:
        """Scan the repository. Returns number of files indexed.

        Uses cached map on disk if available and not forced.
        """
        if not force and self._load_cache():
            self._loaded = True
            return len(self._files)

        self._files.clear()
        self._import_index.clear()
        file_count = 0

        for f in self._root.rglob("*"):
            if file_count >= MAX_FILES:
                break
            if not f.is_file():
                continue
            if any(p in IGNORE_DIRS for p in f.parts):
                continue

            try:
                stat = f.stat()
            except OSError:
                continue

            node = FileNode(f, self._root)
            node.size = stat.st_size
            node.mtime = stat.st_mtime
            file_count += 1

            # Extract symbols based on file type
            self._extract_symbols(node, f)
            self._extract_keywords(node)

            self._files[node.path] = node

        self._build_import_index()
        self._save_cache()
        self._loaded = True
        return len(self._files)

    # ── Query ───────────────────────────────────────────

    def select(self, query: str, top_k: int = 5) -> list[str]:
        """Select the most relevant files for a task query.

        Ranks files by: keyword match + import proximity + recency.
        """
        if not self._loaded:
            self.scan()

        query_terms = set(re.findall(r'\w+', query.lower()))
        scored: list[tuple[float, str]] = []

        for path, node in self._files.items():
            score = 0.0

            # Keyword match in path
            path_lower = path.lower()
            for term in query_terms:
                if term in path_lower:
                    score += RELEVANCE_BOOST_KEYWORDS

            # Keyword match in symbols
            for sym in node.symbols:
                for term in query_terms:
                    if term in sym.lower():
                        score += 1.0
                        break

            # Keyword match in content keywords
            for kw in node.keywords:
                for term in query_terms:
                    if term in kw:
                        score += 0.5
                        break

            # Import proximity: files that import matched files get a boost
            related = self._import_index.get(path, set())
            for rel_path in related:
                for term in query_terms:
                    if term in rel_path.lower():
                        score += RELEVANCE_BOOST_IMPORT
                        break

            # Recency boost
            if node.mtime > time.time() - 86400:  # last 24h
                score *= RELEVANCE_BOOST_RECENT

            if score > 0:
                scored.append((score, path))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [path for _, path in scored[:top_k]]

    def get_dependencies(self, file_path: str) -> list[str]:
        """Return files that this file imports/depends on."""
        if not self._loaded:
            self.scan()
        node = self._files.get(file_path)
        if not node:
            return []
        deps = []
        for imp in node.imports:
            # Try to resolve import to a file
            candidates = self._resolve_import(imp)
            deps.extend(candidates)
        return deps

    def get_dependents(self, file_path: str) -> list[str]:
        """Return files that depend on this file."""
        if not self._loaded:
            self.scan()
        return sorted(self._import_index.get(file_path, set()))

    def stats(self) -> dict:
        if not self._loaded:
            self.scan()
        return {
            "total_files": len(self._files),
            "total_imports": sum(len(n.imports) for n in self._files.values()),
            "total_symbols": sum(len(n.symbols) for n in self._files.values()),
            "languages": sorted(set(n.ext for n in self._files.values())),
        }

    def find_file(self, partial: str) -> list[str]:
        """Fuzzy-find files by partial path match."""
        if not self._loaded:
            self.scan()
        partial_lower = partial.lower()
        matches = [p for p in self._files if partial_lower in p.lower()]
        return sorted(matches)[:20]

    # ── Symbol Extraction ───────────────────────────────

    def _extract_symbols(self, node: FileNode, file_path: Path):
        """Extract functions, classes, imports from source files."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        if node.ext == ".py":
            self._extract_python(node, content)
        elif node.ext in (".js", ".ts", ".jsx", ".tsx", ".mjs"):
            self._extract_javascript(node, content)
        elif node.ext in (".go",):
            self._extract_go(node, content)
        elif node.ext in (".rs",):
            self._extract_rust(node, content)

    def _extract_python(self, node: FileNode, content: str):
        try:
            tree = ast.parse(content)
            for item in ast.walk(tree):
                if isinstance(item, ast.FunctionDef):
                    node.symbols.append(item.name)
                    node.exports.append(item.name)
                elif isinstance(item, ast.ClassDef):
                    node.symbols.append(item.name)
                    node.exports.append(item.name)
                elif isinstance(item, ast.Import):
                    for alias in item.names:
                        node.imports.append(alias.name.split(".")[0])
                elif isinstance(item, ast.ImportFrom):
                    if item.module:
                        node.imports.append(item.module.split(".")[0])
        except SyntaxError:
            pass

    def _extract_javascript(self, node: FileNode, content: str):
        # Function declarations
        funcs = re.findall(
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', content,
        )
        node.symbols.extend(funcs)
        node.exports.extend(funcs)

        # Class declarations
        classes = re.findall(r'(?:export\s+)?class\s+(\w+)', content)
        node.symbols.extend(classes)
        node.exports.extend(classes)

        # Arrow functions assigned to const/let/var
        arrows = re.findall(
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', content,
        )
        node.symbols.extend(arrows)
        node.exports.extend(arrows)

        # Import statements
        imports = re.findall(
            r'(?:import|require)\s*\(?["\']([^"\']+)["\']', content,
        )
        for imp in imports:
            # Take the module/package name (first part of path)
            base = imp.split("/")[0]
            if not base.startswith("."):
                node.imports.append(base)
            elif imp.startswith("./") or imp.startswith("../"):
                # Relative import — store full path for resolution
                node.imports.append(imp)

    def _extract_go(self, node: FileNode, content: str):
        funcs = re.findall(r'func\s+(?:\([^)]+\)\s+)?(\w+)', content)
        node.symbols.extend(funcs)
        node.exports.extend([f for f in funcs if f[0].isupper()])

        imports = re.findall(r'"([^"]+)"', content)
        for imp in imports:
            node.imports.append(imp.split("/")[0])

    def _extract_rust(self, node: FileNode, content: str):
        funcs = re.findall(r'fn\s+(\w+)', content)
        node.symbols.extend(funcs)
        node.exports.extend([f for f in funcs if f[0].isupper() or f == "main"])

        imports = re.findall(r'use\s+(\w+)', content)
        node.imports.extend(imports)

    def _extract_keywords(self, node: FileNode):
        """Extract content keywords from file path and symbols."""
        path_parts = re.findall(r'\w+', node.path.lower())
        node.keywords.update(path_parts)
        node.keywords.update(s.lower() for s in node.symbols)
        node.keywords.update(s.lower() for s in node.exports)

    # ── Import Resolution ───────────────────────────────

    def _build_import_index(self):
        """Build reverse index: file → set of files that import it.

        Uses a stem → paths lookup table so resolution is O(imports) instead
        of O(files × imports). The previous full-scan version made every
        cache load cost 15+ seconds on this repo.
        """
        self._import_index.clear()
        self._stem_index.clear()
        for path in self._files:
            stem = Path(path).stem.lower()
            self._stem_index.setdefault(stem, []).append(path)

        for path, node in self._files.items():
            for imp in node.imports:
                resolved = self._resolve_import(imp)
                for resolved_path in resolved:
                    self._import_index[resolved_path].add(path)

    def _resolve_import(self, import_name: str) -> list[str]:
        """Resolve an import name to actual file paths (bounded to 3 matches)."""
        results: list[str] = []
        name_normalized = import_name.lower().replace(".", "/").replace("\\", "/")
        tail = name_normalized.split("/")[-1]

        # Primary lookup: exact stem match via the index.
        for path in self._stem_index.get(tail, []):
            results.append(path)
            if len(results) >= 3:
                return results

        # Fallback: substring containment, still bounded.
        for path in self._files:
            if len(results) >= 3:
                break
            path_lower = path.lower()
            if name_normalized in path_lower or path_lower.endswith("/" + name_normalized):
                if path not in results:
                    results.append(path)
        return results

    # ── Persistence ─────────────────────────────────────

    def _save_cache(self):
        try:
            cache_dir = self._root / ".widdx"
            cache_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "files": {p: n.to_dict() for p, n in self._files.items()},
                "timestamp": time.time(),
            }
            tmp = str(cache_dir / "repo_map.json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, str(cache_dir / "repo_map.json"))
        except Exception:
            pass

    def _load_cache(self) -> bool:
        try:
            cache_file = self._root / MAP_FILE
            if not cache_file.exists():
                return False
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
            age = time.time() - data.get("timestamp", 0)
            if age > 3600:  # cache expires after 1 hour
                return False
            self._files = {
                p: FileNode.from_dict(d)
                for p, d in data.get("files", {}).items()
            }
            self._build_import_index()
            return True
        except Exception:
            return False
