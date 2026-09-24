"""WIDDX — Terminal AI Chat Tool (root entry point).

Delegates to scripts.web_app which handles config resolution, port detection,
and web server startup. Use ``widdx-web`` after pip install for the same effect.
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path for direct ``python main.py`` usage
_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from core._path import ensure_project_root
    ensure_project_root()
except ImportError:
    pass  # core._path is optional for basic operation

from scripts.web_app import main as run

if __name__ == "__main__":
    run()
