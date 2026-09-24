"""Execution Intelligence — 4-layer runtime monitoring and improvement system.

1. Continuous Evaluation  — monitors quality during execution, not just after
2. Execution Telemetry     — tracks step quality, plan deviation, progress score
3. Preventive Correction   — predicts and prevents errors before they happen
4. Deep Success Learning   — understands WHY something succeeded, not just WHAT

Wired directly into AutonomousAgent loop for real-time monitoring.

Usage:
    from core.execution_intelligence import ExecutionIntelligence
    ei = ExecutionIntelligence()
    ei.start_task(plan, goal)
    ei.evaluate_step(step_num, result, tool_used)  # called after each step
    ei.check_before_action(tool_name, args)         # preventive check
    report = ei.final_report()                       # complete telemetry
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("widdx.exec_intel")


# ═══════════════════════════════════════════════════════════════
# Telemetry Data Structures
# ═══════════════════════════════════════════════════════════════

@dataclass
class StepTelemetry:
    """Telemetry for a single execution step."""
    step_num: int = 0
    tool: str = ""
    args_summary: str = ""
    success: bool = True
    quality_score: float = 0.0       # 0.0-1.0
    plan_adherence: float = 1.0       # how well it follows plan
    novelty_score: float = 0.0        # is this a new approach?
    execution_time: float = 0.0       # seconds
    error_detail: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class TaskTelemetry:
    """Telemetry for the entire task."""
    goal: str = ""
    total_steps: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    avg_quality: float = 0.0
    plan_deviation: float = 0.0       # cumulative deviation from original plan
    progress_score: float = 0.0       # overall progress 0.0-1.0
    interventions_prevented: int = 0  # errors caught before happening
    tools_used: list[str] = field(default_factory=list)
    step_details: list[StepTelemetry] = field(default_factory=list)
    total_time: float = 0.0
    success_pattern: str = ""         # WHAT worked
    success_reason: str = ""          # WHY it worked (deep learning)
    recommendations: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Execution Intelligence
# ═══════════════════════════════════════════════════════════════

class ExecutionIntelligence:
    """4-layer runtime monitoring and improvement."""

    def __init__(self):
        self._telemetry = TaskTelemetry()
        self._plan_steps: list[str] = []
        self._start_time: float = 0.0
        self._error_history: list[dict] = []
        self._success_history: list[dict] = []

    # ── Layer 1: Continuous Evaluation ──────────────────────

    def start_task(self, plan: Any, goal: str):
        """Initialize monitoring for a new task."""
        self._telemetry = TaskTelemetry(goal=goal)
        self._plan_steps = []
        self._start_time = time.time()

        if plan and hasattr(plan, "steps"):
            for s in plan.steps:
                desc = getattr(s, "description", str(s))
                self._plan_steps.append(desc[:100])

        logger.info("ExecutionIntelligence: monitoring started for '%s' (%d plan steps)",
                    goal[:60], len(self._plan_steps))

    def evaluate_step(self, step_num: int, result: str, tool_used: str,
                      tool_args: dict | None = None) -> StepTelemetry:
        """Evaluate quality of a completed step. Called after each tool execution.

        Returns StepTelemetry with quality_score and plan_adherence.
        """
        st = StepTelemetry(
            step_num=step_num,
            tool=tool_used,
            args_summary=str(tool_args)[:100] if tool_args else "",
            success=self._is_success(result),
            execution_time=round(time.time() - self._start_time, 2),
        )

        # ── Quality scoring ──────────────────────
        st.quality_score = self._score_quality(result, tool_used)

        # ── Plan adherence ───────────────────────
        if step_num <= len(self._plan_steps):
            expected = self._plan_steps[step_num - 1].lower()
            actual = (tool_used + " " + str(tool_args)[:50]).lower()
            # Simple: check if tool matches expected step description
            match_words = sum(1 for w in expected.split() if w in actual)
            total_words = max(1, len(expected.split()))
            st.plan_adherence = min(1.0, match_words / total_words)

        # ── Novelty detection ────────────────────
        if self._telemetry.step_details:
            prior_tools = [s.tool for s in self._telemetry.step_details]
            if tool_used not in prior_tools:
                st.novelty_score = 0.8  # New tool being used
        else:
            st.novelty_score = 0.5

        # ── Record ───────────────────────────────
        if st.success:
            self._success_history.append({
                "step": step_num, "tool": tool_used,
                "quality": st.quality_score, "plan_adherence": st.plan_adherence,
            })
        else:
            self._error_history.append({
                "step": step_num, "tool": tool_used,
                "error": result[:200], "quality": st.quality_score,
            })
            st.error_detail = result[:200]

        self._telemetry.step_details.append(st)
        self._telemetry.steps_completed += 1
        if not st.success:
            self._telemetry.steps_failed += 1
        self._telemetry.tools_used.append(tool_used)

        # ── Recalculate progress ─────────────────
        self._recalc_progress()

        logger.debug("Step %d: quality=%.2f adherence=%.2f tool=%s",
                     step_num, st.quality_score, st.plan_adherence, tool_used)

        return st

    def _score_quality(self, result: str, tool: str) -> float:
        """Score the quality of a step result."""
        score = 0.5  # baseline
        r = result.lower()

        # Success indicators
        if any(w in r for w in ("success", "written", "created", "ok", "✅", "passed")):
            score += 0.3
        if tool == "validate" and ("valid" in r or "ok" in r):
            score += 0.2
        if tool == "write" and ("written" in r or "created" in r):
            score += 0.2

        # Failure indicators
        if any(w in r for w in ("error", "failed", "❌", "denied", "not found")):
            score -= 0.4

        return max(0.0, min(1.0, score))

    def _is_success(self, result: str) -> bool:
        """Determine if a step succeeded."""
        r = (result or "").strip()
        if not r:
            return False
        if r.startswith(("❌", "⚠️", "⚠", "⛔", "Error", "Failed", "No such")):
            return False
        return True

    # ── Layer 2: Execution Telemetry ────────────────────────

    def _recalc_progress(self):
        """Calculate overall progress score."""
        t = self._telemetry
        if not t.step_details:
            t.progress_score = 0.0
            return

        # Average quality
        t.avg_quality = sum(s.quality_score for s in t.step_details) / len(t.step_details)

        # Plan deviation: 1.0 = perfect adherence, 0.0 = completely off
        if t.step_details:
            t.plan_deviation = 1.0 - sum(s.plan_adherence for s in t.step_details) / len(t.step_details)

        # Progress score: weighted combination
        completion_pct = t.steps_completed / max(1, len(self._plan_steps)) if self._plan_steps else 0.5
        t.progress_score = round(
            completion_pct * 0.4 +          # how much of plan is done
            t.avg_quality * 0.3 +            # how good each step is
            (1.0 - t.plan_deviation) * 0.3, # how well it follows plan
            2
        )

    def get_control_signals(self) -> list:
        """Return current signals suitable for ECP consumption.
        
        Converts monitoring data into actionable signals for the
        Execution Control Plane to make runtime decisions.
        """
        from core.runtime.execution_control_plane import ExecutionSignal, SignalType
        signals = []
        t = self._telemetry

        if t.plan_deviation > 0.4:
            signals.append(ExecutionSignal(
                signal_type=SignalType.COMPLEXITY_DRIFT,
                value=t.plan_deviation,
                source="ExecutionIntelligence",
                detail=f"Plan deviation {t.plan_deviation:.2f} exceeds threshold",
            ))
        if t.avg_quality < 0.4 and len(t.step_details) >= 2:
            signals.append(ExecutionSignal(
                signal_type=SignalType.QUALITY_DEGRADATION,
                value=1.0 - t.avg_quality,
                source="ExecutionIntelligence",
                detail=f"Avg quality {t.avg_quality:.2f} below threshold",
            ))
        failure_count = sum(1 for s in t.step_details if not s.success)
        if failure_count >= 3:
            signals.append(ExecutionSignal(
                signal_type=SignalType.TOOL_FAILURE_RATE,
                value=min(1.0, failure_count / max(len(t.step_details), 1)),
                source="ExecutionIntelligence",
                detail=f"{failure_count} tool failures detected",
            ))
        
        # ── CONFIDENCE_DROP: activated when quality is declining ──
        if len(t.step_details) >= 3:
            recent = t.step_details[-3:]
            recent_quality = sum(s.quality_score for s in recent) / len(recent)
            older = t.step_details[-6:-3] if len(t.step_details) >= 6 else t.step_details[:3]
            older_quality = sum(s.quality_score for s in older) / len(older)
            
            if recent_quality < older_quality - 0.15:
                signals.append(ExecutionSignal(
                    signal_type=SignalType.CONFIDENCE_DROP,
                    value=older_quality - recent_quality,
                    source="ExecutionIntelligence",
                    detail=f"Quality declining: {older_quality:.2f} → {recent_quality:.2f}",
                ))

        return signals

    def get_live_status(self) -> dict:
        """Return current execution status for live monitoring."""
        t = self._telemetry
        return {
            "progress_pct": round(t.progress_score * 100),
            "steps_done": t.steps_completed,
            "steps_failed": t.steps_failed,
            "avg_quality": round(t.avg_quality, 2),
            "plan_deviation": round(t.plan_deviation, 2),
            "tools_used": len(set(t.tools_used)),
            "interventions": t.interventions_prevented,
        }

    # ── Layer 3: Preventive Self-Correction ─────────────────

    def check_before_action(self, tool_name: str, args: dict | None = None) -> dict:
        """Check if an action is safe/smart BEFORE executing it.
        Returns {"safe": bool, "warning": str, "suggestion": str}
        """
        result = {"safe": True, "warning": "", "suggestion": ""}

        # ── Check against error history ──
        for err in self._error_history:
            if err["tool"] == tool_name:
                # Same tool previously failed — warn
                result["warning"] = f"This tool ({tool_name}) failed at step {err['step']}. Consider a different approach."
                result["safe"] = True  # Not blocking, just warning
                result["suggestion"] = f"Previous error: {err['error'][:100]}"

        # ── Check against success patterns ──
        if tool_name == "write" and args:
            filepath = args.get("file_path", "")
            if filepath:
                # Check if file was recently written successfully
                for s in self._success_history:
                    if s["tool"] == "write" and s.get("file") == filepath:
                        result["warning"] = f"File {filepath} was already written at step {s['step']}. Are you sure?"
                        result["suggestion"] = "Consider editing instead of overwriting."

        # ── Pattern-based prevention ──
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            # Check for deprecated patterns related to this action
            patterns = UnifiedPatternStore().search(
                query=f"{tool_name}", category="debugging", min_confidence=0.4, limit=1,
            )
            if patterns and patterns[0].status == "deprecated":
                result["warning"] = f"Pattern '{patterns[0].name}' was deprecated: {patterns[0].superseded_by}"
                result["safe"] = False
        except Exception as e:
            logger.debug("Preventive check failed: %s", e)

        if result["warning"]:
            self._telemetry.interventions_prevented += 1
            logger.warning("Preventive: %s — %s", tool_name, result["warning"])

        return result

    # ── Layer 4: Deep Success Learning ──────────────────────

    def analyze_success(self, final_result: Any, task_type: str) -> TaskTelemetry:
        """After task completion, deeply analyze WHY it succeeded."""
        t = self._telemetry
        t.total_time = round(time.time() - self._start_time, 2)
        t.total_steps = len(t.step_details)

        # ── What worked ──
        successful_tools = [s for s in t.step_details if s.success]
        if successful_tools:
            tool_counts: dict[str, int] = {}
            for s in successful_tools:
                tool_counts[s.tool] = tool_counts.get(s.tool, 0) + 1
            top_tool = max(tool_counts, key=lambda k: tool_counts[k])
            t.success_pattern = f"Most successful tool: {top_tool} ({tool_counts[top_tool]}x). "
            t.success_pattern += f"Avg quality: {t.avg_quality:.2f}. "

        # ── Why it worked (deep analysis) ──
        reasons = []
        if t.plan_deviation < 0.3:
            reasons.append("followed the plan closely")
        if t.avg_quality > 0.7:
            reasons.append("maintained high step quality")
        if len(t.tools_used) >= 2:
            reasons.append("used multiple tools effectively")
        if t.steps_failed == 0:
            reasons.append("zero step failures")
        if successful_tools and all(s.plan_adherence > 0.5 for s in successful_tools):
            reasons.append("each step stayed on-plan")

        t.success_reason = "Success because: " + "; ".join(reasons) + "." if reasons else "No deep analysis available."

        # ── Recommendations ──
        if t.plan_deviation > 0.5:
            t.recommendations.append("Reduce plan deviation — steps diverged from original plan")
        if t.avg_quality < 0.6:
            t.recommendations.append("Improve step quality — verify after each write")
        if any(s.novelty_score > 0.7 for s in t.step_details):
            t.recommendations.append("Novel approaches detected — consider adding as reusable patterns")

        # ── Record in PatternLibrary for future use ──
        self._record_success_pattern(t)

        return t

    def _record_success_pattern(self, t: TaskTelemetry):
        """Record successful patterns for future learning."""
        try:
            from core.learning.pattern_library import PatternLibrary
            pl = PatternLibrary(global_scope=False)

            if t.success_pattern:
                pl.add(
                    name=f"success-{t.goal[:30].replace(' ', '-').lower()}",
                    category="workflow",
                    description=f"Successful execution of: {t.goal[:80]}",
                    solution=f"{t.success_pattern} | Quality: {t.avg_quality:.2f} | Adherence: {1-t.plan_deviation:.2f}",
                    context=t.goal[:200],
                    tags=["success", "telemetry"] + list(set(t.tools_used)),
                    confidence=min(0.9, t.avg_quality),
                )

            if t.success_reason:
                pl.add(
                    name=f"why-{t.goal[:30].replace(' ', '-').lower()}",
                    category="planning",
                    description=f"Deep analysis of success: {t.goal[:80]}",
                    solution=t.success_reason,
                    context=t.goal[:200],
                    tags=["success", "deep-learning", "why"],
                    confidence=min(0.85, t.avg_quality + 0.1),
                )

            # Promote to global if high quality
            if t.avg_quality > 0.8 and len(t.step_details) >= 3:
                pl.promote_all_ready()

        except Exception as e:
            logger.debug("Failed to record success pattern: %s", e)

    def final_report(self) -> TaskTelemetry:
        """Return the complete telemetry report."""
        return self._telemetry


# Singleton
_ei: ExecutionIntelligence | None = None


def get_execution_intelligence() -> ExecutionIntelligence:
    global _ei
    if _ei is None:
        _ei = ExecutionIntelligence()
    return _ei
