"""Isolation profiles — what each execution environment allows.

Each profile defines the security boundary for a type of execution:
- python: For running Python code (no network, read-only project)
- bash: For shell commands (no network, strict limits)
- browser: For Playwright/browser automation (internal network only)
- mcp: For MCP server processes (512MB, no network)
- trusted: For user-approved commands (full network, higher limits)
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class IsolationProfile:
    """Defines the isolation parameters for an execution environment."""
    name: str
    description: str = ""

    # Container settings
    image: str = "alpine:latest"
    memory: str = "256m"
    cpu: str = "1.0"
    timeout: int = 60

    # Network isolation
    network: str = "none"  # none | internal | restricted | full
    allowed_hosts: list[str] = field(default_factory=list)

    # Filesystem
    read_only: bool = True
    tmpfs: list[str] = field(default_factory=list)  # ["/tmp", "/home"]
    mounts: list[tuple[str, str, str]] = field(default_factory=list)
    # [(host_path, container_path, mode)]

    # Commands
    allowed_commands: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)

    # Resources
    max_processes: int = 50
    max_file_size_mb: int = 100


PROFILES: dict[str, IsolationProfile] = {
    "python": IsolationProfile(
        name="python",
        description="Python code execution — read-only project, no network",
        image="python:3.12-slim",
        memory="512m",
        cpu="1.0",
        timeout=30,
        network="none",
        read_only=True,
        tmpfs=["/tmp", "/home"],
        mounts=[
            ("{cwd}", "/project", "ro"),
            ("{output_dir}", "/output", "rw"),
        ],
        allowed_commands=["python", "python3", "pip", "ls", "cat", "echo"],
        blocked_commands=["rm", "dd", "mkfs", "shutdown", "reboot"],
        max_processes=20,
        max_file_size_mb=50,
    ),

    "bash": IsolationProfile(
        name="bash",
        description="Shell command execution — strict, no network",
        image="alpine:latest",
        memory="256m",
        cpu="0.5",
        timeout=60,
        network="none",
        read_only=True,
        tmpfs=["/tmp"],
        mounts=[
            ("{cwd}", "/workspace", "ro"),
        ],
        allowed_commands=["ls", "cat", "echo", "grep", "find",
                         "wc", "head", "tail", "sort", "uniq",
                         "which", "pwd", "date", "whoami", "id",
                         "git", "python", "python3", "node", "npm",
                         "curl", "wget"],
        blocked_commands=["rm", "dd", "mkfs", "shutdown", "reboot",
                         "poweroff", "halt", "kill", "pkill",
                         "chmod", "chown", "mount", "umount"],
        max_processes=10,
        max_file_size_mb=20,
    ),

    "browser": IsolationProfile(
        name="browser",
        description="Headless browser automation — internal network only",
        image="mcr.microsoft.com/playwright:latest",
        memory="1g",
        cpu="1.0",
        timeout=120,
        network="internal",
        read_only=False,
        tmpfs=["/tmp", "/home"],
        allowed_commands=["node", "npx", "npm"],
        max_processes=50,
        max_file_size_mb=200,
    ),

    "mcp": IsolationProfile(
        name="mcp",
        description="MCP server processes — 512MB, no network by default",
        image="node:20-alpine",
        memory="512m",
        cpu="1.0",
        timeout=300,
        network="none",
        read_only=True,
        tmpfs=["/tmp"],
        allowed_commands=["node", "npx", "npm", "python", "python3", "uvx", "uv"],
        max_processes=30,
        max_file_size_mb=50,
    ),

    "trusted": IsolationProfile(
        name="trusted",
        description="User-approved operations — full network, higher limits",
        image="alpine:latest",
        memory="2g",
        cpu="2.0",
        timeout=600,
        network="restricted",
        read_only=False,
        tmpfs=["/tmp"],
        allowed_commands=[],  # empty = all allowed
        blocked_commands=["rm -rf /", "dd if=/dev/", "mkfs"],
        max_processes=100,
        max_file_size_mb=500,
    ),
}


def get_profile(name: str) -> IsolationProfile | None:
    """Get an isolation profile by name."""
    return PROFILES.get(name)


def list_profiles() -> list[str]:
    """List all available isolation profiles."""
    return list(PROFILES.keys())


def resolve_profile(task_type: str, features: list[str] | None = None) -> str:
    """Resolve the best isolation profile for a task type.

    Args:
        task_type: Task type like 'code_write', 'system', 'browser'
        features: Detected features

    Returns:
        Profile name string.
    """
    features = features or []

    if task_type == "browser":
        return "browser"
    if task_type in ("code_write", "code_modify", "code_review", "complex",
                     "database"):
        return "python"
    if task_type in ("system", "file_ops"):
        return "bash"
    if task_type in ("code_read", "research", "chat", "unknown", "reasoning"):
        return "bash"

    return "bash"  # default safe profile
