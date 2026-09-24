"""Trust Accumulator — learns which engine to trust over time.

Tracks agreement/disagreement between old analyzer and new classifier.
After N consecutive agreements with high confidence, auto-promotes
the engine to primary (stops running old code in parallel).

Persisted to .widdx/engine_trust.json — survives restarts.
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("widdx.trust")


@dataclass
class EngineTrust:
    """Trust metrics for a single engine."""
    engine_name: str
    total_comparisons: int = 0
    agreements: int = 0
    disagreements: int = 0
    engine_won: int = 0      # arbiter proved engine right
    old_won: int = 0          # arbiter proved old right
    ties: int = 0
    trust_level: float = 0.0  # 0.0 - 1.0, auto-calculated
    auto_promoted: bool = False
    promoted_at: str = ""

    @property
    def agreement_rate(self) -> float:
        if self.total_comparisons == 0:
            return 0.0
        return self.agreements / self.total_comparisons

    @property
    def win_rate(self) -> float:
        """When they disagreed, how often did engine win?"""
        total_disputes = self.engine_won + self.old_won
        if total_disputes == 0:
            return 0.5
        return self.engine_won / total_disputes

    def compute_trust(self):
        """Recompute trust level from metrics.

        Trust = agreement_rate * 0.6 + win_rate * 0.4
        But only if we have enough data (>= 50 comparisons).
        """
        if self.total_comparisons < 50:
            self.trust_level = 0.0
            return

        self.trust_level = round(
            self.agreement_rate * 0.6 + self.win_rate * 0.4, 2
        )

        # Auto-promote when trust > 0.95 with >= 100 comparisons
        if self.trust_level > 0.95 and self.total_comparisons >= 100 and not self.auto_promoted:
            from datetime import datetime, timezone
            self.auto_promoted = True
            self.promoted_at = datetime.now(timezone.utc).isoformat()
            logger.info(
                "TRUST PROMOTION: %s auto-promoted (trust=%.2f, %d comparisons)",
                self.engine_name, self.trust_level, self.total_comparisons,
            )

    def should_use_engine(self) -> bool:
        """Should this engine be used as primary instead of old code?"""
        return self.auto_promoted and self.trust_level > 0.9


class TrustTracker:
    """Tracks trust for all engines."""

    def __init__(self, data_dir: Path | str | None = None):
        self._data_dir = Path(data_dir) if data_dir else Path.cwd() / ".widdx"
        self._path = self._data_dir / "engine_trust.json"
        self._engines: dict[str, EngineTrust] = {}
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for name, edata in data.get("engines", {}).items():
                self._engines[name] = EngineTrust(**edata)
            logger.debug("Loaded trust data for %d engines", len(self._engines))
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to load trust data: %s", e)

    def _save(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "engines": {
                name: {
                    "engine_name": e.engine_name,
                    "total_comparisons": e.total_comparisons,
                    "agreements": e.agreements,
                    "disagreements": e.disagreements,
                    "engine_won": e.engine_won,
                    "old_won": e.old_won,
                    "ties": e.ties,
                    "trust_level": e.trust_level,
                    "auto_promoted": e.auto_promoted,
                    "promoted_at": e.promoted_at,
                }
                for name, e in self._engines.items()
            },
        }
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, engine_name: str) -> EngineTrust:
        """Get or create trust metrics for an engine."""
        if engine_name not in self._engines:
            self._engines[engine_name] = EngineTrust(engine_name=engine_name)
        return self._engines[engine_name]

    def record(
        self,
        engine: str,
        agreed: bool = False,
        engine_correct: bool = False,
        old_correct: bool = False,
    ):
        """Record one comparison outcome.

        Args:
            engine: Engine name ('intelligence', 'validation', 'isolation')
            agreed: True if old and new agreed
            engine_correct: True if arbiter proved engine right
            old_correct: True if arbiter proved old right
        """
        trust = self.get(engine)
        trust.total_comparisons += 1

        if agreed:
            trust.agreements += 1
        else:
            trust.disagreements += 1

        if engine_correct:
            trust.engine_won += 1
        elif old_correct:
            trust.old_won += 1
        else:
            trust.ties += 1

        trust.compute_trust()
        self._save()

    def is_promoted(self, engine: str) -> bool:
        """Check if an engine has been auto-promoted."""
        return self.get(engine).auto_promoted

    def should_use_engine(self, engine: str) -> bool:
        """Should this engine replace the old code path?"""
        return self.get(engine).should_use_engine()

    def summary(self) -> dict:
        """Human-readable trust summary."""
        return {
            name: {
                "comparisons": e.total_comparisons,
                "agreements": e.agreements,
                "agreement_rate": round(e.agreement_rate, 2),
                "win_rate": round(e.win_rate, 2),
                "trust": e.trust_level,
                "promoted": e.auto_promoted,
            }
            for name, e in self._engines.items()
        }


# Module-level singleton
_tracker: TrustTracker | None = None


def get_trust_tracker(data_dir: Path | str | None = None) -> TrustTracker:
    global _tracker
    if _tracker is None:
        _tracker = TrustTracker(data_dir)
    return _tracker
