"""Context Pipeline — Unified chain: build → enrich → prune.

A single-call entry point that connects HierarchicalContext, DynamicRAG,
and ContextPruner into one configurable pipeline.

Small models benefit from this pipeline because:
  1. Context is automatically sized to their token limit
  2. RAG enriches with relevant prior knowledge
  3. L1 summary stays visible even when L2-L4 are pruned

Usage:
    from core.context.pipeline import ContextPipeline

    pipe = ContextPipeline(max_tokens=4096)
    result = pipe.run(
        goal="add user login with JWT",
        files=["src/auth.py", "src/models/user.py"],
        messages=conversation_history,
    )
    prompt = result.render()  # ready-to-use prompt
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .hierarchy import HierarchicalContext, HierarchicalResult
from .pruner import ContextPruner, PruneReport
from .rag_integration import DynamicRAG

logger = logging.getLogger("widdx.context.pipeline")


@dataclass
class PipelineResult:
    """Result of running the full context pipeline."""
    context: HierarchicalResult
    pruned: HierarchicalResult | None = None
    rag_docs_found: int = 0
    pruned_tokens: int = 0
    original_tokens: int = 0
    prune_report: PruneReport | None = None

    def render(self) -> str:
        """Render the final (pruned) context as a prompt string."""
        source = self.pruned if self.pruned is not None else self.context
        return source.render()


class ContextPipeline:
    """One-shot context pipeline: build → optionally enrich with RAG → prune.

    Configurable for different model sizes:
      - 8K models:   max_tokens=6144 (leaves ~2K for generation)
      - 16K models:  max_tokens=12288
      - 32K models:  max_tokens=24576
      - 128K models: max_tokens=100000 (lenient)
    """

    def __init__(
        self,
        max_tokens: int = 4096,
        project_dir: str | Path | None = None,
        enable_rag: bool = True,
        auto_index: bool = False,
        max_rag_docs: int = 3,
    ):
        self.max_tokens = max_tokens
        self.project_dir = Path(project_dir or Path.cwd()).resolve()
        self.enable_rag = enable_rag
        self.auto_index = auto_index
        self.max_rag_docs = max_rag_docs

        self._context = HierarchicalContext(self.project_dir)
        self._pruner = ContextPruner(max_tokens=max_tokens)
        self._rag = DynamicRAG() if enable_rag else None

        if auto_index and self._rag is not None and self._rag.is_available:
            count = self._rag.index_project_files(self.project_dir)
            logger.info("ContextPipeline: auto-indexed %d files", count)

    def run(
        self,
        goal: str = "",
        files: list[str] | None = None,
        messages: list[dict] | None = None,
        max_level: int = 4,
    ) -> PipelineResult:
        """Build, enrich, and prune context in one call.

        Args:
            goal: The task goal or user request.
            files: Specific file paths relevant to this task.
            messages: Recent conversation messages.
            max_level: Maximum context level to include (1-4).

        Returns:
            PipelineResult with context, pruned version, and stats.
        """
        # Step 1: Build hierarchical context
        ctx = self._context.build(
            goal=goal,
            files=files or [],
            messages=messages or [],
        )

        rag_count = 0

        # Step 2: Enrich with RAG
        if self._rag is not None and self._rag.is_available and goal:
            try:
                enriched = self._rag.enrich(
                    ctx,
                    goal=goal,
                    top_k=self.max_rag_docs,
                    inject_into_l3=True,
                )
                if enriched.l3.text != ctx.l3.text:
                    rag_count = self._rag.document_count
                    ctx = enriched
            except Exception as e:
                logger.debug("RAG enrichment failed: %s", e)

        # Step 3: Prune to fit token budget
        original_tokens = (
            len(ctx.l1.text) + len(ctx.l2.text) + len(ctx.l3.text) + len(ctx.l4.text)
        ) // 4

        pruned = self._pruner.prune(ctx)

        pruned_tokens = (
            len(pruned.l1.text) + len(pruned.l2.text) + len(pruned.l3.text) + len(pruned.l4.text)
        ) // 4

        logger.info(
            "ContextPipeline: goal=%s files=%d msgs=%d "
            "original=%d→pruned=%d rag=%d",
            goal[:40], len(files or []), len(messages or []),
            original_tokens, pruned_tokens, rag_count,
        )

        return PipelineResult(
            context=ctx,
            pruned=pruned if max_level < 4 else pruned,
            rag_docs_found=rag_count,
            original_tokens=original_tokens,
            pruned_tokens=pruned_tokens,
        )

    def render_for_model(self, model_max_tokens: int, goal: str = "",
                         files: list[str] | None = None,
                         messages: list[dict] | None = None) -> str:
        """One-shot: run pipeline and render for a specific model's context limit.

        Reserves 25% of the token budget for the model's output generation.

        Args:
            model_max_tokens: The model's maximum context window (e.g. 8192).
            goal: The task goal.
            files: Relevant file paths.
            messages: Conversation history.

        Returns:
            Rendered context string ready for prompt injection.
        """
        saved = self.max_tokens
        try:
            self.max_tokens = int(model_max_tokens * 0.75)
            self._pruner.max_tokens = self.max_tokens
            result = self.run(goal=goal, files=files, messages=messages)
            return result.render()
        finally:
            self.max_tokens = saved
            self._pruner.max_tokens = saved
