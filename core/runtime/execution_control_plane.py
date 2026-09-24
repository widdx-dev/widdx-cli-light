"""Execution Control Plane — backward-compatible re-export.

All logic has been decomposed into:
  control/types.py       — ControlActionType, SignalType, ControlAction, ExecutionSignal
  control/evaluation.py  — signal-to-action evaluation engine
  control/policy.py      — stabilization guards (oscillation, cooldown, caps)
  control/execution_plane.py — thin orchestrator (ExecutionControlPlane class)

This module is the public API. It re-exports everything from the decomposed modules.
"""

from .control.types import (
    ControlAction,
    ControlActionType,
    ExecutionSignal,
    SignalType,
)
from .control.evaluation import evaluate_signals
from .control.policy import apply_stabilizers
from .control.execution_plane import (
    ExecutionControlPlane,
    get_control_plane,
)

__all__ = [
    "ControlAction",
    "ControlActionType",
    "ExecutionSignal",
    "SignalType",
    "ExecutionControlPlane",
    "get_control_plane",
    "evaluate_signals",
    "apply_stabilizers",
]
