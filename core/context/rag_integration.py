"""Dynamic RAG Integration — Connect HierarchicalContext with RAGStore.

Auto-searches relevant documents from RAGStore when building context,
indexes project files automatically, and injects relevant content into L3.

This makes the HierarchicalContext self-enriching: each task automatically
retrieves and includes relevant prior knowledge.

Usage:
    from core.context.hierarchy import HierarchicalContext
    from core.context.rag_integration import DynamicRAG

    hc = HierarchicalContext()
    drag = DynamicRAG()
    drag.index_project_files()  # one-time: index current project
    ctx = hc.build(goal="add user auth", files=["src/auth.py"])
    ctx = drag.enrich(ctx, goal="add user auth")
    prompt = ctx.render()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .hierarchy import HierarchicalResult, ContextLevel

logger = logging.getLogger("widdx.context.rag")


class DynamicRAG:
    """Bridges HierarchicalContext with RAGStore for auto-retrieval.

    Two modes:
      1. Enrich: query RAGStore and inject relevant docs into L3
      2. Auto-index: scan project files and index them in RAGStore
    """

    def __init__(self, rag_store: Any | None = None):
        self._rag = rag_store
        self._initialized = False
        self._init_rag()

    def _init_rag(self):
        """Initialize RAGStore."""
        if self._rag is not None:
            self._initialized = True
            return
        try:
            from core.rag import RAGStore
            self._rag = RAGStore()
            self._initialized = True
        except Exception as e:
            logger.debug("RAGStore not available: %s", e)
            self._rag = None
            self._initialized = False

    def index_project_files(
        self,
        project_dir: str | Path | None = None,
        max_files: int = 50,
        extensions: set[str] | None = None,
    ) -> int:
        """Scan project directory and index source files in RAGStore.

        Args:
            project_dir: Root directory to scan. Defaults to cwd.
            max_files: Maximum number of files to index.
            extensions: File extensions to include. Defaults to common source types.

        Returns:
            Number of files indexed.
        """
        if not self._initialized or self._rag is None:
            return 0

        root = Path(project_dir or Path.cwd()).resolve()
        exts = extensions or {".py", ".js", ".ts", ".tsx", ".jsx", ".go",
                               ".rs", ".rb", ".java", ".kt", ".swift",
                               ".md", ".sql", ".yaml", ".yml", ".json",
                               ".html", ".css", ".scss", ".toml"}

        count = 0
        skip_dirs = {"node_modules", ".git", "__pycache__", ".widdx",
                     ".venv", "venv", "env", "dist", "build", ".next",
                     ".cache", "target", "vendor"}

        try:
            for fpath in root.rglob("*"):
                if count >= max_files:
                    break
                if not fpath.is_file():
                    continue
                if any(part in skip_dirs for part in fpath.parts):
                    continue
                if fpath.suffix.lower() not in exts:
                    continue
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    if len(content) > 50000:
                        content = content[:50000]
                    relative = str(fpath.relative_to(root))
                    self._rag.add(
                        doc_id=f"file:{relative}",
                        content=content,
                        metadata={
                            "path": relative,
                            "extension": fpath.suffix,
                            "size": len(content),
                        },
                    )
                    count += 1
                except Exception as e:
                    logger.debug("Skipped %s: %s", fpath, e)
        except Exception as e:
            logger.warning("Project indexing failed: %s", e)

        logger.info("DynamicRAG indexed %d files from %s", count, root)
        return count

    def enrich(
        self,
        ctx: HierarchicalResult,
        goal: str = "",
        top_k: int = 3,
        inject_into_l3: bool = True,
    ) -> HierarchicalResult:
        """Query RAGStore and inject relevant documents into context levels.

        Relevant docs are appended to L3 (key files) and mentioned in L1.

        Args:
            ctx: HierarchicalResult from HierarchicalContext.build().
            goal: The task goal/query for semantic search.
            top_k: Maximum RAG results to inject.
            inject_into_l3: When True, inject RAG results into L3.

        Returns:
            Enriched HierarchicalResult (original is not modified).
        """
        if not self._initialized or self._rag is None or not goal:
            return ctx

        result = HierarchicalResult(
            l1=ContextLevel(text=ctx.l1.text, token_estimate=ctx.l1.token_estimate),
            l2=ContextLevel(text=ctx.l2.text, token_estimate=ctx.l2.token_estimate),
            l3=ContextLevel(text=ctx.l3.text, token_estimate=ctx.l3.token_estimate),
            l4=ContextLevel(text=ctx.l4.text, token_estimate=ctx.l4.token_estimate),
        )

        try:
            docs = self._rag.search(query=goal, top_k=top_k, min_score=0.25)
        except Exception as e:
            logger.debug("RAG search failed: %s", e)
            return result

        if not docs:
            return result

        rag_section_parts = ["# Retrieved from semantic memory (RAG)\n"]
        for score, doc in docs:
            path = doc.get("metadata", {}).get("path", doc.get("id", "unknown"))
            content = doc.get("content", "")
            preview = content[:800]
            if len(content) > 800:
                preview += "\n# ... truncated ..."
            rag_section_parts.append(f"## {path} (relevance: {score:.2f})\n{preview}")

        rag_text = "\n\n".join(rag_section_parts)

        if inject_into_l3:
            if result.l3.text:
                result.l3.text += "\n\n" + rag_text
            else:
                result.l3.text = rag_text
            result.l3.token_estimate = len(result.l3.text) // 4

        # Mention RAG findings in L1 summary
        rag_summary = "; ".join(
            f"{doc.get('metadata', {}).get('path', 'doc')} ({score:.2f})"
            for score, doc in docs[:3]
        )
        if rag_summary:
            result.l1.text += f"\nRAG: {rag_summary}"

        logger.info("DynamicRAG enriched context with %d documents", len(docs))
        return result

    @property
    def is_available(self) -> bool:
        return self._initialized and self._rag is not None

    @property
    def document_count(self) -> int:
        if self._rag is not None:
            return self._rag.count()
        return 0
