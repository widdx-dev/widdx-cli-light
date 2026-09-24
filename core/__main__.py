"""CLI launcher for `python -m core` — launches the terminal interface."""
import sys
try:
    from core._path import ensure_project_root  # noqa: F401
except ImportError:
    from pathlib import Path
    _root = str(Path(__file__).resolve().parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)

from core.cli import run

if __name__ == "__main__":
    run()
