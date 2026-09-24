"""Engine Arbiter — determines truth when engines disagree.

When the old analyzer and new classifier disagree, instead of blindly
choosing "old always wins" (self-deception), the Arbiter:
1. Runs BOTH approaches (only when they disagree on task_type)
2. Validates both outputs using the Validation Engine
3. Selects the result with higher quality_score
4. Records the outcome for trust accumulation

This converts disagreements from "log and ignore" to "verify and learn."
"""

from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger("widdx.arbiter")


@dataclass
class ArbiterVerdict:
    """Result of arbitrating a disagreement between old and new."""
    winner: str  # "old", "new", "tie"
    old_score: float = 0.0
    new_score: float = 0.0
    old_task_type: str = ""
    new_task_type: str = ""
    reasoning: str = ""
    execution_time: float = 0.0


class EngineArbiter:
    """Resolves disagreements between old analyzer and new classifier.

    When the two disagree on task_type, the Arbiter executes BOTH paths
    and lets the Validation Engine determine which produced better results.
    """

    def __init__(self):
        self._verdicts: list[ArbiterVerdict] = []

    def resolve(
        self,
        old_classification: Any,
        new_classification: Any,
        user_input: str,
        executor: Callable,
        old_ctx: Any,
        new_ctx: Any,
        messages: list | None = None,
    ) -> tuple[Any, Any, ArbiterVerdict]:
        """Resolve a disagreement between old and new classification.

        Args:
            old_classification: UIL ClassificationResult from analyzer
            new_classification: Adapted result from intelligence engine
            user_input: Original user input
            executor: The executor function to run both paths
            old_ctx: ExecutionContext for old path
            new_ctx: ExecutionContext for new path
            messages: Conversation messages

        Returns:
            (winning_result, winning_classification, verdict)
        """
        t0 = time.perf_counter()

        old_type = old_classification.task_type
        new_type = new_classification.task_type

        # Only arbitrate if they actually disagree on task_type
        if hasattr(old_type, 'value'):
            old_type = old_type.value
        if hasattr(new_type, 'value'):
            new_type = new_type.value

        if old_type == new_type:
            # They agree — no arbitration needed
            logger.debug("Engines AGREE: both say %s", old_type)
            return None, old_classification, ArbiterVerdict(
                winner="tie",
                old_task_type=str(old_type),
                new_task_type=str(new_type),
                reasoning="Both engines agreed — no arbitration needed",
            )

        logger.info(
            "Arbitration: old=%s vs new=%s — executing both for validation",
            old_type, new_type,
        )

        try:

            # Execute old path
            old_result = self._safe_execute(executor, old_ctx, user_input, messages, "old")
            # Execute new path
            new_result = self._safe_execute(executor, new_ctx, user_input, messages, "new")

            # Validate both
            old_score = self._validate(old_result, old_classification)
            new_score = self._validate(new_result, new_classification)

            elapsed = time.perf_counter() - t0

            # Determine winner — requires significant improvement to switch
            if new_score > old_score + 0.1:
                winner = "new"
                reasoning = (
                    f"Engine wins: new={new_score:.2f} > old={old_score:.2f} "
                    f"(+{new_score - old_score:.2f})"
                )
                result = new_result
                classification = new_classification
            elif old_score > new_score + 0.1:
                winner = "old"
                reasoning = (
                    f"Analyzer keeps: old={old_score:.2f} > new={new_score:.2f} "
                    f"(+{old_score - new_score:.2f})"
                )
                result = old_result
                classification = old_classification
            else:
                winner = "tie"
                reasoning = (
                    f"Too close to call: old={old_score:.2f} new={new_score:.2f} "
                    f"— defaulting to old"
                )
                result = old_result
                classification = old_classification

            verdict = ArbiterVerdict(
                winner=winner,
                old_score=old_score,
                new_score=new_score,
                old_task_type=str(old_type),
                new_task_type=str(new_type),
                reasoning=reasoning,
                execution_time=round(elapsed, 3),
            )

            self._verdicts.append(verdict)
            logger.info("Arbiter: %s", reasoning)

            # Update trust
            try:
                from core.engine_trust import get_trust_tracker
                trust = get_trust_tracker()
                trust.record(
                    engine="intelligence",
                    agreed=(winner == "tie" and old_type == new_type),
                    engine_correct=(winner == "new"),
                    old_correct=(winner == "old"),
                )
            except ImportError:
                pass

            return result, classification, verdict

        except Exception as e:
            logger.warning("Arbitration failed: %s — returning old result", e)
            return None, old_classification, ArbiterVerdict(
                winner="old",
                old_task_type=str(old_type),
                new_task_type=str(new_type),
                reasoning=f"Arbitration error: {e}",
                execution_time=time.perf_counter() - t0,
            )

    def _safe_execute(self, executor, ctx, user_input, messages, label):
        """Execute safely, returning ExecutionResult or error."""
        try:
            result = executor(ctx, user_input, messages or [])
            return result
        except Exception as e:
            logger.warning("Arbiter %s execution failed: %s", label, e)
            from core.uil.contract import ExecutionResult
            return ExecutionResult(
                success=False,
                summary=f"Execution failed: {e}",
                error=str(e),
            )

    def _validate(self, result, classification) -> float:
        """Validate result and return quality score."""
        try:
            from core.validation.reporter import validate_result
            report = validate_result(result, classification)
            return report.overall
        except Exception:
            # Fallback: success-based score
            success = getattr(result, 'success', True)
            return 0.7 if success else 0.3

    @property
    def stats(self) -> dict:
        """Get arbitration statistics."""
        if not self._verdicts:
            return {"total": 0}
        winners = {"new": 0, "old": 0, "tie": 0}
        for v in self._verdicts:
            winners[v.winner] = winners.get(v.winner, 0) + 1
        return {
            "total": len(self._verdicts),
            "winners": winners,
            "avg_old_score": sum(v.old_score for v in self._verdicts) / len(self._verdicts),
            "avg_new_score": sum(v.new_score for v in self._verdicts) / len(self._verdicts),
        }


# Module-level singleton
_arbiter: EngineArbiter | None = None


def get_arbiter() -> EngineArbiter:
    global _arbiter
    if _arbiter is None:
        _arbiter = EngineArbiter()
    return _arbiter
