"""Control types — data structures for the Execution Control Plane.

Single source of truth for ControlActionType, SignalType, ControlAction,
and ExecutionSignal. No logic — pure types.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ControlActionType(Enum):
    CONTINUE = auto()
    REPLAN = auto()
    SWITCH_MODEL = auto()
    ESCALATE_TO_EXPERT = auto()
    ABORT = auto()


class SignalType(Enum):
    STUCK = auto()
    LOOP_DETECTED = auto()
    TOOL_FAILURE_RATE = auto()
    CONFIDENCE_DROP = auto()
    TOKEN_INEFFICIENCY = auto()
    COMPLEXITY_DRIFT = auto()
    MEMORY_PRESSURE = auto()
    PROVIDER_FAILURE = auto()
    DEADLOCK = auto()
    QUALITY_DEGRADATION = auto()


@dataclass
class ControlAction:
    action: ControlActionType = ControlActionType.CONTINUE
    reason: str = ""
    model: str = ""
    confidence: float = 0.0
    escalation_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionSignal:
    signal_type: SignalType
    value: float = 0.0
    source: str = ""
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
