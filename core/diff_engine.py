"""Diff Engine — Unified-diff-based file editing.

Search-and-replace is fragile.  Unified diffs are exact, reversible,
and naturally handle conflict detection (context lines must match).

Architecture:
  DiffEngine    — generate / apply / dry-run unified diffs
  DiffResult    — outcome of applying a patch

Usage:
    from core.diff_engine import DiffEngine

    engine = DiffEngine()
    result = engine.apply(
        file_path="src/main.py",
        old_content=original,
        new_content=modified,
        dry_run=True,
    )
    if result.ok:
        engine.commit(result)  # write to disk
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Diff Result
# ---------------------------------------------------------------------------

@dataclass
class DiffResult:
    ok: bool
    patch: str = ""
    error: str = ""
    stats: dict = field(default_factory=dict)
    dry_run: bool = False

    @property
    def lines_added(self) -> int:
        return self.stats.get("added", 0)

    @property
    def lines_removed(self) -> int:
        return self.stats.get("removed", 0)

    @property
    def lines_changed(self) -> int:
        return self.lines_added + self.lines_removed


# ---------------------------------------------------------------------------
# Diff Engine
# ---------------------------------------------------------------------------

class DiffEngine:
    """Generate and apply unified diffs for safe file editing."""

    @staticmethod
    def generate(
        old_text: str,
        new_text: str,
        filename: str = "file",
        context_lines: int = 3,
    ) -> str:
        """Generate a unified diff between old and new text."""
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        # Ensure trailing newline for difflib
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=filename, tofile=filename,
            n=context_lines,
        )
        return "".join(diff)

    @staticmethod
    def apply(
        file_path: str | Path,
        old_content: str,
        new_content: str,
        dry_run: bool = False,
    ) -> DiffResult:
        """Generate a diff and optionally write the new content to disk.

        Args:
            file_path: Path to the file to modify.
            old_content: Expected current content (for conflict detection).
            new_content: Desired new content.
            dry_run: If True, only generate the diff — don't write.

        Returns:
            DiffResult with patch, stats, and success/failure.
        """
        path = Path(file_path)

        # Verify file exists and matches old_content (conflict detection)
        if path.exists():
            actual = path.read_text(encoding="utf-8")
            if actual != old_content:
                return DiffResult(
                    ok=False,
                    error="Conflict: file content changed since old_content was read. "
                          "Re-read the file and try again.",
                )

        # Generate the patch
        patch = DiffEngine.generate(old_content, new_content, filename=path.name)

        # Count changes
        added = sum(1 for line in patch.splitlines()
                    if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in patch.splitlines()
                      if line.startswith("-") and not line.startswith("---"))

        result = DiffResult(
            ok=True,
            patch=patch,
            stats={"added": added, "removed": removed},
            dry_run=dry_run,
        )

        # Write if not dry run
        if not dry_run:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(new_content, encoding="utf-8")
            except Exception as e:
                return DiffResult(ok=False, error=str(e))

        return result

    @staticmethod
    def apply_patch(
        file_path: str | Path,
        patch_text: str,
        dry_run: bool = False,
    ) -> DiffResult:
        """Apply a unified diff patch to a file.

        Uses simple line-by-line parsing (no external `patch` binary needed).
        Handles the common case of single-file patches.

        Args:
            file_path: Path to modify.
            patch_text: Unified diff text.
            dry_run: If True, preview only.

        Returns:
            DiffResult with outcome.
        """
        path = Path(file_path)
        if not path.exists():
            return DiffResult(ok=False, error=f"File not found: {path}")

        original = path.read_text(encoding="utf-8")
        original_lines = original.splitlines(keepends=True)

        try:
            patched_lines = DiffEngine._apply_patch_lines(original_lines, patch_text)
        except ValueError as e:
            return DiffResult(ok=False, error=str(e))

        patched_text = "".join(patched_lines)

        patch_display = DiffEngine.generate(original, patched_text, filename=path.name)
        added = sum(1 for line in patch_display.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in patch_display.splitlines() if line.startswith("-") and not line.startswith("---"))

        result = DiffResult(
            ok=True,
            patch=patch_display,
            stats={"added": added, "removed": removed},
            dry_run=dry_run,
        )

        if not dry_run:
            path.write_text(patched_text, encoding="utf-8")

        return result

    @staticmethod
    def _apply_patch_lines(
        original_lines: list[str],
        patch_text: str,
    ) -> list[str]:
        """Apply a unified diff patch to a list of lines.

        Uses a simple state-machine approach:
        - Context lines (space-prefixed): verify match with original
        - Deletion lines (minus-prefixed): skip from original
        - Addition lines (plus-prefixed): insert into result

        Raises ValueError if context lines don't match the original.
        """
        result: list[str] = []
        patch_lines = patch_text.splitlines(keepends=True)
        orig_idx = 0

        pi = 0
        while pi < len(patch_lines):
            pl = patch_lines[pi]

            if pl.startswith("@@") and "@@" in pl[2:]:
                # Hunk header — parse old_start
                parts = pl.split()
                old_part = parts[1].lstrip("-").split(",")
                old_start = int(old_part[0]) - 1  # 0-indexed

                # Copy lines before this hunk's old_start from original
                while orig_idx < old_start and orig_idx < len(original_lines):
                    result.append(original_lines[orig_idx])
                    orig_idx += 1

                pi += 1
                # Process hunk body
                while pi < len(patch_lines) and not (
                    patch_lines[pi].startswith("@@") and "@@" in patch_lines[pi][2:]
                ):
                    pl = patch_lines[pi]
                    if pl.startswith(" "):
                        # Context line — verify match
                        ctx = pl[1:]
                        if orig_idx >= len(original_lines):
                            raise ValueError(
                                f"Patch context mismatch: expected '{ctx.rstrip()}' at EOF"
                            )
                        actual = original_lines[orig_idx]
                        if actual.rstrip("\n") != ctx.rstrip("\n"):
                            raise ValueError(
                                f"Patch context mismatch at line {orig_idx + 1}: "
                                f"expected '{ctx.rstrip()}', got '{actual.rstrip()}'"
                            )
                        result.append(actual)
                        orig_idx += 1
                    elif pl.startswith("-"):
                        # Deletion — skip original line
                        if orig_idx < len(original_lines):
                            orig_idx += 1
                    elif pl.startswith("+"):
                        # Addition — insert new line
                        result.append(pl[1:])
                    pi += 1
            else:
                pi += 1

        # Copy remaining original lines after last hunk
        while orig_idx < len(original_lines):
            result.append(original_lines[orig_idx])
            orig_idx += 1

        return result

    @staticmethod
    def preview(file_path: str | Path, old_content: str, new_content: str) -> str:
        """Return a human-readable diff preview."""
        result = DiffEngine.apply(file_path, old_content, new_content, dry_run=True)
        if not result.ok:
            return f"Error: {result.error}"
        return result.patch
