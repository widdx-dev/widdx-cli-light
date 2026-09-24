"""WIDDX Nexus — Web UI launcher.

Usage:
    python scripts/web_app.py                  # → http://localhost:8000
    python scripts/web_app.py --port 9000      # → http://localhost:9000
    widdx-web                                  # after install

Host/port resolution order (first found wins):
    1. CLI args: --host 127.0.0.1 --port 9000
    2. .widdx/config.json: {"server": {"host": "...", "port": ...}}
    3. Default: 127.0.0.1:8000 (auto-increments if taken)

Multiple projects: run 'widdx-web' from each project directory.
Each can have its own port in .widdx/config.json.
If no port specified and default is taken, auto-increments (8001, 8002...).
"""

import json
import socket
import sys
from pathlib import Path


def _find_free_port(start_port: int, host: str = "127.0.0.1") -> int:
    """Find a free port starting from start_port."""
    port = start_port
    for _ in range(100):  # try 100 ports max
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1
    return start_port  # fallback — let uvicorn handle the error


def main():
    """Entry point for `widdx-web` command."""
    try:
        from core._path import ensure_project_root
        ensure_project_root()
    except ImportError:
        _root = str(Path(__file__).resolve().parent.parent)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from core._path import ensure_project_root
        ensure_project_root()

    # ── Defaults ──
    host = "0.0.0.0"  # all interfaces — accessible from other devices
    port = 8000

    # ── 1. Check .widdx/config.json ──
    cwd = Path.cwd()
    config_path = cwd / ".widdx" / "config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            server_cfg = cfg.get("server", {})
            if "host" in server_cfg:
                host = server_cfg["host"]
            if "port" in server_cfg:
                port = int(server_cfg["port"])
        except (json.JSONDecodeError, ValueError, OSError):
            pass

    # ── 2. CLI args override everything ──
    for i, arg in enumerate(sys.argv):
        if arg == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]
        elif arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    # ── 3. If default port is taken, find a free one ──
    port = _find_free_port(port, host)
    if port != 8000:
        print(f"⚠ Port 8000 in use — using port {port}")

    from core.log_setup import setup_logging
    setup_logging("widdx.web")

    # ── Check dependencies before importing ──
    try:
        from scripts.web.server import run as _run
    except ImportError as e:
        missing = str(e)
        print(f"\n❌ Missing dependency: {missing}")
        print("   Install: pip install widdx-nexus[api]")
        print("   Or:      pip install fastapi uvicorn\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Server import failed: {e}")
        print("   Check that Python SSL module is available.")
        print("   Try: python -c \"import ssl; print(ssl.OPENSSL_VERSION)\"\n")
        sys.exit(1)

    # Enable diagnostics
    try:
        from core.diagnostics import error_collector
        error_collector.enable()
    except Exception:
        pass

    print(f"WIDDX Nexus — http://{host}:{port}")
    _run(host=host, port=port)


if __name__ == "__main__":
    main()
