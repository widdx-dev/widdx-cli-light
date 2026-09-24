"""Verification Loop — 4.0 #3.

Verify → Fix → Retest cycle. Never trusts a task is done until
it passes verification. Auto-retries with fixes up to max_retries.

Usage:
    from core.verification.loop import VerifyLoop
    loop = VerifyLoop()
    result = loop.run(output, task_type, fixer_fn=agent_fix)
    if result.passed_all:
        # truly done
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger("widdx.verify_loop")


@dataclass
class LoopResult:
    """Result of a verify-fix-retest cycle."""
    passed_all: bool = False
    iterations: int = 0
    total_time: float = 0.0
    findings_fixed: int = 0
    findings_remaining: int = 0
    final_report: object = None  # VerificationReport


class VerifyLoop:
    """Runs verify → fix → retest until clean or max_retries exhausted."""

    def __init__(self, max_retries: int = 3):
        self._max_retries = max_retries

    def get_learned_strategy(self, error_msg: str) -> dict | None:
        """Query PatternLibrary for a proven fix strategy for this error."""
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()
            patterns = store.search(query=error_msg, category="debugging", min_confidence=0.4, limit=1)
            if patterns:
                return {"name": patterns[0].name, "solution": patterns[0].solution, "confidence": patterns[0].confidence}
        except Exception as e:
            logger.debug("Pattern library search failed: %s", e)
        return None

    def run(
        self,
        output: object,  # ExecutionResult or raw text
        task_type,        # TaskType enum
        fixer_fn: Callable[[list, object], object] | None = None,
    ) -> LoopResult:
        """Execute the verify-fix-retest loop.

        Args:
            output: The execution result to verify.
            task_type: TaskType for choosing the right verifier.
            fixer_fn: Called with (findings, output) → returns fixed output.
                      If None, only verify once (no fixing).

        Returns:
            LoopResult with final status.
        """
        t0 = time.perf_counter()
        iterations = 0
        total_fixed = 0
        final_report = None

        from core.uil.verifier import get_verifier
        verifier = get_verifier(task_type)

        for i in range(1, self._max_retries + 1):
            iterations = i
            report = verifier.verify(output, task_type)  # type: ignore[arg-type]
            final_report = report

            if report.passed_all:
                logger.info("Verification loop: PASSED on iteration %d", i)
                break

            criticals = [f for f in report.findings if not f.passed]
            logger.warning(
                "Verification loop: %d issues on iteration %d — %s",
                len(criticals), i, report.summarize(),
            )

            if fixer_fn is None or i >= self._max_retries:
                break

            # Try to fix
            try:
                output = fixer_fn(criticals, output)
                total_fixed += len(criticals)
                logger.info("Fixer applied for %d findings", len(criticals))
            except Exception as e:
                logger.error("Fixer failed: %s", e)
                break

        elapsed = time.perf_counter() - t0
        remaining = len([f for f in final_report.findings if not f.passed]) if final_report else 0

        return LoopResult(
            passed_all=final_report.passed_all if final_report else False,
            iterations=iterations,
            total_time=round(elapsed, 3),
            findings_fixed=total_fixed,
            findings_remaining=remaining,
            final_report=final_report,
        )


# Singleton
_verify_loop: VerifyLoop | None = None


def get_verify_loop() -> VerifyLoop:
    global _verify_loop
    if _verify_loop is None:
        _verify_loop = VerifyLoop()
    return _verify_loop
