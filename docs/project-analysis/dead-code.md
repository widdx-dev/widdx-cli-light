# WIDDX Nexus — Dead Code Analysis

## Confirmed Dead Code

### 1. `core/project_structure.py` — DEPRECATED
- **Severity**: Low
- **Status**: Emits `DeprecationWarning` on import
- **Reason**: Superseded by `core/project/scanner.py`
- **Impact**: `ProjectStructureAnalyzer` is only used in tests
- **Action**: Safe to remove after updating tests

### 2. `core/project_context.py` — DEPRECATED  
- **Severity**: Low
- **Status**: Not imported by any production code
- **Used only in**: `tests/test_project_context.py`
- **Impact**: `ProjectContextManager` and `get_project_context()` are unused
- **Action**: Safe to remove after updating tests

### 3. `core/auto_commit.py` — PARTIALLY DEAD
- **Severity**: Medium
- **Status**: `AutoCommitManager` is instantiated but `staged_diff()` has a bug (references undefined `logger`)
- **Used in**: `tests/test_auto_commit.py` only
- **Impact**: Auto-commit functionality exists but is not integrated into the main pipeline
- **Action**: Either integrate into main flow or mark as deprecated

### 4. `core/web_launcher.py` — MINIMAL
- **Severity**: Low
- **Status**: Single function, thin wrapper
- **Impact**: Negligible
- **Action**: Keep for backward compatibility

### 5. `scripts/api_server.py` (root) — REDUNDANT
- **Severity**: Low
- **Status**: Root-level file that just imports from `scripts.api_server`
- **Impact**: Duplicate entry point
- **Action**: Keep for backward compatibility

### 6. Root-level wrapper files
- `main.py` → delegates to `scripts/main.py`
- `api_server.py` → delegates to `scripts/api_server.py`  
- `run_textual.py` → delegates to `scripts/run_textual.py`
- **Status**: Entry point shims, not dead code but thin wrappers

## Unused Functions/Methods

| Function | File | Issue |
|----------|------|-------|
| `AutoCommitManager.staged_diff()` | auto_commit.py | References undefined `logger` — will crash |
| `ProjectStructureAnalyzer.get_file_extensions()` | project_structure.py | Deprecated, no callers |
| `ProjectStructureAnalyzer.search_files()` | project_structure.py | Deprecated, no callers |
| `ProjectContextManager.get_file_content()` | project_context.py | Deprecated, no callers |
| `ProjectContextManager.refresh()` | project_context.py | Deprecated, no callers |

## Unused Imports (Potential)

Based on code analysis, these imports may be unused in their files:
- `core/chat.py`: `from datetime import datetime` — used in `_ts()` 
- `core/commands.py`: Some imports only used in specific branches

## Dead Test Files

| Test File | Issue |
|-----------|-------|
| `tests/test_project_context.py` | Tests deprecated module |
| `tests/test_project_validate.py` | Tests deprecated module |

## Summary

| Category | Count | Severity |
|----------|-------|----------|
| Deprecated modules | 2 | Low |
| Partially dead modules | 1 | Medium |
| Redundant entry points | 3 | Low |
| Unused functions | 5 | Low |
| Dead test files | 2 | Low |
