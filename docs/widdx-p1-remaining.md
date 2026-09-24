# WIDDX Nexus — P1 Remaining Issues

> Sprint: Post-commit 9dec166  
> Date: 2026-06-26  
> Status: ✅ ALL 4 CLOSED — commit 12c94ec + follow-up

---

## Context

All 21 issues from the original register are now resolved. The 4 P1 issues
below were the last open items. All are deployment-facing fixes that
complete the security hardening of the project.

---

## ISS-004 — No Request Size Limit ✅ CLOSED

**Fix:** `_BodySizeMiddleware` in `scripts/api_server.py:192-207`.
Rejects requests > 1 MB with 413. Configurable via `WIDDX_MAX_BODY_BYTES`.

---

## ISS-005 — In-Memory Rate Limiter Resets on Restart ✅ CLOSED

**Fix:** Replaced in-memory dict with SQLite-backed storage in
`scripts/web/server.py:647-681`. Rate-limit state now survives restarts.

---

## ISS-006 — CORS Too Permissive ✅ CLOSED

**Fix:** CORS already restricted to localhost origins + limited methods/headers
in `scripts/api_server.py:183-190`. Configurable via `WIDDX_CORS_ORIGINS`.

---

## ISS-007 — Docker Container Runs as Root ✅ CLOSED

**Fix:** Dockerfile already has `USER widdx` at line 39 with `useradd` at line 37.

---

## Summary

| # | Issue | Fix | Commit |
|---|-------|-----|--------|
| ISS-004 | Body size limit | BodySizeMiddleware | 12c94ec |
| ISS-005 | Rate limiter persistence | SQLite-backed | follow-up |
| ISS-006 | CORS restriction | Already restricted | (pre-existing) |
| ISS-007 | Docker non-root | USER widdx | (pre-existing) |

**All 21 issues from the original register: CLOSED** ✅
