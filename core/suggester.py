"""Proactive Suggester — analyze project state and suggest next actions."""

import time
import subprocess
import re
import logging
from dataclasses import dataclass
from pathlib import Path
from .memory import MemoryStore
from .project import git as git_utils

logger = logging.getLogger("widdx.suggester")


@dataclass
class Suggestion:
    """A single proactive suggestion."""
    icon: str        # emoji
    title: str       # one-line
    detail: str      # expanded
    action_type: str # "git", "todo", "memory", "config"
    priority: int    # 0-5


class ProjectSuggester:
    """Checks project state and generates ranked suggestions."""

    def __init__(self, project_dir: str | Path | None = None):
        self._root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        self.mem = MemoryStore(project_dir=self._root)
        self._last: list[str] = []  # dedup: last shown titles

    # ── Main API ────────────────────────────────────────

    def suggest(self) -> list[Suggestion]:
        """Run all checkers, return up to 3 suggestions sorted by priority."""
        all_suggestions = []
        for check in [self._check_git, self._check_todos, self._check_git_activity,
                      self._check_config_changes, self._check_memory_gap]:
            try:
                s = check()
                if s and s.title not in self._last:
                    all_suggestions.append(s)
            except Exception as e:
                logger.debug("Suggestion check failed: %s", e)

        all_suggestions.sort(key=lambda s: -s.priority)
        result = all_suggestions[:3]

        # Dedup for next round
        self._last = [s.title for s in result]
        return result

    # ── Checkers ─────────────────────────────────────────

    def _check_git(self) -> Suggestion | None:
        if not git_utils.is_git_repo(str(self._root)):
            return None
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self._root, capture_output=True, text=True, timeout=5,
            )
            lines = [line for line in r.stdout.splitlines() if line.strip()]
            if lines:
                count = len(lines)
                return Suggestion(
                    icon="📝",
                    title=f"{count} uncommitted change(s) detected",
                    detail="Run git add + commit to save your progress",
                    action_type="git",
                    priority=4,
                )
        except Exception as e:
            logger.debug("Git check failed: %s", e)
        return None

    def _check_todos(self) -> Suggestion | None:
        count = 0
        try:
            for f in self._root.rglob("*.py"):
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    count += len(re.findall(r'\b(TODO|FIXME|HACK|XXX)\b', text))
                    if count >= 3:
                        break
                except Exception as e:
                    logger.debug("Failed to read %s for TODO scan: %s", f, e)
                    continue
        except Exception as e:
            logger.debug("TODO check failed: %s", e)
        if count >= 3:
            return Suggestion(
                icon="📋",
                title=f"{count} TODO/FIXME markers found",
                detail="Consider reviewing and resolving outstanding tasks",
                action_type="todo",
                priority=3,
            )
        return None

    def _check_git_activity(self) -> Suggestion | None:
        if not git_utils.is_git_repo(str(self._root)):
            return None
        try:
            r = subprocess.run(
                ["git", "log", "--oneline", "-5", "--since=24.hours"],
                cwd=self._root, capture_output=True, text=True, timeout=5,
            )
            commits = [line for line in r.stdout.strip().splitlines() if line.strip()]
            if len(commits) >= 3:
                return Suggestion(
                    icon="🔄",
                    title=f"{len(commits)} commits in last 24h",
                    detail="Consider reviewing or pushing to remote",
                    action_type="git",
                    priority=2,
                )
        except Exception as e:
            logger.debug("Git activity check failed: %s", e)
        return None

    def _check_config_changes(self) -> Suggestion | None:
        configs = ["config.json", "pyproject.toml", "package.json",
                    ".widdx/config.json", "docker-compose.yml"]
        modified = []
        for cf in configs:
            p = self._root / cf
            if p.exists() and (time.time() - p.stat().st_mtime) < 120:
                modified.append(cf)
        if modified:
            return Suggestion(
                icon="⚙️",
                title=f"Config changed: {', '.join(modified)}",
                detail="Adjustments may be needed — review changes",
                action_type="config",
                priority=3,
            )
        return None

    def _check_memory_gap(self) -> Suggestion | None:
        try:
            if self.mem.total() == 0:
                return Suggestion(
                    icon="💡",
                    title="No facts recorded yet",
                    detail="I'll auto-learn as we chat — or ask me to remember something",
                    action_type="memory",
                    priority=1,
                )
        except Exception as e:
            logger.debug("Memory gap check failed: %s", e)
        return None
