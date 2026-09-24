"""CLI Commands — organized slash command processing.

Each command group is a separate method on ``CLICommands``.
The class has NO display logic — it calls back into the app for UI.
"""

from pathlib import Path
from core import tools
from core.config.keychain import prompt_key, forget_key, has_key
from core.memory import MemoryStore
from core.skills import skill_manager
from core.project import state as project_state
from core.project.git import undo_last_commit
from core.mcp.client import get_mcp_manager


class CLICommands:
    """Handles slash commands and special inputs.

    Each method receives ``(args, provider, state, messages)``.
    """

    def __init__(self, app_ref):
        self.app = app_ref  # CLIApp reference for display

    # ── Dispatch ─────────────────────────────────────────────
    def handle(self, text: str, provider, state, messages) -> bool:
        """Route command. Returns True if it was a command."""
        parts = text.split(None, 1)
        cmd = parts[0].lower()

        handlers = {
            "/exit": self.exit, "/quit": self.exit,
            "/help": self.help,
            "/clear": self.clear,
            "/tools": self.tools,
            "/skills": self.skills,
            "/history": self.history,
            "/model": self.model,
            "/provider": self.provider,
            "/save": self.save,
            "/load": self.load,
            "/export": self.export,
            "/remember": self.remember,
            "/memories": self.memories,
            "/manifest": self.manifest,
            "/reasoning": self.reasoning,
            "/debug": self.debug,
            "/doctor": self.doctor,
            "/undo": self.undo,
            "/proxy": self.proxy,
            "/sandbox": self.sandbox,
            "/mcp": self.mcp,
            "/gguf": self.gguf,
            "/branch": self.branch,
            "/version": self.version,
            "/replay": self.replay,
            "/permissions": self.permissions,
            "/apikey": self.apikey,
            "/theme": self.theme,
            "/vision": self.vision,
            # New tool commands
            "/dep-graph": self.dep_graph,
            "/search-replace": self.search_replace,
            "/semantic": self.semantic_search,
            "/rename": self.rename_symbol,
            "/docker": self.docker,
            "/db": self.db_query,
            "/api": self.api_request,
            "/pkg": self.pkg_mgr,
            "/terminal": self.terminal,
        }

        handler = handlers.get(cmd)
        if handler:
            arg = parts[1] if len(parts) > 1 else ""
            result = handler(arg, provider, state, messages)
            if isinstance(result, tuple):
                if len(result) == 3:
                    new_provider, new_state, new_messages = result
                    self.app.provider = new_provider
                    self.app.state = new_state
                    messages[:] = new_messages
                elif len(result) == 2:
                    new_provider, new_state = result
                    self.app.provider = new_provider
                    self.app.state = new_state
            return True

        # Skill activation: !name
        if text.startswith("!"):
            self._skill(text[1:].strip(), provider, state, messages)
            return True

        return False

    # ── Core Commands ────────────────────────────────────────
    def help(self, arg, p, s, msgs):
        self.app.show_system("Available commands:")
        self.app.show_system("  /help /clear /model /provider /tools /skills")
        self.app.show_system("  /history /save /load /export /remember /memories")
        self.app.show_system("  /manifest /reasoning /debug /doctor /undo")
        self.app.show_system("  /proxy /sandbox /mcp /gguf /branch /version")
        self.app.show_system("  /replay — list, replay, or verify recorded runs")
        self.app.show_system("  /permissions /apikey /theme /vision /exit")
        self.app.show_system("  /search-replace /semantic /rename /dep-graph")
        self.app.show_system("  /docker /db /api /pkg /terminal")
        self.app.show_system("  !skill_name — activate a skill  |  !off — deactivate")

    def clear(self, arg, p, s, msgs):
        """Clear screen."""
        from cli.display import console
        console.clear()
        self.app.show_header()

    def exit(self, arg, p, s, msgs):
        raise SystemExit(0)

    # ── Provider / Model ─────────────────────────────────────
    def model(self, arg, p, s, msgs):
        from core.providers.providers import get_available_models
        available = get_available_models(p.name, p.base_url, force_refresh=True)
        if available:
            self.app.show_system(f"Available models: {', '.join(available[:15])}")
        else:
            self.app.show_system(f"Current model: {p.model}")

    def provider(self, arg, p, s, msgs):
        from core.commands import handle_provider
        return handle_provider(p, s, {}, preset=arg.strip() or None)


    # ── Tools / Skills ───────────────────────────────────────
    def tools(self, arg, p, s, msgs):
        all_tools = list(tools.TOOL_DEFINITIONS)
        try:
            all_tools.extend(get_mcp_manager().get_all_tool_definitions())
        except Exception:
            pass
        rows = [[t["name"][:30], (t.get("description") or "")[:60]] for t in all_tools]
        self.app.show_table("Available Tools", ["Tool", "Description"], rows[:40])

    # ── New Tool Commands ───────────────────────────────────
    def _exec_tool(self, name: str, args: dict):
        from core.tools.dispatch import execute_with_skills
        result = execute_with_skills(name, args)
        for line in result.split("\n"):
            self.app.show_system(line)

    def search_replace(self, arg, p, s, msgs):
        if not arg:
            self.app.show_system("Usage: /search-replace <pattern> <replacement> [include]")
            return
        parts = arg.split(None, 2)
        pattern = parts[0]
        replacement = parts[1] if len(parts) > 1 else ""
        include = parts[2] if len(parts) > 2 else None
        self._exec_tool("search_replace", {"pattern": pattern, "replacement": replacement, "include": include, "preview": True})

    def semantic_search(self, arg, p, s, msgs):
        if not arg:
            self.app.show_system("Usage: /semantic <query> [include]")
            return
        parts = arg.split(None, 1)
        query = parts[0]
        include = parts[1] if len(parts) > 1 else None
        self._exec_tool("semantic_search", {"query": query, "include": include, "top_k": 10})

    def rename_symbol(self, arg, p, s, msgs):
        if not arg:
            self.app.show_system("Usage: /rename <old_name> <new_name> [include]")
            return
        parts = arg.split(None, 2)
        old_name = parts[0]
        new_name = parts[1] if len(parts) > 1 else ""
        include = parts[2] if len(parts) > 2 else None
        self._exec_tool("rename_symbol", {"symbol": old_name, "new_name": new_name, "include": include, "preview": True})

    def dep_graph(self, arg, p, s, msgs):
        include = arg.strip() or None
        self._exec_tool("dep_graph", {"include": include, "format": "text"})

    def docker(self, arg, p, s, msgs):
        if not arg:
            self._exec_tool("docker", {"action": "list"})
            return
        parts = arg.split(None, 1)
        action = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        if action in ("build", "run", "stop", "rm", "logs", "compose"):
            self.app.show_system("Use the AI chat for detailed docker operations, or /docker <action>")
            self._exec_tool("docker", {"action": action})
        else:
            self._exec_tool("docker", {"action": action, "what": rest or "containers"})

    def db_query(self, arg, p, s, msgs):
        if not arg:
            self.app.show_system("Usage: /db <query> [db_path]")
            self.app.show_system("  Or: /db tables <db_path>  |  /db describe <table> <db_path>")
            return
        parts = arg.split(None, 2)
        cmd = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        rest2 = parts[2] if len(parts) > 2 else ""
        if cmd == "tables":
            self._exec_tool("db_query", {"action": "tables", "db_path": rest or "data.db"})
        elif cmd == "describe":
            self._exec_tool("db_query", {"action": "describe", "table": rest, "db_path": rest2 or "data.db"})
        else:
            self._exec_tool("db_query", {"query": cmd, "db_path": rest or "data.db"})

    def api_request(self, arg, p, s, msgs):
        if not arg:
            self.app.show_system("Usage: /api <url> [method]")
            return
        parts = arg.split(None, 1)
        url = parts[0]
        method = parts[1].upper() if len(parts) > 1 else "GET"
        self._exec_tool("api_request", {"url": url, "method": method})

    def pkg_mgr(self, arg, p, s, msgs):
        if not arg:
            self._exec_tool("pkg_mgr", {"action": "detect"})
            return
        parts = arg.split(None, 1)
        action = parts[0]
        package = parts[1] if len(parts) > 1 else ""
        self._exec_tool("pkg_mgr", {"action": action, "package": package})

    def terminal(self, arg, p, s, msgs):
        if not arg:
            self._exec_tool("terminal", {"action": "list"})
            return
        parts = arg.split(None, 1)
        action = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        if action in ("create", "run"):
            self._exec_tool("terminal", {"action": action, "command": rest})
        elif action in ("stop", "kill", "output", "read", "send"):
            name_rest = rest.split(None, 1)
            name = name_rest[0]
            cmd = name_rest[1] if len(name_rest) > 1 else ""
            if action in ("send",):
                self._exec_tool("terminal", {"action": action, "name": name, "command": cmd})
            else:
                self._exec_tool("terminal", {"action": action, "name": name})
        else:
            self._exec_tool("terminal", {"action": action})

    def skills(self, arg, p, s, msgs):
        all_sk = skill_manager.list_all()
        rows = [[f"!{sk.name}", sk.description[:50], sk.icon or ""] for sk in all_sk]
        self.app.show_table("Skills", ["Command", "Description", "Icon"], rows)

    def _skill(self, name: str, p, s, msgs):
        if name == "off":
            if skill_manager.active:
                old = skill_manager.active.name
                skill_manager.deactivate()
                self.app.show_system(f"Skill '{old}' deactivated")
            return
        ok = skill_manager.toggle(name)
        if ok:
            active = skill_manager.active
            if active:
                icon = active.icon + " " if active.icon else ""
                self.app.show_system(f"{icon}Skill '{active.name}' activated")
                msgs[:] = [m for m in msgs if not m.get("_skill_prompt")]
                msgs.insert(0, {"role": "system", "content": active.prompt, "_skill_prompt": True})
            else:
                msgs[:] = [m for m in msgs if not m.get("_skill_prompt")]
                self.app.show_system("Skill deactivated")
        else:
            self.app.show_system(f"Unknown skill: '{name}'")

    # ── Memory / History ─────────────────────────────────────
    def history(self, arg, p, s, msgs):
        history_text = "\n".join(
            f"[{i+1}] {m.get('role','?')}: {(m.get('content') or '')[:80]}"
            for i, m in enumerate(msgs[-30:])
        )
        self.app.show_panel("Recent History", history_text)

    def save(self, arg, p, s, msgs):
        project_state.save_session(msgs, s)
        self.app.show_system("Session saved")

    def load(self, arg, p, s, msgs):
        from core.commands import handle_load
        return handle_load(p, s, msgs, arg)

    def export(self, arg, p, s, msgs):
        from core.commands import handle_export
        handle_export(msgs)

    def remember(self, arg, p, s, msgs):
        if not arg:
            self.app.show_system("Usage: /remember <fact>")
            return
        mem = MemoryStore()
        mem.save(f"note-{len(arg[:20])}", arg, {"type": "feedback"})
        self.app.show_system(f"Remembered: {arg[:80]}")

    def memories(self, arg, p, s, msgs):
        mem = MemoryStore()
        all_m = mem.search(arg) if arg else mem.list_all()
        if not all_m:
            self.app.show_system("No memories found")
            return
        rows = [[m["name"][:25], m.get("description","")[:60], m.get("type","")] for m in all_m[:30]]
        self.app.show_table("Memories", ["Name", "Fact", "Type"], rows)

    # ── Diagnostics ──────────────────────────────────────────
    def debug(self, arg, p, s, msgs):
        from core.diagnostics import audit_silent_errors
        r = audit_silent_errors()
        self.app.show_system(f"Silent errors: {r['counts']}")
        import json
        self.app.show_system(json.dumps(r['counts'], indent=2))

    def doctor(self, arg, p, s, msgs):
        import subprocess
        self.app.show_system("🩺 Running doctor checks...")
        checks = []
        try:
            r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"Git: {r.stdout.strip()[:30]}")
        except Exception:
            checks.append("Git: not found")
        try:
            r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"Node: {r.stdout.strip()[:10]}")
        except Exception:
            checks.append("Node: not found")
        try:
            r = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"Docker: {r.stdout.strip()[:30]}")
        except Exception:
            checks.append("Docker: not found")
        try:
            r = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"npm: {r.stdout.strip()[:10]}")
        except Exception:
            checks.append("npm: not found")
        try:
            r = subprocess.run(["pip", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"pip: {r.stdout.strip()[:30]}")
        except Exception:
            checks.append("pip: not found")
        try:
            r = subprocess.run(["cargo", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"Cargo: {r.stdout.strip()[:20]}")
        except Exception:
            checks.append("Cargo: not found")
        try:
            r = subprocess.run(["psql", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(f"psql: {r.stdout.strip()[:20]}")
        except Exception:
            checks.append("psql: not found")
        checks.append(f"Provider: {p.name}/{p.model}")
        checks.append(f"Memory: {MemoryStore().total()} facts")
        checks.append(f"MCP: {get_mcp_manager().server_count} servers")
        checks.append(f"Skills: {len(skill_manager.list_all())}")
        for c in checks:
            self.app.show_system(f"  • {c}")

    # ── Manifest / Reasoning ─────────────────────────────────
    def manifest(self, arg, p, s, msgs):
        """Regenerate MANIFEST.json for the project."""
        from core.project.manifest import generate_manifest
        generate_manifest()
        self.app.show_system("MANIFEST.json regenerated")

    def reasoning(self, arg, p, s, msgs):
        """Show the AI's last reasoning / thinking trace."""
        last = s.get("_last_reasoning")
        if last:
            from .display import show_reasoning  # type: ignore[attr-defined]
            show_reasoning(last)
        else:
            self.app.show_system("No reasoning from last turn")

    # ── Git / Undo ───────────────────────────────────────────
    def undo(self, arg, p, s, msgs):
        result = undo_last_commit(Path.cwd())
        self.app.show_system(result)

    # ── Proxy ────────────────────────────────────────────────
    def proxy(self, arg, p, s, msgs):
        from core.proxy import proxy_manager
        self.app.show_system(f"Proxy status: {proxy_manager.status()}")

    # ── Sandbox ──────────────────────────────────────────────
    def sandbox(self, arg, p, s, msgs):
        if arg:
            tools.configure(arg)
            self.app.show_system(f"Sandbox set to: {arg}")
        else:
            self.app.show_system("Usage: /sandbox <path>")

    # ── MCP ──────────────────────────────────────────────────
    def mcp(self, arg, p, s, msgs):
        from core.commands import handle_mcp
        handle_mcp(arg)

    # ── GGUF ─────────────────────────────────────────────────
    def gguf(self, arg, p, s, msgs):
        from core.commands import handle_gguf
        handle_gguf(arg, p, s)

    # ── Branch ───────────────────────────────────────────────
    def branch(self, arg, p, s, msgs):
        from core.project.state import list_branches, get_current_branch, set_current_branch, create_branch
        parts = arg.split()
        action = parts[0] if parts else "list"
        if action == "list":
            current = get_current_branch()
            for b in list_branches():
                prefix = "  * " if b == current else "    "
                self.app.show_system(f"{prefix}{b}")
        elif action == "create" and len(parts) > 1:
            if create_branch(parts[1]):
                self.app.show_system(f"Branch '{parts[1]}' created")
        elif action == "switch" and len(parts) > 1:
            if set_current_branch(parts[1]):
                self.app.show_system(f"Switched to '{parts[1]}'")
        else:
            self.app.show_system("Usage: /branch list|create|switch")

    # ── Theme ────────────────────────────────────────────────
    def theme(self, arg, p, s, msgs):
        from core.config.settings import load, save
        cfg = load()
        current = str(cfg.get("cli_theme", "dark")).lower()
        new = arg.strip().lower() if arg.strip() else ("light" if current == "dark" else "dark")
        if new not in ("dark", "light"):
            self.app.show_system("Usage: /theme [dark|light]")
            return
        cfg["cli_theme"] = new
        save(cfg)
        self.app.cfg = cfg
        self.app.show_system(f"Theme set to {new}")

    # ── Version ──────────────────────────────────────────────
    def version(self, arg, p, s, msgs):
        from core.commands import handle_version
        handle_version()

    # ── Replay ───────────────────────────────────────────────
    def replay(self, arg, p, s, msgs):
        from core.commands import handle_replay
        handle_replay(arg)

    # ── Permissions ──────────────────────────────────────────
    def permissions(self, arg, p, s, msgs):
        from core.commands import handle_permissions
        handle_permissions(arg)

    # ── API Key ──────────────────────────────────────────────
    def apikey(self, arg, p, s, msgs):
        parts = arg.split()
        action = parts[0] if parts else ""
        if action == "forget":
            forget_key(p.name)
            self.app.show_system(f"API key for {p.name} removed")
        elif action == "show":
            if has_key(p.name):
                self.app.show_system(f"API key is set for {p.name}")
            else:
                self.app.show_system(f"No API key set for {p.name}")
        else:
            prompt_key(p.name)
            self.app.show_system(f"API key stored for {p.name}")

    # ── Vision ─────────────────────────────────────────────────
    def vision(self, arg, p, s, msgs):
        """Configure vision/image understanding mode.

        Usage:
          /vision                 — show status
          /vision mode pipeline   — Two-Stage Pipeline (HuggingFace محلي)
          /vision mode ollama     — Ollama Vision Model (deepseek-vl2/llava)
          /vision mode deepseek   — DeepSeek Vision API
          /vision model <name>    — تعيين نموذج Ollama (مثال: deepseek-vl2)
          /vision on|off          — تفعيل/تعطيل الرؤية
        """
        from core.vision import update_config, get_status, VisionMode

        if not arg:
            status = get_status()
            mode_names = {
                VisionMode.PIPELINE: "Two-Stage Pipeline (محلي)",
                VisionMode.OLLAMA: f"Ollama ({status.get('ollama_model', '?')})",
                VisionMode.DEEPSEEK: "DeepSeek Vision API",
            }
            self.app.show_system(f"🖼️ Vision: {'مفعل' if status.get('enabled') else 'معطل'}")
            self.app.show_system(f"   الوضع: {mode_names.get(status.get('mode', ''), status.get('mode', ''))}")
            if status.get('mode') == VisionMode.OLLAMA:
                avail = "متاح ✅" if status.get('ollama_available') else "غير متاح ❌"
                self.app.show_system(f"   النموذج: {status.get('ollama_model')} ({avail})")
            self.app.show_system(f"   Pipeline: {status.get('pipeline_model')}")
            self.app.show_system("\n   /vision mode pipeline|ollama|deepseek")
            self.app.show_system("   /vision model <name>")
            self.app.show_system("   /vision on|off")
            return

        parts = arg.split(None, 1)
        cmd = parts[0].lower()
        val = parts[1] if len(parts) > 1 else ""

        if cmd == "mode" and val:
            msg = update_config("mode", val)
            self.app.show_system(msg)
        elif cmd == "model" and val:
            msg = update_config("model", val)
            self.app.show_system(msg)
        elif cmd in ("on", "off"):
            msg = update_config(cmd, "")
            self.app.show_system(msg)
        else:
            self.app.show_system("Usage: /vision mode pipeline|ollama|deepseek")
            self.app.show_system("       /vision model <model_name>")
            self.app.show_system("       /vision on|off")
