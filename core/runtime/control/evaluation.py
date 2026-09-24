"""Signal evaluation engine — priority-based signal-to-action mapping.

Pure function: signals → raw decision. No stabilization, no policy.
"""

from __future__ import annotations

import logging

from .types import ControlAction, ControlActionType, ExecutionSignal, SignalType

logger = logging.getLogger("widdx.ecp.evaluation")


DEFAULT_CONFIDENCE_THRESHOLD = 0.3
DEFAULT_COMPLEXITY_THRESHOLD = 0.7
DEFAULT_FAILURE_RATE_THRESHOLD = 0.5
DEFAULT_STUCK_ITERATIONS = 5
DEFAULT_TOKEN_INEFFICIENCY_THRESHOLD = 0.6


def _get_adaptive_thresholds() -> dict[str, float]:
    """Try to get learned thresholds from AdaptivePolicy. Falls back to defaults."""
    try:
        from .adaptive_policy import get_adaptive_policy
        return get_adaptive_policy().recommend()
    except Exception:
        return {}


def evaluate_signals(
    signals: list[ExecutionSignal],
    step: int,
    current_model: str = "",
    model_switch_count: int = 0,
    max_model_switches: int = 3,
    escalated: bool = False,
    tool_failures: list[bool] | None = None,
    previous_decisions: list[ControlAction] | None = None,
) -> ControlAction:
    """Transform signals into a raw control action (no stabilization).

    Priority order:
      P1: Abort conditions
      P2: MEMORY_PRESSURE → ABORT
      P3: DEADLOCK → ESCALATE_TO_EXPERT
      P4: LOOP_DETECTED → REPLAN
      P5: STUCK → REPLAN or ESCALATE
      P6: High failure rate → SWITCH_MODEL or ESCALATE
      P7: QUALITY_DEGRADATION → SWITCH_MODEL or REPLAN
      P8: COMPLEXITY_DRIFT → ESCALATE
      P9: TOKEN_INEFFICIENCY → SWITCH_MODEL (downgrade)
      Default: CONTINUE

    Thresholds are adaptive — learned from scorer feedback via AdaptivePolicy.
    """
    if not signals:
        return ControlAction(action=ControlActionType.CONTINUE, confidence=1.0)

    adaptive = _get_adaptive_thresholds()
    failure_threshold = adaptive.get("failure_rate_threshold", DEFAULT_FAILURE_RATE_THRESHOLD)
    complexity_threshold = adaptive.get("complexity_threshold", DEFAULT_COMPLEXITY_THRESHOLD)
    stuck_iters = int(adaptive.get("stuck_iterations", DEFAULT_STUCK_ITERATIONS))
    int(adaptive.get("action_cap", 8))
    int(adaptive.get("cooldown_steps", 2))

    signal_types: set[SignalType] = {s.signal_type for s in signals}

    # P1: Abort conditions
    abort_decision = _check_abort(
        signals, step, model_switch_count,
        max_model_switches, escalated,
        tool_failures or [], previous_decisions or []
    )
    if abort_decision.action == ControlActionType.ABORT:
        return abort_decision

    # P2: Memory pressure
    if SignalType.MEMORY_PRESSURE in signal_types:
        return ControlAction(
            action=ControlActionType.ABORT,
            reason="Memory pressure critical — cannot continue safely",
            confidence=0.9,
        )

    # P3: Deadlock
    if SignalType.DEADLOCK in signal_types:
        if not escalated:
            return ControlAction(
                action=ControlActionType.ESCALATE_TO_EXPERT,
                reason="Deadlock detected by ESC — escalating to expert team",
                confidence=0.85,
            )

    # P4: Loop detection
    if SignalType.LOOP_DETECTED in signal_types:
        return ControlAction(
            action=ControlActionType.REPLAN,
            reason="Repetitive loop detected — regenerating plan",
            confidence=0.8,
        )

    # P5: Stuck
    if SignalType.STUCK in signal_types:
        if step > stuck_iters and not escalated:
            return ControlAction(
                action=ControlActionType.ESCALATE_TO_EXPERT,
                reason=f"Stuck after {step} iterations — escalating to expert team",
                confidence=0.75,
            )
        return ControlAction(
            action=ControlActionType.REPLAN,
            reason=f"Stuck detected at step {step} — regenerating plan",
            confidence=0.7,
        )

    # P6: Tool failure rate
    failure_rate = _compute_failure_rate(tool_failures or [])
    if failure_rate >= failure_threshold:
        if model_switch_count < max_model_switches:
            return _decide_model_switch(step, current_model, model_switch_count)

        if not escalated:
            return ControlAction(
                action=ControlActionType.ESCALATE_TO_EXPERT,
                reason=f"Tool failure rate {failure_rate:.0%} exceeds threshold — "
                       f"max model switches reached, escalating to expert team",
                confidence=0.7,
            )

        return ControlAction(
            action=ControlActionType.REPLAN,
            reason=f"Tool failure rate {failure_rate:.0%} — replanning",
            confidence=0.6,
        )

    # P7: Quality degradation
    if SignalType.QUALITY_DEGRADATION in signal_types:
        if model_switch_count < max_model_switches:
            return _decide_model_switch(step, current_model, model_switch_count)
        return ControlAction(
            action=ControlActionType.REPLAN,
            reason="Sustained quality degradation — replanning",
            confidence=0.55,
        )

    # P8: Complexity drift
    if SignalType.COMPLEXITY_DRIFT in signal_types:
        drift_signal = next(
            (s for s in signals if s.signal_type == SignalType.COMPLEXITY_DRIFT), None
        )
        if drift_signal and drift_signal.value >= complexity_threshold:
            if not escalated:
                return ControlAction(
                    action=ControlActionType.ESCALATE_TO_EXPERT,
                    reason=f"Task complexity drifted to {drift_signal.value:.2f} — escalating",
                    confidence=0.65,
                )
            return ControlAction(
                action=ControlActionType.REPLAN,
                reason=f"Complexity drift {drift_signal.value:.2f} — replanning",
                confidence=0.55,
            )

    # P9: Token inefficiency
    if SignalType.TOKEN_INEFFICIENCY in signal_types:
        if "flash" not in current_model.lower():
            flash_candidates = ["deepseek-chat", "deepseek-v3-flash", "gpt-4o-mini"]
            for candidate in flash_candidates:
                if candidate not in current_model.lower():
                    return ControlAction(
                        action=ControlActionType.SWITCH_MODEL,
                        reason=f"Token inefficiency detected — switching to {candidate}",
                        model=candidate,
                        confidence=0.6,
                    )

    return ControlAction(action=ControlActionType.CONTINUE, confidence=0.9)


def _check_abort(
    signals: list[ExecutionSignal],
    step: int,
    model_switch_count: int,
    max_model_switches: int,
    escalated: bool,
    tool_failures: list[bool],
    previous_decisions: list[ControlAction],
) -> ControlAction:
    """Check if execution should be aborted."""
    has_provider_failure = any(
        s.signal_type == SignalType.PROVIDER_FAILURE for s in signals
    )
    if has_provider_failure and step > 3:
        return ControlAction(
            action=ControlActionType.ABORT,
            reason="Provider failure persists — aborting execution",
            confidence=0.8,
        )

    replay_count = sum(
        1 for d in previous_decisions if d.action == ControlActionType.REPLAN
    )
    # Dynamic abort limit: 3 for 25-step tasks, proportionally more for longer tasks
    # A task with 80 steps needs ~10 replans before abort (3 * 80/25 ≈ 10)
    try:
        from .policy import _task_scope_multiplier
        replan_abort_limit = max(3, int(3 * _task_scope_multiplier))
    except Exception:
        replan_abort_limit = 3
    if replay_count >= replan_abort_limit:
        return ControlAction(
            action=ControlActionType.ABORT,
            reason=f"Replanning {replay_count} times without resolution — aborting",
            confidence=0.9,
        )

    if model_switch_count >= max_model_switches and step > 10:
        failure_rate = _compute_failure_rate(tool_failures)
        if failure_rate >= 0.6 and escalated:
            return ControlAction(
                action=ControlActionType.ABORT,
                reason="All strategies exhausted (switches + escalation) — aborting",
                confidence=0.85,
            )

    return ControlAction(action=ControlActionType.CONTINUE, confidence=1.0)


def _decide_model_switch(step: int, current_model: str, switch_count: int) -> ControlAction:
    """Determine which model to switch to."""
    is_flash = "flash" in current_model.lower() or "v3" in current_model.lower()
    is_mini = "mini" in current_model.lower()

    if is_flash or is_mini:
        pro_candidates = ["deepseek-v4-pro", "deepseek-chat", "gpt-4o"]
        for candidate in pro_candidates:
            if candidate not in current_model.lower():
                return ControlAction(
                    action=ControlActionType.SWITCH_MODEL,
                    reason=f"Upgrading model at step {step}: {current_model} → {candidate}",
                    model=candidate,
                    confidence=0.7,
                    metadata={"direction": "upgrade", "switch_count": switch_count + 1},
                )
    else:
        flash_candidates = ["deepseek-v3-flash", "deepseek-chat", "gpt-4o-mini"]
        for candidate in flash_candidates:
            if candidate not in current_model.lower():
                return ControlAction(
                    action=ControlActionType.SWITCH_MODEL,
                    reason=f"Degrading model at step {step}: {current_model} → {candidate}",
                    model=candidate,
                    confidence=0.6,
                    metadata={"direction": "downgrade", "switch_count": switch_count + 1},
                )

    return ControlAction(
        action=ControlActionType.REPLAN,
        reason=f"Model switch at step {step} failed to find target — replanning",
        confidence=0.5,
    )


def _compute_failure_rate(tool_failures: list[bool]) -> float:
    """Compute rolling tool failure rate."""
    if not tool_failures:
        return 0.0
    recent = tool_failures[-10:]
    return sum(recent) / len(recent)
