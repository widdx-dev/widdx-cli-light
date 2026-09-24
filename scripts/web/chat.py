"""Web UI — Chat handler. Uses UIL Brain for intelligent task processing.

Architecture:
  ChatHandler → UnifiedIntelligenceLayer (brain.process)
  → analyze → route → plan → execute → verify → knowledge → feedback
  → Returns ExecutionResult with summary + tool calls

Usage:
    from scripts.web.chat import ChatHandler
    handler = ChatHandler()
    response = handler.chat("hello")
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.uil.contract import ExecutionResult

logger = logging.getLogger("widdx.web.chat")

from core._path import ensure_project_root  # noqa: E402
ensure_project_root()


class ChatHandler:
    """Handles chat messages via the UIL Brain pipeline.

    The UIL Brain classifies, routes, plans, executes, verifies,
    and records every interaction — single-turn or autonomous.
    """

    def __init__(self):
        self._uil: Any = None
        self._cfg: dict = {}
        self._session_id: str | None = None
        self._init_uil()

    def new_session(self):
        """Force-create a new session, abandoning the current one."""
        self._session_id = None
        return self._create_session()

    def _create_session(self):
        """Create a new session in the database."""
        try:
            from core.database import get_db
            db = get_db()
            self._session_id = db.create_session("Web UI Session")
        except Exception:
            import uuid
            self._session_id = str(uuid.uuid4())
        return self._session_id

    def _ensure_session(self):
        """Get the current session ID (does not create new)."""
        if self._session_id:
            return self._session_id
        try:
            from core.database import get_db
            db = get_db()
            sessions = db.list_sessions(limit=1)
            if sessions:
                self._session_id = sessions[0]["id"]
            else:
                self._session_id = db.create_session("Web UI Session")
        except Exception:
            import uuid
            self._session_id = str(uuid.uuid4())
        return self._session_id

    def _save_message(self, role: str, content: str):
        """Persist a message to the database."""
        try:
            from core.database import get_db
            db = get_db()
            sid = self._ensure_session()
            db.add_message(sid, role, content)
        except Exception:
            pass  # non-critical — session persistence failure shouldn't break chat

    def _init_uil(self):
        """Initialize the UIL Brain from config + auto-setup project."""
        try:
            from core.config.settings import load as load_cfg
            from core.uil import UnifiedIntelligenceLayer

            self._cfg = load_cfg()
            self._cfg.get("provider", {})

            # ── Auto-setup: create planning docs + index project ──
            try:
                from pathlib import Path as _Path
                from core.project_tracker import ensure_docs, build_context_block
                cwd = _Path.cwd()
                ensure_docs(cwd)
                # Build project context for injection into system prompt
                self._project_context = build_context_block(cwd) or ""
            except Exception:
                self._project_context = ""

            # ── Web UI: non-blocking permission mode ──
            # The Web UI has no stdin for interactive Rich prompts.
            # Safe tools auto-allow, dangerous tools auto-allow (logged).
            # Users can change levels via Settings UI; no blocking prompts.
            try:
                from core.permissions import enable_web_mode
                enable_web_mode()
            except Exception:
                pass

            # Create provider from config
            from core.providers.providers import create_provider
            provider = create_provider(self._cfg)

            # Initialize UIL Brain with provider
            self._uil = UnifiedIntelligenceLayer(
                provider=provider,
                tool_defs=self._get_tool_defs(),
            )
            logger.info(
                "ChatHandler: UIL ready — provider=%s model=%s",
                provider.name, provider.model,
            )
        except Exception as e:
            logger.error("ChatHandler init: %s", e)

    def _get_tool_defs(self) -> list[dict]:
        """Get tool definitions from the core tools module."""
        try:
            from core import tools
            return list(tools.TOOL_DEFINITIONS)
        except Exception:
            return []

    def _clean_content(self, content: str) -> str:
        """Strip thinking tags and internal reasoning from content."""
        clean = content
        for tag in ("[thinking]", "[/thinking]", "<thinking>", "</thinking>"):
            clean = clean.replace(tag, "")

        import re
        marker_pat = (
            r'(?:^|\n)\s*(?:'
            r'Response\s+Generation\s*:|'
            r'Response\s+strategy\s*:|'
            r'Final\s+Response\s*:|'
            r'Final\s+Answer\s*:|'
            r'Output\s*:|'
            r'Answer\s*:'
            r')\s*\n*'
        )
        split_result = re.split(marker_pat, clean, flags=re.IGNORECASE)
        if len(split_result) > 1:
            clean = split_result[-1].strip()
        else:
            lines = clean.split('\n')
            kept = []
            found_final = False
            for line in lines:
                s = line.strip()
                if not s:
                    if not found_final:
                        continue
                    kept.append(line)
                    continue
                if not found_final:
                    if re.match(r'^Thinking\.?\s*$', s, re.IGNORECASE):
                        continue
                    if re.match(r'^\d+\.\s+\*\*', s):
                        continue
                    if re.match(r'^[\*\-]\s{2,}\w+', s):
                        continue
                    if re.match(r"^(Let(?:'s)?\s|I\s(?:should|need|can|will|must|think)|"
                                r"My\s|The\s(user|assistant|prompt|model)|"
                                r"Wait[,;]|Actually[,;]|Ah[,;]|"
                                r"Response\s+strategy|Strategy[:;])",
                                s, re.IGNORECASE):
                        continue
                    found_final = True
                kept.append(line)
            if found_final:
                clean = '\n'.join(kept).strip()
            else:
                clean = '\n'.join(line for line in lines if line.strip()).strip()
        return clean

    def _build_context(self, message: str, history: list[dict]) -> tuple[list[dict], list[dict[str, str]]]:
        """Inject context messages into history for UIL Brain processing.

        Adds working directory, project context, ADR, StateManager, DecisionLayer,
        learning patterns, strategy memory, preferences, knowledge graph, and
        learned improvements as system messages.

        Returns:
            Tuple of (enriched_history, suggested_skills)
        """
        uil_history = list(history or [])
        # Strip any previously injected context markers from incoming history
        uil_history = [
            m for m in uil_history
            if not m.get('_cwd_context')
            and not m.get('_project_context')
        ]
        suggested_skills: list[dict[str, str]] = []

        # ── Working directory context ──────────────────
        from pathlib import Path as _P
        cwd = str(_P.cwd().resolve())
        uil_history.insert(0, {
            "role": "system",
            "content": (
                f"<working_directory>\n"
                f"  You are working in: {cwd}\n"
                f"  ALL files you create MUST go in this directory.\n"
                f"  Use relative paths. This is the project root.\n"
                f"  Do NOT use /tmp, /workspace, or any Linux paths.\n"
                f"</working_directory>"
            ),
            "_cwd_context": True,
        })

        # ── Project context ──
        if self._project_context:
            uil_history.insert(0, {
                "role": "system",
                "content": (
                    "<project_context>\n"
                    f"{self._project_context}\n"
                    "Use this context to understand the project goals, "
                    "architecture, current tasks, and roadmap.\n"
                    "Update these docs via the project_tracker when you "
                    "complete tasks or make design decisions.\n"
                    "</project_context>"
                ),
                "_project_context": True,
            })

        # ── Context injectors: lazy-loaded with individual try/except ──
        injectors = [
            # Learned improvements (SelfImprove)
            ("core.self_improve", "get_improver", lambda imp: imp.suggest_prompt_improvements()[:5] if imp.suggest_prompt_improvements() else None,
             lambda sug: (
                 "<learned_improvements>\nBased on past errors, follow these rules:\n"
                 + "\n".join(f"- {s}" for s in sug) + "\n</learned_improvements>")),
            # Architecture Decision Records
            ("core.adr", "adr_manager", lambda mgr: mgr.get_context_for_prompt(),
             lambda ctx: f"{ctx}\n\nDO NOT suggest alternatives listed as 'Rejected' above. They were already evaluated and discarded."),
            # StateManager
            ("core.state_manager", "get_state_manager", lambda sm: sm.get_full_context(goal=message), None),
            # DecisionLayer
            ("core.decision_layer", "get_decision_layer", lambda dl: dl.get_context_for_prompt(), None),
            # Pattern Library
            ("core.learning.pattern_library", "UnifiedPatternStore", lambda ps: ps().get_context_for_prompt(query=message), None),
            # World Model strategies
            ("core.world_model", "get_world_model", lambda wm: wm.strategies.get_context_for_prompt(message), None),
            # User Preferences
            ("core.learning.pattern_extractor", "UserPreferenceLearner", lambda upl: upl().get_context_for_prompt(), None),
            # Knowledge Graph
            ("core.knowledge_graph", "get_knowledge_graph", lambda kg: kg.get_context_snippet(), None),
        ]

        for mod_name, attr_name, getter, formatter in injectors:
            try:
                mod = importlib.import_module(mod_name)
                obj = getattr(mod, attr_name)
                context = getter(obj)
                if context:
                    content = formatter(context) if formatter else context
                    uil_history.insert(0, {"role": "system", "content": content})
            except Exception:
                pass

        # ── Skill suggestions ──
        try:
            from core.skills import skill_manager, Skill
            skill_suggestions: list[Skill] = skill_manager.suggest_skills(message)
            suggested_skills = [
                {"name": s.name, "icon": s.icon, "description": s.description[:80]}
                for s in skill_suggestions[:3]
            ]
        except Exception:
            pass

        return uil_history, suggested_skills

    def chat(self, message: str, history: list[dict] | None = None) -> dict:
        """Send a message through the UIL Brain pipeline.

        Args:
            message: User message text.
            history: Previous messages list.

        Returns:
            {"content": str, "tools": list[dict], "error": str | None}
        """
        if self._uil is None:
            return {"content": "", "error": "UIL Brain not initialized"}

        try:
            # Build context via extracted method
            uil_history, suggested_skills = self._build_context(message, history or [])

            # Process through UIL Brain (pass cfg for engine feature flags)
            result, _routing = self._uil.process(
                user_input=message,
                messages=uil_history,
                cfg=self._cfg,
            )

            # Log to ActivityStore
            try:
                from core.activity import add as add_event
                add_event("message", detail=message[:80], icon="fa-user", agent="user", status="done")
                content = getattr(result, "summary", "") or ""
                if content:
                    add_event("message", detail=content[:80], icon="fa-robot", agent="widdx", status="done")
                for tc in (getattr(result, "tools_used", []) or []):
                    add_event("tool_call", detail=str(tc)[:60], icon="fa-wrench", agent="widdx", status="done")
            except Exception:
                pass

            # Extract content and tool calls from ExecutionResult
            content = getattr(result, "summary", "") or ""
            tool_calls = getattr(result, "tools_used", []) or []

            # Format tool calls for the frontend
            tools_result = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    tools_result.append(tc)
                else:
                    tools_result.append({"name": str(tc)})

            clean = self._clean_content(content)

            # ── Persist to session database ──
            self._save_message("user", message)
            if clean:
                self._save_message("assistant", clean)

            return {
                "content": clean or "",
                "tools": tools_result,
                "error": None,
                "suggested_skills": suggested_skills,
            }
        except Exception as e:
            logger.error("ChatHandler error: %s", e, exc_info=True)
            from core.utils import sanitize_error
            return {"content": "", "error": sanitize_error(str(e))}

    def chat_stream(self, message: str, history: list[dict] | None = None):
        """Generator that yields streaming events during UIL processing.

        Yields dicts with keys: type (reasoning, text, tool, tool_result, done), data

        Runs UIL processing in a background thread, yielding events as they occur.
        """
        if self._uil is None:
            yield {"type": "error", "data": "UIL Brain not initialized"}
            return

        self._save_message("user", message)

        import queue
        import threading

        event_queue: queue.Queue = queue.Queue()
        result_container: list[ExecutionResult] = []
        had_text_events = [False]

        # Reasoning debounce: accumulate chunks and flush at intervals
        _reasoning_buf: list[str] = []
        _reasoning_timer: list[threading.Timer | None] = [None]
        _reasoning_lock = threading.Lock()
        _REASONING_FLUSH_INTERVAL = 0.15  # seconds

        def _flush_reasoning():
            with _reasoning_lock:
                if _reasoning_buf:
                    text = "".join(_reasoning_buf)
                    _reasoning_buf.clear()
                    event_queue.put({"type": "reasoning", "data": text})
                _reasoning_timer[0] = None

        def _on_event(event):
            if event["type"] == "reasoning":
                with _reasoning_lock:
                    _reasoning_buf.append(event["data"])
                    if _reasoning_timer[0] is None:
                        _reasoning_timer[0] = threading.Timer(
                            _REASONING_FLUSH_INTERVAL, _flush_reasoning
                        )
                        _reasoning_timer[0].daemon = True
                        _reasoning_timer[0].start()
                return
            # Flush any pending reasoning before other events
            _flush_reasoning()
            if event["type"] == "text":
                had_text_events[0] = True
            event_queue.put(event)

        def _run():
            try:
                # Reuse _build_context for consistent context injection
                uil_history, _ = self._build_context(message, history or [])

                result, _routing = self._uil.process(
                    user_input=message,
                    messages=uil_history,
                    cfg=self._cfg,
                    on_event=_on_event,
                )
                result_container.append(result)
                event_queue.put(None)  # sentinel
            except Exception as e:
                logger.error("chat_stream error: %s", e, exc_info=True)
                from core.utils import sanitize_error
                event_queue.put({"type": "error", "data": sanitize_error(str(e))})
                event_queue.put(None)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        while True:
            event = event_queue.get()
            if event is None:
                break
            yield event

        # Yield tool events from the result (tools are only available after processing)
        if result_container:
            result = result_container[0]
            tools_used = getattr(result, "tools_used", []) or []
            for tc in tools_used:
                name = tc.get("name", str(tc)) if isinstance(tc, dict) else str(tc)
                args = tc if isinstance(tc, dict) else {}
                yield {"type": "tool", "data": {"name": name, "args": args}}

            # Always save the assistant message, even if streaming text was emitted
            content = getattr(result, "summary", "") or ""
            clean = self._clean_content(content)
            if clean:
                self._save_message("assistant", clean)
                # Only yield text if no streaming events occurred
                if not had_text_events[0]:
                    yield {"type": "text", "data": clean}
        yield {"type": "done", "data": None}

    @property
    def info(self) -> dict:
        """Return UIL/provider info."""
        if self._uil:
            provider = getattr(self._uil, "provider", None)
            if provider:
                return {
                    "name": getattr(provider, "name", "uil"),
                    "model": getattr(provider, "model", "unknown"),
                    "online": True,
                }
            return {"name": "uil", "model": "brain", "online": True}
        return {"name": "none", "model": "none", "online": False}
