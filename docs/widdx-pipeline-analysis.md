# WIDDX Nexus — Real Pipeline Gap Analysis

> Analysis based on direct source code review of `chat-tool.zip`  
> Date: 2026-06-26

---

## Project Overview

WIDDX Nexus is an orchestration framework for LLM-powered coding assistance. It wraps multiple LLM providers behind a unified interface, exposes three UIs (CLI, TUI, Web), and includes sandbox, validation, and isolation subsystems.

### Request Execution Path (UIL Brain Pipeline)

```
User Input
    │
    ▼
1. ANALYZE   (analyzer.py)    → Classify task type (13 types)
    │
    ▼
2. ROUTE     (router.py)      → Select execution mode
    │
    ▼
3. PLAN      (planner.py)     → Decompose into ordered steps
    │
    ▼
4. EXECUTE   (brain.py)       → Run via agent / expert_team / direct_tool
    │
    ▼
4.5 VERIFY   (verifier.py)    → Quality check  ⚠️  static analysis only
    │
    ▼
5. FEEDBACK  (brain.py)       → Cost and tool-use tracking
    │
    ▼
6. KNOWLEDGE (knowledge.py)   → Learn from execution for future routing
```

---

## Discovered Gaps — Ordered by Priority

---

### 🔴 CRITICAL #1 — API Authentication Bypass

**File:** `scripts/api_server.py` — lines 53–56  
**Category:** Security (ISS-001 in project issue register)

#### The Problem

The startup code prints a warning when `WIDDX_API_KEY` is missing, but the
authentication logic is still broken. When `_API_KEY = ""` and the client
sends an empty Bearer token (`credentials.credentials = ""`):

```python
# Current code — broken
credentials.credentials != _API_KEY
# "" != "" → False
# Result: authentication passes with no secret at all
```

The warning message says "REJECT all requests" — the code does not do that.

#### The Fix

```python
def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> None:
    # Reject everything if the key was never configured
    if not _API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Server not configured: WIDDX_API_KEY is not set."
        )
    # Normal token check
    if credentials is None or credentials.credentials != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
```

---

### 🔴 CRITICAL #2 — Default Permission Level = PERMISSIVE

**File:** `core/permissions.py` — line 36  
**Category:** Security + Code Quality (ISS-009 in project issue register)

#### The Problem

```python
# Current code — core/permissions.py:36
self._level = PermissionLevel.PERMISSIVE  # auto-allow everything
```

The default `PERMISSIVE` level means **every command executes automatically**
with no review or restriction. This is the root cause of the "AI produces
locally correct but globally wrong code" problem — nothing stops a destructive
or unintended execution from going through.

The `IsolationPolicy` in `core/isolation/policy.py` is well-designed and
already supports four levels:

| Level | Value | Effect |
|-------|-------|--------|
| `SILENT` | 0 | Read-only commands only |
| `STRICT` | 1 | Safe writes, no network |
| `NORMAL` | 2 | Full tools, restricted network |
| `PERMISSIVE` | 3 | Full access — **current default** |

`PermissionManager` ignores this hierarchy and hard-codes `PERMISSIVE`.

#### The Fix

```python
# core/permissions.py:36 — one-line change
self._level = PermissionLevel.NORMAL  # was PERMISSIVE
```

---

### 🔴 GAP #3 — CodeRunner Is Disconnected from the Pipeline

**Files:** `core/validation/runner.py` vs `core/uil/brain.py`  
**Category:** Code Quality + Technical Debt

#### The Problem

The project has a fully implemented `CodeRunner` class in
`core/validation/runner.py` that actually executes code and catches runtime
errors. However, the VERIFY step in `core/uil/brain.py` only calls
`verifier.py`, which performs **static analysis only** — it never runs the
code.

```
brain.py → verifier.py    ✅ checks syntax
brain.py → CodeRunner     ❌ not wired — class exists, nobody calls it
```

Direct consequence: code that passes the verifier because its syntax is valid
can still fail at runtime with errors that are never surfaced. This is the
exact pattern behind "AI produces code that works now but breaks later."

#### The Fix

In `core/uil/brain.py`, after the existing VERIFY step (line ~339), add
runtime validation for code tasks:

```python
# core/uil/brain.py — after line 339
if classification.task_type in (TaskType.CODE_WRITE, TaskType.CODE_MODIFY):
    from core.validation.runner import CodeRunner
    import re

    runner = CodeRunner(timeout_default=15)

    # Extract Python blocks from the generated output
    code_blocks = re.findall(r'```python\n(.*?)```', raw_text, re.DOTALL)

    for code in code_blocks:
        run_result = runner.run_python(code)
        if not run_result.success:
            # Surface the runtime error in the verification report
            from core.uil.contract import Finding, VerificationSeverity
            verification_report.findings.append(Finding(
                severity=VerificationSeverity.HIGH,
                message=f"Runtime error: {run_result.stderr[:300]}",
                category="runtime_validation"
            ))
```

---

### ⚠️ GAP #4 — AI Operates Without Project Context

**Files:** `core/repo_mapper.py` + `core/project_context.py` — unused in pipeline  
**Category:** Architecture Quality + Inconsistency

#### The Problem

In `core/uil/brain.py` there is no injection of `repo_map` or
`project_context` into the system prompt during planning or execution.

```python
# Search brain.py for: repo_map, project_context, system_prompt injection
# Result: nothing — the AI writes code with no knowledge of the project layout
```

Both modules exist and are ready:
- `core/repo_mapper.py` — builds a full dependency graph of the project
- `core/project_context.py` — aggregates project-wide structural context

Neither is called from the pipeline. This is the exact source of the
"AI understands parts, not the system" problem — it produces code that is
correct in isolation but conflicts with the rest of the codebase.

#### The Fix

In `core/uil/brain.py`, inject a compact project map before EXECUTE for all
code tasks:

```python
# core/uil/brain.py — add this helper method to UnifiedIntelligenceLayer
def _get_project_context_snippet(
    self, project_dir: str, max_tokens: int = 800
) -> str:
    """Returns a compact project map for injection into coding prompts."""
    try:
        from core.repo_mapper import RepoMapper
        mapper = RepoMapper(project_dir)
        repo_map = mapper.get_concise_map(max_tokens=max_tokens)
        return (
            "\n\n---\n"
            "Project structure (follow existing patterns and naming conventions):\n"
            f"{repo_map}\n"
            "---\n"
        )
    except Exception:
        return ""

# Then in the system prompt for code tasks:
system_prompt = base_system_prompt + self._get_project_context_snippet(project_dir)
```

---

## Priority Summary

| Priority | Gap | File | Impact | Effort |
|----------|-----|------|--------|--------|
| 1 | CodeRunner disconnected from pipeline | `core/uil/brain.py` | Prevents silent runtime failures | Medium |
| 2 | No project context injection | `core/uil/brain.py` | Prevents inconsistent code | Low |
| 3 | Default permission = PERMISSIVE | `core/permissions.py` | Prevents unintended execution | Very low (one line) |
| 4 | API auth bypass | `scripts/api_server.py` | Basic security hardening | Low |

---

## Mapping to AI-in-Large-Projects Problems

| Problem (from research) | Root cause in WIDDX | Recommended fix |
|------------------------|---------------------|-----------------|
| AI understands parts, not the system | No context injection in the pipeline | GAP #4 — wire repo_mapper |
| AI produces locally correct, globally wrong code | Verifier checks syntax only | GAP #3 — wire CodeRunner |
| AI creates technical debt fast | No runtime validation gate | GAP #3 — wire CodeRunner |
| Loss of control over execution | Default PERMISSIVE level | CRITICAL #2 — change default |
| Unintentional security vulnerabilities | API auth bypass | CRITICAL #1 — fix the check |

---

## Closing Note

The architectural foundation of WIDDX Nexus is solid. The existence of
`core/isolation/`, `core/validation/`, `core/sandbox.py`, and `core/uil/verifier.py`
reflects serious architectural thinking. The gaps found here are not design
flaws — they are **wiring gaps**: the right components exist but are not
connected to each other inside the pipeline. All four fixes above reuse what
is already built; nothing needs to be created from scratch.
