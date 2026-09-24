"""Entry point to run WIDDX with Textual TUI (script).

Moved under `scripts/` and adjusted `sys.path` to reference project root.
"""

import sys
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
from tui.app import run_tui  # noqa: E402

if __name__ == "__main__":
    run_tui()
