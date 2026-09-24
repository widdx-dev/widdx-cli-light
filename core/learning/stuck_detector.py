"""Multi-Signal Stuck Detection — detects when the agent is stuck using 5 signals.

Signals:
  1. No progress in state diff (iteration count alone is NOT enough)
  2. Repeated tool usage (same tool + same args 3x)
  3. Identical plan regeneration (same plan steps generated again)
  4. Error pattern repetition (same error type appearing repeatedly)
  5. Token entropy drop (responses becoming repetitive/short)

Usage:
    from core.learning.stuck_detector import StuckDetector
    sd = StuckDetector()
    sd.record_iteration(step_result, plan, tool_used)

    if sd.is_stuck():
        reason = sd.stuck_reason
        # → "Repeated tool usage (write, 3x identical)" or similar
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("widdx.stuck_detector")


@dataclass
class StuckSignal:
    type: str = ""          # "no_progress" | "repeated_tool" | "identical_plan" | "error_loop" | "entropy_drop"
    detected: bool = False
    detail: str = ""
    severity: float = 0.0   # 0.0-1.0


class StuckDetector:
    """Detects when the agent is genuinely stuck using multiple signals."""

    def __init__(self):
        self._iterations: list[dict] = []      # history of each iteration
        self._tool_history: list[tuple[str, str]] = []  # (tool_name, args_hash)
        self._plan_history: list[str] = []      # plan step hashes
        self._error_history: list[str] = []     # error types
        self._response_lengths: list[int] = []  # for entropy detection
        self._stuck_reason: str = ""

    def record_iteration(self, result: str, plan_steps: list[str],
                         tool_used: str, tool_args: str = "",
                         error: str = "", response_len: int = 0):
        """Record one iteration for analysis."""
        entry = {
            "result": result[:100],
            "plan": "|".join(plan_steps[:5]),
            "tool": tool_used,
            "args": tool_args[:100],
            "error": error[:100],
            "response_len": response_len,
        }
        self._iterations.append(entry)

        if tool_used:
            self._tool_history.append((tool_used, tool_args[:100]))
        if plan_steps:
            self._plan_history.append("|".join(plan_steps[:5]))
        if error:
            self._error_history.append(error[:50])
        if response_len > 0:
            self._response_lengths.append(response_len)

        # Keep last 10 iterations
        if len(self._iterations) > 10:
            self._iterations.pop(0)
            self._tool_history.pop(0)
            self._plan_history.pop(0) if self._plan_history else None
            self._error_history.pop(0) if self._error_history else None
            self._response_lengths.pop(0) if self._response_lengths else None

    def is_stuck(self) -> bool:
        """Check all signals. Returns True if genuinely stuck."""
        signals = [
            self._check_no_progress(),
            self._check_repeated_tools(),
            self._check_identical_plans(),
            self._check_error_loop(),
            self._check_entropy_drop(),
        ]
        stuck = any(s.detected for s in signals)
        if stuck:
            reasons = [s.detail for s in signals if s.detected]
            self._stuck_reason = "; ".join(reasons)
            logger.warning("StuckDetector: %s", self._stuck_reason)
        return stuck

    @property
    def stuck_reason(self) -> str:
        return self._stuck_reason

    # ── Signal detectors ─────────────────────────────────

    def _check_no_progress(self) -> StuckSignal:
        """Check if state is making zero progress."""
        if len(self._iterations) < 3:
            return StuckSignal(type="no_progress", detected=False)

        recent = self._iterations[-3:]
        # Check if all recent results are failures or empty
        failures = sum(1 for r in recent if not r["result"] or
                      any(w in r["result"].lower() for w in ("error", "failed", "no response")))
        if failures >= 3:
            return StuckSignal(type="no_progress", detected=True,
                              detail="3 consecutive failures with no progress",
                              severity=0.9)
        return StuckSignal(type="no_progress", detected=False)

    def _check_repeated_tools(self) -> StuckSignal:
        """Check if same tool + same args is being called repeatedly."""
        if len(self._tool_history) < 3:
            return StuckSignal(type="repeated_tool", detected=False)

        recent = self._tool_history[-3:]
        if len(set(recent)) == 1:
            tool, args = recent[0]
            return StuckSignal(type="repeated_tool", detected=True,
                              detail=f"Repeated tool '{tool}' with identical args 3x",
                              severity=0.8)
        return StuckSignal(type="repeated_tool", detected=False)

    def _check_identical_plans(self) -> StuckSignal:
        """Check if the planner is generating the same plan repeatedly."""
        if len(self._plan_history) < 2:
            return StuckSignal(type="identical_plan", detected=False)

        recent = self._plan_history[-2:]
        if recent[0] and recent[0] == recent[1]:
            return StuckSignal(type="identical_plan", detected=True,
                              detail="Planner regenerated identical plan — no adaptation",
                              severity=0.7)
        return StuckSignal(type="identical_plan", detected=False)

    def _check_error_loop(self) -> StuckSignal:
        """Check if the same error type keeps appearing."""
        if len(self._error_history) < 2:
            return StuckSignal(type="error_loop", detected=False)

        # Group errors by type (first word)
        groups: dict[str, int] = {}
        for e in self._error_history[-5:]:
            key = e.split()[0] if e.split() else e[:20]
            groups[key] = groups.get(key, 0) + 1
        for key, count in groups.items():
            if count >= 3:
                return StuckSignal(type="error_loop", detected=True,
                                  detail=f"Error '{key}' repeated {count}x",
                                  severity=0.75)
        return StuckSignal(type="error_loop", detected=False)

    def _check_entropy_drop(self) -> StuckSignal:
        """Check if responses are getting shorter (entropy collapse)."""
        if len(self._response_lengths) < 3:
            return StuckSignal(type="entropy_drop", detected=False)

        recent = self._response_lengths[-3:]
        # If last 3 responses are all under 50 chars and decreasing
        if all(r < 50 for r in recent) and recent[-1] < recent[0]:
            return StuckSignal(type="entropy_drop", detected=True,
                              detail=f"Response entropy collapsing: {recent}",
                              severity=0.6)
        return StuckSignal(type="entropy_drop", detected=False)


# Singleton
_sd: StuckDetector | None = None


def get_stuck_detector() -> StuckDetector:
    global _sd
    if _sd is None:
        _sd = StuckDetector()
    return _sd
