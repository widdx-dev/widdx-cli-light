# WIDDX Nexus — Project Analysis

> Complete forensic analysis of the WIDDX Nexus (chat-tool) codebase.
> Generated for AI agent consumption — sufficient to understand the entire project without re-reading source.

## Document Index

| # | Document | Size | Description |
|---|----------|------|-------------|
| 1 | [project-map.md](project-map.md) | 18KB | Complete file-by-file directory map (171+ source files) |
| 2 | [architecture.md](architecture.md) | 14KB | 4-layer architecture, pipeline flow, component interaction |
| 3 | [dependency-graph.md](dependency-graph.md) | 10KB | External + internal dependencies, DAG analysis |
| 4 | [imports.md](imports.md) | 7KB | Import/export analysis, lazy patterns, protected imports |
| 5 | [classes.md](classes.md) | 14KB | 232+ classes with inheritance hierarchy by module |
| 6 | [functions.md](functions.md) | 17KB | 320+ key functions with signatures and call relationships |
| 7 | [routes.md](routes.md) | 7KB | FastAPI + Web UI route table (all endpoints) |
| 8 | [api.md](api.md) | 27KB | Complete API reference (authentication, endpoints, types) |
| 9 | [database.md](database.md) | 8KB | SQLite schema + JSON/MD storage architecture |
| 10 | [dead-code.md](dead-code.md) | 3KB | Deprecated modules, missing imports, broken references |
| 11 | [security.md](security.md) | 5KB | Security controls audit, 6 issues (P0-P3) |
| 12 | [performance.md](performance.md) | 4KB | Performance characteristics, 6 bottlenecks (P1-P3) |
| 13 | [issues.md](issues.md) | 8KB | Complete issues register: 21 real issues + 2 false positives marked |
| 14 | [fix-plan.md](fix-plan.md) | 6KB | Prioritized remediation plan (Week 1-4) |

## Quick Facts

- **Version**: 3.1.0
- **Author**: MUHAMMAD MUSLIH (widdx.com)
- **License**: MIT
- **Language**: Python 3.10+, TypeScript (VSCode extension)
- **Entry Points**: `widdx` (CLI), `widdx-tui` (TUI), `widdx-api` (FastAPI), `widdx-web` (Web)
- **Source Files**: 171+ Python + 10 TypeScript + HTML/CSS/JS
- **Test Files**: 23
- **Core Subpackages**: 12 (`agents`, `config`, `cron`, `gateway`, `intelligence`, `isolation`, `mcp`, `project`, `providers`, `tools`, `uil`, `validation`)

## Architecture Summary

```
Presentation Layer  →  CLI / TUI / Web UI / Gateway (Telegram, Discord)
         ↓
Orchestration Layer →  UIL Brain, Chat Engine, Workflow Engine, Agents
         ↓
Service Layer       →  Session/Memory/Project/Cron/Skills/MCP/Tools
         ↓
Provider Layer      →  DeepSeek / OpenAI / Ollama / GGUF / OpenCode Zen
```

## Key Findings (Top Issues)

| ID | Issue | Severity | File |
|----|-------|----------|------|
| ISS-001 | API Auth Bypass via Empty Token | CRITICAL | `scripts/api_server.py` |
| ISS-002 | Command Injection via shell=True | CRITICAL | `core/sandbox.py` |
| ISS-004 | No Request Size Limits | HIGH | `scripts/api_server.py` |
| ISS-007 | Docker Runs as Root | HIGH | `Dockerfile` |
| ISS-010 | Skill Loader Executes Arbitrary Code | MEDIUM | `core/skills.py` |
| ISS-014 | Error Messages Leak Internals | MEDIUM | Various |
