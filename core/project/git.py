"""Git utilities for WIDDX — auto-commit and undo support."""
import logging


import subprocess
from pathlib import Path
logger = logging.getLogger("widdx.git")


# File patterns that should NEVER be auto-committed (sensitive or generated)
_SENSITIVE_PATTERNS = [
    ".env", ".env.*", "*.key", "*.pem", "*.cert",
    "config.json",           # may contain API keys (though stripped on save)
    ".widdx/session.json",   # conversation history with potential secrets
    ".widdx/keychain.json",
    "*.log",
]


def _is_sensitive(path: str) -> bool:
    """Check if a file path matches any sensitive pattern."""
    import fnmatch
    p = path.replace("\\", "/")
    for pattern in _SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(p, pattern) or fnmatch.fnmatch(p, f"**/{pattern}"):
            return True
    return False


def is_git_repo(path: str | Path) -> bool:
    """Check if the given directory is inside a git repository."""
    return (Path(path).resolve() / ".git").is_dir()


def has_changes(path: str | Path) -> bool:
    """Check if there are uncommitted changes in the repo."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(path), capture_output=True, text=True, timeout=10,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def auto_commit(path: str | Path, user_message: str):
    """Auto-commit changes.

    For new directories (not yet a git repo), runs ``git init`` automatically
    so even brand-new projects get version-controlled.

    SAFETY:
    - Skips sensitive files (see _SENSITIVE_PATTERNS)
    - For existing repos: only updates tracked files (``git add -u``)
    - For new repos: ``git add -A`` (first commit), then ``git add -u`` thereafter
    - Commit message is prefixed with 'WIDDX:' and truncated to 70 chars.
    """
    path_str = str(Path(path).resolve())
    is_new_repo = False

    if not is_git_repo(path_str):
        # New project — auto-init so version control kicks in
        try:
            subprocess.run(
                ["git", "init"],
                cwd=path_str, capture_output=True, text=True, timeout=15,
                check=True,
            )
            is_new_repo = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    if not has_changes(path_str):
        return False
    try:
        # Check for sensitive files in the unstaged changes
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path_str, capture_output=True, text=True, timeout=10,
        )
        changed_files = status_result.stdout.strip().splitlines()
        sensitive_detected = False
        for line in changed_files:
            # Porcelain format: "XY filename" or "XY filename -> newname"
            parts = line.strip().split()
            if len(parts) >= 2:
                fpath = parts[1]
                if _is_sensitive(fpath):
                    sensitive_detected = True

        if sensitive_detected:
            return False  # Skip commit — sensitive files detected

        # For a brand-new repo stage everything; otherwise only tracked files
        if is_new_repo:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=path_str, capture_output=True, text=True, timeout=30,
                check=True,
            )
        else:
            subprocess.run(
                ["git", "add", "-u"],
                cwd=path_str, capture_output=True, text=True, timeout=30,
                check=True,
            )

        msg = f"WIDDX: {user_message[:70].strip()}"
        # Configure minimal user for the auto-commit if not set
        _ensure_git_config(path_str)
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=path_str, capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _ensure_git_config(path_str: str):
    """Set a minimal default git identity so commit doesn't fail on a fresh machine."""
    try:
        for key, value in [("user.email", "widdx@local"), ("user.name", "WIDDX")]:
            r = subprocess.run(
                ["git", "config", key],
                cwd=path_str, capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0 or not r.stdout.strip():
                subprocess.run(
                    ["git", "config", key, value],
                    cwd=path_str, capture_output=True, text=True, timeout=5,
                )
    except Exception:
        pass  # non-critical


def undo_last_commit(path: str | Path) -> str:
    """Undo the last commit (git reset --soft HEAD~1).

    Returns a message describing the result.
    Only undoes if the last commit message starts with 'WIDDX:'.
    Checks for staged files and warns before proceeding.
    """
    path_str = str(Path(path).resolve())
    if not is_git_repo(path_str):
        return "Not a git repository \u2014 cannot undo."

    try:
        # Check last commit message
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=path_str, capture_output=True, text=True, timeout=10,
        )
        last_msg = result.stdout.strip()
        if not last_msg.startswith("WIDDX:"):
            return f"Last commit is not by WIDDX ('{last_msg}'). Use 'git reset --soft HEAD~1' manually."

        # Count commits
        count_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=path_str, capture_output=True, text=True, timeout=10,
        )
        commit_count = int(count_result.stdout.strip())
        if commit_count <= 1:
            return "Cannot undo \u2014 only one commit in the repository."

        # Check for staged files before undo
        staged_check = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=path_str, capture_output=True, text=True, timeout=10,
        )
        has_staged = staged_check.returncode != 0
        if has_staged:
            return ("Warning: You have staged changes that will be un-staged. "
                    "Use 'git reset --soft HEAD~1' manually or stash first.")

        # Undo with --soft to preserve file changes
        subprocess.run(
            ["git", "reset", "--soft", "HEAD~1"],
            cwd=path_str, capture_output=True, text=True, timeout=30,
            check=True,
        )
        return f"Undone: '{last_msg}' \u2014 changes preserved (staged)."

    except subprocess.TimeoutExpired:
        return "Undo timed out."
    except subprocess.CalledProcessError as e:
        return f"Undo failed: {e.stderr.strip()}"
    except FileNotFoundError:
        return "Git not found \u2014 install git or undo manually."
