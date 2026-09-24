# WIDDX Nexus — Database Schema

## Overview

WIDDX uses a hybrid storage approach:
1. **SQLite** — Sessions, search index (primary)
2. **JSON files** — Configuration, knowledge, patterns, cron jobs, permissions
3. **Markdown files** — Memory, skills, project docs
4. **File system** — Project files, session exports

## SQLite Database (core/database.py)

**Location**: `.widdx/sessions.db` (per-project) or `~/.widdx/sessions.db` (global)

### Tables

#### `sessions`
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    branch TEXT DEFAULT 'main',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT  -- JSON: {model, cost, turns, ...}
);
```

#### `messages`
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,          -- 'user' | 'assistant' | 'system' | 'tool'
    content TEXT,
    tool_calls TEXT,             -- JSON array of tool call objects
    tool_call_id TEXT,           -- For tool-role messages
    name TEXT,                   -- Tool name for tool-role messages
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

#### `checkpoints`
```sql
CREATE TABLE checkpoints (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    messages_snapshot TEXT,      -- JSON array of messages
    metadata TEXT,               -- JSON: state snapshot
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

#### `search_index`
```sql
CREATE TABLE search_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    content_hash TEXT,
    tokens TEXT,                 -- Tokenized content for FTS
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (message_id) REFERENCES messages(id)
);
```

### Indexes
```sql
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_role ON messages(role);
CREATE INDEX idx_messages_created ON messages(created_at);
CREATE INDEX idx_checkpoints_session ON checkpoints(session_id);
CREATE INDEX idx_search_session ON search_index(session_id);
```

## JSON Storage Files

### `.widdx/session.json` — Current Session State
```json
{
    "messages": [...],
    "state": {
        "model": "provider/model",
        "cost": 0.0,
        "turns": 0,
        "tools_used": []
    },
    "branch": "main",
    "timestamp": "2026-06-25T..."
}
```

### `.widdx/config.json` — Project Configuration
```json
{
    "provider": {
        "name": "opencode-zen",
        "model": "deepseek-v4-flash-free",
        "base_url": "https://opencode.ai/zen/v1",
        "api_key": "public"
    },
    "temperature": 0.7,
    "max_turns": 10,
    "cli_theme": "dark",
    "auto_commit": true,
    "system_prompt": null,
    "engines": {
        "intelligence": true,
        "validation": true,
        "isolation": true
    },
    "all_providers": {...},
    "exclude_from_index": []
}
```

### `.widdx/knowledge.json` — UIL Knowledge Base
```json
{
    "entries": {
        "task_type:features:mode": {
            "successes": 5,
            "failures": 1,
            "avg_quality": 0.85,
            "last_used": "2026-06-25T..."
        }
    }
}
```

### `.widdx/decisions.json` — Decision Engine Learnings
```json
{
    "overrides": {
        "code_write:api+database:c3": "autonomous"
    },
    "stats": {
        "code_write:api+database:c3": {
            "task_type": "code_write",
            "mode": "autonomous",
            "successes": 5,
            "failures": 1,
            "total_quality": 4.2,
            "last_used": "2026-06-25T..."
        }
    }
}
```

### `.widdx/engine_trust.json` — Engine Trust Metrics
```json
{
    "engines": {
        "intelligence": {
            "engine_name": "intelligence",
            "total_comparisons": 100,
            "agreements": 85,
            "disagreements": 15,
            "engine_won": 10,
            "old_won": 5,
            "ties": 0,
            "trust_level": 0.92,
            "auto_promoted": false,
            "promoted_at": ""
        }
    }
}
```

### `.widdx/patterns.json` — Learned Patterns
```json
{
    "observations": [...],
    "patterns": [
        {
            "name": "learned_code_write_api_database_python",
            "category": "learned",
            "task_types": ["code_write"],
            "features": ["api", "database"],
            "languages": ["python"],
            "steps": [...],
            "description": "Auto-learned from 5 successful executions",
            "estimated_time": "varies",
            "complexity": 2
        }
    ]
}
```

### `.widdx/permissions.json` — Tool Permissions
```json
{
    "level": "permissive",
    "remembered": {
        "bash": true,
        "write": true,
        "edit": false
    }
}
```

### `.widdx/cron_jobs.json` — Scheduled Jobs
```json
{
    "jobs": [
        {
            "id": "abc123",
            "schedule": "0 9 * * *",
            "prompt": "Check project status",
            "status": "active",
            "next_run": "2026-06-26T09:00:00",
            "last_run": null,
            "run_count": 0
        }
    ]
}
```

### `.widdx/repo_map.json` — Repository Map Cache
```json
{
    "files": {
        "core/chat.py": {
            "path": "core/chat.py",
            "size": 8500,
            "mtime": 1719312000.0,
            "ext": ".py",
            "symbols": ["DisplayManager", "run_chat_turn", ...],
            "imports": ["core", "tools", ...],
            "exports": ["run_chat_turn", ...],
            "keywords": ["chat", "display", ...]
        }
    },
    "timestamp": 1719312000.0
}
```

### `.widdx/self_improve/error_patterns.json`
```json
{
    "duplicate variable": {
        "type": "duplicate variable",
        "count": 3,
        "examples": [...],
        "first_seen": 1719312000.0,
        "last_seen": 1719398400.0
    }
}
```

### `.widdx/self_improve/fix_tracker.json`
```json
{
    "duplicate variable": {
        "error_type": "duplicate variable",
        "fix": "grep for variable names before declaring",
        "success": true,
        "timestamp": 1719398400.0
    }
}
```

## Markdown Storage

### Memory Facts (`~/.widdx/memory/` or `.widdx/memory/`)

Each fact is a markdown file:
```markdown
---
name: user-prefers-dark-theme
type: user_preference
timestamp: 2026-06-25T12:00:00
---

The user prefers dark theme for all interfaces.
```

### Skills (`skills/` directory)

Each skill is a folder with `skill.md`:
```markdown
---
name: react-developer
description: React development expertise
icon: ⚛️
---

You are a React development expert...
```

### Project Docs (`.widdx/`)

- `PLAN.md` — Current implementation plan
- `DESIGN.md` — Architecture decisions
- `TASKS.md` — Task list with status
- `ROADMAP.md` — Milestones and progress

## File System Storage

### Session Branches
```
.widdx/
├── sessions/
│   ├── main.json          # Default branch
│   ├── feature-x.json     # Feature branch
│   └── ...
└── sessions.db            # SQLite (all branches)
```

### Exports
```
.widdx/exports/
├── chat_export_20260625_120000.md
└── ...
```

### Voice Files
```
~/.widdx/voice/
├── widdx_20260625_120000_123456.mp3
└── ...
```

## Data Flow Summary

```
User Input
    │
    ├──→ Session Storage (SQLite + JSON dual persistence)
    ├──→ Memory Learning (markdown files, auto-extracted every 2 turns)
    ├──→ Knowledge Base (JSON, records execution outcomes)
    ├──→ Decision Engine (JSON, learns routing preferences)
    ├──→ Trust Tracker (JSON, tracks engine reliability)
    ├──→ Pattern Learner (JSON, extracts reusable patterns)
    ├──→ Error Patterns (JSON, tracks recurring errors)
    ├──→ Activity Log (in-memory, live WebSocket events)
    └──→ Cron Jobs (JSON, scheduled task persistence)
```
