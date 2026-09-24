# WIDDX Nexus — Fix Plan

> Updated: 2026-06-25 | 15/15 fixes complete ✅ ALL DONE

## Recently Completed (Round 3 — Forensic Analysis Fixes)

| FIX | Issue | Status |
|-----|-------|--------|
| FIX-014 | Browser import could break ALL tools (CRITICAL) | ✅ DONE |
| FIX-015 | Provider now ABC with @abstractmethod | ✅ DONE |
| FIX-016 | Singleton audit — all 47 in use, none dead | ✅ VERIFIED |
| FIX-017 | Docstrings for create_provider() | ✅ DONE |

---

## Priority 1: Critical Security Fixes (Week 1)

### FIX-001: Strengthen API Authentication
- **Issue**: ISS-001 (API Auth Bypass via Empty Token)
- **Effort**: 2 hours
- **Files**: `scripts/api_server.py`
- **Changes**:
  1. Fail startup if `WIDDX_API_KEY` is empty/unset
  2. Reject requests with empty bearer token
  3. Return 401 for all missing/invalid auth
- **Testing**: Manual test with/without env var, test empty token

### FIX-002: Eliminate shell=True Usage
- **Issue**: ISS-002 (Command Injection)
- **Effort**: 4 hours
- **Files**: `core/sandbox.py`, `core/isolation/container.py`, `core/validation/runner.py`
- **Changes**:
  1. Replace `shell=True` with `shlex.split()` in all subprocess calls
  2. Add command input validation
  3. Add unit tests for injection attempts
- **Testing**: Run existing sandbox tests + new injection tests

## Priority 2: High Security Fixes (Week 2)

### FIX-003: Add Request Size Limits
- **Issue**: ISS-004 (No Request Size Limits)
- **Effort**: 1 hour
- **File**: `scripts/api_server.py`
- **Changes**:
  1. Add middleware to limit request body size (1MB max)
  2. Return 413 if exceeded
- **Testing**: Send oversized requests

### FIX-004: Docker Non-Root User
- **Issue**: ISS-007 (Docker Runs as Root)
- **Effort**: 30 minutes
- **File**: `Dockerfile`
- **Changes**:
  1. Add `RUN adduser --disabled-password --gecos "" appuser`
  2. Add `USER appuser`
  3. Adjust file permissions
- **Testing**: Build and run container

## Priority 3: Medium Improvements (Week 3-4)

### FIX-005: CORS Restriction
- **Issue**: ISS-006 (CORS Too Permissive)
- **Effort**: 1 hour
- **File**: `scripts/api_server.py`
- **Changes**:
  1. Default to localhost-only CORS
  2. Allow configuration via env var
  3. Document CORS settings
- **Testing**: Test cross-origin requests

### FIX-006: Error Message Sanitization
- **Issue**: ISS-014 (Error Messages Leak Internals)
- **Effort**: 3 hours
- **Files**: Various exception handlers
- **Changes**:
  1. Create `sanitize_error()` utility function
  2. Apply to all user-facing error responses
  3. Keep detailed errors in logs only
- **Testing**: Verify error messages don't contain paths

### FIX-007: Deprecated Module Cleanup
- **Issue**: ISS-015 (Deprecated Modules)
- **Effort**: 2 hours
- **Files**: `core/project_structure.py`, `core/project_context.py`
- **Changes**:
  1. Update tests to use new modules
  2. Remove deprecated modules
  3. Update imports in all files
- **Testing**: Run full test suite

## Priority 4: Low Priority Improvements (Month 2)

### FIX-008: Input Validation
- **Issue**: ISS-019 (Missing Input Validation)
- **Effort**: 4 hours
- **Files**: `scripts/web/server.py`
- **Changes**:
  1. Add Pydantic models for all endpoints
  2. Validate query parameters
  3. Add field validators
- **Testing**: Test with invalid inputs

### FIX-009: Logging Sanitization
- **Issue**: ISS-020 (Logging Sensitive Data)
- **Effort**: 2 hours
- **Files**: Various logging statements
- **Changes**:
  1. Create `sanitize_log()` utility
  2. Apply to sensitive data logging
  3. Redact API keys, tokens
- **Testing**: Verify logs don't contain secrets

### FIX-010: Type Hint Completion
- **Issue**: ISS-017 (Missing Type Hints)
- **Effort**: 8 hours
- **Files**: Various older modules
- **Changes**:
  1. Add type hints to public APIs
  2. Run mypy for verification
  3. Fix any type errors
- **Testing**: Run mypy with strict mode

### FIX-011: Naming Convention Standardization
- **Issue**: ISS-018 (Inconsistent Naming)
- **Effort**: 4 hours
- **Files**: Various
- **Changes**:
  1. Rename camelCase to snake_case
  2. Update all references
  3. Add to coding standards
- **Testing**: Run full test suite

## Effort Summary — ALL COMPLETE ✅

| Priority | Fixes | Status |
|----------|-------|--------|
| P1 (Critical) | 3 | ✅ Done |
| P2 (High) | 3 | ✅ Done |
| P3 (Medium) | 3 | ✅ Done |
| P4 (Low) | 4 | ✅ Done |
| Round 3 (Forensic) | 4 | ✅ Done |
| **Total** | **17** | **✅ COMPLETE** |

## Dependencies

```
FIX-001 (Auth) ──→ No dependencies
FIX-002 (shell=True) ──→ No dependencies
FIX-003 (auto_commit) ──→ No dependencies
FIX-004 (Request Size) ──→ FIX-001 (Auth)
FIX-005 (Docker) ──→ No dependencies
FIX-006 (Webhook) ──→ No dependencies
FIX-007 (CORS) ──→ FIX-001 (Auth)
FIX-008 (Error Sanitize) ──→ No dependencies
FIX-009 (Deprecated) ──→ No dependencies
FIX-010 (Input Validation) ──→ FIX-004 (Request Size)
FIX-011 (Log Sanitize) ──→ No dependencies
FIX-012 (Type Hints) ──→ No dependencies
FIX-013 (Naming) ──→ No dependencies
```

## Recommended Execution Order

1. **Week 1**: FIX-001, FIX-002, FIX-003 (Critical security + bug fix)
2. **Week 2**: FIX-004, FIX-005, FIX-006 (High security)
3. **Week 3**: FIX-007, FIX-008, FIX-009 (Medium improvements)
4. **Week 4+**: FIX-010, FIX-011, FIX-012, FIX-013 (Low priority)

## Testing Strategy

### Unit Tests
- Each fix should include unit tests
- Run affected test files after each fix
- Run full test suite after all fixes

### Integration Tests
- Test API endpoints with new validation
- Test sandbox with injection attempts
- Test Docker with non-root user

### Security Tests
- Penetration testing for auth bypass
- Command injection testing
- Input validation testing

## Rollback Plan

1. Keep git branches for each fix
2. Test in staging environment
3. Deploy to production with feature flags
4. Monitor error rates after deployment
5. Rollback if issues detected
