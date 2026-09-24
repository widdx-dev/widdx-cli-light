"""Plugin Hot-Reload — Watch skills/ directory and reload on changes.

Zero external dependencies. Uses polling with mtime tracking.
Integrates with ``core.skills.SkillManager`` for seamless reload.

Architecture:
  PluginWatcher    — watches a directory, emits events on file changes
  SkillHotReloader — reloads skills into the SkillManager without restart

Usage:
    from core.plugin_loader import SkillHotReloader
    reloader = SkillHotReloader()
    reloader.start()       # background thread watches skills/
    # ... edit a skill ...
    # skill is auto-reloaded within polling interval
    reloader.stop()
"""

from __future__ import annotations
import logging

import os
import threading
import time
from pathlib import Path
from typing import Callable
logger = logging.getLogger("widdx.plugin_loader")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_POLL_INTERVAL = 2.0    # seconds between directory scans
SKILLS_DIR_NAME = "skills"


# ---------------------------------------------------------------------------
# Plugin Watcher (polling-based, no deps)
# ---------------------------------------------------------------------------

class PluginWatcher:
    """Watches a directory tree for file changes using mtime polling.
import logging


    Emits events via callbacks:
      - on_added(path)
      - on_modified(path)
      - on_removed(path)
    """

    def __init__(
        self,
        watch_dir: Path,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        patterns: tuple[str, ...] = (".md", ".py"),
    ):
        self._dir = Path(watch_dir)
        self._interval = poll_interval
        self._patterns = patterns
        self._mtimes: dict[str, float] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

        # Callbacks
        self.on_added: Callable[[Path], None] | None = None
        self.on_modified: Callable[[Path], None] | None = None
        self.on_removed: Callable[[Path], None] | None = None

    # ── Public API ──────────────────────────────────────

    def start(self):
        """Start watching in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._snapshot()  # initial baseline
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the watcher."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._running

    # ── Internals ───────────────────────────────────────

    def _poll_loop(self):
        while self._running:
            try:
                self._scan()
            except Exception:
                pass
            time.sleep(self._interval)

    def _snapshot(self) -> dict[str, float]:
        """Build a dict of {relpath: mtime} for all watched files."""
        mtimes: dict[str, float] = {}
        if not self._dir.exists():
            return mtimes
        for root, _dirs, files in os.walk(str(self._dir)):
            for fname in files:
                if not any(fname.endswith(p) for p in self._patterns):
                    continue
                abspath = os.path.join(root, fname)
                rel = os.path.relpath(abspath, str(self._dir)).replace("\\", "/")
                try:
                    mtimes[rel] = os.path.getmtime(abspath)
                except OSError:
                    continue
        return mtimes

    def _scan(self):
        """Scan for changes and emit events."""
        with self._lock:
            current = self._snapshot()
            old = self._mtimes

            # Added & Modified
            for rel, mtime in current.items():
                if rel not in old:
                    self._emit_added(rel)
                elif mtime > old[rel] + 0.1:  # 100ms fuzz
                    self._emit_modified(rel)

            # Removed
            for rel in old:
                if rel not in current:
                    self._emit_removed(rel)

            self._mtimes = current

    def _emit_added(self, rel: str):
        path = self._dir / rel
        if self.on_added:
            try:
                self.on_added(path)
            except Exception:
                pass

    def _emit_modified(self, rel: str):
        path = self._dir / rel
        if self.on_modified:
            try:
                self.on_modified(path)
            except Exception:
                pass

    def _emit_removed(self, rel: str):
        path = self._dir / rel
        if self.on_removed:
            try:
                self.on_removed(path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Skill Hot-Reloader
# ---------------------------------------------------------------------------

class SkillHotReloader:
    """Watches the skills/ directory and hot-reloads changed skills.

    Integrates with the global ``skill_manager`` singleton from
    ``core.skills``.  When a skill file (``skill.md``) is added,
    modified, or removed, the reloader updates the registry
    in-place — no restart needed.
    """

    def __init__(
        self,
        skills_dir: Path | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        if skills_dir is None:
            skills_dir = Path(__file__).parent.parent / SKILLS_DIR_NAME
        self._dir = Path(skills_dir)
        self._watcher = PluginWatcher(self._dir, poll_interval=poll_interval)
        self._watcher.on_added = self._on_file_changed
        self._watcher.on_modified = self._on_file_changed
        self._watcher.on_removed = self._on_file_removed
        self._reload_count = 0
        self._last_error: str | None = None

    # ── Public API ──────────────────────────────────────

    def start(self):
        """Begin watching for skill changes."""
        self._watcher.start()

    def stop(self):
        """Stop watching."""
        self._watcher.stop()

    @property
    def running(self) -> bool:
        return self._watcher.running

    def reload_all(self):
        """Force a full reload of all skills (for /skills reload command)."""
        from core.skills import skill_manager
        try:
            skill_manager.load_all()
            self._reload_count += 1
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)

    def stats(self) -> dict:
        return {
            "running": self.running,
            "watch_dir": str(self._dir),
            "reload_count": self._reload_count,
            "last_error": self._last_error,
        }

    # ── Callbacks ───────────────────────────────────────

    def _on_file_changed(self, path: Path):
        """Reload just the affected skill."""
        from core.skills import skill_manager
        try:
            # Determine skill folder (the immediate parent of skill.md)
            if path.name == "skill.md":
                skill_dir = path.parent
            elif path.suffix == ".py":
                skill_dir = path.parent
            else:
                return

            # Reload this specific skill
            skill_manager.load_skill(skill_dir)
            self._reload_count += 1
            self._last_error = None
        except Exception as e:
            self._last_error = str(e)

    def _on_file_removed(self, path: Path):
        """Remove skill from registry when its folder is deleted."""
        from core.skills import skill_manager
        try:
            if path.name == "skill.md":
                skill_name = path.parent.name
                skill_manager._skills.pop(skill_name, None)
                self._reload_count += 1
        except Exception as e:
            self._last_error = str(e)


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------

_hot_reloader: SkillHotReloader | None = None
_reloader_lock = threading.Lock()


def get_hot_reloader(
    skills_dir: Path | None = None,
    auto_start: bool = True,
) -> SkillHotReloader:
    """Return the global SkillHotReloader singleton."""
    global _hot_reloader
    with _reloader_lock:
        if _hot_reloader is None:
            _hot_reloader = SkillHotReloader(skills_dir=skills_dir)
            if auto_start:
                _hot_reloader.start()
        return _hot_reloader


class PluginLoader:
    """Interface for managing skills as plugins in the Web UI."""

    def list_plugins(self) -> list[dict[str, str | bool]]:
        """List all skills as plugins with their active status.

        Returns:
            List of plugin info dicts with 'name', 'enabled', and 'description'.
        """
        from core.skills import skill_manager
        skills = skill_manager.list_all()
        active = skill_manager.active
        return [
            {
                "name": s.name,
                "enabled": active is not None and active.name == s.name,
                "description": s.description,
            }
            for s in skills
        ]

    def enable(self, name: str) -> bool:
        """Activate a skill plugin by name.

        Args:
            name: The name of the skill plugin to enable.

        Returns:
            True if activation succeeded, False otherwise.
        """
        from core.skills import skill_manager
        return skill_manager.activate(name)

    def disable(self, name: str) -> None:
        """Deactivate the active skill plugin.

        Args:
            name: The name of the skill plugin to disable.
        """
        from core.skills import skill_manager
        skill_manager.deactivate()
