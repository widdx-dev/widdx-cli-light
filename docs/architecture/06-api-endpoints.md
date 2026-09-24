# API & Endpoints

## Web UI Server (`scripts/web/server.py`)

### Chat
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Single-turn chat (REST) |
| `WS` | `/ws/chat` | Streaming chat (WebSocket) — triggers AutonomousAgent |
| `WS` | `/ws/events` | Live activity event stream |

### Computer Panel
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/computer/exec` | Execute terminal command |
| `GET` | `/api/computer/info` | System information |
| `POST` | `/api/sandbox/exec` | Sandboxed command execution |
| `GET` | `/api/sandbox/files` | List sandbox files |
| `POST` | `/api/sandbox/screenshot` | Take browser screenshot |

### Dashboard
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/dashboard` | Full dashboard data |
| `GET` | `/api/dashboard/cron` | Scheduled tasks |
| `GET` | `/api/dashboard/background` | Background tasks |
| `GET` | `/api/dashboard/agents` | Active agents |
| `GET` | `/api/dashboard/memories` | Memory list |
| `GET` | `/api/dashboard/sessions` | Session list |
| `GET` | `/api/dashboard/activity` | Activity log |
| `GET` | `/api/dashboard/gateway` | Gateway status |

### Project
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/project/session` | Current session |
| `GET` | `/api/project/docs/{name}` | Read PLAN/DESIGN/TASKS/ROADMAP |
| `GET` | `/api/branches` | Git branches |
| `GET` | `/api/git` | Git status |
| `GET` | `/api/git/branches` | Branch list |

### Settings
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings` | Current settings |
| `POST` | `/api/settings` | Update settings (provider, model, API key) |
| `GET` | `/api/settings/models` | Available models for provider |

### System
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI (index.html) |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/status` | System status |
| `GET` | `/api/tools` | Tool definitions |
| `GET` | `/api/version` | Version info |

## REST API Server (`scripts/api_server.py`)

Standalone API server with authentication.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/chat` | Chat (requires auth) |
| `GET` | `/api/providers` | Provider list |
| `GET` | `/api/sessions` | Session list |
| `DELETE` | `/api/sessions` | Clear sessions |
| `GET` | `/api/memory` | Memory list |
| `POST` | `/api/memory` | Save memory |
| `DELETE` | `/api/memory/{id}` | Delete memory |

**Security:** Bearer token via `WIDDX_API_KEY` env var.
Body size limit: 1MB (configurable via `WIDDX_MAX_BODY_BYTES`).

## CLI Commands
```
widdx          → CLI terminal chat
widdx-web      → Web UI server
widdx-tui      → Textual TUI
widdx-api      → REST API server
```

## WebSocket Events

Client receives: `{type, data}`

| type | data | When |
|------|------|------|
| `reasoning` | string | LLM thinking process |
| `text` | string | Streaming response chunk |
| `tool` | `{name, args}` | Tool call started |
| `tool_result` | `{name, success, result}` | Tool execution result |
| `done` | null | Task complete |
| `error` | string | Error occurred |
