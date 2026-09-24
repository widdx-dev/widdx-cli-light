"""Real autonomous agent — AI-driven tool-calling loop with full control.

This implementation wraps tool execution, tracks steps, and enforces
automatic validation after file writes/edits and after `bash` commands
that create/modify known source files.
"""

import json
import logging
import uuid
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

from rich.panel import Panel
from rich.text import Text

from .. import tools as core_tools
from ..skills import skill_manager as _skill_manager
from ..chat import (
    console, print_system_msg, print_tool_call, print_tool_msg,
    print_reasoning, print_ai_stream, print_agent_done,
)
from ..providers.providers import estimate_turn_cost
from ..tool_tracer import t as tool_tracer
from ..provider_reliability import ProviderStreamError


def _vid(tc_id) -> str:
    """Ensure tool_call_id is a non-empty string."""
    if not tc_id or not isinstance(tc_id, str) or not tc_id.strip():
        return f"call_{uuid.uuid4().hex[:12]}"
    return tc_id


# ---------------------------------------------------------------------------
# Agent System Prompt
# ---------------------------------------------------------------------------

AGENT_PROMPT = """# WIDDX Nexus — Autonomous Agent

You are WIDDX Nexus, by MUHAMMAD MUSLIH (widdx.com). 🇵🇸
Your strength is the system: tools, sandbox, delegation, memory.

AVAILABLE TOOLS:
{tool_descriptions}

PROJECT DOCS (check these first):
{project_docs_block}

WORKFLOW:
1. Receive a task from the user
2. FIRST: check project docs (PLAN.md, DESIGN.md, TASKS.md, ROADMAP.md) to understand the project
3. Think step by step about what needs to be done
4. Call ONE tool at a time, analyze the result, then decide next step
5. If a tool fails, analyze the error and try a different approach
6. If you need clarification, use **ask_user** tool to ask the user
7. Validate after every write/edit — quality first
8. When complete, update TASKS.md and summarize what was accomplished

RULES:
- Call one tool at a time (you can call many in sequence)
- YOU MUST use the write tool to create files. NEVER just describe code in text.
- If the user asks you to build/create/make something, use tools to do it.
- After each tool result, analyze and decide what to do next
- On failure: explain what happened, then try a different approach
- ALWAYS run validate after writing or editing code
- NEVER say you're done until the files actually exist on disk
- Your final response MUST be a summary of what was actually accomplished
- Use **ask_user** when the task is ambiguous or you need a decision

ANTI-DUPLICATION (MANDATORY):
- Before creating ANY new variable/function/class: grep the file first.
  If it already exists, REUSE it — do NOT redeclare.
- Duplicate declarations cause fatal SyntaxError and break the app.
- Before ANY edit: Read the target area first — never edit blind.

VERIFICATION (MANDATORY):
- After EVERY file edit, run a syntax check:
  JavaScript: node --check <file>
  Python:     python -m py_compile <file>
- If syntax check FAILS, fix immediately — do NOT proceed.
- After all edits pass: run the project and verify it WORKS.

AUTO-PREVIEW (MANDATORY for HTML/CSS/JS files):
- After creating ANY .html file, you MUST open it in the browser immediately
  using the browser tool to verify it renders correctly.
- After creating a web project, ALWAYS start a local server and preview it.
- Never consider a web project "done" until you have seen it working."""


# ---------------------------------------------------------------------------
# Containment inputs — real measurements from the invariance / Lyapunov / SPC
# layers. These replace the former hardcoded placeholder values.
# ---------------------------------------------------------------------------


def _measure_invariance_score() -> float:
    """Invariance consistency in [0, 1] from the CognitiveInvariance layer.

    Falls back to 1.0 (no violations) when the layer is unavailable, so the
    containment bound stays permissive instead of silently passing a fake value.
    """
    try:
        from core.runtime.semantic import get_cognitive_invariance
        guarantees = get_cognitive_invariance().get_guarantees()
        total = guarantees.get("validations_total", 0)
        passed = guarantees.get("validations_passed", 0)
        if total <= 0:
            return 1.0
        return max(0.0, min(1.0, passed / total))
    except Exception as inv_e:
        logger.debug("Invariance score unavailable, defaulting to 1.0: %s", inv_e)
        return 1.0


def _measure_lyapunov_drift() -> float:
    """Current Lyapunov function value V(θ) from the LyapunovAnalyzer.

    Returns 0.0 (at the optimum) when analysis is unavailable.
    """
    try:
        from core.runtime.lyapunov import get_lyapunov_analyzer
        return float(get_lyapunov_analyzer().get_stability_certificate().get("current_v", 0.0))
    except Exception as lyap_e:
        logger.debug("Lyapunov drift unavailable, defaulting to 0.0: %s", lyap_e)
        return 0.0


def _count_spc_violations() -> int:
    """Number of Statistical Process Control violations from containment's
    acceptance-control subsystem (1 when the process is out of control)."""
    try:
        from core.runtime.containment import get_containment
        verdict = get_containment().acceptance.check()
        return 0 if verdict.get("in_control", True) else 1
    except Exception as spc_e:
        logger.debug("SPC violations unavailable, defaulting to 0: %s", spc_e)
        return 0


# ---------------------------------------------------------------------------
# Agent Step Tracking
# ---------------------------------------------------------------------------


class AgentStep:
    """A single dynamically-recorded step during agent execution."""

    def __init__(self, step_num: int, tool_name: str, args: dict, result: str):
        self.step_num = step_num
        self.tool_name = tool_name
        self.args = args
        self.result = result
        self.status = "done" if self._is_success(result) else "failed"

    def _is_success(self, result: str) -> bool:
        if not result or not result.strip():
            return False
        normalized = result.strip()
        failure_prefixes = ("❌", "⚠️", "⚠", "⛔", "Error", "Failed", "No such", "File not found")
        return not normalized.startswith(failure_prefixes)

    def to_dict(self) -> dict:
        return {
            "step": self.step_num,
            "tool": self.tool_name,
            "args": self.args,
            "result": self.result[:500],
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# Autonomous Agent
# ---------------------------------------------------------------------------


class AutonomousAgent:
    """Real autonomous agent with real-time tool-calling loop.
    The AI is in full control — it decides which tools to call,
    when to retry, when to ask the user, and when to finish.
    """

    def __init__(self, provider, tool_defs: list, cfg: dict, state: dict,
                 custom_prompt: Optional[str] = None,
                 on_event: Optional[Any] = None):
        self.provider = provider
        self.tool_defs = tool_defs
        self.cfg = cfg
        self.state = state
        self.custom_prompt = custom_prompt
        self.steps: list[AgentStep] = []
        self.cost = 0.0
        self._on_event = on_event  # callable(event_dict) for live Web UI streaming

    def _clean_event(self, event: dict) -> dict:
        """Remove surrogate characters from event data."""
        if not event:
            return event
        import re
        _sur = re.compile(r'[\ud800-\udfff]')
        cleaned: dict[str, Any] = {}
        for k, v in event.items():
            if isinstance(v, str):
                cleaned[k] = _sur.sub('\ufffd', v)
            elif isinstance(v, dict):
                cleaned[k] = self._clean_event(v)
            elif isinstance(v, list):
                cleaned[k] = [
                    self._clean_event(i) if isinstance(i, dict)
                    else _sur.sub('\ufffd', i) if isinstance(i, str)
                    else i
                    for i in v
                ]
            else:
                cleaned[k] = v
        return cleaned

    def _emit(self, event: dict):
        """Emit a streaming event to the Web UI if callback is set."""
        if self._on_event:
            try:
                self._on_event(self._clean_event(event))
            except Exception as e:
                logger.warning("Failed to emit streaming event: %s", e)

    def _call_provider_with_retry(self, messages, temperature, ts=None):
        """Call provider with full reliability: failover + retry + checkpoint.

        Tries all available providers in the pool. On transient failure,
        retries with exponential backoff. On auth failure, skips provider.
        Saves TaskState checkpoint before each retry.
        """
        from core.provider_reliability import (
            ReliableProvider, RateLimitError, ProviderAuthError,
            PartialProviderError, ProviderStreamError, classify_exception,
        )
        import time as _time

        if ts:
            ts.set_messages(messages)
            ts.set_agent_steps([s.to_dict() for s in self.steps])
        if isinstance(self.provider, ReliableProvider):
            return self._streaming_call(messages, temperature)
        rp = ReliableProvider(cfg=self.cfg, primary=self.provider)

        last_error = None
        for attempt in range(rp._max_retries):
            provider_entry = rp._pool.get_provider()
            if provider_entry is None:
                delay = 2 ** attempt
                print_system_msg(f"⏳ All providers in cooldown — retrying in {delay}s...")
                _time.sleep(delay)
                continue

            prov = provider_entry["provider"] if isinstance(provider_entry, dict) else provider_entry
            prov_name = getattr(prov, "name", str(prov))

            try:
                # Save checkpoint before call
                if ts:
                    ts.set_messages(messages)
                    ts.set_agent_steps([s.to_dict() for s in self.steps])

                # Try streaming first
                if self._supports_streaming() and prov == self.provider:
                    content, tool_calls = self._streaming_call(messages, temperature)
                else:
                    content, tool_calls = rp._call_provider(prov, messages, self.tool_defs, temperature)
                    if content:
                        self._emit({"type": "text", "data": content})

                rp._pool.mark_success(prov_name)
                if attempt > 0:
                    print_system_msg(f"✅ Recovered with {prov_name} after {attempt} retries")
                return content, tool_calls

            except Exception as raw_error:
                error = classify_exception(raw_error)
                rp._pool.mark_failure(prov_name, str(error)[:100])
                if isinstance(error, PartialProviderError):
                    raise error
                if isinstance(error, ProviderAuthError):
                    rp._pool._health[prov_name]["cooldown_until"] = _time.time() + 86400
                elif attempt < rp._max_retries - 1:
                    _time.sleep(2 ** attempt if isinstance(error, RateLimitError) else 1)
                last_error = error

        if last_error is not None:
            raise last_error
        raise ProviderStreamError("All providers unavailable")

    def run(self, user_input: str, on_event=None) -> tuple[list[AgentStep], str]:
        """Execute the agentic loop. Returns (steps, summary_text).
        
        Args:
            user_input: The task to execute.
            on_event: Optional callback for live streaming (overrides constructor on_event).
        """
        if on_event:
            self._on_event = on_event

        from core.task_state import get_task_state
        ts = get_task_state()

        self._consumed_step_indices: set[int] = set()
        resume = False
        start_iteration = 0
        max_iter = self.cfg.get("agent_max_iterations", 25)

        if ts.is_active():
            saved_messages = ts.get_messages()
            if saved_messages:
                messages = saved_messages
                saved_steps = ts.get_agent_steps()
                self.steps = [
                    AgentStep(s["step"], s["tool"], s["args"], s["result"])
                    for s in saved_steps
                ]
                # Trace restored steps in ToolTracer
                for s in saved_steps:
                    args = s.get("args", {})
                    tool_tracer.tool_call(s["tool"], args)
                    tool_tracer.after_sandbox(
                        exit_code=0,
                        duration=0.0,
                        stdout=s.get("result", ""),
                        stderr=""
                    )
                    tool_tracer.result(s.get("result", ""))
                resume = True
                assistant_turns = sum(1 for m in messages if m.get("role") == "assistant")
                start_iteration = min(assistant_turns, max_iter - 1)
                print_system_msg(f"🔄 Resuming autonomous execution from step {len(self.steps) + 1}...")
                self._emit({"type": "text", "data": f"\n\n[🔄 Resuming from saved state at step {len(self.steps) + 1}...]\n\n"})

        if not resume:
            messages = [
                {"role": "system", "content": self._build_prompt()},
                {"role": "user", "content": user_input},
            ]
            self.steps = []
            ts.set_goal(user_input)
            ts.set_messages(messages)
            ts.set_agent_steps([])

        temperature = self.cfg.get("temperature", 0.7)

        # ── Loop safety: detect repeated identical tool calls ─────
        _recent_calls: list[tuple[str, str]] = []  # (tool_name, json(args))
        _progress_markers = 0

        print_system_msg("Starting autonomous execution...")

        # ── Sensor layer: Guard, EI, ESC (report only, no control) ──
        from core.runtime_guard import get_runtime_guard
        guard = get_runtime_guard()
        guard.start_task()

        from core.execution_intelligence import get_execution_intelligence
        ei = get_execution_intelligence()
        ei.start_task(None, user_input)

        from core.execution_state_controller import get_execution_state_controller
        esc = get_execution_state_controller()
        esc.signal_complete()

        # ── ECP: SOLE DECISION AUTHORITY ──
        from core.runtime.execution_control_plane import (
            get_control_plane, ControlActionType, ExecutionSignal, SignalType,
        )
        ecp = get_control_plane()
        from core.runtime.benchmarks import get_tracer
        get_tracer().start()
        current_model_name = self.state.get("model", "")
        ecp.start_task(current_model=current_model_name)

        # ── Layer 8: Adaptive Policy (evidence-weighted learning) ──
        from core.runtime.control.adaptive_policy import get_adaptive_policy
        adaptive_policy = get_adaptive_policy()
        adaptive_policy.start_task()

        # ── Layer 9: Experiments (counterfactual A/B testing) ──
        from core.runtime.control.experiments import get_experiment_runner
        experiment_runner = get_experiment_runner()
        # experiment_runner is instantiated but no per-task init is needed

        # ── Layer 10: Metalearning (Lyapunov convergence) ──
        from core.runtime.control.metalearning import get_metalearning_monitor
        metalearning = get_metalearning_monitor()
        # metalearning.start_task()

        # ── Layer 11: Containment (4 mathematical bounds) ──
        from core.runtime.containment import get_containment
        containment = get_containment()
        containment.start()

        # ── Layer 12: MCL (constraint reflexivity) ──
        from core.runtime.meta_constraint import get_mcl
        mcl = get_mcl()
        mcl.start()

        # ── Layer 13: CTI (constraint transparency index) ──
        from core.runtime.cti import get_cti
        cti = get_cti()
        cti.start()

        # ── Layer 14: Dashboard (unified A→F grade) ──
        from core.runtime.dashboard import get_dashboard
        dashboard = get_dashboard()

        # ── Layer 15: Neural Signal Learning & Prediction ──
        from core.runtime.neural_signals import get_neural_signals
        neural_signals = get_neural_signals()
        neural_signals.start()

        # ── Replay Engine: start recording this execution ──
        from core.runtime.replay import get_replay_manager
        replay_mgr = get_replay_manager()
        task_id = f"task_{int(time.time())}_{hash(user_input) % 10000:04d}"
        replay_mgr.start_recording(task_id, user_input)

        # ── Semantic stability + self-healing (periodic, every 10 steps) ──
        _semantic_interval = 10
        _semantic_enabled = True
        try:
            from core.runtime.semantic import get_self_healing_monitor
            _sem_healer = get_self_healing_monitor()
            _sem_healer.start_task(goal=user_input)
        except Exception:
            _semantic_enabled = False
            _sem_healer = None

        for iteration in range(start_iteration, max_iter):
            cancel = self.cfg.get("_cancel_flag")
            if cancel and cancel():
                print_system_msg("🛑 Agent cancelled by user")
                break

            # ═══════════════════════════════════════════
            # PHASE 1: COLLECT — all sensors report
            # ═══════════════════════════════════════════
            guard_signals = guard.collect()
            for sig in guard_signals:
                ecp.collect_signal(sig)

            ei_signals = ei.get_control_signals()
            for sig in ei_signals:
                ecp.collect_signal(sig)

            esc_state = esc.collect_state()
            if esc_state["is_deadlocked"]:
                ecp.collect_signal(ExecutionSignal(
                    signal_type=SignalType.DEADLOCK,
                    value=min(1.0, esc_state["escalation_count"] / 5.0),
                    source="ExecutionStateController",
                    detail=f"Layer {esc_state['layer']}, escalation #{esc_state['escalation_count']}",
                ))

            # ═══════════════════════════════════════════
            # PHASE 1.3: PREDICT — neural signal prediction
            # ═══════════════════════════════════════════
            try:
                current_signals = [sig.signal_type.name for sig in ecp._signals]
                if current_signals:
                    neural_result = neural_signals.process_signals(
                        [{"type": s} for s in current_signals], iteration
                    )
                    early_warning = neural_result.get("early_warning")
                    if early_warning:
                        warning_level = early_warning.get("warning_level", "INFO")
                        predicted = early_warning.get("predicted_signal", "")
                        confidence = early_warning.get("confidence", 0)
                        if warning_level == "CRITICAL" and confidence > 0.5:
                            self._emit({
                                "type": "text",
                                "data": f"\n[🔮 Neural: CRITICAL warning — {predicted} predicted (conf={confidence:.2f})]\n"
                            })
                        elif warning_level == "WARNING" and confidence > 0.6:
                            self._emit({
                                "type": "text",
                                "data": f"\n[🔮 Neural: {predicted} predicted (conf={confidence:.2f})]\n"
                            })
            except Exception as pred_e:
                logger.debug("Neural prediction skipped: %s", pred_e)

            # ═══════════════════════════════════════════
            # PHASE 1.5: SEMANTIC — periodic cognitive check + healing execution
            # ═══════════════════════════════════════════
            if _semantic_enabled and _sem_healer and iteration % _semantic_interval == 0 and iteration > 0:
                try:
                    tools_list = list(set(s.tool_name for s in self.steps)) if self.steps else []
                    sem_result = _sem_healer.tick(
                        step=iteration,
                        tools_used=tools_list or ["read"],
                        plan_adherence=getattr(ei, "_telemetry", None) and (
                            1.0 - getattr(ei._telemetry, "plan_deviation", 0.0)
                        ) or 0.8,
                        current_messages=messages[-20:] if messages else None,
                        context_size=len(messages),
                    )
                    if sem_result.get("needs_healing"):
                        executed_ops = sem_result.get("executed_operations", [])
                        failed_ops = sem_result.get("failed_operations", [])

                        # Report healing actions to user
                        if executed_ops:
                            self._emit({
                                "type": "text",
                                "data": f"\n[🧿 Self-Healing: executed {', '.join(executed_ops)}]\n"
                            })

                        # Feed healing results back to ECP as signals
                        if failed_ops:
                            ecp.collect_signal(ExecutionSignal(
                                signal_type=SignalType.QUALITY_DEGRADATION,
                                value=0.6,
                                source="SelfHealing",
                                detail=f"Healing partially failed: {', '.join(t for t, _ in failed_ops)}"
                            ))
                        elif executed_ops:
                            ecp.collect_signal(ExecutionSignal(
                                signal_type=SignalType.STUCK,
                                value=0.2,
                                source="SelfHealing",
                                detail=f"Healing successful: {', '.join(executed_ops)}"
                            ))
                        
                        # Record healing event in replay if active
                        try:
                            from core.runtime.replay import get_replay_manager
                            replay_mgr = get_replay_manager()
                            if replay_mgr._recorder.is_recording:
                                _healing_tool_calls = [{"name": op, "args": {}, "result": "executed"}
                                                       for op in executed_ops]
                                replay_mgr._recorder.capture_step(
                                    step=iteration,
                                    phase="self_healing",
                                    signals=[],
                                    decision_raw="CONTINUE",
                                    decision_final="CONTINUE",
                                    policy_applied=False,
                                    tool_calls=_healing_tool_calls,
                                    messages=messages[-5:],
                                    metadata={"healing_executed": executed_ops,
                                              "healing_failed": failed_ops}
                                )
                        except Exception:
                            logger.debug("Exception suppressed (line 551)")
                except Exception as sem_e:
                    logger.debug("Semantic check skipped: %s", sem_e)

            # ═══════════════════════════════════════════
            # PHASE 1.6: CONTAINMENT — mathematical bounds check
            # ═══════════════════════════════════════════
            try:
                tools_list = list(set(s.tool_name for s in self.steps)) if self.steps else []
                drift_score = 0.0
                if _semantic_enabled and _sem_healer:
                    sem_report = _sem_healer.semantic.measure(iteration, tools_list)
                    drift_score = sem_report.drift.drift_score if sem_report.drift else 0.0

                containment_result = containment.check_all(
                    drift_score=drift_score,
                    invariance_score=_measure_invariance_score(),
                    lyapunov_drift=_measure_lyapunov_drift(),
                    spc_violations=_count_spc_violations(),
                )
                if not containment_result.get("passed", True):
                    print_system_msg(f"🛡️ Containment: {containment_result.get('violations', [])}")
                    ecp.collect_signal(ExecutionSignal(
                        signal_type=SignalType.COMPLEXITY_DRIFT,
                        value=0.7,
                        source="Containment",
                        detail=f"Containment violation: {containment_result.get('violations', [])}"
                    ))
            except Exception as cont_e:
                logger.debug("Containment check skipped: %s", cont_e)

            # ═══════════════════════════════════════════
            # PHASE 1.7: MCL + CTI — constraint reflexivity & transparency
            # ═══════════════════════════════════════════
            # Per-step constraint pressure intake. Decision outcomes (which
            # wall blocked what) are recorded at end-of-iteration once the ECP
            # has acted; here we record the raw containment verdict so MCL and
            # CTI accumulate per-step evidence instead of a placeholder.
            try:
                step_contained = bool(containment.report().get("overall_contained", True))
                cti.record(
                    parameter=f"containment_step_{iteration}",
                    accepted=step_contained,
                    blocked_by="" if step_contained else "containment",
                    would_have_succeeded=False,
                    confidence=1.0 if step_contained else 0.0,
                )
                mcl.record_constraint_action(
                    constraint="invariance",
                    action="holding" if step_contained else "violated",
                    parameter=f"step_{iteration}",
                )
            except Exception as mcl_e:
                logger.warning("MCL/CTI signal intake failed at step %d: %s", iteration, mcl_e)

            # ═══════════════════════════════════════════
            # PHASE 1.8: DASHBOARD — periodic snapshot
            # ═══════════════════════════════════════════
            if iteration % 20 == 0 and iteration > 0:
                try:
                    snapshot = dashboard.snapshot()
                    logger.debug("Dashboard snapshot: grade=%s score=%.1f", snapshot.get("grade"), snapshot.get("score"))
                except Exception as dash_e:
                    logger.debug("Dashboard snapshot skipped: %s", dash_e)

            # ═══════════════════════════════════════════
            # PHASE 2: DECIDE — ECP sole authority
            # ═══════════════════════════════════════════
            current_model_name = self.state.get("model", "")
            ecp.note_model(current_model_name)
            decision = ecp.before_step(
                step=iteration,
                context={"task": user_input},
                messages=messages,
                current_model=current_model_name,
            )

            if decision.action == ControlActionType.SWITCH_MODEL:
                target_model = decision.model or "deepseek-v4-pro"
                print_system_msg(f"🔄 ECP: switching model {current_model_name} → {target_model}: {decision.reason}")
                self._emit({"type": "ecp", "data": {"action": "SWITCH_MODEL", "target": target_model, "reason": decision.reason}})
                try:
                    from core.providers.factory import create_provider as _create_provider
                    new_cfg = dict(self.cfg)
                    new_cfg["provider"] = {"model": target_model}
                    self.provider = _create_provider(new_cfg, raw=True)
                    self.state["model"] = target_model
                except Exception as switch_e:
                    logger.warning("ECP model switch failed: %s", switch_e)
                continue

            if decision.action == ControlActionType.REPLAN:
                print_system_msg(f"📋 ECP: replanning — {decision.reason}")
                self._emit({"type": "ecp", "data": {"action": "REPLAN", "reason": decision.reason}})
                try:
                    from core.uil.analyzer import TaskAnalyzer
                    from core.uil.planner import TaskPlanner
                    ta = TaskAnalyzer(provider=self.provider)
                    classification = ta.analyze(user_input)
                    planner = TaskPlanner()
                    plan = planner.plan(classification, user_input)
                    if plan and plan.steps:
                        plan_text = "\n".join(f"  [{s.id}] {s.description}" for s in plan.steps)
                        messages.append({"role": "user", "content": f"\n\n[SYSTEM: Plan regenerated ({len(plan.steps)} steps)]\n{plan_text}"})
                        ecp.set_plan(len(plan.steps))
                except Exception as replan_e:
                    logger.warning("ECP replan failed: %s", replan_e)
                continue

            if decision.action == ControlActionType.ESCALATE_TO_EXPERT:
                print_system_msg(f"🚀 ECP: escalating to ExpertTeam — {decision.reason}")
                self._emit({"type": "ecp", "data": {"action": "ESCALATE", "reason": decision.reason}})
                try:
                    from .expert import ExpertTeam
                    team = ExpertTeam(self.provider, self.tool_defs, dict(self.cfg), self.state)
                    expert_summary = team.run(user_input)
                    print_system_msg(f"ExpertTeam completed: {expert_summary[:200]}")
                    self._emit({"type": "text", "data": f"\n[ExpertTeam: {expert_summary[:300]}]\n"})
                    ts.clear()
                    return self.steps, expert_summary
                except Exception as expert_e:
                    logger.warning("ECP ExpertTeam escalation failed: %s", expert_e)
                    self._emit({"type": "error", "data": f"ExpertTeam failed: {expert_e}"})
                continue

            if decision.action == ControlActionType.ABORT:
                print_system_msg(f"🛑 ECP: aborting — {decision.reason}")
                self._emit({"type": "ecp", "data": {"action": "ABORT", "reason": decision.reason}})
                ts.set_messages(messages)
                ts.set_agent_steps([s.to_dict() for s in self.steps])
                break

            # ═══════════════════════════════════════════
            # PHASE 3: EXECUTE — no other authority
            # ═══════════════════════════════════════════

            # Guard: sensor only (timing)
            guard.before_provider_call()

            # Provider call
            try:
                content, tool_calls = self._call_provider_with_retry(messages, temperature, ts)
                esc.signal_recovery()
            except Exception as e:
                print_system_msg(f"❌ Agent halted: {e}")
                self._emit({"type": "error", "data": f"All providers exhausted: {e}"})
                esc.signal_error(str(e))
                ecp.collect_signal(ExecutionSignal(
                    signal_type=SignalType.PROVIDER_FAILURE,
                    value=0.9,
                    source="AutonomousAgent",
                    detail=str(e)[:200],
                ))
                ts.set_messages(messages)
                ts.set_agent_steps([s.to_dict() for s in self.steps])
                break

            model = self.state.get("model", "").split("/")[-1] or "unknown"
            self.state["cost"] += estimate_turn_cost(model, 500, 1000)

            # Guard: sensor only (loop detection)
            guard.after_provider_call(content or "")
            esc.signal_stuck(["ECS sensor: step tracked"])

            # ── Process tool calls if AI decided to use tools ──
            if tool_calls:
                for tc in tool_calls:
                    tool_tracer.tool_call(tc.name, tc.args if hasattr(tc, 'args') else {})
                tc_list = [
                    {
                        "id": _vid(tc.id),
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.args, ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ]
                if not (resume and messages and messages[-1].get("role") == "assistant" and messages[-1].get("tool_calls")):
                    messages.append({"role": "assistant", "content": content or None, "tool_calls": tc_list})
                    ts.set_messages(messages)

                for tc in tool_calls:
                    # ── ExecutionIntelligence: preventive check → ECP signal ──
                    try:
                        check = ei.check_before_action(tc.name, tc.args if hasattr(tc, 'args') else {})
                        if check["warning"]:
                            self._emit({"type": "text", "data": f"\n[⚠️ {check['warning']}]\n"})
                            if check["suggestion"]:
                                self._emit({"type": "text", "data": f"\n[💡 {check['suggestion']}]\n"})
                        if not check.get("safe", True):
                            ecp.collect_signal(ExecutionSignal(
                                signal_type=SignalType.QUALITY_DEGRADATION,
                                value=0.6,
                                source="ExecutionIntelligence",
                                detail=check.get("warning", "Tool may be unsafe"),
                            ))
                    except Exception as ei_e:
                        logger.warning("EI check_before_action failed: %s", ei_e)

                    # Emit tool start event for live Web UI
                    self._emit({"type": "tool", "data": {"name": tc.name, "args": tc.args}})

                    # Idempotency / Step lock guard
                    existing_step = None
                    for idx, step in enumerate(self.steps):
                        if idx not in self._consumed_step_indices:
                            if step.tool_name == tc.name and step.args == tc.args:
                                existing_step = step
                                self._consumed_step_indices.add(idx)
                                break

                    if existing_step:
                        result = existing_step.result
                        step = existing_step
                        print_system_msg(f"🔒 [Step Lock] Bypassing already executed tool: {tc.name}")
                        self._emit({"type": "text", "data": f"\n[🔒 Step Lock: retrieved result for {tc.name}]\n"})
                    else:
                        result = self._execute_tool(tc)
                        step = AgentStep(len(self.steps) + 1, tc.name, tc.args, result)
                        self.steps.append(step)
                        self._consumed_step_indices.add(len(self.steps) - 1)

                    # Emit tool result event for live Web UI
                    self._emit({
                        "type": "tool_result",
                        "data": {
                            "name": tc.name,
                            "success": step.status == "done",
                            "result": result[:300],
                        }
                    })

                    # ── POST-EXECUTION: sensor collection + ECP decision ──
                    ecp.note_tool_result(step.status == "done", result)

                    # Collect fresh sensor data
                    if esc.collect_state()["is_deadlocked"]:
                        ecp.collect_signal(ExecutionSignal(
                            signal_type=SignalType.DEADLOCK,
                            value=0.9,
                            source="ESC",
                            detail=f"Layer {esc.collect_state()['layer']}",
                        ))

                    after_decision = ecp.after_step(
                        step=iteration,
                        tool_results={"name": tc.name, "success": step.status == "done"},
                        messages=messages,
                        success=step.status == "done",
                    )

                    # ── Neural signal feedback: record decision outcome ──
                    try:
                        signals_before = [sig.signal_type.name for sig in ecp._signals]
                        # Collect signals after decision
                        guard_sigs = guard.collect()
                        ei_sigs = ei.get_control_signals()
                        signals_after = [sig.signal_type.name for sig in guard_sigs + ei_sigs]
                        
                        neural_signals.record_decision_outcome(
                            step=iteration,
                            signals_before=signals_before,
                            decision=after_decision.action.name,
                            signals_after=signals_after,
                        )
                    except Exception as fb_e:
                        logger.debug("Neural feedback skipped: %s", fb_e)

                    if after_decision.action == ControlActionType.SWITCH_MODEL:
                        target = after_decision.model or "deepseek-v4-pro"
                        print_system_msg(f"🔄 ECP mid-step: switching model → {target}: {after_decision.reason}")
                        try:
                            from core.providers.factory import create_provider as _create_provider
                            new_cfg = dict(self.cfg)
                            new_cfg["provider"] = {"model": target}
                            self.provider = _create_provider(new_cfg, raw=True)
                            self.state["model"] = target
                        except Exception as s_e:
                            logger.warning("ECP mid-step model switch failed: %s", s_e)
                        break  # break out of tool loop, next iteration uses new model

                    if after_decision.action == ControlActionType.REPLAN:
                        print_system_msg(f"📋 ECP mid-step: replanning — {after_decision.reason}")
                        try:
                            from core.uil.analyzer import TaskAnalyzer
                            from core.uil.planner import TaskPlanner
                            ta = TaskAnalyzer(provider=self.provider)
                            classification = ta.analyze(user_input)
                            planner = TaskPlanner()
                            plan = planner.plan(classification, user_input)
                            if plan and plan.steps:
                                plan_text = "\n".join(f"  [{s.id}] {s.description}" for s in plan.steps)
                                messages.append({"role": "user", "content": f"\n\n[SYSTEM: Plan regenerated ({len(plan.steps)} steps)]\n{plan_text}"})
                                ecp.set_plan(len(plan.steps))
                        except Exception as rp_e:
                            logger.warning("ECP mid-step replan failed: %s", rp_e)
                        break  # break out of tool loop, next iteration follows new plan

                    if after_decision.action == ControlActionType.ESCALATE_TO_EXPERT:
                        print_system_msg(f"🚀 ECP mid-step: escalating to ExpertTeam — {after_decision.reason}")
                        try:
                            from .expert import ExpertTeam
                            team = ExpertTeam(self.provider, self.tool_defs,
                                              dict(self.cfg), self.state)
                            expert_summary = team.run(user_input)
                            self._emit({"type": "text", "data": f"\n[ExpertTeam: {expert_summary[:300]}]\n"})
                            ts.clear()
                            return self.steps, expert_summary
                        except Exception as e_e:
                            logger.warning("ECP mid-step ExpertTeam escalation failed: %s", e_e)
                        break

                    if after_decision.action == ControlActionType.ABORT:
                        print_system_msg(f"🛑 ECP mid-step: aborting — {after_decision.reason}")
                        ts.set_messages(messages)
                        ts.set_agent_steps([s.to_dict() for s in self.steps])
                        return self.steps, f"Aborted: {after_decision.reason}"

                    # ── Loop detection: same tool + same args 3x in a row → ECP signal ──
                    call_sig = (tc.name, json.dumps(tc.args, sort_keys=True))
                    _recent_calls.append(call_sig)
                    if len(_recent_calls) > 3:
                        _recent_calls.pop(0)
                    if len(_recent_calls) >= 3 and len(set(_recent_calls)) == 1:
                        print_system_msg("🔁 Loop detected — same tool called 3 times in a row. Aborting.")
                        ecp.collect_signal(ExecutionSignal(
                            signal_type=SignalType.STUCK,
                            value=0.9,
                            source="AutonomousAgent",
                            detail=f"Repeated {tc.name} with same arguments 3x",
                        ))
                        return self.steps, f"Aborted: repeated {tc.name} with same arguments."

                    # ── Progress tracking: count files written + bash successes ──
                    if tc.name in {"write", "edit"} and step.status == "done":
                        _progress_markers += 1
                    elif tc.name == "bash" and step.status == "done":
                        _progress_markers += 1
                    if iteration > 4 and _progress_markers == 0:
                        print_system_msg("⏳ No files written or successful bash commands after 5 iterations — agent may be stuck.")
                        ecp.collect_signal(ExecutionSignal(
                            signal_type=SignalType.STUCK,
                            value=0.6,
                            source="AutonomousAgent",
                            detail=f"No progress after {iteration + 1} iterations",
                        ))

                    # If the tool wrote or edited a file, run validation immediately
                    if tc.name in {"write", "edit"} and not step.result.startswith(("❌", "⚠️", "⚠", "⛔", "Error", "Failed", "No such", "File not found")):
                        file_path = tc.args.get("file_path")
                        if file_path:
                            validation_step = None
                            if existing_step:
                                for idx, s in enumerate(self.steps):
                                    if idx not in self._consumed_step_indices and s.tool_name == "validate" and s.args.get("file_path") == file_path:
                                        validation_step = s
                                        self._consumed_step_indices.add(idx)
                                        break

                            if validation_step:
                                val_result = validation_step.result
                                print_system_msg(f"🔒 [Step Lock] Bypassing already executed validation for: {file_path}")
                            else:
                                self._emit({"type": "tool", "data": {"name": "validate", "args": {"file_path": file_path}}})
                                val_result = self._auto_validate_file(file_path)
                                validation_step = AgentStep(len(self.steps) + 1, "validate", {"file_path": file_path}, val_result)
                                self.steps.append(validation_step)
                                self._consumed_step_indices.add(len(self.steps) - 1)

                            self._emit({
                                "type": "tool_result",
                                "data": {"name": "validate", "success": not val_result.startswith(("❌", "Error")), "result": val_result[:200]}
                            })

                    # Append tool result to messages for context
                    messages.append({
                        "role": "tool",
                        "tool_call_id": _vid(getattr(tc, 'id', None)),
                        "name": tc.name,
                        "content": result,
                    })

                    ts.set_messages(messages)
                    ts.set_agent_steps([s.to_dict() for s in self.steps])

                    model = self.state.get("model", "").split("/")[-1] or "unknown"
                    self.state["cost"] += estimate_turn_cost(model, 200, 100)
                    self.state["turns"] = self.state.get("turns", 0) + 1

            # ═══════════════════════════════════════════
            # PHASE 4: END-OF-ITERATION — layer integration hooks
            # ═══════════════════════════════════════════
            try:
                # Containment check (Layer 11)
                drift_score = 0.0
                if _semantic_enabled and _sem_healer:
                    tools_list = list(set(s.tool_name for s in self.steps)) if self.steps else []
                    sem_report = _sem_healer.semantic.measure(iteration, tools_list)
                    drift_score = sem_report.drift.drift_score if sem_report.drift else 0.0

                # Feed drift into containment's drift subsystem
                containment.drift.register("execution_drift", drift_score)

                # Record tool success/failure for acceptance control
                step_success = any(s.status == "done" for s in self.steps[-5:]) if self.steps else True
                containment.acceptance.record(step_success)

                # CTI recording (Layer 13)
                cti.record(
                    parameter="ecp_action",
                    accepted=decision.action == ControlActionType.CONTINUE,
                    blocked_by=decision.action.name if decision.action != ControlActionType.CONTINUE else "",
                    would_have_succeeded=decision.confidence > 0.7,
                    confidence=decision.confidence,
                )

                # MCL recording (Layer 12)
                mcl.record_proposal(
                    parameter="ecp_decision",
                    accepted=decision.action == ControlActionType.CONTINUE,
                    blocked_by=decision.action.name if decision.action != ControlActionType.CONTINUE else "",
                )

                # Experiment tracking via container's acceptance subsystem
                # Record proposal outcome for metalearning (Layer 10)
                metalearning.record_proposal(
                    parameter="tool_execution",
                    accepted=step_success,
                    confidence=decision.confidence,
                )

            except Exception as layer_e:
                logger.debug("Layer integration hook skipped: %s", layer_e)

            # Dashboard snapshot (Layer 14) - every 20 iterations
            if iteration % 20 == 0 and iteration > 0:
                try:
                    snapshot = dashboard.snapshot()
                    logger.debug("Dashboard: grade=%s score=%.1f", snapshot.get("grade"), snapshot.get("score"))
                except Exception as dash_e:
                    logger.debug("Dashboard snapshot skipped: %s", dash_e)

            if not tool_calls:
                # AI responded without tool calls — task may be complete
                summary = content or "Task completed."
                if not (resume and messages and messages[-1].get("role") == "assistant" and messages[-1].get("content") == content):
                    messages.append({"role": "assistant", "content": content})
                    ts.set_messages(messages)

                # ── Auto-validate written files before declaring done ──
                written_steps = [
                    s for s in self.steps
                    if s.tool_name in {"write", "edit"} and s.status == "done"
                ]
                if written_steps:
                    # Validate the last 3 written files
                    validation_failures = []
                    for step in written_steps[-3:]:
                        file_path = step.args.get("file_path", "")
                        if file_path:
                            val = self._auto_validate_file(file_path)
                            if val.startswith(("❌", "Error", "Failed")):
                                validation_failures.append(f"{file_path}: {val[:120]}")
                    if validation_failures:
                        summary = (
                            "⚠️ Output written but validation found issues:\n"
                            + "\n".join(validation_failures)
                            + "\n\nOriginal summary: " + (content or "(none)")
                        )

                self._show_final_result(content)
                print_agent_done(self.steps, summary)

                # ═══════════════════════════════════════════
                # TASK COMPLETION: Full layer finalization
                # ═══════════════════════════════════════════
                try:
                    from core.runtime.benchmarks import get_tracer, score_session
                    tracer = get_tracer()
                    traces = tracer.get_traces()
                    if traces:
                        score = score_session(traces)
                        adaptive_policy.record_score(
                            stability=score.stability_ratio,
                            policy_intervention_rate=score.policy_intervention_rate,
                            switch_effectiveness=score.switch_effectiveness,
                            escalation_efficiency=score.escalation_efficiency,
                            overall=score.overall_score,
                            anomalies=len(score.anomalies),
                        )
                        # Record experiment task outcome if any experiment is active
                        for exp_param in experiment_runner.active_experiments:
                            experiment_runner.record_task(
                                parameter=exp_param,
                                used_candidate=experiment_runner.should_use_candidate(exp_param),
                                success=score.grade in ("A", "B"),
                                cost=self.state.get("cost", 0),
                                steps=iteration,
                                model_switches=ecp.status.get("model_switches", 0),
                            )
                        # Update metalearning KPIs
                        metalearning.record_proposal(
                            parameter="task_execution",
                            accepted=score.grade in ("A", "B"),
                            confidence=score.overall_score,
                        )
                        # Evaluate transparency and reflexivity
                        cti.evaluate()
                        mcl.evaluate()
                        final_snapshot = dashboard.snapshot()
                        logger.info("Task complete: grade=%s score=%.1f", final_snapshot.get("grade"), final_snapshot.get("score"))
                except Exception as final_e:
                    logger.debug("Task finalization skipped: %s", final_e)

                ts.clear()
                return self.steps, summary

        # Hit max iterations
        summary = f"Reached maximum iterations ({max_iter})."
        print_system_msg(summary)
        print_agent_done(self.steps, summary)
        # ── ExecutionIntelligence: deep success analysis ──
        try:
            report = ei.analyze_success(None, '')
            if report.success_pattern:
                self._emit({"type": "text", "data": f"\n[📊 {report.success_pattern[:120]}]\n"})
            if report.success_reason:
                self._emit({"type": "text", "data": f"\n[💡 {report.success_reason[:200]}]\n"})
        except Exception as ei_e:
            logger.warning("EI analyze_success failed: %s", ei_e)

        # ═══════════════════════════════════════════
        # TASK COMPLETION (max iterations): Full layer finalization
        # ═══════════════════════════════════════════
        try:
            from core.runtime.benchmarks import get_tracer, score_session
            tracer = get_tracer()
            traces = tracer.get_traces()
            if traces:
                score = score_session(traces)
                adaptive_policy.record_score(
                    stability=score.stability_ratio,
                    policy_intervention_rate=score.policy_intervention_rate,
                    switch_effectiveness=score.switch_effectiveness,
                    escalation_efficiency=score.escalation_efficiency,
                    overall=score.overall_score,
                    anomalies=len(score.anomalies),
                )
                for exp_param in experiment_runner.active_experiments:
                    experiment_runner.record_task(
                        parameter=exp_param,
                        used_candidate=experiment_runner.should_use_candidate(exp_param),
                        success=score.grade in ("A", "B"),
                        cost=self.state.get("cost", 0),
                        steps=iteration,
                        model_switches=ecp.status.get("model_switches", 0),
                    )
                metalearning.record_proposal(
                    parameter="task_execution",
                    accepted=score.grade in ("A", "B"),
                    confidence=score.overall_score,
                )
                cti.evaluate()
                mcl.evaluate()
                final_snapshot = dashboard.snapshot()
                logger.info("Task complete (max iter): grade=%s score=%.1f", final_snapshot.get("grade"), final_snapshot.get("score"))
        except Exception as final_e:
            logger.debug("Task finalization skipped: %s", final_e)

        ts.clear()
        return self.steps, summary

    # ── internal helpers ──────────────────────────────────────────────

    def _supports_streaming(self) -> bool:
        """Check whether the current provider supports streaming.

        Returns:
            True if the provider has a ``stream()`` method.
        """
        return hasattr(self.provider, "stream")

    def _streaming_call(self, messages: list, temperature: float) -> tuple:
        """Call provider with streaming display. Returns (content, tool_calls)."""
        live, update, done = print_ai_stream()
        content_chunks = []
        reasoning_chunks = []
        saw_reasoning = False
        tool_calls = None
        err_msg = None

        with live:
            for event in self.provider.stream(messages, self.tool_defs, temperature):
                if event["type"] == "content":
                    update(event["data"])
                    content_chunks.append(event["data"])
                    if saw_reasoning:
                        self._emit({"type": "text", "data": event["data"]})
                elif event["type"] == "reasoning":
                    if not saw_reasoning:
                        saw_reasoning = True
                        for chunk in content_chunks:
                            self._emit({"type": "reasoning", "data": chunk})
                        content_chunks = []
                    reasoning_chunks.append(event["data"])
                    self._emit({"type": "reasoning", "data": event["data"]})
                elif event["type"] == "error":
                    err_msg = event["data"]
                    break
                elif event["type"] == "done":
                    data = event.get("data")
                    if isinstance(data, tuple) and len(data) == 2:
                        content, tool_calls = data
                    elif isinstance(data, list):
                        content, tool_calls = "".join(content_chunks), data
                    break

        if err_msg:
            print_system_msg(f"Error: {err_msg}")
            raise ProviderStreamError(err_msg)

        content = "".join(content_chunks)
        if not saw_reasoning and content:
            self._emit({"type": "text", "data": content})

        if content and tool_calls:
            done()

        full_reasoning = "".join(reasoning_chunks)
        if full_reasoning:
            self.state["_last_reasoning"] = full_reasoning
            print_reasoning(full_reasoning)
        return content, tool_calls

    def _execute_tool(self, tc) -> str:
        """Execute a single tool call and display it.

        Handles automatic validation for `bash` commands that create/modify
        repository files by snapshotting mtimes and validating changed files.

        Uses :class:`core.cache.tool_cache` to skip redundant read operations.
        """
        # ── Cache: check before executing (skip for side-effect tools) ──
        from core.cache import tool_cache
        cache_key = tool_cache.make_key(tc.name, tc.args)
        if tc.name not in ("bash", "write", "edit"):
            cached = tool_cache.get(cache_key)
            if cached is not None:
                print_tool_call(tc.name, json.dumps(tc.args, ensure_ascii=False))
                print_tool_msg(tc.name, f"(cached) {cached[:200]}")
                self._emit({"type": "tool_result", "data": {"name": tc.name, "result": f"(cached) {cached[:200]}"}})
                return cached

        # Track tool usage
        if "tools_used" not in self.state:
            self.state["tools_used"] = []
        if tc.name != "use_skill" and tc.name not in self.state["tools_used"]:
            self.state["tools_used"].append(tc.name)

        tool_tracer.dispatch(tc.name)
        print_tool_call(tc.name, json.dumps(tc.args, ensure_ascii=False))
        self._emit({"type": "tool", "data": {"name": tc.name, "args": tc.args}})

        # Handle bash specially: snapshot time, run command, then validate new/modified files
        if tc.name == "bash":
            t0 = time.time()
            result = core_tools.execute_with_skills(tc.name, tc.args)
            print_tool_msg(tc.name, result[:1000])
            self._emit({"type": "tool_result", "data": {"name": tc.name, "result": result[:500]}})
            # ExecutionIntelligence: evaluate step quality
            try:
                from core.execution_intelligence import get_execution_intelligence
                ei = get_execution_intelligence()
                ei.evaluate_step(len(self.steps) + 1, result, tc.name,
                                 tc.args if hasattr(tc, 'args') else {})
            except Exception as ei_e:
                logger.warning("EI evaluate_step failed: %s", ei_e)

            normalized = (result or "").strip()
            if not normalized.startswith(("\ud83d\udeab", "❌", "⛔", "Error", "Failed")):
                exts = {".py", ".js", ".ts", ".tsx", ".json", ".css", ".html", ".htm", ".go", ".dart", ".rb", ".php", ".yaml", ".yml"}
                changed = []
                try:
                    root = Path(".").resolve()
                    for f in root.rglob("*"):
                        if not f.is_file():
                            continue
                        try:
                            if f.stat().st_mtime >= t0 - 0.5 and f.suffix.lower() in exts:
                                changed.append(f)
                        except Exception:
                            continue
                except Exception:
                    changed = []

                for f in changed[:30]:
                    val_result = self._auto_validate_file(str(f))
                    self.steps.append(AgentStep(len(self.steps) + 1, "validate", {"file_path": str(f)}, val_result))

            # Cache successful bash results briefly
            if not result.startswith(("❌", "⚠️", "⚠", "⛔", "Error", "Failed")):
                from core.cache import tool_cache
                tool_cache.set(cache_key, result, tool_name="bash")
            return result

        # Default execution path
        result = core_tools.execute_with_skills(tc.name, tc.args)
        tool_tracer.result(result)
        print_tool_msg(tc.name, result[:1000])
        self._emit({"type": "tool_result", "data": {"name": tc.name, "result": result[:500]}})
        # Cache successful read-only tool results
        if tc.name not in ("bash", "write", "edit") and not result.startswith(("❌", "⚠️", "⚠", "⛔", "Error", "Failed")):
            from core.cache import tool_cache
            tool_cache.set(cache_key, result, tool_name=tc.name)
        # Invalidate tool cache on writes
        if tc.name in ("write", "edit"):
            from core.cache import tool_cache
            tool_cache.invalidate_on_write()
        return result

    def _auto_verify_build(self) -> str | None:
        """Run automated build verification after agent execution.

        Auto-installs dependencies, runs JavaScript syntax checks with
        ``node --check`` on all ``.js`` files, and reports any syntax
        errors found.

        Returns:
            A concatenated error string if any JS syntax check failed,
            or ``None`` if everything passed.
        """
        from pathlib import Path
        import subprocess as _sp

        root = Path(".").resolve()
        errors = []

        # ── JS syntax-check for all .js files ──
        js_files = list(root.rglob("*.js"))
        js_files = [f for f in js_files[:20]
                    if "node_modules" not in str(f) and f.stat().st_size < 500_000]
        node_bin = None
        import shutil as _sh
        for candidate in ("node", "nodejs"):
            if _sh.which(candidate):
                node_bin = candidate
                break

        if node_bin and js_files:
            for jsf in js_files:
                try:
                    r = _sp.run(
                        [node_bin, "--check", str(jsf)],
                        capture_output=True, text=True, timeout=15,
                    )
                    if r.returncode != 0:
                        err = (r.stderr or r.stdout or "")[:600]
                        errors.append(f"JS SyntaxError in {jsf.name}: {err}")
                except Exception as js_e:
                    logger.warning("JS syntax check failed for %s: %s", jsf, js_e)

        if not errors:
            return None
        return "\\n".join(errors)

    def _auto_validate_file(self, file_path: str) -> str:
        """Automatically validate a file after a write/edit operation."""
        p = Path(file_path)
        if not p.exists():
            return f"⚠️ Validation skipped: file not found {file_path}"
        validation_args = {"file_path": str(p)}
        print_tool_call("validate", json.dumps(validation_args, ensure_ascii=False))
        self._emit({"type": "tool", "data": {"name": "validate", "args": validation_args}})
        result = core_tools.execute_with_skills("validate", validation_args)
        print_tool_msg("validate", result[:1000])
        self._emit({"type": "tool_result", "data": {"name": "validate", "result": result[:500]}})
        return result

    def _build_prompt(self) -> str:
        """Build the agent system prompt with all available tools and project docs.
        If custom_prompt is set, use it instead of the default AGENT_PROMPT."""
        lines = []
        mcp_lines = []
        for td in self.tool_defs:
            line = f"  {td['name']}: {td.get('description', '')}"
            if td["name"].startswith("mcp__"):
                mcp_lines.append(line)
            else:
                lines.append(line)

        tool_text = "\n".join(lines) if lines else "  (none)"
        mcp_text = "\n".join(mcp_lines) if mcp_lines else "  (none)"
        skill_names = [s.name for s in _skill_manager.list_all()]
        skill_text = "\n".join(f"  {s}" for s in skill_names) if skill_names else "  (none)"

        if self.custom_prompt:
            return self.custom_prompt

        # Build project docs block
        project_docs_block = self._build_project_docs_block()

        # Escape curly braces in tool descriptions — they contain JSON schemas
        # that would break str.format()
        safe_tool = tool_text.replace("{", "{{").replace("}", "}}")
        safe_mcp = mcp_text.replace("{", "{{").replace("}", "}}")
        safe_skill = skill_text.replace("{", "{{").replace("}", "}}")
        safe_docs = project_docs_block.replace("{", "{{").replace("}", "}}")

        return AGENT_PROMPT.format(
            tool_descriptions=(
                f"Built-in tools:\n{safe_tool}\n\n"
                f"MCP tools:\n{safe_mcp}\n\n"
                f"Skills:\n{safe_skill}"
            ),
            project_docs_block=safe_docs,
        )

    def _build_project_docs_block(self) -> str:
        """Read and return project docs content."""
        try:
            from core.project_tracker import load_docs, _DOC_NAMES
            docs = load_docs(Path.cwd().resolve())
            if not docs:
                return "(No project docs found — create them with update_project_doc)"
            parts = []
            for name in _DOC_NAMES:
                content = docs.get(name, "").strip()
                if content and len(content) > 20:
                    parts.append(f"=== {name} ===")
                    parts.append(content[:600])
                    parts.append("")
            if not parts:
                return "(Project docs exist but are empty — populate them with update_project_doc)"
            return "\n".join(parts)
        except Exception as e:
            return f"(Could not read project docs: {e})"

    def _show_final_result(self, content: Optional[str]):
        """Show the AI's final response panel if there's content."""
        if not content:
            return
        console.print()
        console.print(Panel(
            Text(content, style="bold #00c896"),
            border_style="#00c896",
            title="[bold #00c896]Agent Result[/]",
            title_align="left",
        ))

    def get_status(self) -> str:
        """Return a short summary of current agent progress."""
        if not self.steps:
            return "No steps executed yet."
        done = sum(1 for s in self.steps if s.status == "done")
        failed = sum(1 for s in self.steps if s.status == "failed")
        return f"{len(self.steps)} steps ({done} done, {failed} failed)"

    def __repr__(self):
        return f"AutonomousAgent({len(self.steps)} steps, cost={self.cost:.4f})"


# ---------------------------------------------------------------------------
# Recursive Agent Spawning — sub-agent → sub-sub-agent tree
# ---------------------------------------------------------------------------

_MAX_DEPTH = 3
_MAX_TOTAL_AGENTS = 10
_agent_counter: dict[str, int] = {}
_agent_results: dict[str, dict] = {}


def spawn_sub_agent(task: str, role: str = "worker", provider=None, tool_defs=None,
                    cfg=None, parent_id: str = "", depth: int = 0) -> dict:
    """Spawn a sub-agent that runs autonomously. Sub-agents can spawn further sub-agents."""
    import uuid
    import threading

    if depth >= _MAX_DEPTH:
        return {"agent_id": "", "role": role, "summary": "Max depth reached", "success": False}

    agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    root_id = parent_id or agent_id

    if _agent_counter.get(root_id, 0) >= _MAX_TOTAL_AGENTS:
        return {"agent_id": agent_id, "role": role, "summary": "Agent cap reached", "success": False}

    _agent_counter[root_id] = _agent_counter.get(root_id, 0) + 1

    role_prompt = f"""You are a specialized sub-agent: {role}. Depth: {depth+1}/{_MAX_DEPTH}.
TASK: {task}
Focus only on your task. Use tools. You can spawn sub-agents via spawn_agent tool for subtasks."""

    from core.providers.providers import create_provider as _cp
    from core.config.settings import load as _load

    if provider is None:
        provider = _cp(_load())
    if tool_defs is None:
        from .. import tools
        tool_defs = tools.TOOL_DEFINITIONS
    if cfg is None:
        cfg = _load()

    # Add spawn_agent tool for recursive spawning
    if depth < _MAX_DEPTH - 1:
        spawn_def = {
            "name": "spawn_agent",
            "description": f"Spawn a sub-agent for a subtask. Sub-agents can spawn further sub-agents (depth {depth+1}/{_MAX_DEPTH}).",
            "parameters": {"type": "object", "properties": {
                "task": {"type": "string", "description": "Subtask description"},
                "role": {"type": "string", "description": "Role: researcher, coder, tester, reviewer"},
            }, "required": ["task", "role"]},
        }
        tool_defs = list(tool_defs) + [spawn_def]

    state = {"model": getattr(provider, "model", ""), "turns": 0, "cost": 0.0}
    result_container: dict[str, Any] = {}

    def _run():
        try:
            agent = AutonomousAgent(provider, tool_defs, cfg, state, custom_prompt=role_prompt)
            steps, summary = agent.run(task)
            result_container["steps"] = len(steps)
            result_container["summary"] = summary or "Done"
            result_container["success"] = True
        except Exception as e:
            result_container["steps"] = 0
            result_container["summary"] = str(e)
            result_container["success"] = False

    t = threading.Thread(target=_run, daemon=True, name=f"sub-{agent_id}")
    t.start()
    t.join(timeout=300)

    if t.is_alive():
        result_container["summary"] = "Timed out after 5min"
        result_container["success"] = False

    result_container["agent_id"] = agent_id
    result_container["role"] = role
    _agent_results[agent_id] = result_container
    return result_container


# ---------------------------------------------------------------------------
# Helper: run agent with a custom system prompt
# ---------------------------------------------------------------------------


def run_agent_with_prompt(provider, tool_defs, cfg, state, system_prompt, user_input):
    """Run AutonomousAgent with a custom system prompt.
    Returns (steps, summary_text).
    
    This is used by ExpertTeam to give each expert a specialized prompt.
    """
    agent = AutonomousAgent(provider, tool_defs, cfg, state,
                            custom_prompt=system_prompt)
    return agent.run(user_input)
