"""TUI Chat Engine — streaming, tool execution, agent dispatch.

Synchronous core logic.  The UI layer (MainScreen) wraps calls in
``@work(thread=True)`` to keep the interface responsive.
"""

from pathlib import Path
from typing import Any
from textual.message import Message
from textual.screen import Screen
from core import tools as core_tools
from core.chat import _valid_tool_call_id, _build_tc_list, _sanitize_tool_call_ids
from core.providers.providers import estimate_turn_cost
from core.memory_learner import MemoryLearner
from core.skills import skill_manager
from core.uil import UnifiedIntelligenceLayer, ExecutionMode
from core.uil.contract import RoutingDecision
from core.project_tracker import build_context_block
from .state import TUIState


# ── UI Messages ──────────────────────────────────────────────
class ResultMsg(Message):
    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()

class ErrorMsg(Message):
    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()

class ToolStepMsg(Message):
    def __init__(self, tool: str, status: str, detail: str) -> None:
        self.tool = tool
        self.status = status
        self.detail = detail
        super().__init__()

class StreamChunkMsg(Message):
    def __init__(self, chunk: str) -> None:
        self.chunk = chunk
        super().__init__()

class StreamEndMsg(Message):
    def __init__(self, content: str, msgs: list) -> None:
        self.content = content
        self.msgs = msgs
        super().__init__()

class ThinkingMsg(Message):
    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()


class ChatEngine:
    """Handles chat execution, routing, streaming, and tool calls.

    Uses ``self.screen`` to post messages (thread-safe).
    Uses ``self.app`` (the Textual App) for ``call_from_thread``.
    """

    def __init__(self, screen: Screen) -> None:
        self.screen = screen
        self._processing = False

    @property
    def app(self):
        return self.screen.app

    # ── Main entry ──────────────────────────────────────────
    def start(self, text: str, state: TUIState) -> None:
        """Start a chat interaction.  Routes to the right executor."""
        if self._processing or not text.strip():
            return
        self._processing = True

        state.messages.append({"role": "user", "content": text})
        state.turns += 1
        state.tools_used = []

        # Inject context for this turn
        msgs = list(state.messages)

        # Project docs
        try:
            pt_ctx = build_context_block(Path.cwd().resolve())
            if pt_ctx:
                msgs = [m for m in msgs if not m.get("_project_docs")]
                msgs.insert(0, {"role": "system", "content": pt_ctx, "_project_docs": True})
        except Exception:
            pass

        # Memory context
        try:
            ml = MemoryLearner(provider=state.provider)
            mem_ctx = ml.load_relevant(text)
            if mem_ctx:
                msgs = [m for m in msgs if not m.get("_memory_context")]
                msgs.insert(0, {"role": "system", "content": mem_ctx, "_memory_context": True})
        except Exception:
            pass

        # ── UIL-powered intent detection ─────────────────
        try:
            from core.uil.analyzer import LLMClassifier
            llm_cls = LLMClassifier(provider=state.provider)
            cls_result = llm_cls.classify(text)
            if cls_result:
                result, steps = cls_result
                # execution_mode is in keywords[1], complexity in keywords[2]
                kw = result.keywords or []
                execution_mode = kw[1] if len(kw) > 1 else "direct"
                complexity = kw[2] if len(kw) > 2 else "simple"

                # Route based on execution_mode
                if execution_mode == "cron":
                    from core.cron.parser import parse_schedule
                    try:
                        cron_expr, dt = parse_schedule(text)
                        from core.cron.scheduler import CronScheduler
                        sched = CronScheduler()
                        job_id = sched.create_job(cron_expr, text)
                        msg = f"✅ Cron job created: {job_id[:8]} — will execute {cron_expr}"
                        self.app.call_from_thread(self.screen._log_message, "system", msg)
                        self._finish()
                        return
                    except (ValueError, ImportError):
                        pass

                elif execution_mode == "background":
                    from core.background import background
                    task_id = background.run(text, sandbox_mode="auto", on_done=lambda t: (
                        self.app.call_from_thread(
                            self.screen._log_message, "system",
                            f"✅ Background task done: {t.id[:8]} | {t.result[:200]}"
                        )
                    ))
                    msg = f"⏳ Background task started: {task_id[:8]} | Use /tasks to check"
                    self.app.call_from_thread(self.screen._log_message, "system", msg)
                    self._finish()
                    return

                elif execution_mode == "delegation" and complexity == "complex":
                    from core.delegation import DelegationManager
                    dlg = DelegationManager()
                    task_id = dlg.run(text, provider=state.provider,
                                      tool_defs=state.tool_defs, cfg=state.cfg)
                    msg = f"🤖 Sub-agent spawned: {task_id[:8]} — decomposing task..."
                    self.app.call_from_thread(self.screen._log_message, "system", msg)
                    agent_result = dlg.wait(task_id, timeout=120)
                    if agent_result and agent_result.status.value == "done":
                        state.messages.append({"role": "assistant", "content": agent_result.summary})
                        self.app.call_from_thread(
                            self.screen._log_message, "system",
                            f"✅ Agent {task_id[:8]} completed ({agent_result.steps} steps, {agent_result.elapsed_seconds:.1f}s)"
                        )
                        self._finish()
                        return

        except Exception as e:
            import logging
            logging.getLogger("widdx.tui").debug("UIL routing fallback: %s", e)

        # ── Auto-detect cron scheduling ────────────────────
        cron_keywords = [
            "every", "daily", "remind", "schedule", "cron", "morning",
            "كل", "يوم", "شوف", "راجع", "ذكرني", "تأكد", "راقب", "صباح", "مساء",
        ]
        if any(kw in text.lower() for kw in cron_keywords):
            from core.cron.parser import parse_schedule
            from core.cron.scheduler import CronScheduler
            try:
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    cron_expr, dt = parse_schedule(line)
                    sched = CronScheduler()
                    job_id = sched.create_job(cron_expr, text)
                    msg = f"✅ Cron job created: `{job_id[:8]}` — will execute `{cron_expr}`"
                    self.app.call_from_thread(
                        self.screen._log_message, "system", msg
                    )
                    self._finish()
                    return
            except (ValueError, ImportError):
                pass

        # ── Auto-detect background tasks ─────────────────
        bg_keywords = [
            "نظف", "install", "download", "update", "upgrade",
            "compile", "build", "deploy", "backup", "restore",
            "npx ", "npm install", "pip install", "docker build",
            "git clone", "wget ", "curl ", "make ",
        ]
        is_bg_task = any(kw in text.lower() for kw in bg_keywords)

        if is_bg_task:
            from core.background import background
            task_id = background.run(text, sandbox_mode="auto", on_done=lambda t: (
                self.app.call_from_thread(
                    self.screen._log_message, "system",
                    f"✅ Background task done: {t.id} — {t.prompt[:60]} | {t.result[:200]}"
                )
            ))
            msg = f"⏳ Background task started: {task_id} — running `{text[:80]}` | Use /tasks to check"
            self.app.call_from_thread(self.screen._log_message, "system", msg)
            self._finish()
            return

        # ── Auto-detect browser / web tasks ──────────────
        browser_keywords = [
            "open ", "navigate to", "go to ", "browser",
            "بحث", "تصفح", "افتح", "شوف", "site", "website",
            "http://", "https://", ".com", ".org",
        ]
        is_browser_task = any(kw in text.lower() for kw in browser_keywords)
        is_url = any(text.lower().startswith(kw) for kw in ["http://", "https://", "www.", "open ", "navigate"])

        if is_browser_task or is_url:
            # Ensure browser tools are in the tool list
            browser_tools = [t for t in core_tools.TOOL_DEFINITIONS if t["name"].startswith("browser_")]
            for bt in browser_tools:
                if bt not in state.tool_defs:
                    state.tool_defs.append(bt)

        # UIL routing (project-aware)
        decision = None
        try:
            uil = UnifiedIntelligenceLayer(provider=state.provider)
            uil.set_tool_defs(state.tool_defs)
            project_card = getattr(state, 'scanner', None)
            project_card = getattr(project_card, '_card', None) if project_card else None
            _, decision = uil.process(
                text,
                project_card=project_card,
            )
            mode = decision.plan.mode if decision else ExecutionMode.SIMPLE_CHAT
        except Exception:
            mode = ExecutionMode.SIMPLE_CHAT

        if mode == ExecutionMode.EXPERT_TEAM:
            self.app.post_message(ThinkingMsg("🧠 Routing to Expert Team..."))
            self._run_expert_team(state, text)
        elif mode == ExecutionMode.AUTONOMOUS:
            self.app.post_message(ThinkingMsg("🧠 Routing to autonomous agent..."))
            self._run_agent(state, text)
        elif mode == ExecutionMode.DIRECT_TOOL and decision:
            self.app.post_message(ThinkingMsg("⚙ Running direct tool..."))
            self._run_direct_tool(state, text, decision)
        else:
            self._run_chat(state, msgs)

    def _finish(self) -> None:
        self._processing = False

    # ── Simple chat (streaming) ─────────────────────────────
    def _run_chat(self, state: TUIState, msgs: list[dict]) -> None:
        cfg_t = state.cfg.get("temperature", 0.7)
        max_iter = state.cfg.get("max_turns", 10)

        try:
            if hasattr(state.provider, "stream"):
                self._stream_loop(state, msgs, cfg_t, max_iter)
            else:
                self._nonstream_loop(state, msgs, cfg_t, max_iter)
        except Exception as e:
            self.app.post_message(ErrorMsg(str(e)))
        finally:
            self.app.call_from_thread(self._finish)

    def _stream_loop(self, state: TUIState, msgs: list[dict], cfg_t: float, max_iter: int) -> None:
        model_name = state.model.split("/")[-1] or "unknown"

        for turn in range(max_iter):
            _sanitize_tool_call_ids(msgs)
            chunks = []
            reasoning = ""
            tool_calls = None
            err = None

            for event in state.provider.stream(msgs, state.tool_defs, cfg_t):
                if event["type"] == "content":
                    chunks.append(event["data"])
                    # Send chunk for typewriter effect (batch every few chars for efficiency)
                    if len(chunks) >= 5 or event["data"].endswith((".", "!", "?", "\n")):
                        chunk_text = "".join(chunks[-5:]) if len(chunks) >= 5 else event["data"]
                        self.app.call_from_thread(
                            self.screen._handle_stream_chunk, chunk_text
                        )
                elif event["type"] == "reasoning":
                    reasoning += event["data"]
                elif event["type"] == "error":
                    err = event["data"]
                    break
                elif event["type"] == "done":
                    _, tool_calls = event["data"]
                    break

            if reasoning:
                state._last_reasoning = reasoning
                self.app.post_message(ThinkingMsg(reasoning))

            if err:
                self.app.post_message(ErrorMsg(err))
                return

            content = "".join(chunks)
            state.cost += estimate_turn_cost(model_name, 500, 1000)

            if tool_calls:
                msgs = self._execute_tools(tool_calls, content, msgs, model_name, state)
            else:
                msgs.append({"role": "assistant", "content": content})
                self.app.post_message(StreamEndMsg(content, msgs))
                state.messages = msgs
                state.save_session()
                # ── Voice auto-play ──────────────────────
                if content and content.strip():
                    try:
                        from core.voice import tts
                        if tts.enabled:
                            tts.speak_sync(content[:500])
                    except Exception:
                        pass
                return

        self.app.post_message(StreamEndMsg("[Max iterations]", msgs))
        state.messages = msgs
        state.save_session()

    def _nonstream_loop(self, state: TUIState, msgs: list[dict], cfg_t: float, max_iter: int) -> None:
        model_name = state.model.split("/")[-1] or "unknown"
        for _ in range(max_iter):
            _sanitize_tool_call_ids(msgs)
            content, calls = state.provider.chat(msgs, state.tool_defs, cfg_t)
            state.cost += estimate_turn_cost(model_name, 500, 1000)

            if not calls:
                msgs.append({"role": "assistant", "content": content})
                self.app.post_message(StreamEndMsg(content, msgs))
                state.messages = msgs
                state.save_session()
                return
            msgs = self._execute_tools(calls, content, msgs, model_name, state)

        self.app.post_message(ResultMsg("[Max iterations]"))

    # ── Tool execution ──────────────────────────────────────
    def _execute_tools(self, tool_calls: list[Any], content: str, msgs: list[dict], model_name: str, state: TUIState) -> list[dict]:
        tc_list = _build_tc_list(tool_calls)
        msgs.append({"role": "assistant", "content": content or None, "tool_calls": tc_list})

        for tc in tool_calls:
            state.turns += 1

            if tc.name == "use_skill":
                result = core_tools.execute_with_skills(tc.name, tc.args)
                if "activated" in result and skill_manager.active:
                    msgs = [m for m in msgs if not m.get("_skill_prompt")]
                    msgs.insert(0, {"role": "system", "content": skill_manager.active.prompt, "_skill_prompt": True})
                elif "deactivated" in result:
                    msgs[:] = [m for m in msgs if not m.get("_skill_prompt")]
                msgs.append({"role": "tool", "tool_call_id": _valid_tool_call_id(tc.id), "name": tc.name, "content": result})
                state.cost += estimate_turn_cost(model_name, 200, 50)
                continue

            if tc.name not in state.tools_used:
                state.tools_used.append(tc.name)

            try:
                result = core_tools.execute_with_skills(tc.name, tc.args)
            except Exception as te:
                result = f"[Tool error: {te}]"

            state.cost += estimate_turn_cost(model_name, 200, 100)
            msgs.append({"role": "tool", "tool_call_id": _valid_tool_call_id(tc.id), "name": tc.name, "content": result})
            self.app.post_message(ToolStepMsg(tc.name, "ok", result[:200]))

        return msgs

    # ── Agent (AutonomousAgent) ─────────────────────────────
    def _run_direct_tool(self, state: TUIState, task: str, decision: RoutingDecision) -> None:
        try:
            from core.uil.executors import run_direct_tool
            summary = run_direct_tool(decision, task)
            state.messages.append({"role": "assistant", "content": summary})
            state.save_session()
            self.app.post_message(ResultMsg(summary))
        except Exception as e:
            self.app.post_message(ErrorMsg(str(e)))
        finally:
            self.app.call_from_thread(self._finish)

    def _run_agent(self, state: TUIState, task: str) -> None:
        try:
            from core.agents.agent import AutonomousAgent
            agent = AutonomousAgent(state.provider, state.tool_defs, state.cfg, {
                "model": state.model, "cost": state.cost, "turns": state.turns,
            })
            steps, summary = agent.run(task)
            state.cost = agent.state.get("cost", state.cost)
            state.turns = agent.state.get("turns", state.turns)
            state.messages.append({"role": "assistant", "content": summary})
            state.save_session()

            # Verify agent output
            self._verify_output(summary, state)
            self.app.post_message(ResultMsg(summary))
        except Exception as e:
            self.app.post_message(ErrorMsg(str(e)))
        finally:
            self.app.call_from_thread(self._finish)

    # ── Expert Team ─────────────────────────────────────────
    def _run_expert_team(self, state: TUIState, task: str) -> None:
        try:
            from core.agents.expert import ExpertTeam
            team = ExpertTeam(state.provider, state.tool_defs, state.cfg, {
                "model": state.model, "cost": state.cost, "turns": state.turns,
            })
            summary = team.run(task)
            state.messages.append({"role": "assistant", "content": summary})
            state.save_session()

            # Verify expert team output
            self._verify_output(summary, state)
            self.app.post_message(ResultMsg(summary))
        except Exception as e:
            self.app.post_message(ErrorMsg(str(e)))
        finally:
            self.app.call_from_thread(self._finish)

    # ── Verification helper ─────────────────────────────────
    def _verify_output(self, summary: str, state) -> None:
        """Run UIL verification on agent/expert output and post warnings."""
        try:
            from core.uil.verifier import get_verifier
            from core.uil.contract import (
                ClassificationResult, ExecutionResult, TaskType, Domain,
            )
            # Use a generic classification for verification
            cls = ClassificationResult(
                task_type=TaskType.CODE_WRITE,
                domain=Domain.CODE,
                confidence=0.8,
                complexity=0.5,
                reasoning="TUI output verification",
            )
            verifier = get_verifier(cls)
            ctx = {}
            if "<!DOCTYPE html" in summary or "<html" in summary[:200]:
                ctx["html_content"] = summary
            elif "rm " in summary or "wget " in summary or "chmod " in summary:
                ctx["bash_commands"] = summary
            else:
                ctx["code_content"] = summary
            report = verifier.verify(
                ExecutionResult(success=True, summary=summary),
                classification=cls, context=ctx or None,
            )
            if report.criticals:
                msg = "🔴 " + "\n".join(f.message[:80] for f in report.criticals[:3])
                self.app.call_from_thread(
                    self.screen._log_message,
                    "system",
                    f"Verification CRITICAL:\n{msg}",
                )
            elif report.errors:
                self.app.call_from_thread(
                    self.screen._log_message,
                    "system",
                    f"⚠️ Verification: {len(report.errors)} issue(s)",
                )
        except Exception:
            pass  # verification is advisory in TUI
