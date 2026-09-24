# Agent System

## Agent Types (9)

| Agent | File | When | LLM Calls |
|-------|------|------|-----------|
| **AutonomousAgent** | `core/agents/agent.py` | Always | 1..N per task |
| **ExpertTeam** | `core/agents/expert.py` | COMPLEX tasks | 5-6 sequential |
| ↳ Orchestrator | same | Plans & coordinates | 1 |
| ↳ Researcher | same | Research & gather info | 1 |
| ↳ Coder | same | Write implementation | 1 |
| ↳ Reviewer | same | Quality review | 1 |
| ↳ Debugger | same | Fix remaining issues | 1 |
| **SubAgent** | `core/agents/agent.py:spawn_sub_agent()` | On spawn_agent tool | 1..N |
| **DelegationAgent** | `core/delegation.py` | Parallel tasks | 1 each |

## AutonomousAgent

The core execution loop. Every task goes through this.

**Capabilities:**
- Tool calling (write, bash, browser, spawn_agent, +15 more)
- Code extraction fallback (for models without tool support)
- TaskState checkpoint/resume (survives restart)
- Step Lock idempotency (skips already-executed steps)
- Provider failover (ReliableProvider integration)
- Auto-validation after file writes
- Cancel support (user escape)

**Lifecycle:**
```
init → run()
  ├─ resume from TaskState OR start fresh
  ├─ loop: call LLM → execute tools → save checkpoint
  └─ return (steps, summary)
```

## ExpertTeam

Activated when `TaskType.COMPLEX` → `ExecutionMode.EXPERT_TEAM`.

**Complexity detection:**
- "full stack", "complete project", "web app", "microservice" → Level 3 (full team)
- "api", "frontend", "backend", "auth" → Level 2 (+researcher)
- Simple tasks → Level 1 (orchestrator + coder + reviewer only)

**KG-aware:** `_detect_project_languages()` uses KnowledgeGraph to select domain-specific experts.

## Recursive Spawning

`spawn_agent(task, role)` — available as a tool to all agents.

**Rules:**
- Max depth: 3 (root → child → grandchild)
- Max total: 10 agents per root task
- Timeout: 5 minutes per sub-agent
- Results flow back to parent

## Comparison

| Feature | AutonomousAgent | ExpertTeam | spawn_agent |
|---------|----------------|------------|-------------|
| Parallel | ❌ | ❌ (sequential) | ✅ (threaded) |
| Specialized prompts | ❌ | ✅ (per role) | ✅ (role-based) |
| Recursive | ❌ | ❌ | ✅ (max depth 3) |
| Checkpoint/resume | ✅ | ❌ | ❌ |
| Provider failover | ✅ | ❌ | ❌ |
