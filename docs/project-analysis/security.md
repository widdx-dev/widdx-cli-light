# WIDDX Nexus — Security Audit

## Critical Issues (Severity: HIGH)

### SEC-01: API Server Authentication
- **File**: `scripts/api_server.py` / `scripts/web/server.py`
- **Issue**: `WIDDX_API_KEY` check is bypassable — env var check falls back to auto-generated key
- **Impact**: Unauthorized access to chat, memory, session management
- **Evidence**: API key validation uses `os.environ.get("WIDDX_API_KEY")` with fallback
- **Risk**: HIGH — allows full system access

### SEC-02: shell=True in Sandbox
- **File**: `core/sandbox.py:641`, `core/isolation/container.py:200`, `core/validation/runner.py:155`
- **Issue**: Multiple locations use `shell=True` with subprocess
- **Impact**: Command injection if user input reaches shell commands
- **Mitigation**: `shlex.split()` used in some paths, but not all
- **Risk**: HIGH — potential command injection

### SEC-03: GitHub Webhook Without Secret
- **File**: `github-app/app.py`
- **Issue**: Webhook handler accepts requests without `WEBHOOK_SECRET` validation
- **Impact**: Any external request can trigger analysis
- **Risk**: HIGH — unauthorized code analysis triggers

## High Issues (Severity: HIGH-MEDIUM)

### SEC-04: CORS Configuration
- **File**: `scripts/api_server.py`
- **Issue**: CORS may be too permissive in development
- **Mitigation**: Configurable via `WIDDX_CORS_ORIGINS` env var
- **Risk**: MEDIUM — cross-origin request abuse

### SEC-05: OAuth Token Storage
- **File**: `core/config/keychain.py`
- **Issue**: API keys stored in environment variables (plaintext)
- **Mitigation**: PBKDF2 + XOR + salt encryption implemented for some tokens
- **Risk**: MEDIUM — plaintext key exposure

### SEC-06: MCP Filesystem Access
- **File**: `core/mcp/client.py`
- **Issue**: MCP servers can access filesystem beyond project directory
- **Mitigation**: Path restrictions implemented
- **Risk**: MEDIUM — unauthorized file access

### SEC-07: Docker Root Execution
- **File**: `Dockerfile`
- **Issue**: Container runs as root (no `USER` directive)
- **Impact**: If container is compromised, attacker has root access
- **Risk**: MEDIUM — container escape impact

## Medium Issues (Severity: MEDIUM)

### SEC-08: Permission Default
- **File**: `core/permissions.py`
- **Issue**: Default permission level is `PERMISSIVE` — all tools auto-allowed
- **Impact**: No user confirmation for dangerous operations
- **Risk**: MEDIUM — accidental destructive operations

### SEC-09: Skill Loader Code Execution
- **File**: `core/skills.py`
- **Issue**: Skills loaded via `exec_module()` can execute arbitrary code
- **Impact**: Malicious skill file = full system compromise
- **Risk**: MEDIUM — supply chain attack vector

### SEC-010: API Request Size
- **File**: `scripts/api_server.py`
- **Issue**: No request body size limit on `/api/chat`
- **Impact**: Memory exhaustion via large payloads
- **Risk**: MEDIUM — denial of service

### SEC-011: Rate Limiting
- **File**: `scripts/web/server.py`
- **Issue**: Rate limiter uses in-memory store (resets on restart)
- **Impact**: Rate limits not persistent across restarts
- **Risk**: LOW-MEDIUM — temporary bypass

## Low Issues (Severity: LOW)

### SEC-012: Error Message Leaking
- **File**: Various `except Exception as e` blocks
- **Issue**: Some error messages may expose internal paths or stack traces
- **Impact**: Information disclosure
- **Risk**: LOW

### SEC-013: Logging Sensitive Data
- **File**: Various logging statements
- **Issue**: API keys, tokens may appear in log files
- **Impact**: Credential exposure in logs
- **Risk**: LOW

### SEC-014: Proxy Credential Exposure
- **File**: `core/proxy.py`
- **Issue**: Free proxies may log or intercept API requests
- **Impact**: API key exposure through proxy
- **Risk**: LOW — proxies are optional

## Security Features Implemented

| Feature | Status | Location |
|---------|--------|----------|
| API Authentication | ✅ Implemented | `scripts/api_server.py` — Bearer token |
| Rate Limiting | ✅ Implemented | `scripts/api_server.py` — 60 req/min sliding window |
| CORS Restriction | ✅ Implemented | Configurable via env var |
| OAuth Token Encryption | ✅ Implemented | PBKDF2 + XOR + salt in `keychain.py` |
| Sandbox Isolation | ✅ Implemented | `shlex.split()` + `shell=False` in main paths |
| MCP Filesystem Restriction | ✅ Implemented | Path validation in `mcp/client.py` |
| Dangerous Pattern Blocking | ✅ Implemented | Regex patterns in `isolation/policy.py`, `core/tools/security.py` (80+ dangerous patterns) |
| GitHub Webhook Validation | ✅ Implemented | `github-app/app.py:204-212` — HMAC-SHA256 with `compare_digest()` |
| Permission Levels | ✅ Implemented | 4 levels in `permissions.py` |

## Recommendations

1. **Add request size limits** to all API endpoints (max 1MB)
2. **Add CSRF protection** for web UI endpoints
3. **Implement persistent rate limiting** (Redis or database-backed)
4. **Add skill code signing** or sandboxing for skill execution
5. **Run Docker containers as non-root** user
6. **Add input sanitization** for all user-provided content
7. **Implement audit logging** for sensitive operations
8. **Add HTTPS enforcement** for production deployment
