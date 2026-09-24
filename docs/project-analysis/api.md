# WIDDX Nexus — Complete API Reference

> Generated: 2026-06-25 | 68 REST endpoints + 2 WebSocket endpoints

## Web UI Server (scripts/web/server.py)

### Core
| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/` | index | Serve SPA |
| GET | `/api/health` | health | Health check → `{"status":"ok"}` |
| GET | `/api/status` | status | Provider + sandbox status |
| GET | `/api/version` | api_version | Version info |

### Chat
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat` | Send message (Pydantic: ChatPayload) |
| WS | `/ws/chat` | Streaming chat via WebSocket |
| WS | `/ws/events` | Live activity events |

### Sandbox
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/sandbox/exec` | Execute command (Pydantic: SandboxPayload) |
| GET | `/api/sandbox/files` | File tree browser |
| POST | `/api/sandbox/screenshot` | Browser screenshot via Playwright |

### Dashboard
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/dashboard` | Full dashboard overview |
| GET | `/api/dashboard/cron` | Cron jobs list |
| POST | `/api/dashboard/cron` | Create cron job |
| DELETE | `/api/dashboard/cron/{job_id}` | Delete cron job |
| GET | `/api/dashboard/background` | Background tasks |
| GET | `/api/dashboard/agents` | Sub-agents status |
| GET | `/api/dashboard/memories` | Memory list |
| GET | `/api/dashboard/sessions` | Session list |
| GET | `/api/dashboard/skills` | Skills list |
| GET | `/api/dashboard/gateway` | Gateway channels |
| GET | `/api/dashboard/activity` | Activity feed |

### Settings
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/settings` | Get settings (Pydantic validated) |
| POST | `/api/settings` | Update settings (SettingsPayload) |
| GET | `/api/settings/models` | Available models per provider |

### Sessions CRUD
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/sessions` | List sessions |
| POST | `/api/sessions` | Save session (SessionPayload) |
| GET | `/api/sessions/{id}` | Load session |
| DELETE | `/api/sessions/{id}` | Delete session |
| GET | `/api/sessions/{id}/export` | Export as markdown |

### Memory CRUD
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/memories/search?q=` | Search memories |
| POST | `/api/memories` | Create memory (MemoryPayload) |
| DELETE | `/api/memories/{id}` | Delete memory |

### MCP Management
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/mcp` | List MCP servers |
| POST | `/api/mcp` | Add MCP server |
| DELETE | `/api/mcp/{name}` | Remove server |
| POST | `/api/mcp/{name}/restart` | Restart server |

### Gateway
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/gateway/start` | Start gateway platform |
| POST | `/api/gateway/stop` | Stop gateway platform |

### Git
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/git` | Git status summary |
| GET | `/api/git/branches` | List branches |
| POST | `/api/git/undo` | Undo last commit |

### DevOps
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/plugins` | List plugins |
| POST | `/api/plugins/{name}/enable` | Enable plugin |
| POST | `/api/plugins/{name}/disable` | Disable plugin |
| GET | `/api/workflows` | List workflows |
| POST | `/api/workflows` | Create workflow |
| POST | `/api/workflows/{id}/run` | Run workflow |
| GET | `/api/gguf` | List GGUF models |
| POST | `/api/gguf/load` | Load GGUF model |
| POST | `/api/gguf/unload` | Unload GGUF model |
| GET | `/api/manifest` | Project manifest |
| POST | `/api/manifest/scan` | Scan manifest |
| GET | `/api/debug` | Debug info |
| GET | `/api/doctor` | System diagnostics |
| GET | `/api/token-budget` | Token budget status |
| POST | `/api/token-budget/reset` | Reset budget |
| GET | `/api/autocommit` | Auto-commit status |
| POST | `/api/autocommit/toggle` | Toggle auto-commit |
| GET | `/api/apikeys` | API key list (masked) |
| GET | `/api/branches` | Session branches |
| GET | `/api/project/session` | Project session |

### Proxy + Permissions
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/proxy` | Proxy status |
| POST | `/api/proxy` | Update proxy |
| GET | `/api/permissions` | Permission status |
| POST | `/api/permissions` | Set permission level |

### Computer
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/computer/info` | System info (OS, CPU, disk) |
| POST | `/api/computer/exec` | Execute command |

---

## REST API Server (scripts/api_server.py)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/tools` | Bearer + RateLimit | List tools |
| POST | `/api/chat` | Bearer + RateLimit | Chat message (Pydantic ChatRequest) |
| GET | `/api/sessions` | Bearer + RateLimit | List sessions |
| GET | `/api/memories` | Bearer + RateLimit | List memories |
| DELETE | `/api/memories/{name}` | Bearer + RateLimit | Delete memory |

### API Server Security
- Bearer token auth via `WIDDX_API_KEY` env var (required)
- Rate limiter: 60 req/min sliding window
- CORS: localhost only
- Body size: Pydantic `max_length=100000` on ChatRequest

---

## GitHub App

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/webhook` | HMAC-SHA256 | GitHub webhook handler |

---

## Pydantic Validation Models

| Model | Fields | Used By |
|-------|--------|---------|
| ChatPayload | message (1-100K), history (max 1000) | POST /api/chat |
| SandboxPayload | command (1-10K), timeout (1-600) | POST /api/sandbox/exec |
| SettingsPayload | provider, system_prompt, temperature, max_turns, cli_theme | POST /api/settings |
| SessionPayload | name (1-200), messages (max 1000) | POST /api/sessions |
| MemoryPayload | content (1-50K), tags (max 500) | POST /api/memories |
| ChatRequest | message (max 100K) | POST /api/chat (API server) |
