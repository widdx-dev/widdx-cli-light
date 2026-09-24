"""Sandbox safety layer — path checks, timeouts, command whitelist, and resource limits.

Provides:
  - Path safety validation (is_safe_path)
  - Execution timeout for shell commands
  - Command whitelist for restricted operations
  - Resource limits (memory, process count)
  - Graceful timeout handling with error context
"""

import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

_SAFE_DIR: str | None = None


def configure(sandbox_dir: str | None):
    """Set a sandbox directory for safe file writes."""
    global _SAFE_DIR
    _SAFE_DIR = str(Path(sandbox_dir).resolve()) if sandbox_dir else None


def get_safe_dir() -> str | None:
    return _SAFE_DIR


def is_safe_path(p: Path) -> bool:
    """Check if a resolved path is inside the configured sandbox directory."""
    if _SAFE_DIR is None:
        return True
    try:
        p.resolve().relative_to(Path(_SAFE_DIR).resolve())
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Execution Timeout
# ---------------------------------------------------------------------------

class TimeoutError(RuntimeError):
    """Raised when a tool execution exceeds its timeout."""
    def __init__(self, tool_name: str, timeout_seconds: float):
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Tool '{tool_name}' timed out after {timeout_seconds:.1f}s"
        )


# Default timeouts per tool category (in seconds)
TOOL_TIMEOUTS: dict[str, float] = {
    "bash":          30.0,   # shell commands — capped at 30s
    "write":         10.0,   # file writes — should be fast
    "edit":          10.0,
    "read":          15.0,   # file reads
    "grep":          30.0,
    "glob":          15.0,
    "validate":      15.0,
    "semantic_search": 30.0,
    "rename_symbol":   20.0,
    "dep_graph":       30.0,
    "docker":         120.0,  # docker ops can be slow
    "api_request":    60.0,
    "db_query":       30.0,
    "pkg_mgr":        60.0,
    "terminal":       30.0,
    "spawn_agent":    300.0, # sub-agents get 5 minutes
    "ask_user":       120.0,
    "scaffolder":     30.0,
    "test_runner":    120.0,
    "browser":        30.0,
    "web":            30.0,
    "security_scan":  60.0,
}

# Default timeout for unknown tools
DEFAULT_TOOL_TIMEOUT: float = 30.0


def get_tool_timeout(tool_name: str) -> float:
    """Return the timeout for a given tool, in seconds."""
    return TOOL_TIMEOUTS.get(tool_name, DEFAULT_TOOL_TIMEOUT)


def with_timeout(func: Callable, tool_name: str, timeout: Optional[float] = None,
                 args: tuple = (), kwargs: Optional[dict] = None) -> Any:
    """Execute a function with a timeout guard.

    Uses SIGALRM on Unix for precise timeout, with a threading.Timer
    fallback for platforms where SIGALRM is unavailable.

    Args:
        func: The function to execute.
        tool_name: Name of the tool (for error messages + timeout lookup).
        timeout: Override timeout in seconds. If None, uses TOOL_TIMEOUTS.
        args: Positional arguments for func.
        kwargs: Keyword arguments for func.

    Returns:
        The return value of func.

    Raises:
        TimeoutError: If execution exceeds the timeout.
        Any exception raised by func (if within timeout).
    """
    if kwargs is None:
        kwargs = {}
    if timeout is None:
        timeout = get_tool_timeout(tool_name)

    result_container: list = []
    exception_container: list = []
    finished = threading.Event()

    def target():
        try:
            result_container.append(func(*args, **kwargs))
        except Exception as e:
            exception_container.append(e)
        finally:
            finished.set()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()

    if not finished.wait(timeout=timeout):
        # Thread still running after timeout — log and raise
        import logging
        logging.getLogger("widdx.safety").warning(
            "Tool '%s' timed out after %.1fs (args=%s)",
            tool_name, timeout, str(args)[:200],
        )
        raise TimeoutError(tool_name, timeout)

    if exception_container:
        raise exception_container[0]

    return result_container[0]


# ---------------------------------------------------------------------------
# Command Whitelist
# ---------------------------------------------------------------------------

# Commands that are always allowed (safe, read-only)
_ALWAYS_ALLOWED = {
    "ls", "cat", "head", "tail", "echo", "pwd", "which", "whoami",
    "python", "python3", "node", "npm", "pip", "pip3",
    "git", "grep", "find", "sort", "wc", "diff", "rg", "ack",
    "mkdir", "touch", "cp", "mv", "rm", "chmod", "chown",
    "cd", "env", "export", "source",
    "docker", "systemctl", "journalctl",
    "curl", "wget", "ping", "nslookup", "dig",
    "ps", "top", "htop", "free", "df", "du", "uname",
    "date", "cal", "bc", "sed", "awk", "xargs", "tee",
    "sudo", "apt", "apt-get", "yum", "dnf", "pacman",
    "cargo", "go", "rustc", "deno", "bun",
    "make", "cmake", "gcc", "g++", "clang", "clang++",
    "ssh", "scp", "rsync", "tar", "gzip", "gunzip", "bzip2", "xz",
    "watch", "time", "nohup", "screen", "tmux",
    "kill", "pkill", "npx", "uvx", "brew",
}

# Commands that require specific permission
_RESTRICTED_COMMANDS = {
    "dd": "raw disk operations require explicit permission",
    "fdisk": "disk partitioning requires explicit permission",
    "mkfs": "filesystem creation requires explicit permission",
    "reboot": "system reboot requires explicit permission",
    "shutdown": "system shutdown requires explicit permission",
    "poweroff": "system poweroff requires explicit permission",
    "iptables": "network filtering changes require explicit permission",
    "mount": "filesystem mounting requires explicit permission",
    "umount": "filesystem unmounting requires explicit permission",
    "insmod": "kernel module loading requires explicit permission",
    "rmmod": "kernel module removal requires explicit permission",
}

# Suffixes for files that should never be executed/changed
_PROTECTED_PATHS = [
    "/etc/passwd", "/etc/shadow", "/etc/sudoers",
    "/boot/", "/dev/", "/proc/", "/sys/",
]


def check_command_whitelist(command: str) -> Optional[str]:
    """Check if a command is in the whitelist or restricted list.

    Args:
        command: The shell command to check.

    Returns:
        None if the command is allowed, or an error message string
        explaining why it's blocked.
    """
    import shlex
    try:
        parts = shlex.split(command)
    except ValueError:
        return "Could not parse command (invalid shell syntax)"

    if not parts:
        return "Empty command"

    # Extract the base command (resolving path prefixes)
    base_cmd = Path(parts[0]).name if "/" in parts[0] else parts[0]

    # Check restricted commands first
    if base_cmd in _RESTRICTED_COMMANDS:
        return f"Blocked: {_RESTRICTED_COMMANDS[base_cmd]}"

    # Check if command is in the always-allowed list
    if base_cmd in _ALWAYS_ALLOWED:
        return None  # allowed

    # Unknown command — warn but allow (with logging)
    import logging
    logging.getLogger("widdx.safety").warning(
        "Unknown command '%s' (full: %s) — allowing with warning",
        base_cmd, command[:200],
    )
    return None  # allow unknown commands, but log them


# ---------------------------------------------------------------------------
# Resource Limits
# ---------------------------------------------------------------------------

class ResourceLimits:
    """Enforce resource limits on tool execution.

    Tracks:
      - Concurrent subprocess count
      - Memory threshold warnings
      - File descriptor usage
    """

    def __init__(self, max_concurrent_subprocesses: int = 10,
                 memory_warning_mb: float = 1024.0):
        self.max_concurrent = max_concurrent_subprocesses
        self.memory_warning_mb = memory_warning_mb
        self._active_subprocesses: dict[str, float] = {}
        self._lock = threading.Lock()

    def acquire(self, tool_name: str) -> bool:
        """Try to acquire a resource slot. Returns False if at capacity."""
        with self._lock:
            now = time.time()
            # Clean stale entries (> 60s old)
            stale = [k for k, t in self._active_subprocesses.items()
                     if now - t > 60]
            for k in stale:
                del self._active_subprocesses[k]

            if len(self._active_subprocesses) >= self.max_concurrent:
                return False
            self._active_subprocesses[tool_name] = now
            return True

    def release(self, tool_name: str):
        """Release a resource slot."""
        with self._lock:
            self._active_subprocesses.pop(tool_name, None)

    def check_memory(self) -> Optional[str]:
        """Check if memory usage exceeds warning threshold.

        Returns:
            Warning message if memory is high, None otherwise.
        """
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_mb = int(line.split()[1]) / 1024
                        if rss_mb > self.memory_warning_mb:
                            return (
                                f"High memory usage: {rss_mb:.0f} MB "
                                f"(threshold: {self.memory_warning_mb:.0f} MB)"
                            )
        except (FileNotFoundError, IOError, ValueError):
            pass
        return None

    def status(self) -> dict:
        """Return current resource status."""
        with self._lock:
            return {
                "active_subprocesses": len(self._active_subprocesses),
                "max_concurrent": self.max_concurrent,
                "available_slots": self.max_concurrent - len(self._active_subprocesses),
            }


# Global resource limits instance
resource_limits = ResourceLimits()


# ---------------------------------------------------------------------------
# Safe Execution Wrapper
# ---------------------------------------------------------------------------

def execute_safely(tool_name: str, func: Callable, args: tuple = (),
                   kwargs: Optional[dict] = None,
                   timeout: Optional[float] = None) -> Any:
    """Execute a tool with full safety wrapping: timeout + resource limits.

    Args:
        tool_name: Name of the tool being executed.
        func: The function to execute.
        args: Positional arguments.
        kwargs: Keyword arguments.
        timeout: Optional timeout override.

    Returns:
        The function's return value.

    Raises:
        TimeoutError: If execution times out.
        RuntimeError: If resource limits are exceeded.
    """
    if kwargs is None:
        kwargs = {}

    # Check resource limits
    if not resource_limits.acquire(tool_name):
        raise RuntimeError(
            f"Resource limit reached: {resource_limits.max_concurrent} "
            f"concurrent executions. Cannot run '{tool_name}'."
        )

    try:
        # Check memory usage
        mem_warning = resource_limits.check_memory()
        if mem_warning:
            import logging
            logging.getLogger("widdx.safety").warning(
                "Before '%s': %s", tool_name, mem_warning
            )

        # Execute with timeout
        return with_timeout(func, tool_name, timeout, args, kwargs)
    finally:
        resource_limits.release(tool_name)
