"""Context Pruner — Compress context to fit small model token limits.

Small models typically have 8K-32K token contexts. The pruner progressively
drops or summarizes context levels when the total exceeds the limit:

  1. Truncate L4 (conversation history) to last N messages
  2. Truncate L3 (file contents) to first N chars per file
  3. Reduce L2 (directory tree) depth
  4. Keep L1 (summary) always — it is the smallest level

Usage:
    from core.context.hierarchy import HierarchicalContext
    from core.context.pruner import ContextPruner

    hc = HierarchicalContext()
    ctx = hc.build(goal="add auth", files=["src/auth.py"], messages=msgs)
    pruner = ContextPruner(max_tokens=4096)
    pruned = pruner.prune(ctx)
    prompt = pruned.render()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from .hierarchy import HierarchicalResult, ContextLevel

logger = logging.getLogger("widdx.context.pruner")


@dataclass
class PruneReport:
    """What the pruner did — useful for debugging context loss."""
    original_tokens: int = 0
    final_tokens: int = 0
    dropped_levels: list[str] = field(default_factory=list)
    truncated_levels: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    fit: bool = True


# Rough token estimation: 1 token ~= 4 chars for English text
# We use a conservative ratio of 4 chars per token
_CHARS_PER_TOKEN = 4.0


def _estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within max_tokens, preserving whole lines."""
    max_chars = int(max_tokens * _CHARS_PER_TOKEN)
    if len(text) <= max_chars:
        return text
    lines = text.split("\n")
    result: list[str] = []
    char_count = 0
    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if char_count + line_len > max_chars:
            remaining = max_chars - char_count
            if remaining > 20:
                result.append(line[:remaining])
            result.append("... [truncated]")
            break
        result.append(line)
        char_count += line_len
    return "\n".join(result)


class ContextPruner:
    """Progressively prunes context to fit within a token budget.

    Pruning strategy (from least to most destructive):
      1. Truncate L4 (conversation history) — keep last N messages
      2. Truncate L3 (file contents) — shorten each file
      3. Drop L4 entirely
      4. Reduce L2 (directory tree) — limit depth
      5. Drop L3 entirely
      6. Drop L2 entirely
      7. Truncate L1 (summary) — only if absolutely necessary
    """

    def __init__(
        self,
        max_tokens: int = 4096,
        l4_message_tokens: int = 200,
        l3_file_tokens: int = 500,
        l2_max_depth: int = 2,
    ):
        self.max_tokens = max_tokens
        self.l4_message_tokens = l4_message_tokens
        self.l3_file_tokens = l3_file_tokens
        self.l2_max_depth = l2_max_depth

    def prune(self, ctx: HierarchicalResult) -> HierarchicalResult:
        """Prune context to fit within max_tokens.

        Returns a new HierarchicalResult with pruned levels.
        The original is not modified.
        """
        report = PruneReport()

        result = HierarchicalResult(
            l1=ContextLevel(text=ctx.l1.text, token_estimate=ctx.l1.token_estimate),
            l2=ContextLevel(text=ctx.l2.text, token_estimate=ctx.l2.token_estimate),
            l3=ContextLevel(text=ctx.l3.text, token_estimate=ctx.l3.token_estimate),
            l4=ContextLevel(text=ctx.l4.text, token_estimate=ctx.l4.token_estimate),
        )

        total = _estimate_tokens(
            result.l1.text + result.l2.text + result.l3.text + result.l4.text
        )
        report.original_tokens = total

        if total <= self.max_tokens:
            report.fit = True
            return result

        # Step 1: Truncate L4 (conversation history)
        if result.l4.text and total > self.max_tokens:
            max_l4 = self.max_tokens - _estimate_tokens(
                result.l1.text + result.l2.text + result.l3.text
            )
            max_l4 = max(max_l4, self.l4_message_tokens * 2)
            truncated = _truncate_to_tokens(result.l4.text, max_l4)
            if len(truncated) < len(result.l4.text):
                result.l4.text = truncated
                result.l4.token_estimate = _estimate_tokens(truncated)
                report.truncated_levels.append("l4")
                report.actions.append("truncated L4 conversation history")
                total = _estimate_tokens(
                    result.l1.text + result.l2.text + result.l3.text + result.l4.text
                )

        # Step 2: Truncate L3 (file contents)
        if result.l3.text and total > self.max_tokens:
            lines = result.l3.text.split("\n")
            truncated_lines: list[str] = []
            current_tokens = 0
            budget = self.max_tokens - _estimate_tokens(
                result.l1.text + result.l2.text + result.l4.text
            )
            budget = max(budget, self.l3_file_tokens)
            for line in lines:
                line_tokens = _estimate_tokens(line)
                if current_tokens + line_tokens > budget:
                    truncated_lines.append(
                        "# ... remaining files truncated to fit token limit ..."
                    )
                    break
                truncated_lines.append(line)
                current_tokens += line_tokens
            result.l3.text = "\n".join(truncated_lines)
            result.l3.token_estimate = current_tokens
            report.truncated_levels.append("l3")
            report.actions.append("truncated L3 file contents")
            total = _estimate_tokens(
                result.l1.text + result.l2.text + result.l3.text + result.l4.text
            )

        # Step 3: Drop L4 entirely
        if result.l4.text and total > self.max_tokens:
            result.l4.text = ""
            result.l4.token_estimate = 0
            report.dropped_levels.append("l4")
            report.actions.append("dropped L4 (conversation history)")
            total = _estimate_tokens(
                result.l1.text + result.l2.text + result.l3.text
            )

        # Step 4: Reduce L2 depth
        if result.l2.text and total > self.max_tokens:
            # Keep only top-level entries
            lines = result.l2.text.split("\n")
            shallow: list[str] = []
            for line in lines:
                if line.startswith("├── ") or line.startswith("└── "):
                    shallow.append(line)
                elif shallow and not line.startswith("│") and not line.startswith("    "):
                    shallow.append(line)
            shallow_text = "\n".join(shallow)
            if len(shallow_text) < len(result.l2.text):
                result.l2.text = shallow_text
                result.l2.token_estimate = _estimate_tokens(shallow_text)
                report.truncated_levels.append("l2")
                report.actions.append("reduced L2 directory tree depth")
                total = _estimate_tokens(
                    result.l1.text + result.l2.text + result.l3.text
                )

        # Step 5: Drop L3 entirely
        if result.l3.text and total > self.max_tokens:
            result.l3.text = ""
            result.l3.token_estimate = 0
            report.dropped_levels.append("l3")
            report.actions.append("dropped L3 (file contents)")
            total = _estimate_tokens(result.l1.text + result.l2.text)

        # Step 6: Drop L2 entirely
        if result.l2.text and total > self.max_tokens:
            result.l2.text = ""
            result.l2.token_estimate = 0
            report.dropped_levels.append("l2")
            report.actions.append("dropped L2 (directory structure)")
            total = _estimate_tokens(result.l1.text)

        # Step 7: Truncate L1 — last resort
        if total > self.max_tokens:
            result.l1.text = _truncate_to_tokens(result.l1.text, self.max_tokens)
            result.l1.token_estimate = _estimate_tokens(result.l1.text)
            report.truncated_levels.append("l1")
            report.actions.append("truncated L1 summary (last resort)")

        report.final_tokens = _estimate_tokens(
            result.l1.text + result.l2.text + result.l3.text + result.l4.text
        )
        report.fit = report.final_tokens <= self.max_tokens

        if report.actions:
            logger.info(
                "ContextPruner: %d→%d tokens, actions=%s",
                report.original_tokens, report.final_tokens,
                report.actions,
            )

        return result
