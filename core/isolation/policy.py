"""Isolation policy — determines what's allowed at each permission level.

Replaces pure regex-based dangerous pattern blocking with
container-enforced isolation at appropriate permission levels.

4 permission levels:
    0 (silent):  read-only, no execution, no containers
    1 (strict):  read + safe write, containers with no network
    2 (normal):  full tools, containers with restricted network
    3 (permissive): full access, less restrictive isolation
"""

from __future__ import annotations
import re
import logging

from .profiles import get_profile, resolve_profile

logger = logging.getLogger("widdx.isolation.policy")

# ── Legacy regex patterns (still used as first line of defense) ──

_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r'\brm\s+-rf\s+/', "recursive force delete from root"),
    (r'>\s*/dev/sd[a-z]', "raw disk write"),
    (r'\bdd\s+if=', "raw disk copy"),
    (r'\bmkfs\.\w+\b', "filesystem format"),
    (r'\bchmod\s+777\b', "world-writable permissions"),
    (r'\bgit\s+push\s+--force\b', "force push"),
    (r'\bshutdown\b', "system shutdown"),
    (r'\breboot\b', "system reboot"),
    (r'\bcurl\b.*\|\s*(sh|bash)', "pipe download to shell"),
    (r'\bwget\b.*\|\s*(sh|bash)', "pipe download to shell"),
    (r'\bkill\s+-9\s+1\b', "kill init"),
    (r'\bdocker\s+run\s+--privileged\b', "privileged container"),
]


class IsolationPolicy:
    """Enforces isolation policy based on permission level.

    At level 0-1: blocks dangerous patterns entirely.
    At level 2-3: allows with container isolation.
    """

    def __init__(self, permission_level: int = 2):
        """Initialize policy engine.

        Args:
            permission_level: 0=silent, 1=strict, 2=normal, 3=permissive
        """
        self.permission_level = permission_level

    def can_execute(self, command: str,
                    profile_name: str = "bash",
                    task_type: str = "unknown") -> tuple[bool, str]:
        """Check if a command can be executed at current permission level.

        Args:
            command: The command to check
            profile_name: Isolation profile to use
            task_type: Task type for profile resolution

        Returns:
            (allowed, reason) tuple.
        """
        # ── Level 0: read only ──
        if self.permission_level == 0:
            read_only = {"ls", "cat", "echo", "head", "tail", "wc",
                         "find", "grep", "which", "pwd", "date",
                         "git status", "git log", "git diff"}
            cmd_lower = command.lower().strip()
            if not any(cmd_lower.startswith(ro) for ro in read_only):
                return False, "Permission level 0: read-only commands only"
            return True, "allowed (read-only)"

        # ── Level 1-2: block dangerous patterns at regex level ──
        if self.permission_level <= 2:
            for pattern, risk_desc in _DANGEROUS_PATTERNS:
                if re.search(pattern, command, re.IGNORECASE):
                    return False, f"Blocked: {risk_desc}"

        # ── All levels: resolve isolation profile ──
        profile = get_profile(profile_name)
        if profile and profile.allowed_commands:
            cmd_name = command.split()[0] if command.split() else ""
            if cmd_name and cmd_name not in profile.allowed_commands:
                if self.permission_level <= 1:
                    return False, (
                        f"Command '{cmd_name}' not in allowed list "
                        f"for profile '{profile_name}'"
                    )
                logger.warning(
                    "Command '%s' not in allowed list for '%s' — "
                    "allowed at permission level %d",
                    cmd_name, profile_name, self.permission_level,
                )

        return True, f"allowed (level {self.permission_level}, profile {profile_name})"

    def resolve_profile_for_task(self, task_type: str,
                                  features: list[str] | None = None) -> str:
        """Get the appropriate isolation profile for a task."""
        # At strict levels, always use the most restrictive profile
        if self.permission_level <= 1:
            return "bash"

        return resolve_profile(task_type, features)

    def should_block_execution(self, command: str) -> bool:
        """Quick check: should this command be blocked entirely?"""
        if self.permission_level >= 3:
            return False  # permissive allows all

        for pattern, _ in _DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    def to_dict(self) -> dict:
        """Export policy configuration."""
        return {
            "permission_level": self.permission_level,
            "blocked_patterns_count": len(_DANGEROUS_PATTERNS),
        }


# Module-level singleton
_policy: IsolationPolicy | None = None


def get_policy(permission_level: int | None = None) -> IsolationPolicy:
    """Get or create the isolation policy."""
    global _policy
    if _policy is None or permission_level is not None:
        _policy = IsolationPolicy(permission_level if permission_level is not None else 2)
    return _policy
