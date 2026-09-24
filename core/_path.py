"""Path setup — single source of truth for sys.path entries.

Every entry point (CLI, TUI, API, Web, tests) needs the project root
on sys.path. This module unifies that logic so we don't repeat
``sys.path.insert(0, ...)`` in 15+ files.

Usage:
    from core._path import ensure_project_root
    ensure_project_root()
"""

import sys
from pathlib import Path


def ensure_project_root() -> Path:
    """Add project root and ``scripts/`` to sys.path if not already there.

    Returns the project root Path.
    """
    # This file is at <root>/core/_path.py → root = parent of core/
    root = Path(__file__).resolve().parent.parent

    paths = [root, root / "scripts"]
    for p in paths:
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    return root
