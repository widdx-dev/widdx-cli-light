# WIDDX Cortex — VS Code Extension

🧠 AI-powered coding assistant inside VS Code. Chat, get explanations, fix bugs, and review code — all from your editor.

## Features

- **Sidebar Chat** — Full AI chat panel with streaming responses
- **Code Context** — Automatically sends open file + selection for context-aware answers
- **Explain Code** — Select code → right-click → "Explain Selected Code"
- **Fix Bugs** — Select code → right-click → "Fix Selected Code"  
- **Review File** — Full file review for bugs, security, and improvements
- **Keyboard Shortcuts** — `Ctrl+Alt+W` open chat, `Ctrl+Alt+S` send selection
- **Status Bar** — Connection indicator with auto health-check

## Requirements

- VS Code 1.85+
- WIDDX Cortex API server running (`widdx-api`)

## Installation

```bash
# 1. Start the WIDDX API server
widdx-api

# 2. Install the VS Code extension
cd vscode-extension
npm install
npm run compile
```

Then press F5 to launch Extension Development Host, or package it:

```bash
npm run package
```

## Configuration

| Setting | Default | Description |
|---|---|---|
| `widdx.apiUrl` | `http://localhost:8000` | API server URL |
| `widdx.model` | `auto` | AI model to use |
| `widdx.autoStartServer` | `true` | Auto-start API server |

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Alt+W` / `Cmd+Alt+W` | Open Chat |
| `Ctrl+Alt+S` / `Cmd+Alt+S` | Send Selection to Chat |

## Architecture

```
src/
├── extension.ts   → Entry point, commands, status bar
├── panel.ts       → Chat webview panel provider
└── client.ts      → HTTP client to WIDDX API
```

🤖 Made in Palestine 🇵🇸
