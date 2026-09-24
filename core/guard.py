"""Dangerous Command Guard — Prevent destructive shell commands.

Blocks or warns about commands that could destroy data, compromise
the system, or perform irreversible operations.

Architecture:
  CommandGuard   — checks commands against block/deny patterns
  GuardResult    — (safe, warn, block) with explanation

Usage:
    from core.guard import guard

    result = guard.check("rm -rf /home/user/project")
    if result.blocked:
        print(f"BLOCKED: {result.reason}")

    # Force override (user explicitly approved)
    result = guard.check("rm -rf /tmp/build", force=True)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Guard Result
# ---------------------------------------------------------------------------

@dataclass
class GuardResult:
    blocked: bool = False
    warn: bool = False
    reason: str = ""
    original_command: str = ""
    sanitized_command: str = ""


# ---------------------------------------------------------------------------
# Blocked Patterns — commands that should NEVER run
# ---------------------------------------------------------------------------

# Patterns that match destructive system commands
_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    # Fork bombs
    (r":\(\)\s*\{.+:\|:&\s*\};:", "Fork bomb detected"),
    # Recursive delete on root / system dirs
    (r"\brm\s+.*-rf\s+(/|/home|/etc|/usr|/var|/boot|/sys|/proc|/dev|C:\\)",
     "Recursive delete on system directory — blocked"),
    # Format / mkfs
    (r"\b(mkfs|format|fdisk|dd\s+if=)\b",
     "Disk formatting / raw write command — blocked"),
    # Chmod 777 on system dirs
    (r"\bchmod\s+.*777\s+(/|/etc|/usr|/bin)",
     "chmod 777 on system directory — blocked"),
    # > /dev/sda or similar device overwrite
    (r">\s*/dev/[sh]d[a-z]", "Redirect to raw device — blocked"),
    # Fork bomb variation
    (r"%0\|%0", "Fork bomb variation — blocked"),
    # Unconditional curl-to-bash without inspection
    # (allow but warn — handled in _WARN_PATTERNS)
]


# Patterns that should trigger a WARNING
_WARN_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\b", "Recursive delete — verify target path"),
    (r"\bgit\s+reset\s+--hard\b", "Git hard reset — uncommitted work will be lost"),
    (r"\bgit\s+push\s+.*(--force|--force-with-lease)\b", "Force push — overwrites remote history"),
    (r"\bdrop\s+table\b", "DROP TABLE — irreversible data loss"),
    (r"\bdrop\s+database\b", "DROP DATABASE — all data will be deleted"),
    (r"\bformat\s+(c:|d:|e:|f:)", "Windows drive format — blocked on system drives"),
    (r"\bchmod\s+777\b", "chmod 777 — world-writable permissions"),
    (r"\bcurl\s+.*\|.*(sh|bash|python)\b", "curl-pipe-shell — inspect script before running"),
    (r"\bwget\s+.*-O\s*-\s*\|.*(sh|bash)\b", "wget-pipe-shell — inspect script before running"),
    (r"\bshutdown\b", "System shutdown — verify before proceeding"),
    (r"\breboot\b", "System reboot — verify before proceeding"),
    (r"\bdel\s+/[fq].*C:\\Windows", "Windows system file deletion"),
]

# Unsafe directories for destructive operations
_UNSAFE_DIRS = [
    "/", "/root", "/home", "/etc", "/usr", "/var", "/boot", "/sys", "/proc", "/dev",
    "C:\\", "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    os.path.expanduser("~"),
]


# ---------------------------------------------------------------------------
# Command Guard
# ---------------------------------------------------------------------------

class CommandGuard:
    """Check shell commands for dangerous patterns before execution."""

    def __init__(self, working_dir: str | Path | None = None):
        self._cwd = Path(working_dir) if working_dir else Path.cwd()

    def check(self, command: str, force: bool = False) -> GuardResult:
        """Check a command. Returns GuardResult with verdict."""
        cmd = command.strip()
        result = GuardResult(original_command=cmd, sanitized_command=cmd)

        if force:
            return result  # explicit override

        # 1. Block patterns — never allow
        for pattern, reason in _BLOCKED_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                result.blocked = True
                result.reason = reason
                return result

        # 2. Warn patterns — allow but warn
        for pattern, reason in _WARN_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                result.warn = True
                result.reason = reason
                break

        # 3. Path traversal: delete operations targeting unsafe dirs
        if self._is_destructive_path_op(cmd):
            result.blocked = True
            result.reason = "Destructive operation targeting unsafe directory"

        return result

    def _is_destructive_path_op(self, cmd: str) -> bool:
        """Check if a destructive command targets an unsafe directory."""
        # Extract paths from rm/del/rmdir commands — absolute AND relative
        destructive = re.findall(
            r'(?:rm|del|rmdir|rd)\s+.*?([/~]\S+|(?:[A-Z]:\\\S+)|(?:\.\.?(?:[/\\]\S+)+))',
            cmd, re.IGNORECASE,
        )
        for path_str in destructive:
            try:
                # Resolve relative paths against CWD
                resolved = (self._cwd / Path(path_str)).resolve()
                for unsafe in _UNSAFE_DIRS:
                    unsafe_path = Path(unsafe).resolve()
                    if resolved == unsafe_path or unsafe_path in resolved.parents:
                        return True
            except Exception:
                continue
        return False

    def is_safe(self, command: str) -> bool:
        """Quick check: is this command definitely safe?"""
        result = self.check(command)
        return not result.blocked


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

guard = CommandGuard()
