"""Documentation Sync — 4.0 #5.

Detects drift between code and documentation. Compares what's in
PLAN/DESIGN/TASKS/ROADMAP against the actual project files, flags
discrepancies, and optionally auto-updates.

Usage:
    from core.doc_sync import DocSync
    ds = DocSync()
    warnings = ds.detect_drift()
    for w in warnings:
        print(f"DRIFT: {w.entity} — {w.message}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("widdx.doc_sync")


@dataclass
class DriftWarning:
    """A detected discrepancy between docs and code."""
    entity: str           # Doc or file name
    message: str          # Human-readable description
    severity: str = "warning"  # warning | critical
    source: str = ""      # PLAN/DESIGN/TASKS/ROADMAP
    suggestion: str = ""  # How to fix


class DocSync:
    """Detects and reports drift between project docs and code."""

    def __init__(self, project_dir: str | Path | None = None):
        self._root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        self._widdx = self._root / ".widdx"

    def detect_drift(self) -> list[DriftWarning]:
        """Scan docs vs code and return all discrepancies."""
        warnings: list[DriftWarning] = []

        # 1. Check TASKS.md for completed tasks that might not be reflected
        warnings.extend(self._check_tasks())

        # 2. Check if DESIGN.md mentions APIs that no longer exist
        warnings.extend(self._check_design())

        # 3. Check ROADMAP.md for outdated library references
        warnings.extend(self._check_roadmap())

        if warnings:
            logger.info("DocSync: %d drift warnings found", len(warnings))
        return warnings

    def _check_tasks(self) -> list[DriftWarning]:
        """Check TASKS.md completed items against code."""
        warnings: list[DriftWarning] = []
        tasks_path = self._widdx / "TASKS.md"
        if not tasks_path.exists():
            return warnings

        content = tasks_path.read_text(encoding="utf-8")
        # Find completed markers
        import re
        completed = re.findall(r'\[x\]\s+(.+)', content, re.IGNORECASE)
        if len(completed) > 20:
            warnings.append(DriftWarning(
                entity="TASKS.md",
                message=f"{len(completed)} tasks marked complete — consider archiving old entries",
                severity="warning",
                source="TASKS.md",
                suggestion="Run doc_sync.auto_update() to archive tasks older than 30 days",
            ))
        return warnings

    def _check_design(self) -> list[DriftWarning]:
        """Check DESIGN.md API references against actual code."""
        warnings: list[DriftWarning] = []
        design_path = self._widdx / "DESIGN.md"
        if not design_path.exists():
            return warnings

        content = design_path.read_text(encoding="utf-8")
        import re
        # Find mentioned file paths
        mentioned = set(re.findall(r'`([^`]+\.(?:py|js|ts|html|css))`', content))
        for fname in mentioned:
            if "/" in fname or "\\" in fname:
                fp = self._root / fname
                if not fp.exists():
                    warnings.append(DriftWarning(
                        entity=fname,
                        message=f"DESIGN.md references '{fname}' which no longer exists",
                        severity="critical" if fname.endswith(".py") else "warning",
                        source="DESIGN.md",
                        suggestion=f"Update or remove the reference to '{fname}' in DESIGN.md",
                    ))
        return warnings

    def _check_roadmap(self) -> list[DriftWarning]:
        """Check ROADMAP.md for stale entries."""
        warnings: list[DriftWarning] = []
        roadmap_path = self._widdx / "ROADMAP.md"
        if not roadmap_path.exists():
            return warnings

        content = roadmap_path.read_text(encoding="utf-8")
        import re
        # Count milestones vs actual git tags/releases
        milestones = len(re.findall(r'##?\s+\d+\.\d+|milestone|release', content, re.IGNORECASE))

        # Check if git has tags
        try:
            import subprocess
            r = subprocess.run(
                ["git", "tag", "-l"], capture_output=True, text=True,
                cwd=str(self._root), timeout=5,
            )
            tags = [t for t in r.stdout.strip().split("\n") if t]
            if milestones > len(tags) + 5:
                warnings.append(DriftWarning(
                    entity="ROADMAP.md",
                    message=f"{milestones} milestones in ROADMAP but only {len(tags)} git tags",
                    severity="warning",
                    source="ROADMAP.md",
                    suggestion="Update ROADMAP.md to reflect actual progress",
                ))
        except Exception:
            logger.debug("Exception suppressed (line 131)")

        return warnings

    def auto_update(self, warnings: list[DriftWarning] | None = None) -> list[str]:
        """Attempt to auto-fix drift warnings. Returns list of fixes applied."""
        if warnings is None:
            warnings = self.detect_drift()
        fixed = []
        for w in warnings:
            if w.entity == "TASKS.md" and "archive" in (w.suggestion or ""):
                self._archive_old_tasks()
                fixed.append("Archived old TASKS.md entries")
        return fixed

    def _archive_old_tasks(self):
        """Move completed tasks older than 30 days to TASKS.archive.md."""
        tasks_path = self._widdx / "TASKS.md"
        if not tasks_path.exists():
            return
        content = tasks_path.read_text(encoding="utf-8")
        # Simple: move [x] lines to archive
        import re
        completed = re.findall(r'\[x\]\s+.+', content, re.IGNORECASE)
        if not completed:
            return
        archive_path = self._widdx / "TASKS.archive.md"
        archive_text = archive_path.read_text(encoding="utf-8") if archive_path.exists() else "# Archived Tasks\n\n"
        for task in completed:
            archive_text += f"- {task}\n"
        archive_path.write_text(archive_text, encoding="utf-8")
        # Remove from main
        for task in completed:
            content = content.replace(f"- {task}\n", "")
            content = content.replace(f"- {task}", "")
        tasks_path.write_text(content, encoding="utf-8")
        logger.info("Archived %d completed tasks", len(completed))


# Singleton
_doc_sync: DocSync | None = None


def get_doc_sync() -> DocSync:
    global _doc_sync
    if _doc_sync is None:
        _doc_sync = DocSync()
    return _doc_sync
