# WIDDX Nexus — Architecture Overview

## System Identity

WIDDX Nexus is an **autonomous software engineering platform** — not a chatbot.
It plans, executes, verifies, fixes, documents, and learns across multiple
sessions without human intervention.

**55 systems. 9 agent types. 7 LLM providers. 523 tests. 0 failures.**

## Architecture Layers

```
┌─────────────────────────────────────────┐
│           PRESENTATION                   │
│  Web UI (FastAPI) │ CLI (Rich) │ TUI    │
├─────────────────────────────────────────┤
│           ORCHESTRATION                  │
│  ChatHandler → UIL Brain Pipeline       │
│  Analyze → Route → Plan → Execute →     │
│  Verify → Learn                         │
├─────────────────────────────────────────┤
│           EXECUTION                      │
│  AutonomousAgent │ ExpertTeam │         │
│  SubAgents(spawn) │ Delegation          │
├─────────────────────────────────────────┤
│           INTELLIGENCE v4.0              │
│  Classifier │ Planner │ Validation │     │
│  Arbiter │ Trust Tracker                 │
├─────────────────────────────────────────┤
│           KNOWLEDGE LAYER (5.0)          │
│  Memory(v) │ KG │ ADR │ DocSync │       │
│  TaskState │ StateManager │ Decision     │
├─────────────────────────────────────────┤
│           RELIABILITY                    │
│  ProviderPool │ Retry │ Failover │       │
│  Checkpoint │ Resume │ Backoff           │
├─────────────────────────────────────────┤
│           INFRASTRUCTURE                 │
│  Providers(7) │ Sandbox │ Guard │        │
│  SQLite │ Cron │ Gateway │ MCP           │
└─────────────────────────────────────────┘
```

## Key Numbers

| Metric | Value |
|--------|-------|
| Python files | 195 |
| Core code lines | 36,600 |
| Test lines | 6,100 |
| Tests | 523 |
| Providers | 7 |
| Agent types | 9 |
| Tools | 15+ |
| Skills | 18 |
| Autonomy level | 4-5/10 |
