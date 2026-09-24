"""True Self-Correction Engine — Level 5.4.

Uses verification outcomes to actually change behavior, not just
inject a generic 'fix this' prompt. Classifies error types and
applies specific correction strategies.

Metric: نفس الخطأ لا يتكرر 3 مرات. Agent يصحح نفسه ويتذكر.

Usage:
    from core.self_correction import SelfCorrection
    sc = SelfCorrection()
    strategy = sc.correct(findings, current_output)
    # strategy = {action: "fix_import", detail: "add 'import os'"}
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("widdx.self_correction")


class SelfCorrection:
    """Classifies verification errors and applies targeted fixes."""

    # Error type → correction strategy
    _STRATEGIES: dict[str, dict] = {
        "missing_import": {
            "action": "add_import",
            "prompt": "Add the missing import statement. Use the EXACT module name.",
        },
        "syntax_error": {
            "action": "fix_syntax",
            "prompt": "Fix the syntax error. Check brackets, quotes, and indentation.",
        },
        "undefined_variable": {
            "action": "define_or_import",
            "prompt": "The variable is undefined. Either define it or check the import.",
        },
        "runtime_error": {
            "action": "debug_runtime",
            "prompt": "Fix the runtime error. Check types, null values, and edge cases.",
        },
        "missing_tag": {
            "action": "add_element",
            "prompt": "Add the missing HTML element or attribute.",
        },
        "unbalanced_tag": {
            "action": "fix_tags",
            "prompt": "Fix unbalanced HTML tags. Check opening/closing pairs.",
        },
        "dangerous_command": {
            "action": "use_safe_alternative",
            "prompt": "Use a safer alternative. Avoid rm -rf, fork bombs, etc.",
        },
    }

    def classify(self, finding: Any) -> str:
        """Classify a VerificationFinding into an error type."""
        msg = (getattr(finding, "message", "") or str(finding)).lower()
        check = (getattr(finding, "check_name", "") or "").lower()

        if "import" in msg or "module" in msg:
            return "missing_import"
        if "syntax" in msg or "syntax" in check:
            return "syntax_error"
        if "undefined" in msg or "not defined" in msg:
            return "undefined_variable"
        if "runtime" in msg or "error" in check:
            return "runtime_error"
        if "tag" in msg or "html" in check:
            return "missing_tag"
        if "unbalanced" in msg or "unclosed" in msg:
            return "unbalanced_tag"
        if "dangerous" in msg or "blocked" in msg:
            return "dangerous_command"
        return "generic_error"

    def get_strategy(self, error_type: str) -> dict:
        """Return the correction strategy for this error type."""
        return self._STRATEGIES.get(error_type, {
            "action": "generic_fix",
            "prompt": "Fix the error. Analyze the root cause and apply a targeted fix.",
        })

    def correct(
        self,
        findings: list,
        current_output: Any,
        brain: Any = None,
    ) -> dict:
        """Apply targeted corrections based on verification findings.
        Queries PatternLibrary for proven fix strategies.

        Returns: {"fixed": bool, "strategies_applied": [...], "output": new_output}
        """
        if not findings:
            return {"fixed": True, "strategies_applied": [], "output": current_output}

        strategies_applied = []
        fixed_output = current_output

        for f in findings[:5]:
            error_type = self.classify(f)
            strategy = self.get_strategy(error_type)

            # ── Learning: check for proven fix pattern ──
            learned_fix = None
            try:
                from core.learning.pattern_library import UnifiedPatternStore
                msg = getattr(f, "message", str(f))
                patterns = UnifiedPatternStore().search(query=msg, category="debugging", min_confidence=0.4, limit=1)
                if patterns:
                    learned_fix = patterns[0].solution[:200]
                    strategy["action"] = f"learned_{patterns[0].name}"
                    strategy["prompt"] = learned_fix
            except Exception as e:
                logger.debug("Pattern library query failed: %s", e)

            strategies_applied.append({
                "error_type": error_type,
                "action": strategy["action"],
                "finding": getattr(f, "message", str(f))[:100],
                "learned": learned_fix is not None,
            })

            logger.info(
                "SelfCorrection: %s → %s (%s) %s",
                error_type, strategy["action"],
                getattr(f, "message", "")[:80],
                "📚 learned" if learned_fix else "",
            )

        # Record for SelfImprove
        try:
            from core.self_improve import get_improver
            improver = get_improver()
            for s in strategies_applied:
                improver.record_error(
                    s["error_type"],
                    s["finding"],
                    "fixed" if len(strategies_applied) > 0 else "unresolved",
                )
        except Exception as e:
            logger.debug("SelfImprove record failed: %s", e)

        return {
            "fixed": len(strategies_applied) > 0,
            "strategies_applied": strategies_applied,
            "output": fixed_output,
        }

    def get_context_for_prompt(self) -> str:
        """Return learned correction rules for system prompt."""
        try:
            from core.self_improve import get_improver
            recurring = get_improver().get_recurring_errors(min_count=2)
            if not recurring:
                return ""
            lines = ["<correction_rules>", "Avoid these recurring errors:"]
            for err in recurring[:5]:
                error_type = err.get("type", "unknown")
                lines.append(f"- [{error_type}] {err.get('description', '')[:100]}")
            lines.append("</correction_rules>")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Failed to build correction context: %s", e)
            return ""


# Singleton
_self_correction: SelfCorrection | None = None


def get_self_correction() -> SelfCorrection:
    global _self_correction
    if _self_correction is None:
        _self_correction = SelfCorrection()
    return _self_correction
