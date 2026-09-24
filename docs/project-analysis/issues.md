# WIDDX Nexus — Issues Register

## Critical Issues (Severity: P0)

### ISS-001: API Authentication Bypass via Empty Token
- **Severity**: CRITICAL
- **File**: `scripts/api_server.py`
- **Location**: API key validation logic (line 40, 53-56)
- **Root Cause**: When `WIDDX_API_KEY` env var is not set, `_API_KEY` defaults to `""`. Sending `Authorization: Bearer ` (empty token) passes `credentials.credentials != _API_KEY` check because both are `""`.
- **Affected Files**: All API endpoints
- **Suggested Fix**: Require non-empty `WIDDX_API_KEY` at startup; exit or reject all requests if not configured
- **Risk Level**: HIGH — full system access without authentication

### ISS-002: Command Injection via shell=True
- **Severity**: CRITICAL
- **Files**: `core/sandbox.py:641`, `core/isolation/container.py:200`, `core/validation/runner.py:155`
- **Location**: subprocess.Popen calls with shell=True
- **Root Cause**: Insufficient input sanitization before shell execution
- **Affected Files**: All command execution paths
- **Suggested Fix**: Use `shlex.split()` consistently, validate all command inputs
- **Risk Level**: HIGH — arbitrary command execution

~~### ISS-003: Undefined Variable in auto_commit.py~~ **FALSE POSITIVE**
- ~~**Severity**: HIGH~~
- ~~**File**: `core/auto_commit.py`~~
- ~~**Location**: `staged_diff()` method references `logger`~~
- ~~**Root Cause**: Missing import statement~~
- **Verdict**: `import logging` (line 12) and `logger = logging.getLogger("widdx.auto_commit")` (line 14) are both present. Issue does not exist. Remove from fix plan.

## High Issues (Severity: P1)

### ISS-004: No Request Size Limits
- **Severity**: HIGH
- **File**: `scripts/api_server.py`
- **Location**: POST `/api/chat` endpoint
- **Root Cause**: No body size validation
- **Affected Files**: All POST endpoints
- **Suggested Fix**: Add request body size limit (max 1MB)
- **Risk Level**: MEDIUM — memory exhaustion DoS

### ISS-005: In-Memory Rate Limiter Not Persistent
- **Severity**: HIGH
- **File**: `scripts/web/server.py`
- **Location**: `_ratelimit_store` dictionary
- **Root Cause**: Rate limit state resets on server restart
- **Affected Files**: Rate-limited endpoints
- **Suggested Fix**: Use Redis or database-backed rate limiting
- **Risk Level**: LOW-MEDIUM — temporary bypass

### ISS-006: CORS Too Permissive in Development
- **Severity**: HIGH
- **File**: `scripts/api_server.py`
- **Location**: CORS middleware configuration
- **Root Cause**: Development-friendly defaults may be too open
- **Affected Files**: All cross-origin requests
- **Suggested Fix**: Restrict to specific origins in production
- **Risk Level**: MEDIUM — cross-origin abuse

### ISS-007: Docker Container Runs as Root
- **Severity**: HIGH
- **File**: `Dockerfile`
- **Location**: No USER directive
- **Root Cause**: Default Docker behavior
- **Affected Files**: Containerized deployment
- **Suggested Fix**: Add `USER nonroot` directive
- **Risk Level**: MEDIUM — container escape impact

~~### ISS-008: GitHub Webhook Without Secret Validation~~ **FALSE POSITIVE**
- ~~**Severity**: HIGH~~
- ~~**File**: `github-app/app.py`~~
- ~~**Location**: Webhook handler~~
- ~~**Root Cause**: Missing `WEBHOOK_SECRET` environment variable check~~
- **Verdict**: `verify_webhook()` at line 204-212 properly validates HMAC-SHA256 signatures. `WEBHOOK_SECRET` is checked at startup (line 44) and in every webhook request (line 206-208). `hmac.compare_digest()` provides timing-safe comparison. Remove from fix plan.

## Medium Issues (Severity: P2)

### ISS-009: Permission Default Too Permissive
- **Severity**: MEDIUM
- **File**: `core/permissions.py`
- **Location**: `PermissionLevel.PERMISSIVE` default
- **Root Cause**: Backward compatibility decision
- **Affected Files**: All tool executions
- **Suggested Fix**: Consider defaulting to NORMAL level
- **Risk Level**: LOW — accidental destructive operations

### ISS-010: Skill Loader Executes Arbitrary Code
- **Severity**: MEDIUM
- **File**: `core/skills.py`
- **Location**: Skill loading mechanism
- **Root Cause**: Skills loaded via `exec_module()` can contain arbitrary Python
- **Affected Files**: Skill system
- **Suggested Fix**: Implement skill sandboxing or code signing
- **Risk Level**: MEDIUM — supply chain attack vector

### ISS-011: OAuth Token Storage in Plaintext
- **Severity**: MEDIUM
- **File**: `core/config/keychain.py`
- **Location**: API key storage
- **Root Cause**: Environment variables are plaintext
- **Affected Files**: All provider integrations
- **Suggested Fix**: Use OS keychain or encrypted storage
- **Risk Level**: LOW — requires local access

### ISS-012: MCP Filesystem Access Beyond Project
- **Severity**: MEDIUM
- **File**: `core/mcp/client.py`
- **Location**: MCP server file access
- **Root Cause**: Insufficient path restriction
- **Affected Files**: MCP integrations
- **Suggested Fix**: Enforce project directory restriction
- **Risk Level**: LOW — requires MCP server compromise

### ISS-013: No HTTPS Enforcement
- **Severity**: MEDIUM
- **File**: `scripts/web/server.py`
- **Location**: Server startup
- **Root Cause**: HTTP-only by default
- **Affected Files**: Web UI deployment
- **Suggested Fix**: Add HTTPS redirect or TLS configuration
- **Risk Level**: LOW — requires network access

### ISS-014: Error Messages May Leak Internals
- **Severity**: MEDIUM
- **Files**: Various exception handlers
- **Location**: `except Exception as e` blocks
- **Root Cause**: Exception messages may contain file paths or stack traces
- **Affected Files**: All error handling paths
- **Suggested Fix**: Sanitize error messages before returning to user
- **Risk Level**: LOW — information disclosure

### ISS-015: Deprecated Modules Still in Codebase
- **Severity**: MEDIUM
- **Files**: `core/project_structure.py`, `core/project_context.py`
- **Location**: Module-level deprecation warnings
- **Root Cause**: Backward compatibility
- **Affected Files**: Tests only
- **Suggested Fix**: Remove after updating tests
- **Risk Level**: LOW — code maintenance

## Low Issues (Severity: P3)

### ISS-016: Inconsistent Error Handling Patterns
- **Severity**: LOW
- **Files**: Various
- **Location**: Exception handling blocks
- **Root Cause**: Mixed patterns (bare except, except Exception, except SpecificError)
- **Affected Files**: Throughout codebase
- **Suggested Fix**: Standardize error handling patterns
- **Risk Level**: LOW — code quality

### ISS-017: Missing Type Hints in Some Modules
- **Severity**: LOW
- **Files**: Various older modules
- **Location**: Function signatures
- **Root Cause**: Incomplete type annotation
- **Affected Files**: core/memory.py, core/session_v2.py, etc.
- **Suggested Fix**: Add type hints incrementally
- **Risk Level**: LOW — code quality

### ISS-018: Debug Script Uses Fragile Monkey-Patch
- **Severity**: LOW
- **File**: `_debug_brain.py`
- **Location**: Monkey-patches `UnifiedIntelligenceLayer._resolve_executor`
- **Root Cause**: Overrides staticmethod at runtime with debug wrapper
- **Affected Files**: UIL Brain routing logic
- **Suggested Fix**: Replace monkey-patch with proper debug hook or logging configuration
- **Risk Level**: LOW — developer-only utility

### ISS-019: Inconsistent Naming Conventions
- **Severity**: LOW
- **Files**: Various
- **Location**: Function and variable names
- **Root Cause**: Mixed naming styles (snake_case, camelCase in some places)
- **Affected Files**: Throughout codebase
- **Suggested Fix**: Standardize on snake_case for Python
- **Risk Level**: LOW — code readability

### ISS-020: No Input Validation on Some Endpoints
- **Severity**: LOW
- **File**: `scripts/web/server.py`
- **Location**: Several GET endpoints
- **Root Cause**: Trust client-provided query parameters
- **Affected Files**: Query parameter handling
- **Suggested Fix**: Add input validation for all parameters
- **Risk Level**: LOW — edge case exploits

### ISS-021: Logging Sensitive Data
- **Severity**: LOW
- **Files**: Various logging statements
- **Location**: Logger calls with user input
- **Root Cause**: Insufficient log sanitization
- **Affected Files**: All logging paths
- **Suggested Fix**: Sanitize sensitive data before logging
- **Risk Level**: LOW — credential exposure in logs

### ISS-022: Missing Graceful Shutdown
- **Severity**: LOW
- **Files**: Various background threads
- **Location**: Thread cleanup on exit
- **Root Cause**: No shutdown hook registration
- **Affected Files**: All daemon threads
- **Suggested Fix**: Add signal handlers for graceful shutdown
- **Risk Level**: LOW — resource cleanup

### ISS-023: No Database Migrations
- **Severity**: LOW
- **File**: `core/database.py`
- **Location**: Schema creation
- **Root Cause**: Schema changes may break existing data
- **Affected Files**: SQLite database
- **Suggested Fix**: Implement migration system
- **Risk Level**: LOW — data loss on schema changes

## Summary by Severity

| Severity | Count | Priority |
|----------|-------|----------|
| CRITICAL (P0) | 2 | Fix immediately |
| HIGH (P1) | 4 | Fix before release |
| MEDIUM (P2) | 7 | Fix in next sprint |
| LOW (P3) | 8 | Fix when convenient |
| **Total** | **21** | |
