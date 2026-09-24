"""WIDDX Web launcher — entry point for widdx-we command."""
import sys
from pathlib import Path

# Ensure project root is in sys.path
_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from widdx_web import main

if __name__ == "__main__":
    main()
