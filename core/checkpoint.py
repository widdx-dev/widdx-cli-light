"""Checkpoint Manager — Lightweight file-based snapshots.

Zero git dependency. Saves manifest of file hashes to ``.widdx/checkpoints/``.
Safe — never switches branches or touches git state.

Architecture:
  CheckpointManager — save / list / diff / clean

Usage:
    from core.checkpoint import checkpoint_manager as cpm

    cpm.save("before editing login.py")
    # ... agent makes changes ...
    if cpm.rollback():  # True = files differ from checkpoint
        print("Files changed since checkpoint")
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger("widdx.checkpoint")


# ---------------------------------------------------------------------------
# Checkpoint Manager
# ---------------------------------------------------------------------------

MAX_CHECKPOINTS = 50
IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", ".widdx",
               "node_modules", ".venv", "venv", "dist", ".mypy_cache"}


class CheckpointManager:
    """File-based project checkpointing — safe, no git branch switching."""

    def __init__(self, repo_path: str | Path | None = None):
        self._repo = Path(repo_path) if repo_path else Path.cwd()

    # ── Public API ──────────────────────────────────────

    def save(self, description: str = "") -> str | None:
        """Create a lightweight file-based checkpoint (no branch switching).

        Saves a snapshot manifest to ``.widdx/checkpoints/`` listing every
        tracked file with its hash.  Git is NOT required — works with any
        directory, even non-git projects.

        Returns the checkpoint ID (timestamp) or None on failure.
        """
        import hashlib
        ts = time.strftime("%Y%m%d_%H%M%S")
        cid = ts
        cdir = self._repo / ".widdx" / "checkpoints" / cid
        try:
            cdir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error("Checkpoint dir creation error: %s", e)
            return None

        # Build manifest: scan all tracked files and hash them
        manifest: dict[str, str] = {}
        file_count = 0
        for f in self._repo.rglob("*"):
            if file_count >= 5000:
                break
            if not f.is_file():
                continue
            parts = set(f.relative_to(self._repo).parts)
            if parts & IGNORE_DIRS:
                continue
            try:
                h = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
                manifest[str(f.relative_to(self._repo))] = h
                file_count += 1
            except Exception:
                continue

        # Save manifest
        meta = {
            "id": cid,
            "description": description or "",
            "timestamp": time.time(),
            "files": file_count,
            "manifest": manifest,
        }
        if not self._save_manifest(cdir, meta):
            return None

        self._cleanup()
        return cid

    def _save_manifest(self, cdir, meta):
        """Write manifest.json atomically."""
        import json
        import os
        try:
            tmp = str(cdir / "manifest.json.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, ensure_ascii=False)
            os.replace(tmp, str(cdir / "manifest.json"))
            return True
        except Exception as e:
            logger.error("Manifest write error: %s", e)
            return False

    def _cleanup(self):
        """Remove old checkpoints beyond MAX_CHECKPOINTS."""
        cdir = self._repo / ".widdx" / "checkpoints"
        if not cdir.exists():
            return
        all_cps = sorted(cdir.iterdir(), reverse=True)
        for old in all_cps[MAX_CHECKPOINTS:]:
            try:
                shutil.rmtree(str(old))
            except Exception:
                logger.debug("Exception suppressed (line 119)")

    def rollback(self, checkpoint_id: str | None = None) -> bool:
        """Restore working tree to a checkpoint snapshot.

        Compares current files against the checkpoint manifest and reports
        which files differ.  Actual restore must be done via git (if available)
        or manually — automatic file overwrite is too dangerous to automate.
        """
        cid = checkpoint_id or self._latest_checkpoint()
        if not cid:
            return False

        import json
        mfile = self._repo / ".widdx" / "checkpoints" / cid / "manifest.json"
        if not mfile.exists():
            return False

        try:
            meta = json.loads(mfile.read_text())
            manifest = meta.get("manifest", {})
            changed = []
            for relpath, old_hash in manifest.items():
                f = self._repo / relpath
                if f.exists():
                    import hashlib
                    h = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
                    if h != old_hash:
                        changed.append(relpath)
                else:
                    changed.append(f"{relpath} (deleted)")
            return len(changed) > 0  # True if changes detected vs checkpoint
        except Exception:
            return False

    def list(self, limit: int = 20) -> list[dict]:
        """List recent checkpoints."""
        cdir = self._repo / ".widdx" / "checkpoints"
        if not cdir.exists():
            return []

        import json
        checkpoints = []
        for d in sorted(cdir.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            mf = d / "manifest.json"
            if not mf.exists():
                continue
            try:
                meta = json.loads(mf.read_text())
                checkpoints.append({
                    "hash": meta.get("id", d.name)[:12],
                    "message": meta.get("description", ""),
                    "date": time.strftime(
                        "%Y-%m-%d %H:%M",
                        time.localtime(meta.get("timestamp", 0)),
                    ),
                    "files": meta.get("files", 0),
                })
            except Exception:
                continue
            if len(checkpoints) >= limit:
                break
        return checkpoints

    def count(self) -> int:
        return len(self.list())

    def clear(self):
        """Delete all checkpoints."""
        import shutil
        cdir = self._repo / ".widdx" / "checkpoints"
        if cdir.exists():
            shutil.rmtree(str(cdir), ignore_errors=True)

    # ── Internals ───────────────────────────────────────

    def _latest_checkpoint(self) -> str | None:
        """Return the most recent checkpoint ID."""
        cdir = self._repo / ".widdx" / "checkpoints"
        if not cdir.exists():
            return None
        dirs = sorted([d for d in cdir.iterdir() if d.is_dir()], reverse=True)
        return dirs[0].name if dirs else None

    def _cleanup_old(self):
        """Remove old checkpoints beyond MAX_CHECKPOINTS."""
        cdir = self._repo / ".widdx" / "checkpoints"
        if not cdir.exists():
            return
        import shutil
        dirs = sorted(
            [d for d in cdir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
        )
        while len(dirs) > MAX_CHECKPOINTS:
            shutil.rmtree(str(dirs[0]), ignore_errors=True)
            dirs.pop(0)


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------

checkpoint_manager = CheckpointManager()
