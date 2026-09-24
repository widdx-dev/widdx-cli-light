"""Unified Intelligence Layer — orchestrator only.

Orchestrates the UIL pipeline:
  1. Analyze (classify user input)
  2. Route (select mode + filter tools)
  3. Plan (optional cognitive enhancer)
  4. Execute (delegate to executor via ExecutionContext)
  5. Verify (post-execution quality checks — Phase VERIFY)
  6. Feedback (wrap result in ExecutionResult)
  7. Knowledge (record execution outcome)

Contains NO classification logic.
Contains NO tool selection logic.
Pure orchestration — delegates everything.
"""

import time
import logging
from typing import Any, Callable

logger = logging.getLogger("widdx.uil.brain")

from core.tool_tracer import t as tool_tracer

from .analyzer import TaskAnalyzer  # noqa: E402
from .router import DecisionRouter  # noqa: E402
from .planner import TaskPlanner  # noqa: E402
from .contract import (ExecutionMode, RoutingDecision,  # noqa: E402
                       DecisionStep, ExecutionContext, ExecutionResult,
                       StepResult, ExecutionMetrics, TaskType,
                       VerificationSeverity, VerificationFinding)
from .knowledge import KnowledgeBase  # noqa: E402
from .verifier import get_verifier  # noqa: E402

# ── v4.0 Engine adapters (feature-flagged, safe by default) ──
try:
    from core.engine_adapters import (
        engine_enabled, unified_classify,
        adapt_validation,
    )
    _ENGINES_AVAILABLE = True
except ImportError:
    _ENGINES_AVAILABLE = False

# -------------------------------------------------------------------
# Execution Mode Executor Map — imported lazily to avoid circular
# dependency issues at module-load time.
# -------------------------------------------------------------------

_EXECUTOR_MAP: dict[ExecutionMode, Callable] | None = None


def _get_executor_map() -> dict[ExecutionMode, Callable]:
    """Lazy-load EXECUTOR_MAP from executor_adapter on first call.

    Returns an empty dict (with a logged warning) if the import fails,
    keeping ``_resolve_executor``'s error message clear.
    """
    global _EXECUTOR_MAP
    if _EXECUTOR_MAP is not None:
        return _EXECUTOR_MAP

    try:
        from ..agents.executor_adapter import EXECUTOR_MAP as _MAP
        _EXECUTOR_MAP = _MAP
    except ImportError as exc:
        logger.warning("Could not load EXECUTOR_MAP from executor_adapter: %s", exc)
        _EXECUTOR_MAP = {}
    return _EXECUTOR_MAP


# -------------------------------------------------------------------
# UIL — Main Orchestrator
# -------------------------------------------------------------------

class UnifiedIntelligenceLayer:
    """Central orchestrator for the WIDDX AI system.

    Pipeline:
      process(user_input)
        → analyzer.analyze()    [classification]
        → router.route()        [decision]
        → executor()            [execution]

    The executor function is injected as a dependency (executors dict).
    This keeps brain.py testable without importing main.py or system modules.
    """

    def __init__(self, analyzer: TaskAnalyzer | None = None,
                 router: DecisionRouter | None = None,
                 planner: TaskPlanner | None = None,
                 tool_defs: list[dict] | None = None,
                 provider=None):
        # If no provider given, use a mock for testing
        if provider is None:
            from types import SimpleNamespace
            provider = SimpleNamespace(
                name="mock", model="mock", api_key="mock",
                chat=lambda msgs, tools=None, temp=0.7: ("Mock reply", []),
            )
        # Pass provider to TaskAnalyzer for LLM-based classification fallback
        self.analyzer = analyzer or TaskAnalyzer(provider=provider)
        self.router = router or DecisionRouter()
        # Phase 2.1: Planner is ALWAYS active — dead code removal
        self.planner = planner or TaskPlanner()
        self._tool_defs = tool_defs or []
        self.knowledge = KnowledgeBase()
        self.provider = provider

    # ── Context Pipeline: HierarchicalContext + RAG + Pruner ────
    @staticmethod
    def _get_context_pipeline(messages: list | None = None,
                               goal: str = "",
                               max_tokens: int = 4096) -> str:
        """Build pruned, RAG-enriched context for code tasks.

        Chains HierarchicalContext → DynamicRAG → ContextPruner into
        a single compact prompt snippet injected into the executor input.
        """
        try:
            from core.context.pipeline import ContextPipeline
            pipe = ContextPipeline(max_tokens=max_tokens, enable_rag=True)
            result = pipe.run(goal=goal, messages=messages or [])
            rendered = result.render()
            if not rendered.strip():
                return ""
            return (
                "\n\n---\n"
                "Project context (hierarchical, RAG-enriched):\n"
                f"{rendered}\n"
                "---\n"
            )
        except Exception:
            return ""

    def process(self, user_input: str,
                messages: list | None = None,
                executors: dict[ExecutionMode, Callable] | None = None,
                cfg: dict | None = None,
                state: dict | None = None,
                project_card: Any | None = None,
                on_event: Callable | None = None,
                ) -> tuple[ExecutionResult, RoutingDecision]:
        """Full UIL pipeline: analyze → route → plan → execute → feedback.

        Args:
            user_input: Raw text from the user.
            messages: Current conversation messages (optional context).
            executors: Execution mode → callable mapping.
                       If None, uses ``EXECUTOR_MAP`` from
                       ``core.agents.executor_adapter`` (real agents).
            cfg: User configuration dict (passed to executors via ctx).
            state: Mutable run state dict (cost, turns, model).
                   Mutations by the executor are visible to the caller.
            project_card: Optional ``ProjectCard`` from ``ProjectScanner``.
                          Injected into the analyzer context so classifiers
                          can make project-aware decisions.

        Returns:
            (execution_result, routing_decision_with_full_trace)
            ExecutionResult carries plan-vs-execution delta for Phase 2.
        """
        # Step 0: Status event — analyzing
        if on_event:
            try:
                on_event({"type": "status", "data": {"phase": "analyzing", "label": "Analyzing request...", "detail": user_input[:60]}})
            except Exception:
                logger.debug("Exception suppressed (line 167)")

        # Step 1: Analyze — classify the user input
        tool_tracer.start_session()
        ctx_analyzer: dict = {}
        if messages:
            ctx_analyzer["messages"] = messages
        if project_card is not None:
            ctx_analyzer["project_card"] = project_card
        classification = self.analyzer.analyze(
            user_input,
            context=ctx_analyzer or None,
        )

        # ── v4.0: Unified classification (TF-IDF first, LLM fallback) ──
        if _ENGINES_AVAILABLE and engine_enabled(cfg or {}, "intelligence"):
            unified = unified_classify(user_input, analyzer=self.analyzer)
            if unified is not None:
                logger.info(
                    "Unified classification: %s (%.2f)%s",
                    unified.task_type.value, unified.confidence,
                    " [CONFUSED]" if getattr(unified, 'confusion_margin', 0) > 0 else "",
                )
                classification = unified

        # ── v4.1: Log confusion signals if available ──
        confusion_margin = getattr(classification, 'confusion_margin', 0.0)
        if confusion_margin > 0:
            logger.info(
                "Classification quality: task=%s confidence=%.2f "
                "confusion_margin=%.3f query_type=%s",
                classification.task_type.value,
                classification.confidence,
                confusion_margin,
                getattr(classification, 'query_type', 'command'),
            )

        # ── v4.1: Multi-part query logging ──
        sub_intents = getattr(classification, 'sub_intents', [])
        if sub_intents:
            logger.info(
                "Multi-part query detected: %d intents — %s",
                len(sub_intents),
                ", ".join(f"{s['task_type']}({s['confidence']:.2f})" for s in sub_intents),
            )

        # Step 1.5: Validate — check classification confidence
        # Correction boundary: if fallback + very low confidence → force CHAT
        if getattr(classification, 'is_fallback', False) and classification.confidence < 0.4:
            logger.warning(
                "Fallback classification with very low confidence (%.2f) — "
                "forcing CHAT to prevent cascading errors.",
                classification.confidence,
            )
            if hasattr(classification.task_type, '__class__'):
                classification.task_type = classification.task_type.__class__.CHAT
            else:
                classification.task_type = None  # type: ignore[assignment]
            try:
                from core.uil.contract import TaskType as _TT
                classification.task_type = _TT.CHAT
                classification.confidence = 0.3
            except ImportError:
                logger.debug("Could not import TaskType for confidence correction")
            except Exception as e:
                logger.debug("TaskType assignment failed: %s", e)

        if classification.confidence < 0.4:
            logger.warning(
                "Low classification confidence (%.2f) for '%s' — "
                "classified as %s. Execution may produce poor results.",
                classification.confidence, user_input[:60],
                classification.task_type.value,
            )
        elif classification.confidence < 0.6:
            logger.info(
                "Moderate confidence (%.2f) for '%s' → %s",
                classification.confidence, user_input[:60],
                classification.task_type.value,
            )

        # Step 2: Route — decide how to execute
        decision = self.router.route(classification, self._tool_defs,
                                        knowledge=self.knowledge)

        # ── v4.1: Override routing with intelligence signals ──
        _is_confused = getattr(classification, 'is_confused', False)
        if _is_confused and decision.plan.mode != ExecutionMode.SIMPLE_CHAT:
            logger.info(
                "Confused classification — downgrading %s → SIMPLE_CHAT",
                decision.plan.mode.value,
            )
            decision.plan.mode = ExecutionMode.SIMPLE_CHAT
            decision.tool_defs = self._tool_defs
            decision.decision_path.append(DecisionStep(
                component="Brain",
                input_summary="is_confused=True",
                output="SIMPLE_CHAT (safety)",
                score=0.5,
                detail="Classifier uncertainty caused conservative routing",
            ))

        # Correction boundary: low-confidence → never run AUTONOMOUS or EXPERT_TEAM
        if classification.confidence < 0.5 and not _is_confused:
            if decision.plan.mode in (ExecutionMode.AUTONOMOUS, ExecutionMode.EXPERT_TEAM):
                logger.warning(
                    "Low confidence (%.2f) — downgrading %s → SIMPLE_CHAT with full tools",
                    classification.confidence, decision.plan.mode.value,
                )
                decision.plan.mode = ExecutionMode.SIMPLE_CHAT
                decision.tool_defs = self._tool_defs

        # Step 2.5: Plan — ALWAYS runs (Phase 2.1: dead-code removal)
        # Enable TDD-first mode for code tasks with medium+ complexity
        use_tdd = (
            classification.task_type
            in (TaskType.CODE_WRITE, TaskType.CODE_MODIFY, TaskType.COMPLEX)
            and classification.complexity >= 0.4
        )
        plan = self.planner.plan(classification, user_input, use_tdd=use_tdd)
        decision.plan.decomposed = plan

        # ── v4.1: Enrich plan decisions with risk info ──
        high_risk_steps = [s for s in plan.steps if getattr(s, 'risk_score', 0) >= 0.6]
        plan_risk_detail = f"Risk: {len(high_risk_steps)}/{len(plan.steps)} high-risk steps"
        if _is_confused:
            plan_risk_detail += " (confused → conservative plan)"

        decision.decision_path.append(DecisionStep(
            component="TaskPlanner",
            input_summary=f"type={classification.task_type.value}",
            output=f"{'minimal' if plan.is_minimal else 'decomposed'}: "
                   f"{len(plan.steps)} step(s) "
                   f"{'(TDD)' if use_tdd else ''}",
            score=1.0,
            detail=("Minimal (simple task)" if plan.is_minimal
                    else f"Full decomposition. {plan_risk_detail}"),
        ))

        # Step 3: Build ExecutionContext with per-step telemetry
        step_results = []
        if plan and plan.steps:
            for s in plan.steps:
                step_results.append(StepResult(
                    step_id=s.id,
                    status="pending",
                    tools_used=[],
                ))
        ctx = ExecutionContext(
            decision=decision,
            task_plan=plan,
            current_step=plan.steps[0] if plan and plan.steps else None,
            step_results=step_results,
            # Execution resources — injected for real executors.
            # tool_defs comes from the RoutingDecision (filtered by router),
            # not from self._tool_defs (full unfiltered list).
            provider=getattr(self, "provider", None),
            tool_defs=decision.tool_defs,
            cfg=cfg or {},
            state=state or {},
        )

        # Step 3.5: Status event — execution phase
        if on_event:
            try:
                mode_label = decision.plan.mode.value if decision.plan and decision.plan.mode else "chat"
                plan_steps = (
                    len(decision.plan.decomposed.steps)
                    if decision.plan and decision.plan.decomposed
                    else 0
                )
                n_tools = len(decision.tool_defs) if decision.tool_defs else 0
                if mode_label == "autonomous":
                    status_label = f"Running in autonomous mode ({n_tools} tools)"
                elif mode_label == "expert_team":
                    status_label = f"Assembling expert team ({n_tools} tools)"
                elif plan_steps > 1:
                    status_label = f"Executing {plan_steps}-step plan"
                elif n_tools > 0:
                    status_label = f"Ready with {n_tools} tools"
                else:
                    status_label = "Thinking..."
                on_event({"type": "status", "data": {"phase": mode_label, "label": status_label, "detail": f"{classification.task_type.value} | {n_tools} tools"}})
            except Exception:
                logger.debug("Exception suppressed (line 351)")

        # Step 4: Execute — delegate via ExecutionContext, measure time
        executor = self._resolve_executor(decision, executors)
        t0 = time.perf_counter()
        err_msg: str | None = None

        # ── Route-by-complexity: set temperature/max_tokens from complexity ──
        try:
            from core.provider_reliability import ProviderPool
            pool = ProviderPool()
            route_cfg = pool.route_by_complexity(classification.complexity)
            ctx_cfg = ctx.cfg or {}
            ctx_cfg["temperature"] = ctx_cfg.get("temperature", route_cfg["temperature"])
            ctx_cfg["max_tokens"] = ctx_cfg.get("max_tokens", route_cfg["max_tokens"])
            decision.decision_path.append(DecisionStep(
                component="RouteByComplexity",
                input_summary=f"complexity={classification.complexity:.2f}",
                output=f"temp={route_cfg['temperature']} tokens={route_cfg['max_tokens']}",
                score=1.0 - classification.complexity * 0.3,
                detail=f"Route-by-complexity: complexity {classification.complexity:.2f} "
                       f"→ temperature {route_cfg['temperature']} "
                       f"max_tokens {route_cfg['max_tokens']}",
            ))
        except Exception:
            logger.debug("Exception suppressed (line 376)")

        # Inject plan steps into executor input so LLM-guided executors follow the plan
        enriched_input = user_input
        if plan and plan.steps and not plan.is_minimal:
            plan_text = "\n".join(
                f"  [{s.id}] {s.description}"
                for s in plan.steps
            )
            enriched_input = (
                f"{user_input}\n\n"
                f"Execution Plan ({len(plan.steps)} steps):\n{plan_text}\n\n"
                f"Follow this plan step by step."
            )

        # Inject hierarchical context for code tasks (RAG-enriched, pruned)
        if classification.task_type in (TaskType.CODE_WRITE, TaskType.CODE_MODIFY, TaskType.COMPLEX):
            project_ctx = self._get_context_pipeline(
                messages=messages,
                goal=user_input,
                max_tokens=4096,
            )
            if project_ctx:
                enriched_input = enriched_input + project_ctx

        try:
            if on_event:
                try:
                    raw = executor(ctx, enriched_input, messages, on_event=on_event)
                except TypeError:
                    # Executor doesn't support streaming — fall back to synchronous
                    raw = executor(ctx, enriched_input, messages)
            else:
                raw = executor(ctx, enriched_input, messages)
        except Exception as exc:
            err_msg = str(exc)
            raw = ExecutionResult(
                success=False,
                summary=f"Executor failed: {exc}",
                mode=decision.plan.mode if decision.plan else None,
                error=err_msg,
            )
        elapsed = time.perf_counter() - t0

        # Step 4.5: Verify — post-execution quality checks (Phase VERIFY)
        # Runs on the raw output before wrapping it in ExecutionResult.
        # Non-blocking: findings are attached, but execution continues.
        # Critical findings set result.success = False later.
        verify_t0 = time.perf_counter()
        verifier = get_verifier(classification)

        # Extract verifier context from whatever form raw is in
        raw_text = raw.summary if isinstance(raw, ExecutionResult) else str(raw)
        verifier_context = {}
        if raw_text.strip().startswith("<!DOCTYPE html") or raw_text.strip().startswith("<html"):
            verifier_context["html_content"] = raw_text
        elif "rm " in raw_text or "chmod " in raw_text or "wget " in raw_text:
            verifier_context["bash_commands"] = raw_text
        elif raw_text:
            verifier_context["code_content"] = raw_text

        verification_report = verifier.verify(
            result=raw if isinstance(raw, ExecutionResult) else ExecutionResult(
                success=True,
                summary=raw_text,
                error=err_msg,
            ),
            classification=classification,
            context=verifier_context if verifier_context else None,
        )
        verification_report.execution_time = round(time.perf_counter() - verify_t0, 4)

        # ── Runtime validation: run extracted code through CodeRunner ──
        try:
            from core.uil.contract import TaskType as _TT
            is_code_task = classification.task_type in (
                _TT.CODE_WRITE, _TT.CODE_MODIFY,
            )
        except Exception:
            is_code_task = False

        if is_code_task:
            try:
                import re
                code_blocks: list[str] = re.findall(
                    r'```(?:python|bash|sh)\n(.*?)```', raw_text, re.DOTALL
                )
                # Guard: only run CodeRunner if code blocks are actually present
                if code_blocks:
                    from core.validation.runner import CodeRunner
                    runner = CodeRunner(timeout_default=15)
                    for i, code in enumerate(code_blocks[:5]):  # max 5 blocks
                        # Determine language from code fence
                        try:
                            fence_match = re.search(
                                r'```(python|bash|sh)\n' + re.escape(code)[:50],
                                raw_text, re.DOTALL,
                            )
                            lang = fence_match.group(1) if fence_match else "python"
                        except Exception:
                            logger.debug("Fence language detection failed, defaulting to python")
                            lang = "python"
                        run_result = runner.run_python(code) if lang == "python" else runner.run_bash(code)
                        if not run_result.success:
                            verification_report.findings.append(VerificationFinding(
                                check_name=f"runtime_check_{i}",
                                severity=VerificationSeverity.ERROR,
                                message=f"Runtime error in code block {i+1}: {run_result.stderr[:300]}",
                                passed=False,
                            ))
            except ImportError:
                pass  # CodeRunner unavailable — skip runtime validation

        # Log verification findings
        if verification_report.findings:
            logger.info(
                "Verification (%s): %s",
                verification_report.verifier_name,
                verification_report.summarize(),
            )
            for f in verification_report.findings:
                if not f.passed:
                    level = (logging.ERROR if f.severity == VerificationSeverity.CRITICAL
                             else logging.WARNING)
                    logger.log(level, "  [%s] %s — %s", f.severity.value, f.check_name, f.message)

        # ── v4.0: Validation Engine parallel check ──
        if _ENGINES_AVAILABLE and engine_enabled(cfg or {}, "validation"):
            try:
                from core.validation.reporter import validate_result
                val_report = validate_result(
                    raw if isinstance(raw, ExecutionResult) else ExecutionResult(
                        success=True, summary=raw_text, error=err_msg,
                    ),
                    classification,
                    context=verifier_context,
                )
                logger.info(
                    "ValidationEngine: score=%.2f (syntax=%.2f runtime=%.2f quality=%.2f) "
                    "vs old verifier: %s",
                    val_report.overall,
                    val_report.syntax_score, val_report.runtime_score,
                    val_report.quality_score,
                    verification_report.summarize(),
                )
                # Attach adapted report for comparison
                adapted_val = adapt_validation(val_report)
                if adapted_val.passed_all != verification_report.passed_all:
                    logger.warning(
                        "Validation DISAGREE: new=%s old=%s → merging findings",
                        "PASS" if adapted_val.passed_all else "FAIL",
                        "PASS" if verification_report.passed_all else "FAIL",
                    )
                # Merge validation findings into verification report
                for f in adapted_val.findings:
                    if f.severity == VerificationSeverity.CRITICAL:
                        verification_report.findings.insert(0, f)
                    else:
                        verification_report.findings.append(f)
                verification_report.recompute()
            except Exception as e:
                logger.debug("ValidationEngine unavailable: %s", e)

        # Auto-retry on critical verification failures (up to 3 retries)
        MAX_RETRIES = 3
        for retry_attempt in range(1, MAX_RETRIES + 1):
            if not verification_report.criticals:
                break

            logger.warning(
                "Verification CRITICAL — retry %d/%d with re-analysis. "
                "(%d criticals)",
                retry_attempt, MAX_RETRIES, len(verification_report.criticals),
            )
            error_hint = "VERIFICATION FAILED:\n" + "\n".join(
                f"  - {f.message}" for f in verification_report.criticals
            )
            # Re-analyze with error context — may change task type
            retry_input = user_input + "\n\n[PREVIOUS OUTPUT HAD BUGS]\n" + error_hint
            retry_classification = self.analyzer.analyze(
                retry_input,
                context=ctx_analyzer or None,
            )
            # Only re-route if confidence dropped or task type changed
            if (retry_classification.task_type != classification.task_type
                    or retry_classification.confidence < classification.confidence):
                retry_decision = self.router.route(
                    retry_classification, self._tool_defs,
                    knowledge=self.knowledge,
                )
                retry_plan = self.planner.plan(retry_classification, retry_input)
                retry_decision.plan.decomposed = retry_plan
                retry_ctx = ExecutionContext(
                    decision=retry_decision,
                    task_plan=retry_plan,
                    provider=getattr(self, "provider", None),
                    tool_defs=retry_decision.tool_defs,
                    cfg=cfg or {},
                    state=state or {},
                )
                retry_executor = self._resolve_executor(retry_decision, executors)
            else:
                retry_ctx = ctx
                retry_executor = executor

            try:
                raw = retry_executor(retry_ctx, retry_input, messages)
                elapsed = time.perf_counter() - t0
                # Re-run verification on the retry output
                raw_text = raw.summary if isinstance(raw, ExecutionResult) else str(raw)
                verifier_context = {}
                if raw_text.strip().startswith("<!DOCTYPE html") or raw_text.strip().startswith("<html"):
                    verifier_context["html_content"] = raw_text
                elif "rm " in raw_text or "chmod " in raw_text or "wget " in raw_text:
                    verifier_context["bash_commands"] = raw_text
                elif raw_text:
                    verifier_context["code_content"] = raw_text
                verification_report = verifier.verify(
                    result=raw if isinstance(raw, ExecutionResult) else ExecutionResult(
                        success=True,
                        summary=raw_text,
                    ),
                    classification=retry_classification,
                    context=verifier_context if verifier_context else None,
                )
                verification_report.execution_time = round(time.perf_counter() - verify_t0, 4)
                logger.info(
                    "Retry %d/%d verification: %s",
                    retry_attempt, MAX_RETRIES, verification_report.summarize(),
                )
                if not verification_report.criticals:
                    logger.info("Retry %d succeeded — criticals resolved.", retry_attempt)
            except Exception as retry_err:
                logger.warning(
                    "Retry %d/%d failed with exception: %s",
                    retry_attempt, MAX_RETRIES, retry_err,
                )
        else:
            # Loop completed all retries without breaking (still has criticals)
            if verification_report.criticals:
                logger.warning(
                    "All %d retries exhausted. %d critical(s) remain unresolved. "
                    "Delivering best-effort result.",
                    MAX_RETRIES, len(verification_report.criticals),
                )

        # ── SelfCorrection ← Verify: targeted fixes ──
        if verification_report.criticals:
            try:
                from core.self_correction import SelfCorrection
                sc = SelfCorrection()
                correction = sc.correct(verification_report.criticals, raw)
                logger.info(
                    "SelfCorrection: %d strategies applied — %s",
                    len(correction["strategies_applied"]),
                    ", ".join(s["error_type"] for s in correction["strategies_applied"]),
                )
            except Exception as e:
                logger.debug("SelfCorrection unavailable: %s", e)

        # ── SelfImprove ← Verify: record verification outcome ──
        try:
            from core.self_improve import get_improver
            improver = get_improver()
            if verification_report.criticals:
                for f in verification_report.criticals:
                    improver.record_error(
                        f"verify_{f.check_name}",
                        f"{f.message} (severity={f.severity.value})",
                        "unresolved" if verification_report.criticals else "fixed",
                    )
            else:
                improver.record_error(
                    "verify_pass", "Verification passed all checks", "fixed"
                )
        except Exception as se_e:
            logger.warning("SelfImprove record failed: %s", se_e)

        # Step 5: Feedback — build ExecutionResult + populate telemetry
        steps_count = len(plan.steps) if plan and plan.steps else 0
        if isinstance(raw, tuple) and len(raw) >= 3:
            summary, completed, failed = raw[:3]
            tools_used = raw[3] if len(raw) >= 4 else []
            result = ExecutionResult(
                success=failed == 0,
                summary=summary,
                mode=decision.plan.mode,
                steps_planned=steps_count,
                steps_completed=completed,
                steps_failed=failed,
                tools_used=tools_used,
                error=err_msg,
                plan_decomposed=plan,
            )
        elif isinstance(raw, ExecutionResult):
            result = raw
            result.steps_planned = steps_count
            if err_msg:
                result.error = err_msg
        else:
            result = ExecutionResult(
                success=True,
                summary=str(raw),
                mode=decision.plan.mode,
                steps_planned=steps_count,
                plan_decomposed=plan,
                error=err_msg,
            )
        result.execution_time = round(elapsed, 3)

        # Attach verification report to result
        result.verification = verification_report
        # If verification found critical issues, mark execution as failed
        if verification_report.criticals and result.success:
            result.success = False
            result.error = (
                f"Verification failed: {len(verification_report.criticals)} critical "
                f"issue(s). Run with /debug or check logs for details."
            )

        # ── Quality score: multi-signal metric beyond "no exception" ──
        score = 1.0
        score -= 0.3 * len(verification_report.criticals)
        score -= 0.1 * len([f for f in verification_report.findings if not f.passed])
        if result.summary and len(result.summary) < 50:
            score -= 0.2  # suspiciously short output
        if hasattr(result, 'steps_completed') and result.steps_completed > 0:
            tool_failures = sum(
                1 for sr in (ctx.step_results or [])
                if getattr(sr, 'status', '') == 'failed'
            )
            if tool_failures > 0:
                score -= 0.1 * (tool_failures / result.steps_completed)
        result.quality_score = round(max(0.0, min(1.0, score)), 2)  # type: ignore[attr-defined]

        # Mark step_results as completed/failed based on execution outcome
        if ctx.step_results:
            for sr in ctx.step_results:
                if result.steps_failed > 0:
                    sr.status = "failed"
                    sr.error = result.error or "step failed"
                else:
                    sr.status = "completed"
                sr.start_time = t0
                sr.end_time = t0 + elapsed
                sr.duration = round(elapsed, 3)
                sr.tools_used = list(result.tools_used)

        # Populate execution_metrics
        ctx.execution_metrics = ExecutionMetrics(
            total_execution_time=round(elapsed, 3),
            total_steps=steps_count,
            completed_steps=result.steps_completed,
            failed_steps=result.steps_failed,
            tools_used_count=len(result.tools_used),
        )

        # ── Post-execution integrations (Level 4.0 + 5.0) ──

        # VerifyLoop (only if criticals remain)
        if verification_report.criticals:
            try:
                from core.verification.loop import get_verify_loop
                loop = get_verify_loop()
                loop_result = loop.run(raw, classification.task_type)
                logger.info(
                    "VerifyLoop: passed=%s iterations=%d fixed=%d",
                    loop_result.passed_all, loop_result.iterations, loop_result.findings_fixed,
                )
                if loop_result.passed_all:
                    verification_report = loop_result.final_report or verification_report  # type: ignore[assignment]
            except Exception as e:
                logger.debug("VerifyLoop unavailable: %s", e)

        # ADR: record decisions with multiple tools
        if len(result.tools_used) >= 3:
            try:
                from core.adr import adr_manager
                adr_manager.record(
                    title=f"Auto: {user_input[:80]}",
                    context=f"Task executed in {len(result.tools_used)} tool call(s)",
                    decision=f"Tools: {', '.join(str(t) for t in result.tools_used[:5])}",
                    consequences=getattr(raw, 'summary', '')[:200] if hasattr(raw, 'summary') else '',
                )
            except Exception as e:
                logger.warning("ADR recording failed: %s", e)

        # KG → Memory
        try:
            from core.knowledge_graph import get_knowledge_graph
            from core.memory import MemoryStore
            kg = get_knowledge_graph()
            kg.build()
            kg_snippet = kg.get_context_snippet()
            if kg_snippet:
                MemoryStore().save(
                    "project_structure", kg_snippet,
                    metadata={"type": "reference", "source": "knowledge_graph"},
                    confidence=0.9,
                )
        except Exception as e:
            logger.warning("KG → Memory failed: %s", e)

        # DocSync
        try:
            from core.doc_sync import get_doc_sync
            ds = get_doc_sync()
            drifts = ds.detect_drift()
            if drifts:
                ds.auto_update(drifts)
        except Exception as e:
            logger.warning("DocSync failed: %s", e)

        # ── World Model: learn WHY, not just WHAT ──
        try:
            from core.world_model import get_world_model
            wm = get_world_model()
            success = getattr(result, "success", True)
            summary = getattr(raw, "summary", "") if hasattr(raw, "summary") else str(raw)
            wm.learn_from_outcome(
                strategy_name=f"{classification.task_type.value}_{'success' if success else 'fail'}",
                context=user_input[:200],
                outcome="success" if success else "failure",
                why=f"Tools used: {result.tools_used}. {summary[:200]}" if success else f"Failed: {summary[:200]}",
            )
        except Exception as e:
            logger.warning("World Model learn failed: %s", e)

        # ── Learning: extract patterns + promote ──
        try:
            from core.learning.pattern_extractor import PatternExtractor
            pe = PatternExtractor()
            pe.extract_from_execution(
                result=raw, task_type=classification.task_type,
                user_input=user_input, steps=getattr(plan, "steps", []),
                success=getattr(result, "success", True),
            )
            pe.local_lib.promote_all_ready()
        except Exception as e:
            logger.warning("Pattern extraction failed: %s", e)

        # Step 6: Knowledge — record execution outcome
        self.knowledge.record(
            classification=classification,
            result=result,
            decision=decision,
        )

        # ── v4.1: Feed back to DecisionEngine ──
        try:
            from core.intelligence.decision_engine import get_decision_engine
            de = get_decision_engine()
            de.record(
                task_type=classification.task_type.value,
                mode=decision.plan.mode.value,
                features=list(getattr(classification, 'detected_features', {})),
                success=getattr(result, 'success', False),
                quality_score=getattr(result, 'quality_score', 0.5) if hasattr(result, 'quality_score') else 0.5,
                complexity=len(plan.steps) if plan and plan.steps else 1,
                cost=getattr(result, 'cost', 0.0),
                latency=elapsed,
            )
        except Exception as e:
            logger.debug("DecisionEngine record failed: %s", e)

        tool_tracer.print_summary()

        return result, decision

    def set_tool_defs(self, tool_defs: list[dict]):
        """Update the internal tool definitions list.

        Called externally when the available tool set changes
        (e.g. after loading/unloading skills or MCP servers).
        """
        self._tool_defs = tool_defs

    # ------------------------------------------------------------------
    # Internal: executor resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_executor(
        decision: RoutingDecision,
        executors: dict[ExecutionMode, Callable] | None,
    ) -> Callable:
        """Find the right executor for this decision."""
        mode = decision.plan.mode
        if executors and mode in executors:
            return executors[mode]
        # Fallback to real executors from executor_adapter
        executor_map = _get_executor_map()
        if mode in executor_map:
            return executor_map[mode]
        # Last resort — raise a clear error instead of returning a stub
        raise RuntimeError(
            f"No executor registered for {mode.value}. "
            "Ensure EXECUTOR_MAP covers this mode "
            "or pass an explicit executors dict to process()."
        )



