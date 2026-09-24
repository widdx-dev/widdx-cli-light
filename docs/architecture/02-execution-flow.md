# Execution Flow — Step by Step

## Single Request Flow (WebSocket)

```
1. Browser → WebSocket /ws/chat
2. websocket_chat() — scripts/web/server.py:742
3. ChatHandler.chat_stream() — scripts/web/chat.py:289
4. Thread spawn: _run()
   │
5. Build context from 7 sources:
   ├─ StateManager.get_full_context()
   ├─ DecisionLayer.get_context_for_prompt()
   ├─ KG.get_context_snippet()
   ├─ ADR.get_context_for_prompt()
   ├─ Memory.search_active()
   ├─ SelfImprove.suggest()
   └─ ProjectDocs (PLAN/DESIGN/TASKS/ROADMAP)
   │
6. brain.process(user_input, messages)
   ├─ 1. ANALYZE  → TaskType + confidence
   ├─ 2. ROUTE    → ExecutionMode + tool filter
   ├─ 3. PLAN     → DecisionStep[]
   ├─ 4. EXECUTE  → AutonomousAgent.run()
   │   └─ Loop: provider.call → tool execution → repeat
   ├─ 4.5 VERIFY  → VerificationReport
   │   ├─ CodeRunner (runtime validation)
   │   ├─ SelfCorrection (classified fixes)
   │   └─ SelfImprove (record outcome)
   ├─ 5. FEEDBACK → ExecutionResult
   └─ Post-execution:
       ├─ VerifyLoop (fix+retest if criticals)
       ├─ ADR.record (if 3+ tools used)
       ├─ KG → Memory (project structure)
       └─ DocSync (drift detection)
   │
7. WebSocket events → browser rendering
8. Messages saved to SQLite (session persistence)
```

## Agent Autonomy Loop

```
AutonomousAgent.run(task)
  │
  ├─ Load TaskState (resume if active)
  ├─ Build messages with system prompt
  │
  ▼
  FOR iteration in 1..max_iter:
    │
    ├─ _call_provider_with_retry()
    │   ├─ Try primary provider (streaming)
    │   ├─ On fail → mark + backoff
    │   ├─ Try fallback (OpenCode Zen)
    │   └─ 3 retries max
    │
    ├─ If tool_calls:
    │   ├─ Step Lock (skip if already executed)
    │   ├─ Execute tool (write/bash/browser/spawn_agent)
    │   ├─ Auto-validate after write/edit
    │   └─ Save TaskState checkpoint
    │
    ├─ If no tool_calls + code blocks:
    │   └─ Code Extraction Fallback → write files
    │
    └─ If no tool_calls + no code:
        └─ Task complete → return summary
```

## ExpertTeam Flow

```
Task → COMPLEX classification
  │
  ├─ Orchestrator  ← LLM call #1
  ├─ Researcher    ← LLM call #2 (sees Orchestrator output)
  ├─ Coder         ← LLM call #3 (sees all previous)
  ├─ Reviewer      ← LLM call #4
  └─ Debugger      ← LLM call #5 (if errors found)
```

## Agent Tree (spawn_agent)

```
Root Agent
  ├─ spawn_agent("research X", "researcher")
  │   └─ Sub-Agent #1
  │       └─ spawn_agent("test Y", "tester")
  │           └─ Sub-Sub-Agent #2 → result
  └─ spawn_agent("build Z", "coder")
      └─ Sub-Agent #3 → result
```
