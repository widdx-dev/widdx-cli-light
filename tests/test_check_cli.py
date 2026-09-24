"""Isolated CLI startup and diagnostic command tests."""

import json
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest


PROBE_OUTPUTS = {
    "git": "git version 2.50.0",
    "node": "v22.0.0",
    "docker": "Docker version 28.0.0",
    "npm": "10.0.0",
    "pip": "pip 25.0",
    "cargo": "cargo 1.85.0",
    "psql": "psql 17.0",
}


@pytest.fixture
def cli_app(tmp_path, monkeypatch):
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("WIDDX_PROJECT_DIR", str(project))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    def blocked(*args, **kwargs):
        pytest.fail("Unexpected external I/O in isolated CLI test")

    def probe(args, **kwargs):
        if args in (
            ["git", "branch", "--show-current"],
            ["git", "status", "--porcelain"],
            ["git", "log", "--oneline", "-3"],
        ):
            assert Path(kwargs["cwd"]).resolve() == project
            return subprocess.CompletedProcess(args, 128, "", "not a git repository")
        if len(args) != 2 or args[1] != "--version" or args[0] not in PROBE_OUTPUTS:
            pytest.fail(f"Unexpected subprocess: {args!r}")
        return subprocess.CompletedProcess(args, 0, PROBE_OUTPUTS[args[0]] + "\n", "")

    probes = Mock(side_effect=probe)
    monkeypatch.setattr(subprocess, "run", probes)
    monkeypatch.setattr(subprocess, "Popen", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)

    from core.config import keychain, settings

    config_path = project / "config.json"
    config_path.write_text(json.dumps({
        "provider": {"name": "ollama", "model": "cli-test-model"},
        "mcp_servers": [],
        "auto_commit": False,
    }), encoding="utf-8")
    monkeypatch.setattr(settings, "_config_path", config_path)
    monkeypatch.setattr(settings, "_config_writable", True)
    monkeypatch.setattr(settings, "_USER_CONFIG_DIR", home / ".widdx")
    monkeypatch.setattr(keychain, "_load_persisted_keys", lambda: {})
    monkeypatch.setattr(keychain, "_save_persisted_keys", blocked)

    from core.providers import providers

    def make_provider(cfg):
        p = cfg["provider"]
        return SimpleNamespace(
            name=p["name"], model=p["model"],
            base_url="http://localhost:11434", api_key="",
        )

    factory = Mock(side_effect=make_provider)
    discovery = Mock(return_value=["cli-discovered-model"])

    from core import commands, permissions, project_context, proxy, skills
    from core.mcp import client
    from core.project import manifest, state
    from core.tools import safety
    from cli import app, commands as cli_commands

    monkeypatch.setattr(providers, "create_provider", factory)
    monkeypatch.setattr(providers, "get_available_models", discovery)
    monkeypatch.setattr(providers, "fetch_free_models", discovery)
    monkeypatch.setattr(commands, "create_provider", factory)
    monkeypatch.setattr(commands, "fetch_free_models", discovery)
    monkeypatch.setattr(commands.RPrompt, "ask", blocked)
    monkeypatch.setattr(client, "_mcp_manager", client.MCPClientManager())
    monkeypatch.setattr(client, "generate_project_mcp_config", lambda root: [])
    monkeypatch.setattr(project_context, "_project_context_manager", None)
    monkeypatch.setattr(permissions, "_permission_manager", None)
    monkeypatch.setattr(proxy, "proxy_manager", proxy.ProxyManager())
    monkeypatch.setattr(manifest, "ROOT", project)
    monkeypatch.setattr(state, "_project_db", Mock(side_effect=RuntimeError("Use JSON persistence")))
    monkeypatch.setattr(safety, "_SAFE_DIR", None)
    monkeypatch.setattr(skills.skill_manager, "_skills", {})
    monkeypatch.setattr(skills.skill_manager, "_active", None)
    monkeypatch.setattr(app, "create_provider", factory)
    monkeypatch.setattr(app, "CLIInput", Mock())
    monkeypatch.setattr(app, "has_key", lambda name: False)
    monkeypatch.setattr(app, "prompt_key", blocked)
    monkeypatch.setattr(cli_commands, "has_key", lambda name: False)
    monkeypatch.setattr(cli_commands, "prompt_key", blocked)

    instance = app.CLIApp()
    instance.startup()
    instance.test_probes = probes
    instance.test_discovery = discovery
    instance.test_factory = factory
    return instance


def test_doctor_runs_without_error(cli_app, monkeypatch):
    output = Mock()
    monkeypatch.setattr(cli_app, "show_system", output)
    cli_app.test_probes.reset_mock()
    assert cli_app.cmds.handle(
        "/doctor", cli_app.provider, cli_app.state, cli_app.messages,
    ) is True
    assert cli_app.test_probes.call_args_list == [
        call([name, "--version"], capture_output=True, text=True, timeout=5)
        for name in PROBE_OUTPUTS
    ]
    text = "\n".join(args[0] for args, _ in output.call_args_list)
    for value in PROBE_OUTPUTS.values():
        assert value in text
    assert "Provider: ollama/cli-test-model" in text
    assert "Memory: 0 facts" in text
    assert "MCP: 0 servers" in text
    assert "Skills: 0" in text


@pytest.mark.parametrize("failure", [FileNotFoundError, subprocess.TimeoutExpired])
def test_doctor_reports_unavailable_probes(cli_app, monkeypatch, failure):
    output = Mock()
    monkeypatch.setattr(cli_app, "show_system", output)
    error = failure("missing") if failure is FileNotFoundError else failure("probe", 5)
    cli_app.test_probes.reset_mock()
    cli_app.test_probes.side_effect = error
    assert cli_app.cmds.handle(
        "/doctor", cli_app.provider, cli_app.state, cli_app.messages,
    ) is True
    text = "\n".join(args[0] for args, _ in output.call_args_list)
    for name in ("Git", "Node", "Docker", "npm", "pip", "Cargo", "psql"):
        assert f"{name}: not found" in text
    assert cli_app.test_probes.call_count == len(PROBE_OUTPUTS)
    assert "Provider: ollama/cli-test-model" in text


def test_cli_app_has_provider(cli_app):
    assert cli_app.provider.name == "ollama"
    assert cli_app.provider.model == "cli-test-model"
    cli_app.test_factory.assert_called_once_with(cli_app.cfg)


def test_cli_app_has_state(cli_app):
    assert cli_app.state == {"model": "ollama/cli-test-model", "cost": 0.0, "turns": 0}
    assert cli_app.messages[0]["role"] == "system"
    assert "WIDDX" in cli_app.messages[0]["content"]
    assert Path.cwd().name == "project"
    assert (Path.cwd() / ".widdx").is_dir()


def test_cli_app_cmds_registered(cli_app):
    from cli.commands import CLICommands

    assert isinstance(cli_app.cmds, CLICommands)
    assert cli_app.cmds.app is cli_app
