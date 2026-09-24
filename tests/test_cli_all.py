"""Deterministic slash-command tests with real dispatch and isolated persistence."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.test_check_cli import cli_app as cli_app


COMMANDS = [
    ("/help", "Available commands"),
    ("/clear", "WIDDX Nexus"),
    ("/model", "cli-discovered-model"),
    ("/provider opencode-zen", "Provider changed to opencode-zen"),
    ("/tools", "Available Tools"),
    ("/skills", "Skills"),
    ("/history", "Recent History"),
    ("/save", "Session saved"),
    ("/load .", "No session found"),
    ("/export", "Exported"),
    ("/remember test-fact-from-cli-test", "Remembered: test-fact-from-cli-test"),
    ("/memories", "No memories found"),
    ("/manifest", "MANIFEST.json regenerated"),
    ("/reasoning", "No reasoning from last turn"),
    ("/debug", "Silent errors"),
    ("/doctor", "Docker: Docker version 28.0.0"),
    ("/undo", "Not a git repository"),
    ("/proxy", "Proxy status"),
    ("/sandbox .", "Sandbox set to: ."),
    ("/mcp", "No MCP servers configured"),
    ("/gguf", "/gguf"),
    ("/branch list", "main"),
    ("/version", "WIDDX Nexus"),
    ("/permissions", "Permissions"),
    ("/apikey show", "No API key set for ollama"),
]


@pytest.mark.parametrize("cmd,expected", COMMANDS, ids=[cmd for cmd, _ in COMMANDS])
def test_cli_command(cmd, expected, cli_app, capsys):
    capsys.readouterr()
    assert cli_app.cmds.handle(
        cmd, cli_app.provider, cli_app.state, cli_app.messages,
    ) is True
    assert expected in capsys.readouterr().out


@pytest.mark.parametrize("cmd", ["/exit", "/quit"])
def test_exit_command(cli_app, cmd):
    with pytest.raises(SystemExit) as exc:
        cli_app.cmds.handle(cmd, cli_app.provider, cli_app.state, cli_app.messages)
    assert exc.value.code == 0


@pytest.mark.parametrize("cmd", ["ordinary chat", "/unknown"])
def test_non_command_preserves_session(cli_app, cmd):
    messages = deepcopy(cli_app.messages)
    state = dict(cli_app.state)
    assert cli_app.cmds.handle(cmd, cli_app.provider, cli_app.state, cli_app.messages) is False
    assert cli_app.messages == messages
    assert cli_app.state == state


def test_model_discovery(cli_app, monkeypatch):
    output = Mock()
    monkeypatch.setattr(cli_app, "show_system", output)
    assert cli_app.cmds.handle("/model", cli_app.provider, cli_app.state, cli_app.messages)
    cli_app.test_discovery.assert_called_once_with(
        "ollama", cli_app.provider.base_url, force_refresh=True,
    )
    output.assert_called_once_with("Available models: cli-discovered-model")


def test_provider_switch_updates_app(cli_app):
    old_provider = cli_app.provider
    messages = deepcopy(cli_app.messages)
    assert cli_app.cmds.handle(
        "/provider opencode-zen", old_provider, cli_app.state, cli_app.messages,
    )
    cli_app.test_discovery.assert_called_once_with()
    cli_app.test_factory.assert_called_with({
        "provider": {"name": "opencode-zen", "model": "cli-discovered-model"},
    })
    assert cli_app.provider is not old_provider
    assert cli_app.provider.name == "opencode-zen"
    assert cli_app.state["model"] == "opencode-zen/cli-discovered-model"
    assert cli_app.messages == messages


def test_save_load_round_trip(cli_app):
    from core.project import state

    cli_app.messages[:] = [
        {"role": "system", "content": "Isolated session"},
        {"role": "user", "content": "isolated conversation"},
    ]
    cli_app.state.update(cost=0.125, turns=3)
    saved_messages = deepcopy(cli_app.messages)
    saved_state = dict(cli_app.state)
    assert cli_app.cmds.handle("/save", cli_app.provider, cli_app.state, cli_app.messages)
    session = state.load_session(Path.cwd())
    assert session["messages"] == saved_messages
    assert session["state"] == saved_state
    cli_app.messages.clear()
    cli_app.state.update(cost=0.0, turns=0)
    assert cli_app.cmds.handle("/load .", cli_app.provider, cli_app.state, cli_app.messages)
    assert cli_app.messages == saved_messages
    assert cli_app.state == saved_state


@pytest.mark.parametrize("path", [".", "missing-project"])
def test_load_missing_session_preserves_messages(cli_app, path):
    messages = deepcopy(cli_app.messages)
    state = dict(cli_app.state)
    assert cli_app.cmds.handle(
        f"/load {path}", cli_app.provider, cli_app.state, cli_app.messages,
    )
    assert cli_app.messages == messages
    assert cli_app.state == state


def test_export_writes_conversation_in_project(cli_app):
    cli_app.messages[:] = [
        {"role": "user", "content": "isolated question"},
        {"role": "assistant", "content": "isolated answer"},
    ]
    assert cli_app.cmds.handle("/export", cli_app.provider, cli_app.state, cli_app.messages)
    exports = list((Path.cwd() / ".widdx" / "exports").glob("chat_export_*.md"))
    assert len(exports) == 1
    text = exports[0].read_text(encoding="utf-8")
    assert "Model: cli-test-model" in text
    assert "Messages: 2" in text
    assert "### USER\n\nisolated question" in text
    assert "### ASSISTANT\n\nisolated answer" in text


def test_manifest_scans_isolated_project(cli_app):
    (Path.cwd() / "example.py").write_text('"""Isolated example."""\n', encoding="utf-8")
    assert cli_app.cmds.handle("/manifest", cli_app.provider, cli_app.state, cli_app.messages)
    manifest = json.loads((Path.cwd() / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["files"] == [{"path": "example.py", "description": "Isolated example."}]
    assert manifest["skills"] == []


def test_undo_uses_isolated_project(cli_app, monkeypatch):
    from cli import commands

    undo = Mock(return_value="isolated undo result")
    output = Mock()
    monkeypatch.setattr(commands, "undo_last_commit", undo)
    monkeypatch.setattr(cli_app, "show_system", output)
    assert cli_app.cmds.handle("/undo", cli_app.provider, cli_app.state, cli_app.messages)
    undo.assert_called_once_with(Path.cwd())
    output.assert_called_once_with("isolated undo result")


def test_remember_uses_isolated_home(cli_app):
    from core.memory import MemoryStore

    assert MemoryStore().total() == 0
    assert cli_app.cmds.handle(
        "/remember isolated fact", cli_app.provider, cli_app.state, cli_app.messages,
    )
    store = MemoryStore()
    assert store.root == Path.home() / ".widdx"
    assert store.total() == 1
    assert "isolated fact" in store.get("note-13")


def test_sandbox_uses_isolated_project(cli_app):
    from core import tools

    assert tools.get_safe_dir() is None
    assert cli_app.cmds.handle("/sandbox .", cli_app.provider, cli_app.state, cli_app.messages)
    assert tools.get_safe_dir() == str(Path.cwd())
