"""Real ML Signal Predictor — uses actual machine learning for prediction.

Implements:
  1. Feature extraction from signal patterns
  2. Anomaly detection using statistical methods
  3. Pattern classification for signal prediction
  4. Online learning from new data
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("widdx.ml_predictor")


@dataclass
class SignalFeatures:
    """Features extracted from signal history for ML."""
    signal_type: str
    frequency: float  # signals per minute
    recency: float  # seconds since last occurrence
    co_occurrence_count: int  # how many other signals appear with this
    trend: float  # increasing (+1), stable (0), decreasing (-1)
    avg_value: float  # average signal value
    std_value: float  # standard deviation of values


@dataclass
class AnomalyScore:
    """Anomaly detection result."""
    signal_type: str
    is_anomaly: bool
    anomaly_score: float  # 0 = normal, 1 = highly anomalous
    expected_range: tuple[float, float]
    actual_value: float
    explanation: str


class StatisticalAnomalyDetector:
    """Detects anomalies using statistical methods (Z-score + IQR)."""

    def __init__(self, z_threshold: float = 2.0):
        self._history: dict[str, list[float]] = {}
        self._z_threshold = z_threshold
        self._window_size = 100

    def add_value(self, signal_type: str, value: float) -> None:
        """Add a value to the history."""
        if signal_type not in self._history:
            self._history[signal_type] = []
        self._history[signal_type].append(value)
        if len(self._history[signal_type]) > self._window_size:
            self._history[signal_type] = self._history[signal_type][-self._window_size:]

    def detect(self, signal_type: str, value: float) -> AnomalyScore:
        """Detect if a value is anomalous."""
        history = self._history.get(signal_type, [])

        if len(history) < 5:
            return AnomalyScore(
                signal_type=signal_type,
                is_anomaly=False,
                anomaly_score=0.0,
                expected_range=(0.0, 1.0),
                actual_value=value,
                explanation="Insufficient data",
            )

        # Calculate statistics
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = math.sqrt(variance) if variance > 0 else 0.001

        # Z-score
        z_score = abs(value - mean) / std if std > 0 else 0

        # IQR method
        sorted_history = sorted(history)
        q1_idx = len(sorted_history) // 4
        q3_idx = 3 * len(sorted_history) // 4
        q1 = sorted_history[q1_idx]
        q3 = sorted_history[q3_idx]
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        # Combined anomaly score
        is_anomaly = z_score > self._z_threshold or value < lower_bound or value > upper_bound
        anomaly_score = min(1.0, z_score / (self._z_threshold * 2))

        return AnomalyScore(
            signal_type=signal_type,
            is_anomaly=is_anomaly,
            anomaly_score=round(anomaly_score, 3),
            expected_range=(round(lower_bound, 3), round(upper_bound, 3)),
            actual_value=value,
            explanation=(
                f"Z-score={z_score:.2f}, IQR range=[{lower_bound:.3f}, {upper_bound:.3f}]"
            ),
        )

    def get_baseline(self, signal_type: str) -> dict[str, float]:
        """Get baseline statistics for a signal type."""
        history = self._history.get(signal_type, [])
        if not history:
            return {"mean": 0, "std": 0, "count": 0}

        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        return {
            "mean": round(mean, 4),
            "std": round(math.sqrt(variance), 4),
            "count": len(history),
        }


class MarkovChainPredictor:
    """Predicts next signal using Markov chain transition probabilities."""

    def __init__(self, order: int = 2):
        self._order = order
        self._transitions: dict[tuple[str, ...], dict[str, int]] = {}
        self._totals: dict[tuple[str, ...], int] = {}

    def train(self, sequence: list[str]) -> None:
        """Train on a sequence of signals."""
        if len(sequence) <= self._order:
            return

        for i in range(len(sequence) - self._order):
            state = tuple(sequence[i:i + self._order])
            next_state = sequence[i + self._order]

            if state not in self._transitions:
                self._transitions[state] = {}
                self._totals[state] = 0

            self._transitions[state][next_state] = self._transitions[state].get(next_state, 0) + 1
            self._totals[state] += 1

    def predict(self, recent_sequence: list[str]) -> dict[str, float]:
        """Predict next signal probabilities."""
        if len(recent_sequence) < self._order:
            return {}

        state = tuple(recent_sequence[-self._order:])
        if state not in self._transitions:
            return {}

        transitions = self._transitions[state]
        total = self._totals[state]

        return {signal: count / total for signal, count in transitions.items()}

    def get_top_prediction(self, recent_sequence: list[str]) -> tuple[str, float] | None:
        """Get the most likely next signal."""
        predictions = self.predict(recent_sequence)
        if not predictions:
            return None

        top_signal = max(predictions, key=lambda k: predictions[k])
        return top_signal, predictions[top_signal]


class TrendAnalyzer:
    """Analyzes trends in signal values."""

    def __init__(self, window_size: int = 10):
        self._window_size = window_size
        self._values: dict[str, list[tuple[float, float]]] = {}

    def add(self, signal_type: str, value: float, timestamp: float | None = None) -> None:
        """Add a value with timestamp."""
        ts = timestamp or time.time()
        if signal_type not in self._values:
            self._values[signal_type] = []
        self._values[signal_type].append((ts, value))
        if len(self._values[signal_type]) > self._window_size:
            self._values[signal_type] = self._values[signal_type][-self._window_size:]

    def get_trend(self, signal_type: str) -> dict[str, Any]:
        """Get trend analysis for a signal type."""
        values = self._values.get(signal_type, [])
        if len(values) < 3:
            return {"trend": "insufficient_data", "slope": 0}

        # Simple linear regression
        n = len(values)
        sum_x = sum(v[0] for v in values)
        sum_y = sum(v[1] for v in values)
        sum_xy = sum(v[0] * v[1] for v in values)
        sum_x2 = sum(v[0] ** 2 for v in values)

        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return {"trend": "stable", "slope": 0}

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        if slope > 0.01:
            trend = "increasing"
        elif slope < -0.01:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "slope": round(slope, 6),
            "current_value": values[-1][1],
            "change_rate": round(slope * 60, 4),  # per minute
        }

    def is_deteriorating(self, signal_type: str, threshold: float = 0.05) -> bool:
        """Check if a signal is getting worse."""
        trend = self.get_trend(signal_type)
        return trend.get("trend") == "increasing" and trend.get("slope", 0) > threshold


class MLPredictionSystem:
    """Unified ML system for signal prediction."""

    def __init__(self):
        self.anomaly_detector = StatisticalAnomalyDetector()
        self.markov_predictor = MarkovChainPredictor(order=2)
        self.trend_analyzer = TrendAnalyzer()
        self._signal_sequence: list[str] = []
        self._is_trained = False

    def add_signal(self, signal_type: str, value: float = 0.5) -> None:
        """Add a signal to the system."""
        self.anomaly_detector.add_value(signal_type, value)
        self.trend_analyzer.add(signal_type, value)
        self._signal_sequence.append(signal_type)

        # Retrain Markov chain every 50 signals
        if len(self._signal_sequence) % 50 == 0:
            self.markov_predictor.train(self._signal_sequence)
            self._is_trained = True

    def predict(self) -> dict[str, Any]:
        """Get comprehensive prediction."""
        # Markov prediction
        markov_pred = self.markov_predictor.get_top_prediction(self._signal_sequence)

        # Anomaly detection for recent signals
        recent = self._signal_sequence[-5:] if len(self._signal_sequence) >= 5 else self._signal_sequence
        anomalies = []
        for signal in set(recent):
            trend = self.trend_analyzer.get_trend(signal)
            if trend.get("trend") == "increasing":
                anomalies.append({
                    "signal": signal,
                    "trend": trend["trend"],
                    "rate": trend.get("change_rate", 0),
                })

        return {
            "next_signal": markov_pred[0] if markov_pred else None,
            "confidence": markov_pred[1] if markov_pred else 0,
            "anomalies": anomalies,
            "is_trained": self._is_trained,
            "sequence_length": len(self._signal_sequence),
        }

    def get_signal_health(self, signal_type: str) -> dict[str, Any]:
        """Get health status for a signal type."""
        baseline = self.anomaly_detector.get_baseline(signal_type)
        trend = self.trend_analyzer.get_trend(signal_type)
        is_deteriorating = self.trend_analyzer.is_deteriorating(signal_type)

        return {
            "signal_type": signal_type,
            "baseline": baseline,
            "trend": trend,
            "is_deteriorating": is_deteriorating,
            "status": "critical" if is_deteriorating else "healthy",
        }


_ml_predictor: MLPredictionSystem | None = None


def get_ml_predictor() -> MLPredictionSystem:
    global _ml_predictor
    if _ml_predictor is None:
        _ml_predictor = MLPredictionSystem()
    return _ml_predictor
