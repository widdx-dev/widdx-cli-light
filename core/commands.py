"""Command handlers for WIDDX slash commands."""
import logging


import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from rich.prompt import Prompt as RPrompt

from core.chat import print_system_msg
from rich.console import Console
logger = logging.getLogger("widdx.commands")

console = Console(highlight=False)
from rich.text import Text  # noqa: E402
from rich.table import Table  # noqa: E402
from core.providers.providers import create_provider, fetch_free_models, fetch_ollama_models  # noqa: E402
from core.config.keychain import prompt_key  # noqa: E402


def build_mcp_discover_table(discovered: list[dict], mgr=None) -> "Table":
    """Build a Rich Table for discovered MCP servers. Shared by CLI and TUI."""
    if mgr is None:
        from core.mcp.client import get_mcp_manager
        mgr = get_mcp_manager()
    table = Table(title=f"Discovered {len(discovered)} MCP servers",
                  border_style="dim", header_style="bold #f5a623")
    table.add_column("Name", style="bold #00c896")
    table.add_column("Command", style="white")
    table.add_column("Status", style="dim")
    for s in discovered:
        name = s["name"]
        exists = "✅" if mgr.get_server(name) else "⬜"
        table.add_row(name, f"{s['command']} {' '.join(s.get('args', []))[:40]}", exists)
    return table


def handle_model(provider, state):
    """Handle /model command — change AI model."""
    from core.providers.providers import get_available_models, resolve_model

    # ── Ollama: auto-discover local models ──────────────────────
    if provider.name == "ollama":
        return _handle_ollama_model(provider, state)

    available = get_available_models(provider.name, provider.base_url, force_refresh=True)
    if available:
        print_system_msg(f"Available models: {', '.join(available[:10])}")
        new = RPrompt.ask("Model name", default=available[0])
    else:
        new = RPrompt.ask("Model name", default=provider.model)

    # Auto-resolve if the chosen name is empty or doesn't exist
    resolved = resolve_model(provider.name, preferred=new if new else None,
                             base_url=provider.base_url)
    if resolved and resolved != new:
        print_system_msg(f"Auto-resolved to available model: {resolved}")
        new = resolved

    provider.model = new
    state["model"] = f"{provider.name}/{new}"
    print_system_msg(f"Model changed to {new}")
    return provider, state


def _handle_ollama_model(provider, state):
    """Let the user pick from locally-installed Ollama models."""
    from rich.table import Table
    from core.providers.providers import _TOOL_CAPABLE_PATTERNS, _REASONING_PATTERNS

    def _guess_caps(model_name: str) -> str:
        """Quick name-based capability badges (no API probe)."""
        lower = model_name.lower()
        badges = []
        has_tools = any(pat in lower for pat in _TOOL_CAPABLE_PATTERNS)
        has_reason = any(pat in lower for pat in _REASONING_PATTERNS)
        if has_tools:
            badges.append("[bold #00c896]🧰 tools[/]")
        else:
            badges.append("[dim]⚠ no-tools[/]")
        if has_reason:
            badges.append("[bold #f5a623]🧠 thinking[/]")
        return " ".join(badges) if badges else ""

    models = fetch_ollama_models(base_url=provider.base_url, force_refresh=True)
    if not models:
        print_system_msg("⚠️  No Ollama models found — is 'ollama serve' running?")
        new = RPrompt.ask("Model name (manual)", default=provider.model)
        provider.model = new
        state["model"] = f"ollama/{new}"
        print_system_msg(f"Model changed to {new}")
        return provider, state

    # Display model table
    table = Table(title=f"Installed Ollama Models ({len(models)})",
                  border_style="dim", header_style="bold #00c896")
    table.add_column("#", style="dim", width=4)
    table.add_column("Model", style="bold white")
    table.add_column("Size", style="#f5a623")
    table.add_column("Capabilities", style="white")
    for i, m in enumerate(models, 1):
        size_str = f"{m['size'] / 1e9:.1f} GB" if m["size"] > 1e9 else f"{m['size'] / 1e6:.0f} MB"
        caps = _guess_caps(m["name"])
        table.add_row(str(i), m["name"], size_str, caps)
    console.print(table)

    # Let user pick by number or name
    choice = RPrompt.ask(
        "Pick model (# or name)",
        default=provider.model or models[0]["name"],
    )
    # If user typed a number, map to model name
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            choice = models[idx]["name"]
    except ValueError:
        pass  # user typed a name directly

    provider.model = choice
    state["model"] = f"ollama/{choice}"
    caps = _guess_caps(choice)
    print_system_msg(f"Model changed to {choice} {caps}")
    return provider, state


def handle_provider(provider, state, cfg, preset: str | None = None):
    """Handle /provider command — switch provider type.

    If ``preset`` is given (e.g. from /provider opencode-zen) the interactive
    prompt is skipped and the preset is used directly.
    """
    print_system_msg(f"Current provider: {provider.name}")
    if preset:
        new_p = preset
    else:
        new_p = RPrompt.ask(
            "Provider (from config / opencode-zen / ollama / openai / deepseek)",
            default=provider.name,
        )
    if new_p != provider.name:
        if new_p == "openai":
            url = RPrompt.ask("Base URL", default="https://api.openai.com/v1")
            prompt_key(new_p)  # stores key in env
            provider = create_provider({
                "provider": {"name": "openai", "base_url": url}
            })
        elif new_p == "opencode-zen":
            # Auto-detect best free model
            free_list = fetch_free_models()
            model = free_list[0] if free_list else "deepseek-v4-flash-free"
            print_system_msg(f"✨ Auto-selected: {model} (from {len(free_list)} free model(s))")
            provider = create_provider({"provider": {"name": "opencode-zen", "model": model}})
        elif new_p == "deepseek":
            prompt_key(new_p)
            provider = create_provider({
                "provider": {"name": "deepseek", "base_url": "https://api.deepseek.com"}
            })
        elif new_p == "ollama":
            url = RPrompt.ask("Ollama URL", default="http://localhost:11434")
            # Auto-discover installed models
            models = fetch_ollama_models(base_url=url, force_refresh=True)
            if models:
                from rich.table import Table
                table = Table(title=f"Installed Ollama Models ({len(models)})",
                              border_style="dim", header_style="bold #00c896")
                table.add_column("#", style="dim", width=4)
                table.add_column("Model", style="bold white")
                table.add_column("Size", style="#f5a623")
                for i, m in enumerate(models, 1):
                    size_str = f"{m['size'] / 1e9:.1f} GB" if m["size"] > 1e9 else f"{m['size'] / 1e6:.0f} MB"
                    table.add_row(str(i), m["name"], size_str)
                console.print(table)
                choice = RPrompt.ask("Pick model (# or name)", default=models[0]["name"])
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(models):
                        choice = models[idx]["name"]
                except ValueError:
                    pass
                model = choice
            else:
                print_system_msg("⚠️  No Ollama models found — is 'ollama serve' running?")
                model = RPrompt.ask("Model name (manual)", default="")
            provider = create_provider({
                "provider": {"name": "ollama", "model": model, "base_url": url}
            })
        else:
            print_system_msg(f"Unknown provider '{new_p}'. Keeping {provider.name}")
            return provider, state
        state["model"] = f"{provider.name}/{provider.model}"
        print_system_msg(f"Provider changed to {provider.name}")
    return provider, state


def handle_sandbox(tools):
    """Handle /sandbox command — set safe write directory."""
    from pathlib import Path
    path = RPrompt.ask("Path", default=".")
    p = Path(path).resolve()
    tools.configure(str(p))
    print_system_msg(f"Sandbox set to: {p}")
    return str(p)


def _parse_mcp_sub(raw_input: str) -> tuple[str, str]:
    """Parse /mcp sub-command from the raw user input.

    Returns (action, rest) where action is one of:
      "list", "discover", "add", "remove", or "" for default.
    """
    parts = raw_input.strip().split(None, 2)
    if len(parts) < 2:
        return ("list", "")
    cmd = parts[1].lower()
    rest = parts[2] if len(parts) > 2 else ""
    if cmd == "discover":
        return ("discover", "")
    elif cmd == "add" and rest:
        return ("add", rest)
    elif cmd == "remove" and rest:
        return ("remove", rest)
    return ("list", "")


def handle_mcp(user_input: str = ""):
    """Handle /mcp command — manage MCP servers.

    Usage:
      /mcp              — list servers and tools
      /mcp discover     — auto-discover servers from system
      /mcp add name cmd [args...] — add a new server
      /mcp remove name  — remove a server
    """
    from core.mcp.client import get_mcp_manager, discover_mcp_servers
    from rich.table import Table

    action, rest = _parse_mcp_sub(user_input)
    mgr = get_mcp_manager()

    if action == "discover":
        discovered = discover_mcp_servers(force_refresh=True)
        if not discovered:
            print_system_msg("No MCP servers discovered.")
            return
        console.print(build_mcp_discover_table(discovered, mgr))
        print_system_msg("Use /mcp add <name> <command> [args] to add a server")
        return

    if action == "add":
        parts = rest.split(None, 1)
        if len(parts) < 2:
            print_system_msg("Usage: /mcp add <name> <command> [args...]")
            return
        srv_name, cmd_rest = parts[0], parts[1]
        cmd_parts = cmd_rest.split()
        srv_cmd = cmd_parts[0]
        srv_args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        ok = mgr.add_server(srv_name, srv_cmd, srv_args)
        if ok:
            conn = mgr.get_server(srv_name)
            tools_count = len(conn.get_tool_definitions()) if conn else 0
            print_system_msg(f"MCP server '{srv_name}' added ({tools_count} tools)")
        else:
            conn = mgr.get_server(srv_name)
            err = conn.error if conn else "unknown"
            print_system_msg(f"Failed to add '{srv_name}': {err}")
        return

    if action == "remove":
        srv_name = rest.strip()
        if not srv_name:
            print_system_msg("Usage: /mcp remove <name>")
            return
        mgr.remove_server(srv_name)
        print_system_msg(f"MCP server '{srv_name}' removed")
        return

    # Default: show current servers
    mgr.start()
    servers = mgr.get_servers()

    if not servers:
        print_system_msg("No MCP servers configured. Use '!mcp discover' to find available ones.")
        return

    for conn in servers:
        if conn.is_connected:
            status = "✅ connected"
        elif conn._proc is None:
            status = "⏸️  pending (lazy)"
        else:
            status = f"❌ {conn.error or 'disconnected'}"
        tools_list = conn.get_tool_definitions()
        table = Table(title=f"MCP Server: {conn.name} [{status}]",
                      border_style="dim", header_style="bold #f5a623")
        table.add_column("Tool", style="bold #00c896")
        table.add_column("Description", style="white")
        for td in tools_list:
            desc = td.get("description", "").replace(f"[MCP {conn.name}] ", "")
            table.add_row(td["name"], desc)
        console.print(table)
    console.print()
    print_system_msg("Sub-commands: /mcp discover, /mcp add <name> <cmd> [args], /mcp remove <name>")


def handle_agent(_state):
    """Handle /agent command — Expert Team is now always active."""
    print_system_msg("Expert Team is always active — type your task and it will be handled automatically")
    return _state


def handle_load(provider, state, messages, args: str):
    """Handle /load command — load session from another project directory."""
    from pathlib import Path
    from core.project.state import load_session

    path = args.strip() if args else ""
    if not path:
        path = RPrompt.ask("Project path", default=".")
    p = Path(path).resolve()
    if not p.is_dir():
        print_system_msg(f"Directory not found: {p}")
        return provider, state, messages

    session = load_session(p)
    if not session:
        print_system_msg(f"No session found in {p}")
        return provider, state, messages

    new_messages = session.get("messages", [])
    new_state_data = session.get("state", {})
    new_state = dict(state)
    new_state["cost"] = new_state_data.get("cost", 0.0)
    new_state["turns"] = new_state_data.get("turns", 0)
    if new_state_data.get("model"):
        new_state["model"] = new_state_data["model"]

    msg_count = len(new_messages)
    print_system_msg(f"Loaded session from {p} ({msg_count} messages, ${new_state['cost']:.4f}, {new_state['turns']} turns)")
    return provider, new_state, new_messages


def handle_undo():
    """Handle /undo command — undo last WIDDX commit."""
    from pathlib import Path
    from core.project.git import undo_last_commit
    msg = undo_last_commit(Path().resolve())
    print_system_msg(msg)
    return msg


def handle_doctor():
    """Run a system health check and display results."""
    from rich.table import Table
    from core.mcp.client import get_mcp_manager

    table = Table(title="WIDDX System Health",
                  border_style="dim", header_style="bold #f5a623")
    table.add_column("Check", style="bold #00c896")
    table.add_column("Status", style="white")
    table.add_column("Detail", style="dim")

    checks = []

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 10)
    checks.append(("Python", "✅" if ok else "❌", f"{py_ver} (need >= 3.10)"))

    # Git
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        git_ver = r.stdout.strip() if r.returncode == 0 else "not found"
        checks.append(("Git", "✅" if r.returncode == 0 else "❌", git_ver[:40]))
    except Exception:
        checks.append(("Git", "❌", "not found"))

    # Node.js
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        node_ver = r.stdout.strip() if r.returncode == 0 else "not found"
        checks.append(("Node.js", "✅" if r.returncode == 0 else "❌", node_ver))
    except Exception:
        checks.append(("Node.js", "❌", "not found"))

    # uvx (needed for fetch + sqlite MCP)
    try:
        r = subprocess.run(["uvx", "--version"], capture_output=True, text=True, timeout=5)
        uvx_ver = r.stdout.strip()[:30] if r.returncode == 0 else "not found"
        checks.append(("uvx", "✅" if r.returncode == 0 else "❌", uvx_ver))
    except Exception:
        checks.append(("uvx", "❌", "not found (pip install uv)"))

    # Docker
    try:
        r = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
        docker_ver = r.stdout.strip()[:40] if r.returncode == 0 else "not found"
        checks.append(("Docker", "✅" if r.returncode == 0 else "❌", docker_ver))
    except Exception:
        checks.append(("Docker", "❌", "not found"))

    # npm
    try:
        r = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=5)
        npm_ver = r.stdout.strip()[:20] if r.returncode == 0 else "not found"
        checks.append(("npm", "✅" if r.returncode == 0 else "❌", npm_ver))
    except Exception:
        checks.append(("npm", "❌", "not found"))

    # pip
    try:
        r = subprocess.run(["pip", "--version"], capture_output=True, text=True, timeout=5)
        pip_ver = r.stdout.strip()[:30] if r.returncode == 0 else "not found"
        checks.append(("pip", "✅" if r.returncode == 0 else "❌", pip_ver))
    except Exception:
        checks.append(("pip", "❌", "not found"))

    # Cargo
    try:
        r = subprocess.run(["cargo", "--version"], capture_output=True, text=True, timeout=5)
        cargo_ver = r.stdout.strip()[:20] if r.returncode == 0 else "not found"
        checks.append(("Cargo", "✅" if r.returncode == 0 else "❌", cargo_ver))
    except Exception:
        checks.append(("Cargo", "❌", "not found"))

    # psql
    try:
        r = subprocess.run(["psql", "--version"], capture_output=True, text=True, timeout=5)
        psql_ver = r.stdout.strip()[:30] if r.returncode == 0 else "not found"
        checks.append(("psql", "✅" if r.returncode == 0 else "❌", psql_ver))
    except Exception:
        checks.append(("psql", "❌", "not found"))

    # MCP servers
    mgr = get_mcp_manager()
    checks.append(("MCP registered", "ℹ️", f"{mgr.server_count} server(s)"))
    checks.append(("MCP connected", "ℹ️", f"{mgr.tool_count} tool(s) available"))

    # Memory system
    from core.memory import MemoryStore
    mem = MemoryStore()
    checks.append(("Memory", "ℹ️", f"{mem.total()} fact(s) stored"))

    # Config
    from core.config.settings import load as load_cfg
    cfg = load_cfg()
    provider_name = cfg.get("provider", {}).get("name", "?")
    provider_model = cfg.get("provider", {}).get("model", "?")
    checks.append(("Provider", "ℹ️", f"{provider_name}/{provider_model}"))

    # Skills
    from core.skills import skill_manager
    checks.append(("Skills", "ℹ️", f"{len(skill_manager.list_all())} skill(s) loaded"))

    # Tests
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--tb=no", "-q"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).parent.parent),
        )
        if r.returncode == 0:
            last = [line for line in r.stdout.strip().splitlines() if line][-1]
            checks.append(("Tests", "✅", last))
        else:
            checks.append(("Tests", "❌", f"{r.returncode} failure(s)"))
    except Exception as e:
        checks.append(("Tests", "❌", str(e)))

    for name, status, detail in checks:
        table.add_row(name, status, detail)
    console.print(table)


def handle_export(messages):
    """Export the current conversation as a Markdown file."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = Path(".widdx/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"chat_export_{ts}.md"

    from core import config as cfg_mod
    cfg = cfg_mod.load()
    model = cfg.get("provider", {}).get("model", "unknown")

    lines = [
        f"# WIDDX Chat Export — {ts}",
        f"Model: {model}",
        f"Messages: {len(messages)}",
        "",
        "---",
        "",
    ]

    for m in messages:
        role = m.get("role", "?").upper()
        content = m.get("content", "")
        if m.get("tool_calls"):
            names = ", ".join(tc.get("function", {}).get("name", "?")
                            for tc in m["tool_calls"])
            content = f"[Tool calls: {names}]"

        if role == "SYSTEM":
            lines.append(f"> **{role}**: {content[:200]}")
        else:
            lines.append(f"### {role}")
            lines.append("")
            lines.append(content)
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print_system_msg(f"Exported {len(messages)} messages to {path}")
    return path


def handle_replay(cmd: str = ""):
    """Handle /replay — list, inspect, replay, or verify recorded executions.

    Usage:
        /replay                     list recent recordings
        /replay <run_id>            replay a recording and diff decisions
        /replay <run_id> --verify   only check recording integrity
    """
    from core.runtime.replay import get_replay_manager

    mgr = get_replay_manager()
    parts = cmd.split()
    verify_only = "--verify" in parts
    target = next((p for p in parts if not p.startswith("--")), "")

    if not target:
        recordings = mgr.list_recordings(limit=20)
        if not recordings:
            print_system_msg("No recordings found in .widdx/recordings/")
            return
        table = Table(title="Replay Recordings", border_style="dim", header_style="bold #f5a623")
        table.add_column("Run ID", style="bold #00c896")
        table.add_column("Steps", justify="right")
        table.add_column("Goal")
        table.add_column("File", style="dim")
        for r in recordings:
            table.add_row(r["task_id"], str(r["steps"]), r["goal"] or "—", r["file"])
        console.print(table)
        print_system_msg("Use /replay <run_id> to replay, or --verify to check integrity.")
        return

    candidates = mgr.list_recordings(limit=200)
    match = next(
        (
            r for r in candidates
            if r["file"] == target
            or r["task_id"].startswith(target)
            or target.startswith(r["task_id"])
        ),
        None,
    )
    if match is None:
        print_system_msg(f"No recording matches '{target}'. Run /replay to list available runs.")
        return

    path = match["file"]
    if verify_only:
        report = mgr.verify_recording(path)
        status = "✅ intact" if report["integrity_valid"] else "❌ checksum mismatch"
        print_system_msg(f"Recording {report['task_id']}: {status} ({report['steps']} steps, checksum {report['checksum']})")
        return

    try:
        player = mgr.load_recording(path)
        result = player.replay()
    except Exception as e:
        print_system_msg(f"Replay failed: {e}")
        return

    table = Table(title=f"Replay — {result.task_id}", border_style="dim", header_style="bold #f5a623")
    table.add_column("Metric", style="bold #00c896")
    table.add_column("Value")
    table.add_row("Steps replayed", str(result.steps_replayed))
    table.add_row("Decisions match", "✅ yes" if result.decisions_match else "⚠️ no")
    table.add_row("Divergence step", str(result.divergence_step) if result.divergence_step is not None else "—")
    table.add_row("Duration", f"{result.replay_time_ms:.1f} ms")
    console.print(table)

    if not result.decisions_match and result.divergence_details.get("divergences"):
        for d in result.divergence_details["divergences"][:5]:
            print_system_msg(
                f"  step {d.get('step')} ({d.get('phase')}): "
                f"expected={d.get('expected')} actual={d.get('actual')}"
            )


def handle_version():
    """Show version information."""
    from rich.table import Table

    # Read version from pyproject.toml
    ver = "3.0.0"
    try:
        try:
            import tomllib as _toml
        except ImportError:  # Python < 3.11
            import tomli as _toml  # type: ignore[no-redef]
        p = Path(__file__).parent.parent.parent / "pyproject.toml"
        if p.exists():
            with open(p, "rb") as f:
                ver = _toml.load(f).get("project", {}).get("version", ver)
    except Exception:
        pass

    table = Table(title="WIDDX Nexus", border_style="dim", header_style="bold #f5a623")
    table.add_column("Field", style="bold #00c896")
    table.add_column("Value", style="white")
    table.add_row("Version", ver)
    table.add_row("Creator & Designer", "MUHAMMAD MUSLIH")
    table.add_row("Company", "widdx")
    table.add_row("Python", f"{sys.version_info.major}.{sys.version_info.minor}")
    table.add_row("Platform", sys.platform)
    table.add_row("CWD", os.getcwd())
    from core.config.settings import get_config_path
    table.add_row("Config", str(get_config_path()))
    console.print(table)


def handle_permissions(cmd: str = ""):
    """Handle /permissions command — view/change permission level."""
    from core.permissions import get_permission_manager, PermissionLevel
    from rich.table import Table

    pm = get_permission_manager()
    parts = cmd.strip().split(None, 1) if cmd else []

    if not parts:
        # Show current status
        table = Table(title="Permissions", border_style="dim", header_style="bold #f5a623")
        table.add_column("Field", style="bold #00c896")
        table.add_column("Value", style="white")
        table.add_row("Level", pm.level.value)
        table.add_row("Status", pm.status())
        remembered = pm._remembered
        if remembered:
            allowed = [k for k, v in remembered.items() if v]
            denied = [k for k, v in remembered.items() if not v]
            if allowed:
                table.add_row("Allowed", ", ".join(allowed))
            if denied:
                table.add_row("Denied", ", ".join(denied))
        console.print(table)
        console.print(Text(
            "  Usage: /permissions level <name>  |  /permissions forget [tool]",
            style="dim",
        ))
        return

    action = parts[0]
    if action == "level" and len(parts) > 1:
        try:
            pm.level = PermissionLevel(parts[1])
            print_system_msg(f"Permission level set to {parts[1]}")
        except ValueError:
            valid = [lvl.value for lvl in PermissionLevel]
            print_system_msg(f"Invalid level. Choose: {', '.join(valid)}")
    elif action == "forget":
        tool = parts[1] if len(parts) > 1 else None
        pm.forget(tool)
        print_system_msg(f"Forgot permissions{' for ' + tool if tool else ' (all)'}")
    else:
        print_system_msg(f"Unknown: /permissions {action}")


def handle_gguf(cmd: str, provider, state):
    """Handle /gguf command — import/list/remove GGUF models.

    Usage:
      /gguf import <path> [--name <name>] [--template <tmpl>] [--context <N>]
      /gguf list
      /gguf remove <name>
    """
    from core.providers.gguf import (
        import_gguf, list_imports, remove_import,
        read_gguf_metadata, suggest_model_name, suggest_template,
        _CHAT_TEMPLATES,
    )
    from rich.table import Table

    parts = cmd.strip().split(None, 1)
    action = parts[0].lower() if parts else ""

    if action == "import":
        # Parse: /gguf import <path> [--name X] [--template X] [--context N]
        rest = parts[1] if len(parts) > 1 else ""
        if not rest:
            print_system_msg("Usage: /gguf import <path/to/model.gguf> [--name X] [--template X] [--context N]")
            return

        tokens = rest.split()
        gguf_path = tokens[0]
        model_name = None
        template = None
        context_size = None

        i = 1
        while i < len(tokens):
            if tokens[i] == "--name" and i + 1 < len(tokens):
                model_name = tokens[i + 1]
                i += 2
            elif tokens[i] == "--template" and i + 1 < len(tokens):
                template = tokens[i + 1]
                i += 2
            elif tokens[i] == "--context" and i + 1 < len(tokens):
                try:
                    context_size = int(tokens[i + 1])
                except ValueError:
                    print_system_msg(f"Invalid context size: {tokens[i+1]}")
                    return
                i += 2
            else:
                i += 1

        # ── Phase 1: Read metadata ─────────────────────────
        try:
            meta = read_gguf_metadata(gguf_path)
        except FileNotFoundError:
            print_system_msg(f"File not found: {gguf_path}")
            return
        except ValueError as e:
            print_system_msg(f"Invalid GGUF file: {e}")
            return

        # Display metadata
        size_mb = meta["file_size"] / (1024 ** 2)
        size_str = f"{size_mb:.0f} MB" if size_mb < 1024 else f"{size_mb/1024:.1f} GB"

        suggested_name = model_name or suggest_model_name(gguf_path, meta)
        suggested_tmpl = template or suggest_template(meta) or "auto"

        table = Table(title="GGUF Model Info", border_style="dim", header_style="bold #f5a623")
        table.add_column("Field", style="bold #00c896")
        table.add_column("Value", style="white")
        table.add_row("File", str(Path(gguf_path).name))
        table.add_row("Size", size_str)
        table.add_row("Architecture", meta.get("architecture", "unknown"))
        table.add_row("Context", str(meta.get("context_length", 2048)))
        table.add_row("Model Name", suggested_name)
        table.add_row("Template", suggested_tmpl)
        if meta.get("description"):
            table.add_row("Description", meta["description"][:100])
        console.print(table)

        # Show available templates if user wants to choose
        if not template:
            console.print(Text(
                "Available --template values: " + ", ".join(_CHAT_TEMPLATES.keys()),
                style="dim",
            ))

        # ── Confirm ─────────────────────────────────────────
        confirm = RPrompt.ask(
            f"\nImport as '{suggested_name}'?",
            choices=["y", "n", "q"],
            default="y",
        )
        if confirm != "y":
            print_system_msg("Import cancelled")
            return

        # ── Phase 2: Import ─────────────────────────────────
        print_system_msg(f"Importing {suggested_name} ... (this may take several minutes for large models)")
        result = import_gguf(
            gguf_path,
            model_name=suggested_name,
            template=suggested_tmpl if suggested_tmpl != "auto" else None,
            context_size=context_size,
        )

        if result["success"]:
            from core.providers.gguf import log_import
            log_import(result)
            # Reload Ollama models cache
            from core.providers.providers import fetch_ollama_models
            fetch_ollama_models(force_refresh=True)
            print_system_msg(f"✅ Successfully imported: {result['model_name']}")
            console.print(Text(result["output"][:500], style="dim"))
            # Offer to switch to it
            switch = RPrompt.ask(
                f"Switch to '{result['model_name']}' now?",
                choices=["y", "n"],
                default="y",
            )
            if switch == "y":
                provider.model = result["model_name"]
                state["model"] = f"ollama/{result['model_name']}"
                print_system_msg(f"Switched to ollama/{result['model_name']}")
        else:
            print_system_msg(f"❌ Import failed: {result['error']}")

    elif action == "list":
        imports = list_imports()
        if not imports:
            print_system_msg("No GGUF models imported yet. Use /gguf import <path>")
            return

        table = Table(title=f"Imported GGUF Models ({len(imports)})",
                      border_style="dim", header_style="bold #00c896")
        table.add_column("#", style="dim", width=3)
        table.add_column("Model", style="bold white")
        table.add_column("Arch", style="#f5a623")
        table.add_column("Size", style="dim")
        table.add_column("Imported", style="dim")
        table.add_column("Status", style="white")

        for i, entry in enumerate(imports, 1):
            size_mb = entry.get("metadata", {}).get("file_size", 0) / (1024 ** 2)
            size_str = f"{size_mb:.0f} MB" if size_mb < 1024 else f"{size_mb/1024:.1f} GB"
            arch = entry.get("metadata", {}).get("architecture", "?")
            imported = entry.get("imported_at", 0)
            date_str = datetime.fromtimestamp(imported).strftime("%Y-%m-%d") if imported else "?"

            # Check if model exists in Ollama
            from core.providers.providers import fetch_ollama_models
            ollama_models = fetch_ollama_models(force_refresh=False)
            exists = any(m["name"] == entry["model_name"] for m in ollama_models)
            status = "✅ available" if exists else "⚠️ missing"

            table.add_row(str(i), entry["model_name"], arch, size_str, date_str, status)
        console.print(table)

    elif action == "scan":
        print_system_msg("🔍 Scanning your computer for .gguf files...")
        from core.providers.gguf import scan_gguf_files
        found = scan_gguf_files(force_refresh=True)
        if not found:
            print_system_msg("No .gguf files found. Try /gguf import <path> instead.")
            return
        table = Table(title=f"Found {len(found)} GGUF files on your computer",
                      border_style="dim", header_style="bold #f5a623")
        table.add_column("#", style="dim", width=3)
        table.add_column("File", style="bold white")
        table.add_column("Size", style="#f5a623")
        table.add_column("Path", style="dim")
        for i, f in enumerate(found, 1):
            size_str = f"{f['size_gb']:.1f} GB" if f["size_gb"] >= 1 else f"{f['size_mb']:.0f} MB"
            table.add_row(str(i), f["name"], size_str, f["path"])
        console.print(table)
        print_system_msg("Use /gguf import <path> to import any of these files")

    elif action == "remove":
        rest = parts[1] if len(parts) > 1 else ""
        name = rest.strip() if rest else ""
        if not name:
            print_system_msg("Usage: /gguf remove <model-name>")
            return

        confirm = RPrompt.ask(
            f"Remove '{name}' from Ollama? This cannot be undone.",
            choices=["y", "n"],
            default="n",
        )
        if confirm != "y":
            print_system_msg("Cancelled")
            return

        result = remove_import(name)
        if result["success"]:
            from core.providers.providers import fetch_ollama_models
            fetch_ollama_models(force_refresh=True)
            print_system_msg(f"✅ Removed: {name}")
        else:
            print_system_msg(f"❌ Failed to remove: {result.get('output', 'unknown error')}")

    else:
        console.print(Text(
            "Usage:\n"
            "  /gguf import <path.gguf> [--name X] [--template X] [--context N]\n"
            "  /gguf scan      — auto-discover .gguf files on your computer\n"
            "  /gguf list       — list imported models\n"
            "  /gguf remove <name>\n\n"
            "Available --template values: " + ", ".join(_CHAT_TEMPLATES.keys()),
        ))
        print_system_msg("See /gguf import --help for details")
