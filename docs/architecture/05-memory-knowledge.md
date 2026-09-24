# Memory & Knowledge Layer

## Memory Types

| Type | Storage | Lifetime | Usage |
|------|---------|----------|-------|
| **Long-term** | `~/.widdx/memory/*.md` + `.widdx/memory/*.md` | Forever | Facts, preferences, fixes |
| **Episodic** | SQLite (`widdx.db` → `messages` table) | Forever | Conversation history |
| **Short-term** | LLM context window | Per-request | Current conversation |

## Memory Versioning (4.0)

Every memory has frontmatter metadata:
```yaml
name: fix-sql-connection
version: 3
confidence: 0.85
status: active        # active | deprecated | superseded
created: 2026-06-26T10:00:00
last_validated: 2026-06-26T12:00:00
```

**API:**
- `search_active(query)` — excludes deprecated
- `deprecate(name, reason)` — marks as deprecated
- `validate(name)` — confirms still true, boosts confidence +0.1
- `cleanup_deprecated(days=90)` — removes old deprecated entries

## Memory Store

- **Global:** `~/.widdx/memory/` — shared across all projects
- **Project:** `<project>/.widdx/memory/` — project-specific

**Capabilities:**
- Markdown files with YAML frontmatter
- MEMORY.md index with one-line pointers
- Conflict detection: old versions saved as `.v{n}.old.md`
- Semantic search via VectorMemory (TF-IDF)
- MemoryLearner: auto-extracts facts from conversations

## KnowledgeGraph (4.0)

Builds a graph of the project: files → symbols → dependencies.

- **Nodes:** files, classes, functions
- **Edges:** imports, contains, depends_on
- **Query:** `kg.query("UserModel")` → find entity + connections
- **Path:** `kg.find_path("auth.py", "database.py")` → BFS shortest path
- **Context:** `kg.get_context_snippet()` → injects into system prompt

## ADR — Architecture Decision Records (4.0)

Prevents re-suggesting rejected solutions.

- `record(title, context, decision, alternatives, consequences)`
- `get_context_for_prompt()` → injected as `<architecture_decisions>`
- Stored in `.widdx/adr/`

## DocSync (4.0)

Detects drift between docs and code.

- `detect_drift()` → compares DESIGN.md references vs actual files
- `auto_update()` → archives old TASKS.md entries
- Runs after each brain execution

## TaskState (5.1)

Persists execution state for resume.

- `set_goal()` / `get_goal()`
- `add_step()` / `update_step()`
- `get_messages()` / `set_messages()` — checkpoint
- `get_agent_steps()` / `set_agent_steps()` — agent step persistence
- `is_active()` — checks for resumable state
- Atomic writes (`.tmp` + `os.replace`)

## StateManager (5.2)

Unifies all context sources into single coherent view.

`get_full_context(goal)` → combines:
1. Goal
2. TaskState (progress, steps)
3. KnowledgeGraph (project structure)
4. Memory (active facts)
5. ADR (decisions + rejected alternatives)
6. ProjectDocs (PLAN/DESIGN/TASKS/ROADMAP)
7. SelfImprove (learned rules)

Cached for 2 seconds to avoid rebuild on rapid calls.

## DecisionLayer (5.5)

Weighs all knowledge sources to evaluate suggestions.

```python
score = dl.evaluate("Use Redis for caching")
# → DecisionScore(score=0.44, blocked=False, components={adr:0.8, memory:0.3, kg:0.1, plan:0.6})
```

Weights: ADR(30%) + Memory(30%) + KG(20%) + Plan(20%).
Blocks suggestions that were explicitly rejected in ADR.
