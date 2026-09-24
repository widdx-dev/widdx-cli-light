"""TUI Commands — slash command handling for the TUI.

Each command is a method on CommandHandler.  The handler is attached
to the app and calls back into it for UI operations.
"""

from core.memory import MemoryStore
from core.skills import skill_manager
from core.diagnostics import audit_silent_errors
import os


class CommandHandler:
    """Processes slash (/), exclamation (!), and normal input."""

    def __init__(self, app_ref):
        self.app = app_ref

    async def handle(self, text: str, state):
        text = self._auto_correct(text)
        text = self._process_mentions(text, state)
        self._track_patterns(text, state)

        if text.startswith("/"):
            await self._cmd(text, state)
        elif text.startswith("!"):
            self._do_skill(text[1:], state)
        else:
            return False  # not a command — let chat engine handle it
        return True

    # ── Slash commands ──────────────────────────────────────
    async def _cmd(self, text: str, state):
        parts = text.split(None, 1)
        cmd = parts[0].lower()

        if cmd in ("/exit", "/quit"):
            self.app.app.exit()
        elif cmd == "/help":
            await self.app._do_action("help")
        elif cmd == "/tools":
            await self.app._do_action("tools")
        elif cmd == "/skills":
            await self.app._do_action("skills")
        elif cmd == "/history":
            await self.app._do_action("history")
        elif cmd == "/memories":
            await self.app._do_action("memories")
        elif cmd == "/sessions":
            await self.app._do_action("sessions")
        elif cmd == "/settings":
            await self.app._do_action("settings")
        elif cmd == "/export":
            await self.app._do_action("export")
        elif cmd == "/save":
            state.save_session()
            self.app._log_message("system", "💾 Session saved")
        elif cmd == "/clear":
            if len(parts) > 1:
                # /clear session → wipe session data
                state.clear_session()
                self.app._log_message("system", "🧹 Session cleared")
            else:
                # /clear → clear chat log only
                self.app._chat_log.clear()
                self.app._show_chat()

        # ── Model ─────────────────────────────────────────
        elif cmd == "/model":
            from core.providers.providers import get_available_models
            available = get_available_models(state.provider.name, state.provider.base_url, True)
            if available:
                self.app._log_message("system", f"Models: {', '.join(available[:10])}")
            else:
                self.app._log_message("system", "No models available for current provider")

        # ── Remember / Memories ───────────────────────────
        elif cmd == "/remember" and len(parts) > 1:
            fact = parts[1]
            mem = MemoryStore()
            mem.save(f"note-{len(fact[:20])}", fact, {"type": "feedback"})
            self.app._log_message("system", f"✓ Remembered: {fact[:80]}")
            self.app._show_chat()

        # ── Debug ─────────────────────────────────────────
        elif cmd == "/debug":
            r = audit_silent_errors()
            self.app._log_message("system", f"🔍 Silent errors: {r['counts']}")

        # ── Doctor ────────────────────────────────────────
        elif cmd == "/doctor":
            await self.app._do_doctor()

        elif cmd == "/branch":
            from core.project.state import list_branches, get_current_branch, create_branch
            sub = parts[1].split() if len(parts) > 1 else []
            action = sub[0] if sub else "list"
            if action == "list":
                current = get_current_branch()
                for b in list_branches():
                    marker = " *" if b == current else ""
                    self.app._log_message("system", f"  {b}{marker}")
            elif action == "create" and len(sub) > 1:
                name = sub[1]
                if create_branch(name):
                    self.app._log_message("system", f"🌿 Branch '{name}' created")
                    try:
                        from tui.widgets.header import HeaderWidget
                        self.app.query_one(HeaderWidget).refresh_branches(name)
                    except Exception:
                        pass
                else:
                    self.app._log_message("system", f"Branch '{name}' already exists")
            elif action == "switch" and len(sub) > 1:
                name = sub[1]
                if not self.app._switch_session_branch(name):
                    pass
            else:
                self.app._log_message("system", "Usage: /branch list|create|switch")

        elif cmd == "/theme":
            from core.config.settings import load, save
            cfg = load()
            current = str(cfg.get("cli_theme", "dark")).lower()
            new = parts[1].strip().lower() if len(parts) > 1 else ("light" if current == "dark" else "dark")
            if new not in ("dark", "light"):
                self.app._log_message("system", "Usage: /theme [dark|light]")
            else:
                cfg["cli_theme"] = new
                save(cfg)
                state.cfg = cfg
                applied = self.app._apply_theme(cfg)
                self.app._log_message("system", f"🎨 Theme set to {applied}")
                self.app._show_toast(f"Theme: {applied}")

        elif cmd == "/version":
            self.app._log_message("system", "WIDDX Nexus v3.0.0 — By MUHAMMAD MUSLIH (widdx.com) 🇵🇸")

        # ── Search messages ───────────────────────────────
        elif cmd == "/search" and len(parts) > 1:
            query = parts[1].strip().lower()
            results = []
            for i, m in enumerate(state.messages):
                c = (m.get("content") or "").lower()
                if query in c:
                    results.append(f"[{i+1}] {m.get('role','?')}: {c[:100]}...")
            if results:
                self.app._log_message("system", f"🔍 {len(results)} match(es):")
                for result_item in results[:10]:
                    self.app._log_message("system", result_item)
            else:
                self.app._log_message("system", f"🔍 No matches for '{query}'")

        # ── Voice / TTS ────────────────────────────────────
        elif cmd == "/voice":
            from core.voice import tts
            voice_sub = parts[1].strip() if len(parts) > 1 else ""

            if voice_sub == "on" or voice_sub == "enable":
                tts.enabled = True
                self.app._log_message("system", "🔊 Voice enabled — AI will speak responses")

            elif voice_sub == "off" or voice_sub == "disable":
                tts.enabled = False
                self.app._log_message("system", "🔇 Voice disabled")

            elif voice_sub == "status" or not voice_sub:
                self.app._log_message("system", tts.status)

            elif voice_sub.startswith("say "):
                text = voice_sub[4:].strip()
                if text:
                    voice = tts.auto_voice(text)
                    self.app._log_message("system", f"🔊 Speaking ({voice})...")
                    path = tts.speak_sync(text)
                    if path:
                        self.app._log_message("system", f"✅ Audio saved: {path}")
                    else:
                        self.app._log_message("system", "❌ TTS failed")

            elif voice_sub == "voices" or voice_sub == "list":
                self.app._log_message("system", "🔊 Fetching voice list...")
                voices = tts.list_voices()[:20]
                for v in voices:
                    self.app._log_message("system", f"  {v['name']} — {v['locale']} ({v['gender']})")
                self.app._log_message("system", f"  ... and {tts.list_voices().__len__() - 20} more")

            elif voice_sub.startswith("voice "):
                new_voice = voice_sub[6:].strip()
                tts.voice = new_voice
                self.app._log_message("system", f"🔊 Voice set to {new_voice}")

            elif voice_sub.startswith("speed "):
                speed = voice_sub[6:].strip()
                tts.set_speed(speed)
                self.app._log_message("system", f"🔊 Speed set to {speed}")

            else:
                self.app._log_message("system",
                    "Usage: /voice [on|off|status|say <text>|voices|voice <name>|speed <rate>]"
                )

        # ── Sub-Agents ────────────────────────────────────
        elif cmd == "/agents":
            from core.delegation import DelegationManager
            dlg = DelegationManager()
            agents = dlg.list_agents()
            if not agents:
                self.app._log_message("system", "🤖 No sub-agents.")
            else:
                running = [a for a in agents if a.status.value == "running"]
                if running:
                    self.app._log_message("system", f"🔄 {len(running)} running:")
                for a in agents[:10]:
                    icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌", "cancelled": "🚫"}.get(a.status.value, "❓")
                    self.app._log_message("system",
                        f"  {icon} {a.task_id[:8]} — {a.task[:50]}"
                    )
                    if a.status.value == "done":
                        self.app._log_message("system",
                            f"     {a.steps} steps, {a.elapsed_seconds:.1f}s"
                        )
                    elif a.status.value == "failed" and a.error:
                        self.app._log_message("system", f"     Error: {a.error[:100]}")

        # ── Gateway / Multi-Channel ──────────────────────
        elif cmd == "/gateway":
            from core.gateway import GatewayCore
            gw_sub = parts[1].strip() if len(parts) > 1 else ""

            if gw_sub == "start" or gw_sub == "all":
                gateway = GatewayCore()

                def _gateway_handler(msg) -> str:
                    """Handle incoming gateway messages through the WIDDX engine."""
                    try:
                        content, _ = state.provider.chat(
                            [{"role": "user", "content": msg.text}],
                            state.tool_defs,
                            state.cfg.get("temperature", 0.7),
                        )
                        return content or "[done]"
                    except Exception as e:
                        return f"⚠️ Error: {e}"

                gateway.set_handler(_gateway_handler)
                gateway.start_platform("telegram")
                gateway.start_platform("discord")
                self._gateway = gateway
                self.app._log_message("system", "✅ Gateway started: Telegram + Discord")
                self.app._log_message("system", "ℹ️  Set TELEGRAM_BOT_TOKEN and DISCORD_BOT_TOKEN in .env")

            elif gw_sub == "status" or not gw_sub:
                env_telegram = "✅ SET" if os.environ.get("TELEGRAM_BOT_TOKEN") else "❌ NOT SET"
                env_discord = "✅ SET" if os.environ.get("DISCORD_BOT_TOKEN") else "❌ NOT SET"
                self.app._log_message("system", "🤖 Gateway Status:")
                self.app._log_message("system", f"  📱 Telegram: {env_telegram}")
                self.app._log_message("system", f"  💬 Discord:  {env_discord}")
                gateway_active = hasattr(self, '_gateway') and self._gateway is not None
                self.app._log_message("system", f"  🟢 Active: {'Yes' if gateway_active else 'No'}")

            else:
                self.app._log_message("system", "Usage: /gateway [start|status]")

        # ── Background Tasks ──────────────────────────────
        elif cmd == "/tasks":
            from core.background import background
            bg_tasks = background.list_tasks()
            bg_running = [t for t in bg_tasks if t.status.value == "running"]
            if bg_running:
                self.app._log_message("system", f"🔄 {len(bg_running)} running:")
                for t in bg_running[:5]:
                    self.app._log_message("system", f"  {t.summary}")
            if not bg_tasks:
                self.app._log_message("system", "📭 No background tasks.")
            elif not bg_running:
                bg_recent = bg_tasks[:5]
                self.app._log_message("system", f"📋 Last {len(bg_recent)} tasks:")
                for t in bg_recent:
                    self.app._log_message("system", f"  {t.summary}")
                    if t.result:
                        self.app._log_message("system", f"     Result: {t.result[:100]}")
                    if t.error:
                        self.app._log_message("system", f"     Error: {t.error[:100]}")

        # ── Cron Jobs ─────────────────────────────────────
        elif cmd == "/cron":
            from core.cron.scheduler import CronScheduler
            sched = CronScheduler()

            cron_sub = parts[1].strip() if len(parts) > 1 else ""

            if cron_sub == "list" or not cron_sub:
                jobs = sched.list_jobs()
                if not jobs:
                    self.app._log_message("system", "📭 No cron jobs scheduled.")
                else:
                    self.app._log_message("system", "📅 Cron Jobs:")
                    for j in jobs:
                        status_icon = "✅" if j.status.value == "active" else "⏸️"
                        self.app._log_message("system",
                            f"  {status_icon} [{j.id[:8]}] {j.prompt}"
                        )
                        self.app._log_message("system",
                            f"     Schedule: {j.schedule}  Next: {(j.next_run or 'N/A')[:19]}"
                        )
                        self.app._log_message("system",
                            f"     Runs: {j.run_count}  Last: {(j.last_run or 'N/A')[:19]}"
                        )

            elif cron_sub.startswith("add "):
                import shlex
                try:
                    rest = cron_sub[4:].strip()
                    sched_parts = shlex.split(rest)
                    if len(sched_parts) >= 2:
                        schedule = sched_parts[0]
                        prompt = " ".join(sched_parts[1:])
                        job_id = sched.create_job(schedule, prompt)
                        self.app._log_message("system",
                            f"✅ Cron job created: {job_id[:8]} — {prompt} (every {schedule})"
                        )
                    else:
                        self.app._log_message("system",
                            "Usage: /cron add <schedule> <prompt>"
                        )
                except Exception as e:
                    self.app._log_message("system", f"❌ {e}")

            elif cron_sub.startswith("rm ") or cron_sub.startswith("remove "):
                job_id = cron_sub.split(maxsplit=1)[1].strip()
                if sched.remove_job(job_id):
                    self.app._log_message("system", f"✅ Removed job: {job_id[:8]}")
                else:
                    self.app._log_message("system", f"❌ Job not found: {job_id[:8]}")

            elif cron_sub.startswith("pause "):
                job_id = cron_sub.split(maxsplit=1)[1].strip()
                if sched.pause_job(job_id):
                    self.app._log_message("system", f"⏸️ Paused job: {job_id[:8]}")
                else:
                    self.app._log_message("system", f"❌ Job not found: {job_id[:8]}")

            elif cron_sub.startswith("resume "):
                job_id = cron_sub.split(maxsplit=1)[1].strip()
                if sched.resume_job(job_id):
                    self.app._log_message("system", f"▶️ Resumed job: {job_id[:8]}")
                else:
                    self.app._log_message("system", f"❌ Job not found: {job_id[:8]}")

            else:
                self.app._log_message("system",
                    "Usage: /cron [list|add|rm|pause|resume]"
                )

        # ── Unknown ───────────────────────────────────────
        else:
            self.app._log_message("system", f"Unknown: {cmd}. Try /help")

    # ── Skills ──────────────────────────────────────────────
    def _do_skill(self, name: str, state):
        skill_name = name.strip().lower()
        if skill_name == "off":
            if skill_manager.active:
                old = skill_manager.active.name
                skill_manager.deactivate()
                self.app._log_message("system", f"Skill '{old}' deactivated")
            return

        ok = skill_manager.toggle(skill_name)
        if ok:
            active = skill_manager.active
            if active:
                icon = active.icon + " " if active.icon else ""
                self.app._log_message("system", f"{icon}Skill '{active.name}' activated")
                state.messages = [m for m in state.messages if not m.get("_skill_prompt")]
                state.messages.insert(0, {"role": "system", "content": active.prompt, "_skill_prompt": True})
                state._rebuild_tool_defs()
            else:
                state.messages = [m for m in state.messages if not m.get("_skill_prompt")]
                self.app._log_message("system", "Skill deactivated")
                state._rebuild_tool_defs()
        else:
            self.app._log_message("system", f"Unknown skill: '{skill_name}'")

    # ── Auto-correct ───────────────────────────────────────
    def _auto_correct(self, text: str) -> str:
        corrections = {
            "/clea": "/clear", "/clera": "/clear", "/hepl": "/help",
            "/hel": "/help", "/sav": "/save", "/doctro": "/doctor",
            "/searhc": "/search", "/serach": "/search",
        }
        for typo, correction in corrections.items():
            if text.startswith(typo):
                self.app._show_toast(f"✏️ Auto-corrected: {typo} → {correction}", "info", 2)
                return text.replace(typo, correction, 1)
        return text

    def _process_mentions(self, text: str, state) -> str:
        import re
        msgs = state.messages
        if not msgs:
            return text
        mentions = re.findall(r'@(\d+)', text)
        for mention in mentions:
            try:
                idx = int(mention) - 1
                if 0 <= idx < len(msgs):
                    m = msgs[idx]
                    text = text.replace(f"@{mention}", f"[Referring to #{mention}: {m.get('role','?')} - {(m.get('content') or '')[:200]}...]")
            except ValueError:
                pass
        return text

    def _track_patterns(self, text: str, state):
        if text.startswith("/"):
            cmd = text.split()[0]
            if not hasattr(state, '_patterns'):
                state._patterns = {}
            state._patterns[cmd] = state._patterns.get(cmd, 0) + 1
