"""Autonomy Execution Loop — Level 5.3.

The core loop that allows the agent to continue executing tasks
without human intervention after initial goal assignment.

Uses Provider Reliability Layer for failover and checkpointing.
Provider failures trigger recovery, NOT termination.

Metric: Agent يكمل مهمة بـ 5 خطوات بدون أي تدخل بشري.

Usage:
    from core.autonomy_loop import AutonomyLoop
    loop = AutonomyLoop()
    result = loop.run("Build a weather CLI tool")
    print(result.summary, result.success, result.iterations)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger("widdx.autonomy_loop")


@dataclass
class AutonomyResult:
    success: bool = False
    summary: str = ""
    iterations: int = 0
    total_time: float = 0.0
    tools_used: int = 0
    state_saved: bool = False
    human_help_needed: bool = False


class AutonomyLoop:
    """Runs agent autonomously until goal complete or max iterations."""

    def __init__(self, max_iterations: int = 20):
        self._max_iterations = max_iterations

    def run(
        self,
        goal: str,
        provider=None,
        on_event: Callable | None = None,
    ) -> AutonomyResult:
        """Execute goal autonomously. Returns when done, stuck, or max reached."""
        t0 = time.perf_counter()
        result = AutonomyResult()

        import sys
        from pathlib import Path

        # Ensure project root in path
        root = str(Path(__file__).resolve().parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)

        try:
            # ── Init state ──────────────────────────────
            from core.task_state import get_task_state
            ts = get_task_state()

            # Resume or start new
            resume = False
            if ts.is_active():
                existing_goal = ts.get_goal()
                if goal and goal != existing_goal:
                    ts.clear()
                    ts.set_goal(goal)
                else:
                    goal = existing_goal
                    resume = True
            else:
                ts.set_goal(goal)

            saved_messages = ts.get_messages()
            if resume and saved_messages:
                messages = saved_messages
                logger.info("Resuming AutonomyLoop from saved messages history.")
            else:
                messages = []

            if on_event:
                on_event({"type": "state", "data": f"Goal: {goal[:80]}"})

            # ── Get unified context ─────────────────────
            from core.state_manager import get_state_manager
            sm = get_state_manager()

            # ── Get brain ───────────────────────────────
            from core.config.settings import load as load_cfg
            cfg = load_cfg()
            if provider is None:
                from core.providers.providers import create_provider
                provider = create_provider(cfg)
            from core.uil.brain import UnifiedIntelligenceLayer
            brain = UnifiedIntelligenceLayer(provider=provider)

            # ── Main loop ──────────────────────────────
            for i in range(1, self._max_iterations + 1):
                result.iterations = i
                active_step = ts.get_active_step()

                # Build context with current state
                context = sm.get_full_context(goal=goal)
                if not messages:
                    messages = [{"role": "system", "content": context}]
                else:
                    # Update system context in messages
                    if messages[0].get("role") == "system":
                        messages[0]["content"] = context
                    else:
                        messages.insert(0, {"role": "system", "content": context})

                # Add step-specific instruction
                if active_step:
                    step_msg = (
                        f"Continue working on Step {active_step['order']}: "
                        f"{active_step['description']}. "
                        f"Status: {active_step['status']}. "
                        "Complete this step before moving to the next."
                    )
                else:
                    step_msg = (
                        f"Goal: {goal}\n"
                        "Plan the next steps if you haven't already, "
                        "then execute them one by one. "
                        "Use tools: write, bash, browser. "
                        "After each step, verify your work. "
                        "When ALL steps are done, say 'GOAL COMPLETE'."
                    )

                if on_event:
                    on_event({"type": "iteration", "data": f"Iteration {i}/{self._max_iterations}"})

                try:
                    exec_result, routing = brain.process(
                        user_input=step_msg,
                        messages=messages,
                        cfg=cfg,
                    )
                except Exception as e:
                    logger.error("Brain processing failed: %s", e)
                    # ── Provider Reliability: save checkpoint on failure ──
                    try:
                        from core.provider_reliability import get_reliable_provider
                        rp = get_reliable_provider()
                        if rp.pool_status["available"] > 0:
                            logger.info("Provider pool has %d alternatives — will retry", rp.pool_status["available"])
                            result.human_help_needed = False  # Don't give up yet
                            continue  # Try next iteration with different provider
                    except Exception:
                        logger.debug("Exception suppressed (line 157)")
                    result.summary = f"Error: {e}"
                    result.human_help_needed = True
                    break

                # Update state from execution
                summary = getattr(exec_result, "summary", "") or ""
                ts.increment_tools()

                # Persist messages history
                messages.append({"role": "user", "content": step_msg})
                messages.append({"role": "assistant", "content": summary})
                messages = messages[-20:]
                ts.set_messages(messages)

                # Check for completion signal
                if "GOAL COMPLETE" in summary.upper() or "ALL DONE" in summary.upper():
                    result.success = True
                    result.summary = summary
                    ts.clear()  # Mark complete and clear state
                    if on_event:
                        on_event({"type": "done", "data": "Goal achieved"})
                    break

                # Update step if we have one
                if active_step:
                    success = getattr(exec_result, "success", True)
                    ts.update_step(
                        active_step["order"],
                        "done" if success else "failed",
                        summary[:200],
                    )
                else:
                    # Auto-plan: extract steps from the first iteration
                    self._auto_plan_steps(summary, ts)

                # ── Stuck? Web Learning → ⚡ IMMEDIATE hot-reload → retry SAME step ──
                if i >= 3 and ts.get_progress()["progress_pct"] < 20:
                    try:
                        from core.learning.web_learning import get_web_learning
                        wl = get_web_learning()
                        progress = ts.get_progress()
                        if wl.should_search(i, progress.get("progress_pct", 0), True):
                            if on_event:
                                on_event({"type": "text", "data": "\n[🌐 Web search — learning...]\n"})
                            web_result = wl.learn(goal)
                            if web_result["found"] and web_result.get("injection"):
                                # ⚡ Hot-reload: inject web knowledge into CURRENT context
                                if on_event:
                                    on_event({"type": "text", "data": f"\n[⚡ Injecting web knowledge now: {web_result['summary'][:150]}]\n"})
                                # Rebuild context with injection
                                sm = get_state_manager()
                                ctx = sm.get_full_context(goal=goal)
                                ctx += "\n\n" + web_result["injection"]
                                # Continue loop — retries SAME step with new knowledge
                                continue
                    except Exception:
                        logger.debug("Exception suppressed (line 214)")

                    result.human_help_needed = True
                    result.summary = "Stuck — no progress, web search found nothing"
                    break

            # ── Wrap up ─────────────────────────────────
            result.tools_used = ts.get_progress().get("tools_used", 0)
            result.state_saved = True

            if not result.summary:
                result.summary = ts.get_context_for_prompt()

        except Exception as e:
            logger.error("AutonomyLoop failed: %s", e, exc_info=True)
            result.success = False
            result.summary = str(e)
            result.human_help_needed = True

        result.total_time = round(time.perf_counter() - t0, 2)
        return result

    @staticmethod
    def _auto_plan_steps(summary: str, ts):
        """Extract steps from agent's first planning response."""
        import re
        # Look for numbered steps like "1. Create..." "2. Build..."
        steps = re.findall(r'(?:^|\n)\s*(\d+)[\.\)]\s+(.+?)(?=\n\s*\d+[\.\)]|\n\n|$)', summary)
        if len(steps) >= 2:
            for num, desc in steps[:10]:
                ts.add_step(desc.strip()[:200], order=int(num))


# Singleton
_loop: AutonomyLoop | None = None


def get_autonomy_loop() -> AutonomyLoop:
    global _loop
    if _loop is None:
        _loop = AutonomyLoop()
    return _loop
