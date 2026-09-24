"""Multi-file Editor — Atomic edits across multiple files.

All-or-nothing semantics: either all files are written, or none are.
Uses backup files for rollback on partial failure.

Usage:
    from core.multi_editor import MultiFileEditor

    editor = MultiFileEditor()
    editor.add("src/a.py", "new content for a")
    editor.add("src/b.py", "new content for b")
    result = editor.commit()
    # → MultiEditResult(ok=True, files_written=2)
"""

from __future__ import annotations
import logging

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
logger = logging.getLogger("widdx.multi_editor")


@dataclass
class MultiEditResult:
    ok: bool
    files_written: int = 0
    files_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    backups: dict[str, str] = field(default_factory=dict)  # path → backup_path

    @property
    def summary(self) -> str:
        if self.ok:
            return f"OK: {self.files_written} files written"
        return f"FAILED: {self.files_written} written, {len(self.errors)} errors"


class MultiFileEditor:
    """Atomic multi-file editor with automatic rollback."""
    def __init__(self):
        self._edits: dict[str, str] = {}    # path → new_content
        self._backups: dict[str, str] = {}  # path → backup_path

    def add(self, file_path: str | Path, new_content: str):
        """Stage a file edit."""
        self._edits[str(file_path)] = new_content

    def remove(self, file_path: str | Path):
        """Unstage a file edit."""
        self._edits.pop(str(file_path), None)

    @property
    def staged_count(self) -> int:
        return len(self._edits)

    def clear(self):
        self._edits.clear()
        self._backups.clear()

    def preview(self) -> str:
        """Return a human-readable summary of pending changes."""
        lines = [f"Pending edits ({len(self._edits)} files):"]
        for path in sorted(self._edits):
            lines.append(f"  M {path}")
        return "\n".join(lines)

    def commit(self, dry_run: bool = False) -> MultiEditResult:
        """Write all staged edits to disk. Rolls back on failure.

        Args:
            dry_run: If True, validate without writing.

        Returns:
            MultiEditResult with outcome.
        """
        if not self._edits:
            return MultiEditResult(ok=True)

        # Phase 1: Create backups
        for path_str in self._edits:
            p = Path(path_str)
            if p.exists():
                try:
                    backup = tempfile.NamedTemporaryFile(
                        delete=False, suffix=p.suffix,
                    )
                    shutil.copy2(str(p), backup.name)
                    self._backups[path_str] = backup.name
                except Exception as e:
                    self._rollback()
                    return MultiEditResult(
                        ok=False, errors=[f"Backup failed for {path_str}: {e}"],
                    )

        if dry_run:
            self._rollback()
            return MultiEditResult(ok=True, files_written=0)

        # Phase 2: Write new content
        written = 0
        try:
            for path_str, content in self._edits.items():
                p = Path(path_str)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                written += 1
        except Exception as e:
            self._rollback()
            return MultiEditResult(
                ok=False,
                files_written=written,
                errors=[f"Write failed at {written}/{len(self._edits)}: {e}"],
            )

        # Phase 3: Clean up backups (success)
        self._clean_backups()
        return MultiEditResult(ok=True, files_written=written)

    # ── Internals ───────────────────────────────────────

    def _rollback(self):
        """Restore all files from backups."""
        for path_str, backup_path in self._backups.items():
            try:
                shutil.copy2(backup_path, path_str)
            except Exception:
                pass
        self._clean_backups()

    def _clean_backups(self):
        """Delete all backup files."""
        import os
        for backup_path in self._backups.values():
            try:
                os.unlink(backup_path)
            except Exception:
                pass
        self._backups.clear()


# Global
multi_editor = MultiFileEditor()
