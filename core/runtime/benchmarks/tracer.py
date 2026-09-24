"""Decision tracer — logs every control decision for benchmarking and replay.

Records: timestamp, step, signal summary, raw decision, stabilized decision,
decision delta (whether policy changed the raw outcome).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..control.types import ControlAction, ExecutionSignal


logger = logging.getLogger("widdx.benchmarks.tracer")


@dataclass
class DecisionTrace:
    """Complete trace of a single control decision."""
    timestamp: float = 0.0
    step: int = 0
    phase: str = ""  # "before" or "after"
    signals_input: list[str] = field(default_factory=list)
    signal_count: int = 0
    raw_action: str = ""
    stabilized_action: str = ""
    policy_applied: bool = False
    reason: str = ""
    confidence: float = 0.0
    cooldown_active: bool = False
    action_cap_active: bool = False
    oscillation_guard_fired: bool = False
    elapsed_ms: float = 0.0


class DecisionTracer:
    """Records every ECP decision for post-execution analysis."""

    def __init__(self):
        self._traces: list[DecisionTrace] = []
        self._start_time: float = 0.0

    def start(self):
        self._traces.clear()
        self._start_time = time.time()

    def trace(
        self,
        step: int,
        phase: str,
        signals: list[ExecutionSignal],
        raw: ControlAction,
        stabilized: ControlAction,
        cooldown: bool = False,
        cap_active: bool = False,
        oscillation: bool = False,
    ):
        self._traces.append(DecisionTrace(
            timestamp=time.time() - self._start_time,
            step=step,
            phase=phase,
            signals_input=[f"{s.signal_type.name}({s.value:.2f})" for s in signals],
            signal_count=len(signals),
            raw_action=raw.action.name,
            stabilized_action=stabilized.action.name,
            policy_applied=raw.action != stabilized.action,
            reason=stabilized.reason,
            confidence=stabilized.confidence,
            cooldown_active=cooldown,
            action_cap_active=cap_active,
            oscillation_guard_fired=oscillation,
        ))

    def to_dicts(self) -> list[dict]:
        return [
            {
                "t": round(t.timestamp, 4),
                "step": t.step,
                "phase": t.phase,
                "signals": t.signals_input,
                "raw": t.raw_action,
                "final": t.stabilized_action,
                "policy": t.policy_applied,
                "reason": t.reason,
                "confidence": round(t.confidence, 2),
                "cooldown": t.cooldown_active,
            }
            for t in self._traces
        ]

    def get_traces(self) -> list[DecisionTrace]:
        """Return a copy of all recorded decision traces."""
        return list(self._traces)

    def reset(self):
        """Clear all traces and reset start time."""
        self._traces.clear()
        self._start_time = 0.0

    def save(self, path: str | Path = ".widdx/decision_trace.json"):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dicts(), indent=2), encoding="utf-8")
        logger.info("Decision trace saved: %d decisions → %s", len(self._traces), path)

    @property
    def summary(self) -> dict:
        if not self._traces:
            return {}
        actions = [t.stabilized_action for t in self._traces]
        policy_hits = sum(1 for t in self._traces if t.policy_applied)
        return {
            "total_decisions": len(self._traces),
            "actions": {a: actions.count(a) for a in set(actions)},
            "policy_interventions": policy_hits,
            "policy_rate": round(policy_hits / len(self._traces), 3) if self._traces else 0,
            "avg_confidence": round(sum(t.confidence for t in self._traces) / len(self._traces), 3),
        }


_tracer: DecisionTracer | None = None


def get_tracer() -> DecisionTracer:
    global _tracer
    if _tracer is None:
        _tracer = DecisionTracer()
    return _tracer
