"""Execution State Controller (ESC) — Deterministic layer transition engine.

The CONTROL PLANE that sits ABOVE all 5 autonomy layers. The LLM operates
INSIDE the current layer — the ESC decides which layer is active based on
deterministic signals, not LLM inference.

State transitions:
  L1 (EXECUTE)   → default start
  L2 (RETRY)     ← L1 + error detected
  L3 (ADAPT)     ← L2 + repeated failure OR stuck detection
  L4 (PREDICT)   ← L3 + risk detected BEFORE execution
  L5 (CREATE)    ← L4 + all known strategies exhausted

The ESC NEVER delegates layer selection to the LLM. It uses only:
  - Error counts
  - Stuck detector signals
  - PreFailureSim risk scores
  - Pattern availability

This is the difference between:
  "agent with layers" (LLM-driven transitions)
  "engineered cognition loop" (deterministic state machine)

Usage:
    from core.execution_state_controller import ExecutionStateController
    esc = ExecutionStateController()
    esc.signal_error("write failed")
    current_layer = esc.current_layer  # → L2
    action = esc.get_action()  # → {"layer": "L2", "action": "retry_with_backoff"}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger("widdx.esc")


class AutonomyLayer(Enum):
    """Deterministic autonomy levels — controlled by ESC, not LLM."""
    L1_EXECUTE = auto()   # Normal execution
    L2_RETRY = auto()     # Error recovery with backoff
    L3_ADAPT = auto()     # Stuck → web learning, hot-reload
    L4_PREDICT = auto()   # Pre-failure simulation, strategy shift
    L5_CREATE = auto()    # All strategies exhausted → creative mode


@dataclass
class LayerAction:
    """What to do in the current layer."""
    layer: AutonomyLayer = AutonomyLayer.L1_EXECUTE
    action: str = "execute"          # "execute" | "retry" | "learn" | "predict" | "create"
    transition_reason: str = ""
    escalation_count: int = 0        # How many times we've escalated
    max_iterations: int = 25         # Max iterations in this layer
    current_iteration: int = 0


class ExecutionStateController:
    """Constraint-based controller for L1→L5 transitions.

    World Model does NOT advise ESC — it CONSTRAINS ESC's state space.
    ESC can ONLY transition to states that World Model has not removed.
    This is the difference between advisory intelligence and
    deterministic cognitive control.

    The CONTROL PLANE. LLM operates inside layers — ESC decides the layer.
    World Model removes invalid options before ESC chooses.
    """

    def __init__(self):
        self._current_layer = AutonomyLayer.L1_EXECUTE
        self._error_count: int = 0
        self._consecutive_errors: int = 0
        self._escalation_count: int = 0
        self._max_escalations: int = 5
        self._iteration_in_layer: int = 0
        self._stuck_signals: list[str] = []
        self._risk_score: float = 0.0
        self._alternatives_available: bool = True
        self._transition_log: list[dict] = []
        # ── Constraint Engine ──
        self._disabled_transitions: set[str] = set()  # transitions World Model removed
        self._forced_action: str = ""                 # if set, MUST use this action

    # ── Signal Inputs (called by external components) ──────

    def collect_state(self) -> dict:
        """Return current ESC state for ECP. PURE SENSOR — no side effects.
        
        Returns a dict with layer info, escalation count, and risk signals
        that ECP uses to make decisions.
        """
        return {
            "layer": self._current_layer.name,
            "layer_value": self._current_layer.value,
            "error_count": self._error_count,
            "consecutive_errors": self._consecutive_errors,
            "escalation_count": self._escalation_count,
            "stuck_signals": self._stuck_signals.copy(),
            "risk_score": self._risk_score,
            "is_deadlocked": self._escalation_count >= 3,
            "is_at_max": self._escalation_count >= self._max_escalations,
            "alternatives_available": self._alternatives_available,
            "current_layer": self.layer_name,
        }

    # ── Constraint API (called by World Model) ─────────────

    def disable_transition(self, from_layer: str, to_layer: str, reason: str):
        """World Model removes this transition from ESC's available options.
        ESC CANNOT choose this transition. It is removed from state space."""
        key = f"{from_layer}→{to_layer}"
        self._disabled_transitions.add(key)
        logger.warning("ESC constrained: %s DISABLED — %s", key, reason[:100])

    def force_action(self, action: str, reason: str):
        """World Model forces ESC to use a specific action.
        ESC MUST use this. No choice."""
        self._forced_action = action
        logger.warning("ESC constrained: FORCED action '%s' — %s", action, reason[:100])

    def clear_constraints(self):
        """Reset all constraints (called at task start)."""
        self._disabled_transitions.clear()
        self._forced_action = ""

    # ── Signal Inputs ──────────────────────────────────────

    def signal_error(self, error_msg: str = "", steps: list[str] | None = None, tool: str = ""):
        """An error occurred. ESC asks World Model BEFORE escalating.

        World Model now CONSTRAINS ESC — it can REMOVE options from ESC's
        state space. If World Model determines 'retry won't fix this',
        the L2_RETRY transition is disabled and ESC MUST go to L4.
        """
        self._error_count += 1
        self._consecutive_errors += 1

        # ── World Model: diagnose and CONSTRAIN ──
        try:
            from core.world_model import get_world_model
            wm = get_world_model()
            diagnosis = wm.diagnose_failure(error_msg, steps or [], tool)
            if diagnosis.skip_retry:
                # CONSTRAINT: remove L2_RETRY and L3_ADAPT from state space
                self.disable_transition("L2_RETRY", "L3_ADAPT",
                                       f"WorldModel: {diagnosis.root_cause}")
                self.disable_transition("L1_EXECUTE", "L2_RETRY",
                                       f"WorldModel: {diagnosis.root_cause}")
                # Force redesign path
                self.force_action("redesign",
                                 f"{diagnosis.root_cause} requires architectural change")
                logger.warning("ESC constrained: retry paths DISABLED — %s", diagnosis.root_cause)
                self._maybe_transition(AutonomyLayer.L4_PREDICT,
                                      f"WorldModel: {diagnosis.root_cause} — {diagnosis.reasoning[:100]}")
                return
        except Exception:
            logger.debug("Exception suppressed (line 160)")

        if self._consecutive_errors >= 1:
            self._maybe_transition(AutonomyLayer.L2_RETRY, f"Error: {error_msg[:80]}")

    def signal_recovery(self):
        """Error was recovered. ESC resets to L1."""
        self._consecutive_errors = 0
        self._maybe_transition(AutonomyLayer.L1_EXECUTE, "Error recovered")

    def signal_stuck(self, reasons: list[str]):
        """StuckDetector found the agent is stuck. ESC may escalate to L3."""
        self._stuck_signals = reasons
        if len(reasons) >= 2:  # Multi-signal confirmation
            self._maybe_transition(AutonomyLayer.L3_ADAPT, f"Stuck: {reasons[0][:80]}")

    def signal_risk(self, risk_score: float, alternatives: int):
        """PreFailureSim evaluated the plan. ESC may escalate to L4."""
        self._risk_score = risk_score
        self._alternatives_available = alternatives > 0
        if risk_score >= 0.6 and not self._alternatives_available:
            self._maybe_transition(AutonomyLayer.L4_PREDICT,
                                  f"High risk ({risk_score:.2f}), no alternatives")

    def signal_exhausted(self):
        """All strategies failed. ESC escalates to L5."""
        self._maybe_transition(AutonomyLayer.L5_CREATE,
                              "All known strategies exhausted")

    def signal_complete(self):
        """Task completed successfully. ESC resets to L1 + clears constraints."""
        self._current_layer = AutonomyLayer.L1_EXECUTE
        self._error_count = 0
        self._consecutive_errors = 0
        self._escalation_count = 0
        self._iteration_in_layer = 0
        self.clear_constraints()

    # ── Internal Transition Logic ─────────────────────────

    def _maybe_transition(self, target: AutonomyLayer, reason: str):
        """Transition to target layer if it's an escalation AND not constrained.

        World Model constraints are checked: if a transition was disabled,
        ESC CANNOT use it. This is the difference between advisory and
        deterministic control.
        """
        # ── CONSTRAINT CHECK ──
        transition_key = f"{self._current_layer.name}→{target.name}"
        if transition_key in self._disabled_transitions:
            logger.warning("ESC: transition %s BLOCKED by World Model constraint", transition_key)
            return  # Cannot make this transition

        if self._forced_action and target != AutonomyLayer.L4_PREDICT and target != AutonomyLayer.L5_CREATE:
            logger.warning("ESC: transition to %s blocked — forced action is '%s'", target.name, self._forced_action)
            return  # Must use forced action path

        if target.value > self._current_layer.value:
            old = self._current_layer
            self._current_layer = target
            self._escalation_count += 1
            self._iteration_in_layer = 0
            entry = {
                "from": old.name, "to": target.name,
                "reason": reason, "escalation": self._escalation_count,
                "forced": bool(self._forced_action),
            }
            self._transition_log.append(entry)
            logger.warning("ESC: %s → %s (escalation #%d: %s) %s",
                          old.name, target.name, self._escalation_count, reason[:100],
                          "[FORCED]" if self._forced_action else "")
        elif target.value < self._current_layer.value:
            old = self._current_layer
            self._current_layer = target
            self._iteration_in_layer = 0
            logger.info("ESC: %s → %s (de-escalation: %s)",
                       old.name, target.name, reason[:100])

    # ── Public API ─────────────────────────────────────────

    @property
    def current_layer(self) -> AutonomyLayer:
        return self._current_layer

    @property
    def layer_name(self) -> str:
        return self._current_layer.name

    def tick(self) -> LayerAction:
        """Called each iteration. Returns what to do now."""
        self._iteration_in_layer += 1

        # Safety: max escalations
        if self._escalation_count > self._max_escalations:
            return LayerAction(
                layer=AutonomyLayer.L5_CREATE,
                action="create",
                transition_reason="Max escalations reached — creative mode only",
                escalation_count=self._escalation_count,
                current_iteration=self._iteration_in_layer,
            )

        if self._current_layer == AutonomyLayer.L1_EXECUTE:
            return LayerAction(layer=self._current_layer, action="execute",
                              escalation_count=self._escalation_count,
                              current_iteration=self._iteration_in_layer)
        elif self._current_layer == AutonomyLayer.L2_RETRY:
            return LayerAction(layer=self._current_layer, action="retry",
                              transition_reason=f"Error count: {self._error_count}",
                              escalation_count=self._escalation_count,
                              current_iteration=self._iteration_in_layer)
        elif self._current_layer == AutonomyLayer.L3_ADAPT:
            return LayerAction(layer=self._current_layer, action="learn",
                              transition_reason="; ".join(self._stuck_signals[:2]),
                              escalation_count=self._escalation_count,
                              current_iteration=self._iteration_in_layer)
        elif self._current_layer == AutonomyLayer.L4_PREDICT:
            return LayerAction(layer=self._current_layer, action="predict",
                              transition_reason=f"Risk: {self._risk_score:.2f}",
                              escalation_count=self._escalation_count,
                              current_iteration=self._iteration_in_layer)
        else:  # L5_CREATE
            return LayerAction(layer=self._current_layer, action="create",
                              transition_reason="All strategies exhausted",
                              escalation_count=self._escalation_count,
                              current_iteration=self._iteration_in_layer)

    def get_action(self) -> dict:
        """Get the current layer action as a dict for external use."""
        la = self.tick()
        return {
            "layer": la.layer.name,
            "action": la.action,
            "escalation": la.escalation_count,
            "iteration": la.current_iteration,
            "reason": la.transition_reason,
        }

    @property
    def transition_history(self) -> list[dict]:
        return list(self._transition_log)

    @property
    def is_at_max_escalation(self) -> bool:
        return self._escalation_count >= self._max_escalations


# Singleton
_esc: ExecutionStateController | None = None


def get_execution_state_controller() -> ExecutionStateController:
    global _esc
    if _esc is None:
        _esc = ExecutionStateController()
    return _esc
