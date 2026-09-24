"""Advanced Self-Improvement — Learn from repeated errors & optimize prompts.

Detects error patterns across sessions, tracks which fixes work,
and auto-suggests prompt improvements to prevent recurring failures.

Architecture:
  ErrorPatternLearner — detects repeated errors and groups them
  FixTracker           — records attempted fixes and their outcomes
  PromptOptimizer      — suggests prompt modifications based on error history

Usage:
    from core.self_improve import get_improver

    improver = get_improver()
    improver.record_error("bgStars", "duplicate variable", "fixed")
    suggestions = improver.suggest_prompt_improvements()
    # → ["Add rule: grep for variable names before declaring"]
"""

from __future__ import annotations
import logging

import json
import time
import threading
from pathlib import Path
logger = logging.getLogger("widdx.self_improve")


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

IMPROVE_DIR = Path.home() / ".widdx" / "self_improve"


# ---------------------------------------------------------------------------
# Error Pattern Learner
# ---------------------------------------------------------------------------

class ErrorPatternLearner:
    """Detects repeated error patterns and learns which fixes work."""

    def __init__(self, storage_dir: Path | None = None):
        self._dir = storage_dir or IMPROVE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._errors_file = self._dir / "error_patterns.json"
        self._fixes_file = self._dir / "fix_tracker.json"
        self._lock = threading.RLock()

        self._patterns: dict[str, dict] = {}  # pattern_key → {count, examples, last_seen}
        self._fixes: dict[str, dict] = {}    # error_key → {fix, outcome, timestamp}
        self._load()

    # ── Public API ──────────────────────────────────────

    def record_error(
        self,
        error_type: str,
        description: str,
        outcome: str = "unknown",
    ):
        """Record an error occurrence. ``outcome`` = fixed | workaround | unresolved."""
        key = self._normalize_key(error_type)
        with self._lock:
            if key not in self._patterns:
                self._patterns[key] = {
                    "type": error_type,
                    "count": 0,
                    "examples": [],
                    "first_seen": time.time(),
                }
            p = self._patterns[key]
            p["count"] += 1
            p["last_seen"] = time.time()
            if len(p["examples"]) < 5:
                p["examples"].append({
                    "description": description[:200],
                    "outcome": outcome,
                    "timestamp": time.time(),
                })
            self._save_patterns()

    def record_fix(
        self,
        error_type: str,
        fix_description: str,
        success: bool,
    ):
        """Record an attempted fix for an error pattern."""
        key = self._normalize_key(error_type)
        with self._lock:
            self._fixes[key] = {
                "error_type": error_type,
                "fix": fix_description[:300],
                "success": success,
                "timestamp": time.time(),
            }
            self._save_fixes()

    def get_recurring_errors(self, min_count: int = 2) -> list[dict]:
        """Return error patterns that have occurred at least ``min_count`` times."""
        with self._lock:
            recurring = []
            for key, p in self._patterns.items():
                if p["count"] >= min_count:
                    recurring.append({
                        "type": p["type"],
                        "count": p["count"],
                        "examples": p["examples"],
                        "last_seen": p["last_seen"],
                        "has_fix": key in self._fixes and self._fixes[key].get("success"),
                    })
            return sorted(recurring, key=lambda x: x["count"], reverse=True)

    def suggest_prompt_improvements(self) -> list[str]:
        """Generate prompt improvement suggestions based on error history."""
        suggestions = []
        recurring = self.get_recurring_errors(min_count=2)

        for err in recurring:
            etype = err["type"].lower()

            if "duplicate" in etype or "already declared" in etype or "already been declared" in etype:
                suggestions.append(
                    "ANTI-DUPLICATION: Before adding any variable/function, "
                    "MUST grep the project for that identifier first."
                )

            if "syntax" in etype or "syntaxerror" in etype:
                suggestions.append(
                    "VERIFY: After EVERY file edit, run syntax check "
                    "(node --check for JS, python -m py_compile for Python)."
                )

            if "import" in etype or "modulenotfound" in etype:
                suggestions.append(
                    "IMPORT CHECK: Verify module exists AND is importable "
                    "before referencing it in new code."
                )

            if "changed" in etype or "unexpected" in etype or "broke" in etype:
                suggestions.append(
                    "CHANGE AUDIT: Before modifying existing values, "
                    "understand WHY they were set that way originally."
                )

            if not err["has_fix"]:
                suggestions.append(
                    f"UNRESOLVED: '{err['type']}' occurred {err['count']} times "
                    f"with no verified fix. Consider adding a specific guard."
                )

        return suggestions

    def stats(self) -> dict:
        """Return learning statistics."""
        with self._lock:
            return {
                "total_patterns": len(self._patterns),
                "total_errors": sum(p["count"] for p in self._patterns.values()),
                "fixes_attempted": len(self._fixes),
                "fixes_successful": sum(1 for f in self._fixes.values() if f.get("success")),
                "recurring": len(self.get_recurring_errors()),
        }

    # ── Internals ───────────────────────────────────────

    @staticmethod
    def _normalize_key(text: str) -> str:
        """Normalize error text to a stable pattern key."""
        import re
        # Collapse whitespace, lowercase, remove timestamps/UUIDs
        key = re.sub(r'\s+', ' ', text.lower().strip())
        key = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<uuid>', key)
        key = re.sub(r'\d{4}-\d{2}-\d{2}[tT]\d{2}:\d{2}:\d{2}', '<timestamp>', key)
        return key[:100]

    def _save_patterns(self):
        try:
            tmp = str(self._errors_file) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._patterns, f, ensure_ascii=False, indent=2, default=str)
            import os
            os.replace(tmp, str(self._errors_file))
        except Exception:
            pass

    def _save_fixes(self):
        try:
            tmp = str(self._fixes_file) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._fixes, f, ensure_ascii=False, indent=2, default=str)
            import os
            os.replace(tmp, str(self._fixes_file))
        except Exception:
            pass

    def _load(self):
        for fname, attr in [(self._errors_file, "_patterns"), (self._fixes_file, "_fixes")]:
            try:
                if fname.exists():
                    with open(fname, encoding="utf-8") as f:
                        setattr(self, attr, json.load(f))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------

_improver: ErrorPatternLearner | None = None
_improver_lock = threading.Lock()


def get_improver() -> ErrorPatternLearner:
    global _improver
    with _improver_lock:
        if _improver is None:
            _improver = ErrorPatternLearner()
        return _improver
