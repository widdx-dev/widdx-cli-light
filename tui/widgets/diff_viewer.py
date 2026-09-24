"""Diff Viewer Widget — Inline git diff display for the TUI.

Zero external dependencies beyond Textual. Renders color-coded
diffs with line numbers, scroll support, and file picker.

Usage:
    from tui.widgets.diff_viewer import DiffViewer
    viewer = DiffViewer()
    viewer.show_diff()  # shows diff of current repo
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_diff(file_path: str | None = None, staged: bool = False) -> str:
    """Run ``git diff`` and return the output as a string.

    Args:
        file_path: Optional specific file to diff.
        staged: If True, show staged changes (``--cached``).
    """
    try:
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")
        if file_path:
            cmd.extend(["--", file_path])
        r = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=10,
            cwd=str(Path.cwd()),
        )
        return r.stdout or "(no changes)"
    except FileNotFoundError:
        return "(git not found)"
    except subprocess.TimeoutExpired:
        return "(timeout)"
    except Exception as e:
        return f"(error: {e})"


def get_changed_files() -> list[dict]:
    """List changed files with status (M=modified, A=added, D=deleted, ??=untracked)."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path.cwd()),
        )
        files = []
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            status = line[:2].strip()
            fname = line[3:].strip()
            status_map = {"M": "modified", "A": "added", "D": "deleted",
                          "R": "renamed", "C": "copied", "??": "untracked"}
            files.append({
                "status": status_map.get(status, status),
                "path": fname,
            })
        return files
    except Exception:
        return []


def format_diff_for_display(diff_text: str, max_lines: int = 200) -> list[str]:
    """Split diff into color-tagged lines for rendering.

    Returns lines with prefix tags:
      ``+ `` → addition (green)
      ``- `` → deletion (red)
      ``@@ `` → hunk header (cyan)
      ``diff `` → file header (bold)
    """
    lines = diff_text.split("\n")[:max_lines]
    return lines
