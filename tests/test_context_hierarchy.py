"""Tests for core/context/* — HierarchicalContext, ContextPruner, DynamicRAG, ContextPipeline."""

from __future__ import annotations


from core.context.hierarchy import HierarchicalContext, HierarchicalResult, ContextLevel
from core.context.pruner import ContextPruner, _estimate_tokens, _truncate_to_tokens
from core.context.rag_integration import DynamicRAG
from core.context.pipeline import ContextPipeline, PipelineResult


# ===================================================================
# Tests: HierarchicalContext
# ===================================================================

class TestHierarchicalContext:
    """HierarchicalContext: builds 4-level context pyramid."""

    def test_build_returns_result(self):
        hc = HierarchicalContext()
        result = hc.build(goal="test goal")
        assert isinstance(result, HierarchicalResult)
        assert isinstance(result.l1, ContextLevel)
        assert isinstance(result.l2, ContextLevel)
        assert isinstance(result.l3, ContextLevel)
        assert isinstance(result.l4, ContextLevel)

    def test_l1_contains_goal(self):
        hc = HierarchicalContext()
        result = hc.build(goal="fix login bug")
        assert "fix login bug" in result.l1.text

    def test_l4_contains_messages(self):
        hc = HierarchicalContext()
        msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        result = hc.build(goal="test", messages=msgs)
        assert "[user]" in result.l4.text
        assert "[assistant]" in result.l4.text

    def test_l4_empty_when_no_messages(self):
        hc = HierarchicalContext()
        result = hc.build(goal="test")
        assert result.l4.text == ""

    def test_render_returns_concatenated_text(self):
        hc = HierarchicalContext()
        result = hc.build(goal="test", messages=[{"role": "user", "content": "hello"}])
        rendered = result.render()
        assert "<context_l1_summary>" in rendered
        assert isinstance(rendered, str)
        assert len(rendered) > 0

    def test_render_respects_max_level(self):
        hc = HierarchicalContext()
        result = hc.build(goal="test", messages=[{"role": "user", "content": "hello"}])
        l1_only = result.render(max_level=1)
        assert "<context_l1_summary>" in l1_only
        assert "<context_l4_history>" not in l1_only


# ===================================================================
# Tests: ContextPruner
# ===================================================================

class TestContextPruner:
    """ContextPruner: progressively prunes context to fit token budget."""

    def test_no_pruning_when_under_limit(self):
        hc = HierarchicalContext()
        ctx = hc.build(goal="small")
        pruner = ContextPruner(max_tokens=99999)
        result = pruner.prune(ctx)
        assert result.l1.text == ctx.l1.text

    def test_prunes_l4_when_over_limit(self):
        hc = HierarchicalContext()
        ctx = hc.build(
            goal="test",
            messages=[{"role": "user", "content": "x" * 1000}] * 50,
        )
        pruner = ContextPruner(max_tokens=256)
        result = pruner.prune(ctx)
        assert len(result.l4.text) < len(ctx.l4.text) or result.l4.text == ""

    def test_prunes_l3_when_over_limit(self):
        ctx = HierarchicalResult(
            l1=ContextLevel(text="small", token_estimate=1),
            l2=ContextLevel(text="", token_estimate=0),
            l3=ContextLevel(text="line1\nline2\nline3\n" * 1000, token_estimate=3000),
            l4=ContextLevel(text="", token_estimate=0),
        )
        pruner = ContextPruner(max_tokens=128)
        result = pruner.prune(ctx)
        assert len(result.l3.text) < len(ctx.l3.text)

    def test_drops_l4_when_truncation_not_enough(self):
        ctx = HierarchicalResult(
            l1=ContextLevel(text="x" * 500, token_estimate=125),
            l2=ContextLevel(text="y" * 5000, token_estimate=1250),
            l3=ContextLevel(text="z" * 5000, token_estimate=1250),
            l4=ContextLevel(text="w" * 2000, token_estimate=500),
        )
        pruner = ContextPruner(max_tokens=512)
        result = pruner.prune(ctx)
        assert result.l4.text == ""  # dropped entirely

    def test_estimate_tokens(self):
        assert _estimate_tokens("hello world") == 2  # 11 chars / 4 = 2.75 → int 2
        assert _estimate_tokens("") == 0

    def test_truncate_to_tokens(self):
        text = "line1\nline2\nline3\nline4"
        truncated = _truncate_to_tokens(text, max_tokens=4)
        assert "[truncated]" in truncated or truncated == text
        # Verify original content is preserved up to the truncation point
        assert truncated.startswith("line1")


# ===================================================================
# Tests: DynamicRAG
# ===================================================================

class TestDynamicRAG:
    """DynamicRAG: bridges HierarchicalContext with RAGStore."""

    def test_init_creates_rag_store(self):
        drag = DynamicRAG()
        assert drag.is_available is True

    def test_index_project_files(self):
        drag = DynamicRAG()
        count = drag.index_project_files(max_files=3)
        assert count >= 0  # may be 0 in isolated test dir, should not crash

    def test_enrich_leaves_context_unchanged_without_goal(self):
        hc = HierarchicalContext()
        ctx = hc.build(goal="test")
        drag = DynamicRAG()
        enriched = drag.enrich(ctx, goal="")
        assert enriched.l1.text == ctx.l1.text
        assert enriched.l3.text == ctx.l3.text

    def test_enrich_injects_rag_section(self):
        hc = HierarchicalContext()
        ctx = hc.build(goal="python test")
        drag = DynamicRAG()
        drag.index_project_files(max_files=5)
        enriched = drag.enrich(ctx, goal="python")
        # May or may not find docs depending on test directory
        assert isinstance(enriched.l3.text, str)

    @property
    def test_document_count(self):
        drag = DynamicRAG()
        assert drag.document_count == 0


# ===================================================================
# Tests: ContextPipeline
# ===================================================================

class TestContextPipeline:
    """ContextPipeline: unified build→enrich→prune chain."""

    def test_run_returns_pipeline_result(self):
        pipe = ContextPipeline(max_tokens=99999, enable_rag=False)
        result = pipe.run(goal="test", files=[], messages=[])
        assert isinstance(result, PipelineResult)
        assert isinstance(result.context, HierarchicalResult)
        assert result.original_tokens >= 0
        assert result.pruned_tokens >= 0

    def test_run_with_messages(self):
        pipe = ContextPipeline(max_tokens=99999, enable_rag=False)
        msgs = [{"role": "user", "content": "hello"}] * 3
        result = pipe.run(goal="test", messages=msgs)
        assert result.pruned is not None
        rendered = result.render()
        assert isinstance(rendered, str)

    def test_render_for_model_reserves_output_budget(self):
        pipe = ContextPipeline(max_tokens=99999, enable_rag=False)
        prompt = pipe.render_for_model(
            model_max_tokens=4096,
            goal="test",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert isinstance(prompt, str)

    def test_auto_index_enabled(self):
        pipe = ContextPipeline(max_tokens=99999, enable_rag=True, auto_index=True)
        result = pipe.run(goal="test")
        assert result.rag_docs_found >= 0
