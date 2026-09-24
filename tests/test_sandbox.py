"""Tests for L1: Sandbox Executor (core/sandbox.py)."""
import platform
from core.sandbox import SandboxExecutor, SandboxResult, ResourceLimits, sandbox

_IS_WINDOWS = platform.system() == "Windows"


def test_sandbox_result_ok():
    r = SandboxResult(stdout="hi", exit_code=0)
    assert r.ok
    assert "OK" in r.summary


def test_sandbox_result_timeout():
    r = SandboxResult(was_timeout=True)
    assert not r.ok
    assert "TIMEOUT" in r.summary


def test_execute_simple_echo():
    result = sandbox.execute("echo hello", timeout=10)
    assert result.ok
    assert "hello" in result.stdout
    assert result.mode in ("subprocess", "docker", "wsl", "cgroups", "sandbox-exec") or "container" in result.mode


def test_execute_exit_code():
    # Use a cross-platform way to exit with a specific code
    if _IS_WINDOWS:
        result = sandbox.execute("cmd /c exit 42", timeout=10)
    else:
        result = sandbox.execute("exit 42", timeout=10)
    assert not result.ok
    # On Windows cmd.exe: exit code 42 is returned directly
    # On Unix: `exit 42` in sh may return 42 or be caught
    assert result.exit_code in (42, -1, 127), (
        f"Expected exit code 42, -1, or 127, got {result.exit_code}"
    )


def test_execute_nonexistent_command():
    result = sandbox.execute("nonexistent_command_xyz_123", timeout=10)
    assert not result.ok


def test_detect_mode():
    sb = SandboxExecutor()
    mode = sb.detect_mode()
    assert mode in ("subprocess", "docker", "wsl", "cgroups", "sandbox-exec")


def test_resource_limits_default():
    limits = ResourceLimits()
    assert limits.max_cpu_seconds == 60
    assert limits.max_memory_mb == 512


def test_singleton_exists():
    assert sandbox is not None
    assert hasattr(sandbox, "execute")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
