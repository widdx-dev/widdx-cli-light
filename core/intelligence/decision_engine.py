"""Learning decision tree for routing — upgrades router.py from static to adaptive.

The DecisionEngine learns from execution history (knowledge.json):
- Which execution mode succeeded best for which task type + features?
- If AUTONOMOUS failed 3x for database tasks → learn to use DIRECT_TOOL
- If EXPERT_TEAM succeeded for complex web apps → prefer it next time

Decision tree is persisted to .widdx/decisions.json and updated after each execution.
Pure Python — zero LLM calls, zero network I/O.
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("widdx.intelligence.decision")


@dataclass
class DecisionStats:
    """Statistics for a specific (task_type, mode) combination."""
    task_type: str
    mode: str
    successes: int = 0
    failures: int = 0
    total_quality: float = 0.0  # sum of quality scores
    last_used: str = ""  # ISO timestamp

    # ── v4.1 Cost & latency tracking ──
    total_cost: float = 0.0       # sum of execution costs
    total_latency: float = 0.0    # sum of execution latencies (seconds)

    @property
    def total(self) -> int:
        return self.successes + self.failures

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.successes / self.total

    @property
    def avg_quality(self) -> float:
        if self.total == 0:
            return 0.0
        return self.total_quality / self.total

    @property
    def avg_cost(self) -> float:
        if self.total == 0:
            return 0.0
        return self.total_cost / self.total

    @property
    def avg_latency(self) -> float:
        if self.total == 0:
            return 0.0
        return self.total_latency / self.total

    @property
    def cost_efficiency(self) -> float:
        """Quality per dollar — higher is better."""
        if self.avg_cost <= 0:
            return self.success_rate
        return (self.success_rate * self.avg_quality) / max(0.001, self.avg_cost)


# Default mode mapping (mirrors router.py static table)
DEFAULT_MODE_MAP: dict[str, str] = {
    "chat": "simple_chat",
    "code_read": "simple_chat",
    "file_ops": "simple_chat",
    "code_write": "autonomous",
    "code_modify": "autonomous",
    "code_review": "autonomous",
    "browser": "autonomous",
    "database": "autonomous",
    "research": "autonomous",
    "reasoning": "autonomous",
    "complex": "expert_team",
    "system": "direct_tool",
    "unknown": "simple_chat",
}


class DecisionEngine:
    """Learned decision tree for task routing.

    Routes (task_type, features, complexity) → best execution mode.
    Learns from execution history: if AUTONOMOUS keeps failing
    for a task type, it promotes SIMPLE_CHAT or DIRECT_TOOL.
    """

    def __init__(self, knowledge_path: Path | str | None = None):
        """Initialize decision engine.

        Args:
            knowledge_path: Path to knowledge.json for learning.
                           If not provided, uses default static mapping.
        """
        self._knowledge_path = Path(knowledge_path) if knowledge_path else None
        self._stats: dict[str, DecisionStats] = {}
        self._overrides: dict[str, str] = {}  # learned mode overrides
        self._total_decisions: int = 0  # total routing decisions made

        # ── v4.1 Exploration/Exploitation ──
        self._exploration_factor: float = 0.5  # UCB exploration constant
        self._min_trials_for_exploit: int = 3  # minimum trials before exploiting
        self._ucb_mode: bool = True  # use UCB-based exploration

        self._load()

    def _load(self):
        """Load learned decisions from disk."""
        if not self._knowledge_path:
            return
        decisions_path = self._knowledge_path.parent / "decisions.json"
        if not decisions_path.exists():
            return
        try:
            data = json.loads(decisions_path.read_text(encoding="utf-8"))
            for key, override in data.get("overrides", {}).items():
                self._overrides[key] = override
            for key, stats_dict in data.get("stats", {}).items():
                self._stats[key] = DecisionStats(**stats_dict)
            self._total_decisions = data.get("total_decisions", 0)
            logger.debug("Loaded %d overrides, %d stat entries (%d total decisions)",
                         len(self._overrides), len(self._stats), self._total_decisions)
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.warning("Failed to load decisions: %s", e)

    def _save(self):
        """Persist learned decisions to disk."""
        if not self._knowledge_path:
            return
        decisions_path = self._knowledge_path.parent / "decisions.json"
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "overrides": self._overrides,
            "total_decisions": self._total_decisions,
            "stats": {k: {
                "task_type": v.task_type,
                "mode": v.mode,
                "successes": v.successes,
                "failures": v.failures,
                "total_quality": v.total_quality,
                "total_cost": v.total_cost,
                "total_latency": v.total_latency,
                "last_used": v.last_used,
            } for k, v in self._stats.items()},
        }
        decisions_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def route(self, task_type: str, features: list[str] | None = None,
              confidence: float = 0.5, complexity: int = 1,
              is_confused: bool = False) -> str:
        """Route a task to the best execution mode.

        v4.1: Uses UCB-based exploration when data is limited.
        Explores untested modes for a (task_type, features) pair.
        Exploits known-good modes after sufficient trials.

        Args:
            task_type: Task type string ('code_write', 'research', etc.)
            features: Detected features like ['api', 'database', 'web']
            confidence: Classification confidence (0.0-1.0)
            complexity: Task complexity (1=simple, 2=medium, 3=complex)
            is_confused: Whether the classifier was uncertain

        Returns:
            Execution mode string: 'simple_chat', 'autonomous',
            'expert_team', or 'direct_tool'
        """
        features = features or []

        # ── Low confidence or confused → always simple_chat (safety) ──
        if confidence < 0.4 or is_confused:
            return "simple_chat"

        # ── Check learned overrides ──
        feature_key = self._make_key(task_type, features, complexity)
        if feature_key in self._overrides:
            learned_mode = self._overrides[feature_key]
            logger.debug("Learned override: %s → %s", feature_key, learned_mode)
            return learned_mode

        # ── UCB-based exploration/exploitation ──
        if self._ucb_mode:
            mode = self._route_ucb(task_type, features, complexity, confidence)
            if mode:
                return mode

        # ── Check stats for best performing mode (without UCB) ──
        best_mode = self._best_mode_by_stats(task_type, features)
        if best_mode and confidence >= 0.5:
            return best_mode

        # ── Fallback to default static mapping ──
        return DEFAULT_MODE_MAP.get(task_type, "simple_chat")

    def _route_ucb(self, task_type: str, features: list[str],
                   complexity: int, confidence: float) -> str | None:
        """Route using Upper Confidence Bound for explore/exploit.

        For each candidate mode, computes:
          score = success_rate + exploration_factor * sqrt(ln(N) / n)

        Where:
          N = total trials across all modes for this (task_type, features)
          n = trials for this specific mode
          exploration_factor = how much to favor exploration (0.5 default)
        """

        task_stats = {k: v for k, v in self._stats.items()
                      if v.task_type == task_type}

        if not task_stats:
            return None

        total_trials = sum(s.total for s in task_stats.values())
        if total_trials == 0:
            return None

        # Compute UCB score for each mode
        ucb_scores: list[tuple[float, str]] = []
        for mode_key in DEFAULT_MODE_MAP.values():
            # Find stat for this specific (task_type, mode)
            mode_stat = None
            for k, s in task_stats.items():
                if s.mode == mode_key:
                    mode_stat = s
                    break

            if mode_stat and mode_stat.total >= self._min_trials_for_exploit:
                # Exploit: known performance
                exploitation = mode_stat.success_rate * 0.6 + mode_stat.avg_quality * 0.4
                # Exploration bonus (UCB1)
                import math
                exploration = self._exploration_factor * math.sqrt(
                    math.log(total_trials + 1) / max(1, mode_stat.total)
                )
                score = exploitation + exploration
            elif mode_stat and mode_stat.total > 0:
                # Some data but not enough → moderate exploration
                import math
                exploration = self._exploration_factor * math.sqrt(
                    math.log(total_trials + 1) / max(1, mode_stat.total)
                )
                score = mode_stat.success_rate * 0.5 + exploration
            else:
                # No data for this mode → high exploration bonus
                import math
                exploration = self._exploration_factor * 2.0 * math.sqrt(
                    math.log(total_trials + 1) / 1.0
                )
                # Default score from static map
                default_score = 0.5 if mode_key == DEFAULT_MODE_MAP.get(task_type) else 0.3
                score = default_score + exploration

            ucb_scores.append((score, mode_key))

        ucb_scores.sort(key=lambda x: x[0], reverse=True)

        # Log top-2 UCB scores for transparency
        if len(ucb_scores) >= 2:
            logger.debug(
                "UCB routing for %s: %s (%.3f) > %s (%.3f)",
                task_type,
                ucb_scores[0][1], ucb_scores[0][0],
                ucb_scores[1][1], ucb_scores[1][0],
            )

        if ucb_scores and confidence >= 0.5:
            return ucb_scores[0][1]

        return None

    def _make_key(self, task_type: str, features: list[str], complexity: int) -> str:
        """Create a stable key for this task profile."""
        feat_str = "+".join(sorted(features)) if features else "none"
        return f"{task_type}:{feat_str}:c{complexity}"

    def _best_mode_by_stats(self, task_type: str, features: list[str]) -> str | None:
        """Find the statistically best mode for this task profile."""
        candidates: list[tuple[float, str]] = []

        for key, stats in self._stats.items():
            if stats.task_type != task_type:
                continue
            if stats.total < 3:
                continue  # not enough data
            # Weight: success_rate * 0.6 + avg_quality * 0.4
            score = stats.success_rate * 0.6 + stats.avg_quality * 0.4
            candidates.append((score, stats.mode))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_mode = candidates[0]

        # Only override if the best mode is significantly better than default
        default_mode = DEFAULT_MODE_MAP.get(task_type, "simple_chat")
        if best_mode != default_mode and best_score >= 0.5:
            return best_mode
        return None

    def record(self, task_type: str, mode: str, features: list[str],
               success: bool, quality_score: float = 0.0,
               complexity: int = 1,
               cost: float = 0.0, latency: float = 0.0):
        """Record an execution outcome for learning.

        v4.1: Tracks cost and latency. Uses dynamic thresholds that
        adapt based on total data volume.

        Args:
            task_type: Task type that was used
            mode: Execution mode that was used
            features: Task features
            success: Whether the execution succeeded
            quality_score: Quality score from validation (0.0-1.0)
            complexity: Task complexity level
            cost: Execution cost in dollars
            latency: Execution latency in seconds
        """
        from datetime import datetime, timezone

        key = self._make_key(task_type, features, complexity)
        if key not in self._stats:
            self._stats[key] = DecisionStats(
                task_type=task_type, mode=mode,
            )

        stats = self._stats[key]
        if success:
            stats.successes += 1
        else:
            stats.failures += 1
        stats.total_quality += quality_score
        stats.total_cost += cost
        stats.total_latency += latency
        stats.last_used = datetime.now(timezone.utc).isoformat()
        self._total_decisions += 1

        # ── Dynamic thresholds based on data volume ──
        # With little data: conservative (need more evidence)
        # With lots of data: more aggressive learning
        if self._total_decisions < 20:
            failure_threshold = 4
            success_threshold = 6
            rate_threshold = 0.35
        elif self._total_decisions < 100:
            failure_threshold = 3
            success_threshold = 5
            rate_threshold = 0.4
        else:
            failure_threshold = 2
            success_threshold = 3
            rate_threshold = 0.45

        # ── Automatically learn from failures ──
        if stats.failures >= failure_threshold and stats.success_rate < rate_threshold:
            alternatives = {
                "expert_team": "autonomous",
                "autonomous": "simple_chat",
            }
            if mode in alternatives:
                new_mode = alternatives[mode]
                self._overrides[key] = new_mode
                logger.info(
                    "Learned: %s (mode=%s) failed %d/%d times (rate=%.2f) → "
                    "downgrading to %s",
                    key, mode, stats.failures, stats.total,
                    stats.success_rate, new_mode,
                )

        # ── Promote good alternatives (v4.1: auto-escalation) ──
        if (stats.successes >= success_threshold
                and stats.success_rate >= 0.8
                and stats.avg_quality >= 0.7):
            escalations = {
                "simple_chat": "autonomous",
            }
            if mode in escalations and key not in self._overrides:
                self._overrides[key] = escalations[mode]
                logger.info(
                    "Promoted: %s (mode=%s) succeeded %d/%d times (rate=%.2f) → "
                    "escalating to %s",
                    key, mode, stats.successes, stats.total,
                    stats.success_rate, escalations[mode],
                )

        # ── Cost-based optimization ──
        if stats.total >= 3 and stats.cost_efficiency < 0.3 and mode != "simple_chat":
            logger.info(
                "Cost optimization: %s (mode=%s) cost_efficiency=%.2f"
                " — cost may be too high for this task type",
                key, mode, stats.cost_efficiency,
            )

        self._save()

    def get_stats(self, task_type: str | None = None) -> dict[str, DecisionStats]:
        """Get decision statistics, optionally filtered by task_type."""
        if task_type:
            return {k: v for k, v in self._stats.items()
                    if v.task_type == task_type}
        return dict(self._stats)

    def reset(self):
        """Clear all learned decisions. Start fresh."""
        self._stats.clear()
        self._overrides.clear()
        self._save()


# Module-level singleton
_engine: DecisionEngine | None = None


def get_decision_engine(knowledge_path: Path | str | None = None) -> DecisionEngine:
    """Get or create the decision engine."""
    global _engine
    if _engine is None:
        _engine = DecisionEngine(knowledge_path)
    return _engine
