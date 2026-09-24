"""Memory contamination tracker — detects when accumulated context distorts reasoning.

Monitors: message history growth, repeated patterns in context,
tool argument inflation, and response template degradation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("widdx.semantic.memory")


@dataclass
class ContaminationReport:
    """Report on memory/context contamination level."""
    message_count: int = 0
    total_tokens: int = 0
    repeated_patterns: int = 0
    argument_inflation: float = 0.0  # 0.0 = stable, >0.5 = inflating
    template_degradation: float = 0.0  # 0.0 = fresh, >0.5 = degraded
    contamination_score: float = 0.0
    recommendation: str = ""


class MemoryContaminationTracker:
    """Tracks whether accumulated execution context is corrupting reasoning.

    Detects:
      - Context window bloat (messages > threshold)
      - Argument inflation (tool args growing over time)
      - Template degradation (responses becoming formulaic)
      - Repeated system message patterns
    """

    MAX_HEALTHY_MESSAGES = 50
    TOKEN_WARNING_THRESHOLD = 8000

    def __init__(self):
        self._message_count: int = 0
        self._estimated_tokens: int = 0
        self._tool_arg_lengths: list[int] = []
        self._response_templates: list[str] = []
        self._system_message_hashes: list[int] = []

    def start_task(self):
        """Reset contamination tracker for a new task."""
        self._message_count = 0
        self._estimated_tokens = 0
        self._tool_arg_lengths.clear()
        self._response_templates.clear()
        self._system_message_hashes.clear()

    def note_message(self, role: str = "", content: str = ""):
        """Record a message added to execution context."""
        self._message_count += 1
        token_estimate = len(content) // 4 if content else 0
        self._estimated_tokens += token_estimate

        if role == "system" and content:
            h = hash(content[:200])
            self._system_message_hashes.append(h)

    def note_tool_args(self, args: dict | None = None):
        """Record tool argument complexity."""
        if args:
            self._tool_arg_lengths.append(len(str(args)))
            if len(self._tool_arg_lengths) > 30:
                self._tool_arg_lengths.pop(0)

    def note_response(self, content: str):
        """Record response for template detection."""
        if content:
            prefix = content[:100]
            self._response_templates.append(prefix)
            if len(self._response_templates) > 20:
                self._response_templates.pop(0)

    def measure(self) -> ContaminationReport:
        """Compute current contamination level."""
        # Message count score
        msg_score = min(1.0, self._message_count / self.MAX_HEALTHY_MESSAGES)

        # Token saturation
        token_score = min(1.0, self._estimated_tokens / self.TOKEN_WARNING_THRESHOLD)

        # Argument inflation
        if len(self._tool_arg_lengths) >= 5:
            first_half = self._tool_arg_lengths[:len(self._tool_arg_lengths) // 2]
            second_half = self._tool_arg_lengths[len(self._tool_arg_lengths) // 2:]
            avg_first = sum(first_half) / len(first_half) if first_half else 0
            avg_second = sum(second_half) / len(second_half) if second_half else 0
            if avg_first > 0:
                arg_inflation = min(1.0, max(0.0, (avg_second - avg_first) / avg_first))
            else:
                arg_inflation = 0.0
        else:
            arg_inflation = 0.0

        # Template degradation
        if len(self._response_templates) >= 8:
            unique = len(set(self._response_templates))
            template_degradation = 1.0 - (unique / len(self._response_templates))
        else:
            template_degradation = 0.0

        # Repeated system patterns
        if self._system_message_hashes:
            unique_hashes = len(set(self._system_message_hashes))
            repeat_ratio = 1.0 - (unique_hashes / len(self._system_message_hashes))
        else:
            repeat_ratio = 0.0

        # Composite contamination score
        contamination = round(
            msg_score * 0.25
            + token_score * 0.25
            + arg_inflation * 0.25
            + max(template_degradation, repeat_ratio) * 0.25,
            3
        )

        recommendation = ""
        if contamination > 0.6:
            recommendation = "CRITICAL: Prune context or reset conversation"
        elif contamination > 0.4:
            recommendation = "WARNING: Consider context compression"
        elif contamination > 0.2:
            recommendation = "Elevated — monitor closely"
        else:
            recommendation = "Healthy"

        return ContaminationReport(
            message_count=self._message_count,
            total_tokens=self._estimated_tokens,
            repeated_patterns=int(repeat_ratio * len(self._system_message_hashes)),
            argument_inflation=round(arg_inflation, 3),
            template_degradation=round(template_degradation, 3),
            contamination_score=contamination,
            recommendation=recommendation,
        )


_mem_contam: MemoryContaminationTracker | None = None


def get_memory_contamination_tracker() -> MemoryContaminationTracker:
    global _mem_contam
    if _mem_contam is None:
        _mem_contam = MemoryContaminationTracker()
    return _mem_contam
