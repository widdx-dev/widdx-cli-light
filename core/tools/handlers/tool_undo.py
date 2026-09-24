"""Tool undo — keep history of file changes and allow undo."""

import logging
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("widdx.tools.tool_undo")

_UNDO_DIR: Path | None = None
_undo_stack: list[dict[str, Any]] = []
_MAX_UNDO = 50


def _get_undo_dir() -> Path:
    global _UNDO_DIR
    if _UNDO_DIR is None:
        _UNDO_DIR = Path(tempfile.mkdtemp(prefix="widdx_undo_"))
    return _UNDO_DIR


def _record_snapshot(file_path: str) -> bool:
    """Record a snapshot of a file before modification."""
    p = Path(file_path).resolve()
    if not p.exists():
        return False

    try:
        content = p.read_bytes()
        undo_dir = _get_undo_dir()
        ts = int(time.time() * 1000)
        snapshot_path = undo_dir / f"{p.name}.{ts}.snap"
        snapshot_path.write_bytes(content)

        _undo_stack.append({
            "timestamp": ts,
            "file_path": str(p),
            "snapshot": str(snapshot_path),
            "action": "edit",
        })
        if len(_undo_stack) > _MAX_UNDO:
            old = _undo_stack.pop(0)
            try:
                Path(old["snapshot"]).unlink(missing_ok=True)
            except Exception:
                logger.debug("Exception suppressed (line 46)")

        return True
    except Exception as e:
        logger.debug("Failed to record snapshot: %s", e)
        return False


def _undo_last() -> str:
    """Undo the last recorded file change."""
    if not _undo_stack:
        return "Nothing to undo"

    entry = _undo_stack.pop()
    file_path = Path(entry["file_path"])
    snapshot_path = Path(entry["snapshot"])

    if not snapshot_path.exists():
        return f"Snapshot lost for {file_path}"

    try:
        content = snapshot_path.read_bytes()
        file_path.write_bytes(content)
        snapshot_path.unlink(missing_ok=True)
        return f"✅ Undone: {file_path} restored to before '{entry.get('action', 'edit')}'"
    except Exception as e:
        return f"Failed to undo {file_path}: {e}"


def _undo_list() -> str:
    """List recent undo entries."""
    if not _undo_stack:
        return "No undo history"
    lines = [f"📋 Undo History ({len(_undo_stack)} entries):", ""]
    for i, entry in enumerate(reversed(_undo_stack[-10:]), 1):
        ts = time.strftime("%H:%M:%S", time.localtime(entry["timestamp"] / 1000))
        lines.append(f"  [{len(_undo_stack) - i + 1}] {ts} — {entry['file_path']}")
    return "\n".join(lines)


def intercept_edit(file_path: str):
    """Called before an edit to record the original content."""
    _record_snapshot(file_path)


def _tool_undo(action: str = "undo", file_path: str | None = None) -> str:
    """Undo file changes made during this session."""
    actions = {
        "undo": _undo_last,
        "list": _undo_list,
        "record": lambda: (
            f"Snapshot recorded for {file_path}"
            if file_path and _record_snapshot(file_path)
            else "file_path required"
        ),
    }
    handler = actions.get(action)
    if not handler:
        return f"Unknown action: {action}. Use: undo, list, record"
    return handler()
