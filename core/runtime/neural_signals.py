"""Neural Signal Learning and Prediction System.

Enhances the ECP with:
  1. Signal pattern learning — learns from historical signal patterns
  2. Predictive signals — predicts problems before they occur
  3. Complete feedback loop — decision outcomes feed back to sensors
  4. CONFIDENCE_DROP activation — from ExecutionIntelligence
  5. Signal correlation analysis — detects signal cascades

Architecture:
  SignalLearner: learns patterns from historical signal sequences
  SignalPredictor: predicts future signals based on current patterns
  SignalFeedback: feeds decision outcomes back to improve sensors
  SignalAnalyzer: detects correlations and cascades between signals
"""

from __future__ import annotations

import logging
import time
import math
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict

logger = logging.getLogger("widdx.neural_signals")


@dataclass
class SignalPattern:
    """A learned pattern of signal sequences."""
    sequence: list[str]  # e.g., ["QUALITY_DEGRADATION", "TOOL_FAILURE_RATE"]
    next_signal: str  # predicted next signal
    confidence: float  # 0-1, how reliable this pattern is
    occurrence_count: int = 0
    last_seen: float = field(default_factory=time.time)


@dataclass
class PredictionResult:
    """A predicted future signal."""
    predicted_signal: str
    confidence: float
    time_horizon: float  # seconds into the future
    source_pattern: str
    recommendation: str


@dataclass
class FeedbackRecord:
    """Records the outcome of a control decision for learning."""
    step: int
    signals_before: list[str]
    decision: str
    outcome: str  # "improved", "worsened", "unchanged"
    signals_after: list[str]
    timestamp: float = field(default_factory=time.time)


class SignalLearner:
    """Learns patterns from historical signal sequences.

    Uses n-gram analysis to predict future signals based on
    current signal patterns.
    """

    def __init__(self, max_pattern_length: int = 3):
        self._patterns: dict[tuple[str, ...], dict[str, SignalPattern]] = {}
        self._max_length = max_pattern_length
        self._signal_history: list[tuple[float, str]] = []
        self._min_occurrences = 2  # minimum occurrences to trust a pattern

    def start(self):
        self._patterns.clear()
        self._signal_history.clear()

    def record_signal(self, signal_type: str, timestamp: float | None = None) -> None:
        """Record a signal occurrence for pattern learning."""
        ts = timestamp or time.time()
        self._signal_history.append((ts, signal_type))
        # Keep last 1000 signals
        if len(self._signal_history) > 1000:
            self._signal_history = self._signal_history[-1000:]

    def learn_patterns(self) -> None:
        """Extract patterns from signal history."""
        if len(self._signal_history) < 3:
            return

        signals = [s for _, s in self._signal_history]

        for length in range(2, self._max_length + 1):
            for i in range(len(signals) - length):
                sequence = tuple(signals[i:i + length])
                next_signal = signals[i + length]

                if sequence not in self._patterns:
                    self._patterns[sequence] = {}

                if next_signal not in self._patterns[sequence]:
                    self._patterns[sequence][next_signal] = SignalPattern(
                        sequence=list(sequence),
                        next_signal=next_signal,
                        confidence=0.0,
                        occurrence_count=0,
                    )

                pattern = self._patterns[sequence][next_signal]
                pattern.occurrence_count += 1
                pattern.last_seen = time.time()

                # Confidence based on occurrence count and recency
                count_factor = min(1.0, pattern.occurrence_count / 10.0)
                age_hours = (time.time() - pattern.last_seen) / 3600
                recency_factor = math.exp(-age_hours / 24)  # decay over 24h
                pattern.confidence = round(count_factor * recency_factor, 3)

    def predict_next(self, recent_signals: list[str]) -> list[PredictionResult]:
        """Predict the next signal based on recent signal history."""
        predictions: list[PredictionResult] = []

        for length in range(min(len(recent_signals), self._max_length), 1, -1):
            sequence = tuple(recent_signals[-length:])
            if sequence in self._patterns:
                for next_signal, pattern in self._patterns[sequence].items():
                    if pattern.occurrence_count >= self._min_occurrences:
                        predictions.append(PredictionResult(
                            predicted_signal=next_signal,
                            confidence=pattern.confidence,
                            time_horizon=30.0,  # predict 30s ahead
                            source_pattern=" → ".join(list(sequence)),
                            recommendation=self._get_recommendation(next_signal),
                        ))

        # Sort by confidence
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        return predictions[:5]  # top 5 predictions

    def _get_recommendation(self, signal: str) -> str:
        """Get a recommendation for a predicted signal."""
        recommendations = {
            "STUCK": "Prepare for possible replan — review current plan",
            "LOOP_DETECTED": "Consider breaking the loop with a different approach",
            "TOOL_FAILURE_RATE": "Prepare fallback tools or switch model",
            "QUALITY_DEGRADATION": "Increase verification frequency",
            "COMPLEXITY_DRIFT": "Consider task decomposition",
            "MEMORY_PRESSURE": "Reduce context size or prune messages",
            "PROVIDER_FAILURE": "Prepare backup provider",
            "DEADLOCK": "Prepare escalation to expert team",
            "TOKEN_INEFFICIENCY": "Consider switching to a more efficient model",
            "CONFIDENCE_DROP": "Increase verification and validation",
        }
        return recommendations.get(signal, "Monitor situation")

    def get_learned_patterns(self) -> list[dict[str, Any]]:
        """Return all learned patterns for inspection."""
        patterns = []
        for sequence, next_signals in self._patterns.items():
            for next_signal, pattern in next_signals.items():
                if pattern.occurrence_count >= self._min_occurrences:
                    patterns.append({
                        "sequence": list(sequence),
                        "predicts": next_signal,
                        "confidence": pattern.confidence,
                        "occurrences": pattern.occurrence_count,
                    })
        return sorted(patterns, key=lambda p: p["confidence"], reverse=True)


class SignalPredictor:
    """Predicts future signals based on current system state."""

    def __init__(self):
        self._learner = SignalLearner()
        self._recent_signals: list[tuple[float, str]] = []

    def start(self):
        self._learner.start()
        self._recent_signals.clear()

    def add_signal(self, signal_type: str, value: float = 0.5) -> None:
        """Add a signal to the recent history."""
        self._recent_signals.append((time.time(), signal_type))
        self._learner.record_signal(signal_type)
        # Keep last 50 signals
        if len(self._recent_signals) > 50:
            self._recent_signals = self._recent_signals[-50:]

    def predict(self) -> list[PredictionResult]:
        """Predict upcoming signals based on recent history."""
        signals = [s for _, s in self._recent_signals]
        if len(signals) < 2:
            return []

        self._learner.learn_patterns()
        return self._learner.predict_next(signals)

    def get_early_warning(self) -> dict[str, Any] | None:
        """Get early warning if a critical signal is predicted."""
        predictions = self.predict()
        if not predictions:
            return None

        # Check for critical predictions
        critical_signals = {"DEADLOCK", "PROVIDER_FAILURE", "MEMORY_PRESSURE"}
        for pred in predictions:
            if pred.predicted_signal in critical_signals and pred.confidence > 0.5:
                return {
                    "warning_level": "CRITICAL",
                    "predicted_signal": pred.predicted_signal,
                    "confidence": pred.confidence,
                    "recommendation": pred.recommendation,
                    "time_horizon_seconds": pred.time_horizon,
                }

        # Check for warning-level predictions
        warning_signals = {"STUCK", "LOOP_DETECTED", "TOOL_FAILURE_RATE", "QUALITY_DEGRADATION"}
        for pred in predictions:
            if pred.predicted_signal in warning_signals and pred.confidence > 0.6:
                return {
                    "warning_level": "WARNING",
                    "predicted_signal": pred.predicted_signal,
                    "confidence": pred.confidence,
                    "recommendation": pred.recommendation,
                    "time_horizon_seconds": pred.time_horizon,
                }

        return None


class SignalFeedback:
    """Feeds decision outcomes back to improve sensor accuracy."""

    def __init__(self):
        self._feedback_history: list[FeedbackRecord] = []
        self._decision_outcomes: dict[str, dict[str, int]] = defaultdict(
            lambda: {"improved": 0, "worsened": 0, "unchanged": 0}
        )

    def start(self):
        self._feedback_history.clear()
        self._decision_outcomes.clear()

    def record_outcome(
        self,
        step: int,
        signals_before: list[str],
        decision: str,
        signals_after: list[str],
    ) -> None:
        """Record the outcome of a control decision."""
        # Determine if the decision improved the situation
        before_critical = sum(1 for s in signals_before if s in {"DEADLOCK", "PROVIDER_FAILURE", "MEMORY_PRESSURE"})
        after_critical = sum(1 for s in signals_after if s in {"DEADLOCK", "PROVIDER_FAILURE", "MEMORY_PRESSURE"})

        before_warning = len(signals_before)
        after_warning = len(signals_after)

        if after_critical < before_critical or after_warning < before_warning - 1:
            outcome = "improved"
        elif after_critical > before_critical or after_warning > before_warning + 1:
            outcome = "worsened"
        else:
            outcome = "unchanged"

        record = FeedbackRecord(
            step=step,
            signals_before=signals_before,
            decision=decision,
            outcome=outcome,
            signals_after=signals_after,
        )
        self._feedback_history.append(record)
        self._decision_outcomes[decision][outcome] += 1

    def get_decision_effectiveness(self) -> dict[str, dict[str, float]]:
        """Get effectiveness statistics for each decision type."""
        result = {}
        for decision, outcomes in self._decision_outcomes.items():
            total = sum(outcomes.values())
            if total > 0:
                result[decision] = {
                    "improvement_rate": round(outcomes["improved"] / total, 3),
                    "worsen_rate": round(outcomes["worsened"] / total, 3),
                    "total": total,
                }
        return result

    def get_best_decision(self, current_signals: list[str]) -> str | None:
        """Recommend the best decision based on historical outcomes."""
        if not self._feedback_history:
            return None

        # Find similar situations and what worked best
        decision_scores: dict[str, float] = defaultdict(float)
        decision_counts: dict[str, int] = defaultdict(int)

        for record in self._feedback_history:
            # Check if signals match
            if any(s in record.signals_before for s in current_signals):
                if record.outcome == "improved":
                    decision_scores[record.decision] += 1.0
                elif record.outcome == "worsened":
                    decision_scores[record.decision] -= 1.0
                decision_counts[record.decision] += 1

        if not decision_scores:
            return None

        # Return decision with highest score
        best = max(decision_scores, key=lambda k: decision_scores[k])
        return best if decision_scores[best] > 0 else None


class SignalAnalyzer:
    """Analyzes signal correlations and cascades."""

    def __init__(self):
        self._signal_co_occurrence: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._signal_totals: dict[str, int] = defaultdict(int)

    def start(self):
        self._signal_co_occurrence.clear()
        self._signal_totals.clear()

    def record_window(self, signals: list[str]) -> None:
        """Record a window of co-occurring signals."""
        for s in signals:
            self._signal_totals[s] += 1
        # Record co-occurrences
        for i in range(len(signals)):
            for j in range(i + 1, len(signals)):
                self._signal_co_occurrence[signals[i]][signals[j]] += 1
                self._signal_co_occurrence[signals[j]][signals[i]] += 1

    def get_correlations(self, min_strength: float = 0.3) -> list[dict[str, Any]]:
        """Get signal correlations above threshold."""
        correlations = []
        seen = set()

        for s1, others in self._signal_co_occurrence.items():
            for s2, count in others.items():
                pair = tuple(sorted([s1, s2]))
                if pair in seen:
                    continue
                seen.add(pair)

                # Jaccard similarity
                total_s1 = self._signal_totals[s1]
                total_s2 = self._signal_totals[s2]
                if total_s1 == 0 or total_s2 == 0:
                    continue

                union = total_s1 + total_s2 - count
                jaccard = count / union if union > 0 else 0

                if jaccard >= min_strength:
                    correlations.append({
                        "signal_1": s1,
                        "signal_2": s2,
                        "co_occurrence": count,
                        "correlation_strength": round(jaccard, 3),
                    })

        return sorted(correlations, key=lambda c: c["correlation_strength"], reverse=True)

    def detect_cascade(self, recent_signals: list[str]) -> list[dict[str, Any]]:
        """Detect signal cascades (one signal leading to another)."""
        cascades = []
        correlations = self.get_correlations(min_strength=0.2)

        for i in range(len(recent_signals) - 1):
            s1 = recent_signals[i]
            s2 = recent_signals[i + 1]

            # Check if this pair is correlated
            for corr in correlations:
                if (corr["signal_1"] == s1 and corr["signal_2"] == s2) or \
                   (corr["signal_1"] == s2 and corr["signal_2"] == s1):
                    cascades.append({
                        "from": s1,
                        "to": s2,
                        "strength": corr["correlation_strength"],
                    })

        return cascades


class NeuralSignalSystem:
    """Unified neural signal system combining all components."""

    def __init__(self):
        self.learner = SignalLearner()
        self.predictor = SignalPredictor()
        self.feedback = SignalFeedback()
        self.analyzer = SignalAnalyzer()
        self._is_active = False

    def start(self):
        self.learner.start()
        self.predictor.start()
        self.feedback.start()
        self.analyzer.start()
        self._is_active = True

    def process_signals(self, signals: list[dict[str, Any]], step: int) -> dict[str, Any]:
        """Process current signals and return enhanced analysis."""
        if not self._is_active:
            return {}

        signal_types = [s.get("type", "unknown") for s in signals]

        # Record signals
        for sig in signal_types:
            self.predictor.add_signal(sig)

        # Record co-occurrences
        if signal_types:
            self.analyzer.record_window(signal_types)

        # Get predictions
        predictions = self.predictor.predict()
        early_warning = self.predictor.get_early_warning()

        # Get best decision recommendation
        best_decision = self.feedback.get_best_decision(signal_types)

        # Detect cascades
        cascades = self.analyzer.detect_cascade(signal_types)

        return {
            "step": step,
            "current_signals": signal_types,
            "predictions": [
                {
                    "signal": p.predicted_signal,
                    "confidence": p.confidence,
                    "recommendation": p.recommendation,
                }
                for p in predictions[:3]
            ],
            "early_warning": early_warning,
            "recommended_decision": best_decision,
            "cascades": cascades,
        }

    def record_decision_outcome(
        self, step: int, signals_before: list[str], decision: str, signals_after: list[str]
    ) -> None:
        """Record the outcome of a decision for learning."""
        self.feedback.record_outcome(step, signals_before, decision, signals_after)

    def get_status(self) -> dict[str, Any]:
        """Get complete status of the neural signal system."""
        return {
            "is_active": self._is_active,
            "learned_patterns": len(self.learner.get_learned_patterns()),
            "decision_effectiveness": self.feedback.get_decision_effectiveness(),
            "signal_correlations": self.analyzer.get_correlations()[:5],
        }


_neural_signals: NeuralSignalSystem | None = None


def get_neural_signals() -> NeuralSignalSystem:
    global _neural_signals
    if _neural_signals is None:
        _neural_signals = NeuralSignalSystem()
    return _neural_signals
