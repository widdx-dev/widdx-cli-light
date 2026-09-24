"""Persistent Memory System for WIDDX.

Two-tier architecture:
  1. **Global memory** — ``~/.widdx/memory/`` — shared across ALL projects.
     Facts learned in one project are available in every other project.
     This is the DEFAULT when ``MemoryStore()`` is called without arguments.

  2. **Project memory** — ``<project>/.widdx/memory/`` — facts specific to one
     project.  Created by passing ``project_dir=...``.

This means WIDDX learns once and remembers everywhere — continuous
self-improvement across sessions, projects, and even users (when deployed).

Each memory is a markdown file with frontmatter:
  ---
  name: <short-kebab-case>
  description: <one-line summary>
  metadata:
    type: user | feedback | project | reference
  ---
  <the fact>

MEMORY.md serves as the index with one-line pointers.
"""
import logging

from pathlib import Path
from datetime import datetime
from typing import Any

from .utils import parse_frontmatter, strip_frontmatter, to_slug
logger = logging.getLogger("widdx.memory")



MEMORY_DIR_NAME = "memory"
INDEX_FILE = "MEMORY.md"


class MemoryStore:
    """Persistent memory store backed by markdown files with frontmatter.
import logging

    Args:
        project_dir: If given, stores memory in ``<project>/.widdx/memory/``.
                     If ``None`` (default), stores in ``~/.widdx/memory/``
                     (global — shared across all projects).
    """

    def __init__(self, project_dir: str | Path | None = None) -> None:
        if project_dir is None:
            # Global memory — shared across ALL projects
            self.root = Path.home() / ".widdx"
        else:
            self.root = Path(project_dir).resolve()
        self.widdx_dir = self.root / ".widdx" if project_dir else self.root
        self.memory_dir = self.widdx_dir / MEMORY_DIR_NAME
        self.index_path = self.widdx_dir / INDEX_FILE
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    # ── CRUD ───────────────────────────────────────────────────────────

    def save(self, name: str, content: str, metadata: dict | None = None,
             confidence: float = 0.5, version: int = 1,
             status: str = "active") -> Path:
        """Save a memory with versioning metadata.

        Args:
            name: Short kebab-case name.
            content: The fact body.
            metadata: Arbitrary metadata dict.
            confidence: 0.0–1.0 how confident we are in this fact.
            version: Integer version number (auto-incremented on conflict).
            status: 'active', 'deprecated', or 'superseded'.
        """
        slug = to_slug(name)
        filepath = self.memory_dir / f"{slug}.md"

        # ── Versioning: bump version on content change ──────────
        existing_body = self.get(name)
        if existing_body is not None and existing_body.strip() != content.strip():
            old_path = self.memory_dir / f"{slug}.v{version}.old.md"
            try:
                existing_text = filepath.read_text(encoding="utf-8")
                # Extract old version number
                old_meta, _ = parse_frontmatter(existing_text, nested_metadata=True)
                old_ver = int(old_meta.get("version", 1))
                old_path = self.memory_dir / f"{slug}.v{old_ver}.old.md"
                old_path.write_text(existing_text, encoding="utf-8")
                version = old_ver + 1
                logging.getLogger("widdx.memory").info(
                    "Memory versioned: '%s' v%d → v%d. Previous saved to %s",
                    name, old_ver, version, old_path,
                )
            except OSError:
                pass

        meta = metadata or {}
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()

        # ── Versioning frontmatter fields ──
        meta.update({
            "version": version,
            "confidence": round(confidence, 2),
            "status": status,
            "updated": now,
        })
        if "created" not in meta:
            meta["created"] = now
        if "last_validated" not in meta and status == "active":
            meta["last_validated"] = now

        meta_lines = ["metadata:"]
        for k, v in meta.items():
            meta_lines.append(f"  {k}: {v}")
        meta_str = "\n" + "\n".join(meta_lines)

        frontmatter = (
            f"---\n"
            f"name: {slug}\n"
            f"description: {content[:80].strip()}\n"
            f"version: {version}\n"
            f"confidence: {round(confidence, 2)}\n"
            f"status: {status}\n"
            f"{meta_str}\n"
            f"---\n"
        )
        full = frontmatter + "\n" + content
        filepath.write_text(full, encoding="utf-8")

        # Update index
        self._update_index(slug, content[:60])

        return filepath

    def get(self, name: str) -> str | None:
        """Read a memory by name/slug. Returns None if not found."""
        slug = to_slug(name)
        filepath = self.memory_dir / f"{slug}.md"
        if not filepath.exists():
            return None
        text = filepath.read_text(encoding="utf-8")
        # Strip frontmatter
        body = strip_frontmatter(text)
        return body

    def delete(self, name: str) -> bool:
        """Delete a memory. Returns True if deleted."""
        slug = to_slug(name)
        filepath = self.memory_dir / f"{slug}.md"
        if not filepath.exists():
            return False
        filepath.unlink()
        self._rebuild_index()
        return True

    def list_all(self) -> list[dict]:
        """Return all memories as [{name, description, type, path}, ...]."""
        memories = []
        for f in sorted(self.memory_dir.glob("*.md")):
            meta, _ = parse_frontmatter(f.read_text(encoding="utf-8"), nested_metadata=True)
            memories.append({
                "name": meta.get("name", f.stem),
                "description": meta.get("description", ""),
                "type": meta.get("metadata", {}).get("type", "unknown"),
                "path": str(f.relative_to(self.root)),
            })
        return memories

    def search(self, query: str, semantic: bool = False) -> list[dict]:
        """Search memory contents by keyword. Set semantic=True for vector similarity search."""
        # ── Semantic search (vector_memory) ─────────────────
        if semantic:
            try:
                from core.vector_memory import VectorMemoryStore
                vstore = VectorMemoryStore()
                vmatches = vstore.search(query, top_k=10)
                if vmatches:
                    return [{
                        "name": r.get("name", "?"),
                        "description": r.get("content", "")[:80],
                        "snippet": r.get("content", "")[:200],
                        "score": r.get("score", 0.0),
                    } for _, r in vmatches]
            except Exception:
                pass

        # ── TF-IDF similarity search ────────────────────────
        try:
            from core.intelligence.embeddings import get_embedder
            embedder = get_embedder()
            contents = []
            file_map = []
            for f in self.memory_dir.glob("*.md"):
                text = f.read_text(encoding="utf-8")
                body = strip_frontmatter(text)
                if body.strip():
                    contents.append(body)
                    file_map.append(f)
            if contents:
                embedder.index(contents)
                matches = embedder.search(query, top_k=5, min_score=0.08)
                if matches:
                    vec_results: list[dict[str, Any]] = []
                    for score, matched_text in matches:
                        idx = contents.index(matched_text)
                        f = file_map[idx]
                        meta, _ = parse_frontmatter(f.read_text(encoding="utf-8"), nested_metadata=True)
                        vec_results.append({
                            "name": meta.get("name", f.stem),
                            "description": meta.get("description", "")[:80],
                            "snippet": matched_text[:200],
                            "score": round(score, 3),
                        })
                    return vec_results
        except Exception:
            pass

        # ── Keyword fallback ────────────────────────────────
        query_lower = query.lower()
        kw_results: list[dict[str, Any]] = []
        for f in self.memory_dir.glob("*.md"):
            text = f.read_text(encoding="utf-8")
            if query_lower in text.lower():
                meta, _ = parse_frontmatter(text, nested_metadata=True)
                body = strip_frontmatter(text)
                kw_results.append({
                    "name": meta.get("name", f.stem),
                    "description": meta.get("description", "")[:80],
                    "snippet": body[:200],
                })
        return kw_results

    # ── Versioning API ──────────────────────────────────────────

    def search_active(self, query: str) -> list[dict]:
        """Search only ACTIVE memories (excludes deprecated/superseded)."""
        results = self.search(query)
        active = []
        for r in results:
            name = r.get("name", "")
            filepath = self.memory_dir / f"{to_slug(name)}.md"
            if filepath.exists():
                meta, _ = parse_frontmatter(
                    filepath.read_text(encoding="utf-8"), nested_metadata=True
                )
                if meta.get("status", "active") == "active":
                    r["version"] = meta.get("version", 1)
                    r["confidence"] = meta.get("confidence", 0.5)
                    r["status"] = "active"
                    active.append(r)
        return active

    def deprecate(self, name: str, reason: str = "") -> bool:
        """Mark a memory as deprecated."""
        content = self.get(name)
        if content is None:
            return False
        slug = to_slug(name)
        filepath = self.memory_dir / f"{slug}.md"
        existing = filepath.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(existing, nested_metadata=True)
        if reason:
            body = f"{body}\n\n---\nDeprecated: {reason}"
        return self.save(
            name, body,
            metadata=meta.get("metadata", {}),
            confidence=float(meta.get("confidence", 0.3)),
            version=int(meta.get("version", 1)),
            status="deprecated",
        ) is not None

    def validate(self, name: str) -> bool:
        """Update last_validated timestamp (confidence boost)."""
        content = self.get(name)
        if content is None:
            return False
        slug = to_slug(name)
        filepath = self.memory_dir / f"{slug}.md"
        existing = filepath.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(existing, nested_metadata=True)
        md = meta.get("metadata", {})
        from datetime import timezone
        md["last_validated"] = datetime.now(timezone.utc).isoformat()
        new_conf = min(1.0, float(meta.get("confidence", 0.5)) + 0.1)
        return self.save(
            name, body,
            metadata=md,
            confidence=new_conf,
            version=int(meta.get("version", 1)),
            status="active",
        ) is not None

    def cleanup_deprecated(self, older_than_days: int = 90) -> int:
        """Delete deprecated memories older than the threshold."""
        import time
        cutoff = time.time() - (older_than_days * 86400)
        removed = 0
        for f in self.memory_dir.glob("*.md"):
            if ".old." in f.name or f.name.startswith("._"):
                continue
            text = f.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text, nested_metadata=True)
            if meta.get("status") == "deprecated":
                try:
                    updated = meta.get("metadata", {}).get("updated", "")
                    from datetime import datetime
                    ts = datetime.fromisoformat(updated).timestamp()
                    if ts < cutoff:
                        f.unlink()
                        removed += 1
                except (ValueError, OSError):
                    pass
        if removed:
            self._rebuild_index()
        return removed

    def total(self) -> int:
        """Number of stored memories (excluding old versions)."""
        return len([f for f in self.memory_dir.glob("*.md") if ".old." not in f.name])

    # ── Index management ──────────────────────────────────────────────

    def _update_index(self, slug: str, description: str) -> None:
        """Append or update one line in MEMORY.md."""
        line = f"- [{slug}]({MEMORY_DIR_NAME}/{slug}.md) — {description.strip()}"
        if self.index_path.exists():
            text = self.index_path.read_text(encoding="utf-8")
            # Replace existing line for this slug
            for i, existing in enumerate(text.splitlines()):
                if existing.strip().startswith(f"- [{slug}]"):
                    lines = text.splitlines()
                    lines[i] = line
                    self.index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    return
            # Append
            with self.index_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        else:
            self.index_path.write_text(line + "\n", encoding="utf-8")

    def _rebuild_index(self) -> None:
        """Regenerate MEMORY.md from all memory files."""
        lines = []
        for f in sorted(self.memory_dir.glob("*.md")):
            meta, _ = parse_frontmatter(f.read_text(encoding="utf-8"), nested_metadata=True)
            desc = meta.get("description", "")
            lines.append(f"- [{meta.get('name', f.stem)}]({MEMORY_DIR_NAME}/{f.name}) — {desc}")
        self.index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
