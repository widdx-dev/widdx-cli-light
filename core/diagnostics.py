"""Diagnostics — collect and surface silent/runtime errors.

All those ``logger.debug("...skipped: %s", e)`` calls and
``except Exception: pass`` blocks hide real failures.
This module gives you visibility into them.

Usage:
    from core.diagnostics import error_collector
    error_collector.enable()          # start collecting
    # ... run your code ...
    errors = error_collector.report() # see what failed silently
"""

import time
import threading
from collections import defaultdict


class ErrorCollector:
    """Intercepts logging calls and collects errors in-memory.

    Does NOT change program behaviour — just records what goes wrong.
    """

    def __init__(self):
        self._errors: list[dict] = []
        self._counts: defaultdict = defaultdict(int)
        self._enabled = False
        self._lock = threading.Lock()
        self._original_loggers: dict = {}

    # ── Public API ──────────────────────────────────────

    def enable(self, max_errors: int = 100):
        """Start collecting errors. Safe to call multiple times."""
        if self._enabled:
            return
        self._enabled = True
        self._max = max_errors

        # Patch Python's logging to intercept warnings and errors
        import logging
        self._original_loggers.clear()

        # Hook into existing loggers
        for name in ("widdx", "widdx.tui", ""):
            logger = logging.getLogger(name)
            self._original_loggers[name] = logger
            logger.addFilter(self._filter)

    def disable(self):
        """Stop collecting."""
        self._enabled = False
        for name, logger in self._original_loggers.items():
            logger.removeFilter(self._filter)

    def record(self, source: str, error: str, detail: str = ""):
        """Manually record an error (for bare except blocks)."""
        if not self._enabled:
            return
        with self._lock:
            if len(self._errors) >= self._max:
                return
            key = f"{source}:{error[:80]}"
            self._counts[key] += 1
            self._errors.append({
                "source": source,
                "error": error,
                "detail": detail,
                "time": time.time(),
                "count": self._counts[key],
            })

    def report(self, clear: bool = False) -> dict:
        """Return structured report of all collected errors."""
        with self._lock:
            errors = list(self._errors)
            counts = dict(self._counts)
            if clear:
                self._errors.clear()
                self._counts.clear()
        return {
            "total": len(errors),
            "unique": len(counts),
            "top": sorted(counts.items(), key=lambda x: -x[1])[:20],
            "recent": errors[-20:],
        }

    def report_text(self, clear: bool = False) -> str:
        """Return human-readable error report."""
        r = self.report(clear)
        if r["total"] == 0:
            return "[dim]No silent errors collected. (Run with --debug or enable error_collector)[/]"

        lines = [f"[bold #f5a623]Silent Errors: {r['total']} total, {r['unique']} unique[/]\n"]
        lines.append("[bold]Top errors:[/]")
        for key, cnt in r["top"][:10]:
            lines.append(f"  [dim]{cnt}x[/] [bold]{key.split(':')[0]}[/]: {key.split(':')[1][:100]}")
        if r["recent"]:
            lines.append(f"\n[bold]Most recent {len(r['recent'])}:[/]")
            for e in r["recent"][-5:]:
                lines.append(f"  [{e['source']}] {e['error'][:120]}")
        return "\n".join(lines)

    # ── Internal ────────────────────────────────────────

    def _filter(self, record):
        """logging.Filter — intercept WARNING and ERROR level messages."""
        if record.levelno >= 30:  # WARNING or above
            self.record(
                source=record.name or "logger",
                error=record.getMessage(),
                detail=f"{record.pathname}:{record.lineno}",
            )
        return True  # always allow the record through


# ── Decorator for catching bare excepts ────────────────

def catch_silent(source: str):
    """Decorator that records any exception silently caught by a function.

    Usage:
        @catch_silent("my_module")
        def my_function():
            try:
                ...
            except Exception:
                logger.debug("Exception suppressed (line 128)")  # previously silent
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_collector.record(
                    source=source,
                    error=str(e),
                    detail=f"{func.__name__} in {func.__code__.co_filename}:{func.__code__.co_firstlineno}",
                )
                raise  # re-raise so original behaviour is preserved
        return wrapper
    return decorator


# ── Singleton ──────────────────────────────────────────

error_collector = ErrorCollector()


# ── Quick audit: scan codebase for silent error patterns ─

def audit_silent_errors(root_dir: str | None = None) -> dict:
    """Scan Python files for common silent-error patterns.

    Returns counts of:
      - bare except: / pass
      - except Exception: ... logger.debug
      - except Exception as e: ... pass
    """
    from pathlib import Path
    import re

    root = Path(root_dir) if root_dir else Path.cwd()
    patterns = {
        "bare_except_pass": re.compile(r'except\s*:.*\bpass\b'),
        "except_exception_log": re.compile(r'except\s+Exception\s+as\s+\w+:\s*\n\s+logger\.(debug|warning)'),
        "except_exception_pass": re.compile(r'except\s+Exception\s*\w*:.*\bpass\b'),
        "except_continue": re.compile(r'except\s+.*:\s*\n\s+continue'),
    }
    counts = {k: 0 for k in patterns}
    files_found = []

    for py_file in root.rglob("*.py"):
        if any(p in str(py_file) for p in ("__pycache__", "node_modules", ".git", "test_")):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            found_any = False
            loc = {}
            for name, pat in patterns.items():
                matches = pat.findall(text)
                if matches:
                    counts[name] += len(matches)
                    loc[name] = len(matches)
                    found_any = True
            if found_any:
                files_found.append({"file": str(py_file.relative_to(root)), "loc": loc})
        except Exception as e:
            import logging
            logging.getLogger("widdx.diagnostics").warning("audit_silent_errors scan error: %s", e)

    return {"counts": counts, "files": files_found}
