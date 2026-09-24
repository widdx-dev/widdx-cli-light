# WIDDX Nexus — Route Map

> All entry points, CLI commands, API routes, and WebSocket endpoints.

## Entry Points (console_scripts)

| Command | Module | Function | Interface |
|---------|--------|----------|-----------|
| `widdx` | core.cli.run | CLIApp.run() | Terminal CLI |
| `widdx-tui` | tui.app | run_tui | Textual TUI |
| `widdx-api` | scripts.api_server | main | REST API |
| `widdx-web` | scripts.web_app | main | Web UI (:8000) |

## CLI Commands (27 slash commands)

help, clear, model, provider, tools, skills, skill, history, save, load, export, remember, memories, debug, doctor, undo, proxy, sandbox, mcp, gguf, branch, theme, version, permissions, apikey, exit, voice

## TUI Screens (8)

MainScreen, TextDetailScreen, HelpScreen, MemoryList/Edit/Picker/DeleteScreen, SessionList/Picker/Rename/DeleteScreen, SettingsScreen, ToolDetailScreen, UbuntuGrid

## TUI Key Bindings

| Key | Action |
|-----|--------|
| Ctrl+K | Command palette |
| Ctrl+S | Save session |

## WebSocket (2)

| Path | Events |
|------|--------|
| /ws/chat | text, tool, reasoning, done, error |
| /ws/events | Live activity feed |

## HTTP: 68 endpoints

Full catalog in api.md. Served by `scripts/web/server.py` (FastAPI) at `http://localhost:8000`.

## VSCode Extension (6 commands)

openChat, newSession, sendSelection, explainCode, fixCode, reviewFile

## GitHub App

POST /webhook — PR review + issue triage (HMAC-SHA256)
