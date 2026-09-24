"""WIDDX Nexus — Web Server entry point.

A thin wrapper around ``scripts.web.server`` with direct CORSMiddleware enabled.

Usage:

    python server.py              # → http://localhost:8000
    python server.py --port 9000  # → http://localhost:9000
"""

import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

# ── Direct CORS activation ──────────────────────────────────────────
# Enable CORSMiddleware directly in server.py (required for tests & prod)
try:
    from fastapi.middleware.cors import CORSMiddleware
    from scripts.web.server import app as fastapi_app, ALLOWED_ORIGINS

    # Guard against double registration (run() also adds it dynamically)
    _has_cors = any(
        getattr(m, "cls", None) == CORSMiddleware or getattr(m, "cls", None).__name__ == "CORSMiddleware"
        if hasattr(m, "cls") else False
        for m in getattr(fastapi_app, "user_middleware", [])
    )

    if not _has_cors:
        fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS if 'ALLOWED_ORIGINS' in dir() else ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
except Exception:
    # FastAPI not installed or import failed — will be handled in web_app
    pass

from scripts.web_app import main  # noqa: E402

if __name__ == "__main__":
    main()
