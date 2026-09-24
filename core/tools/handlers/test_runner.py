"""Test runner — detect and run tests for the project."""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("widdx.tools.test_runner")


def _detect_test_framework(root: Path) -> dict | None:
    """Detect which test framework to use."""
    if (root / "pyproject.toml").exists():
        text = (root / "pyproject.toml").read_text("utf-8")
        if "pytest" in text:
            return {"cmd": [sys.executable, "-m", "pytest", "-v"], "name": "pytest"}
        if "unittest" in text:
            return {"cmd": [sys.executable, "-m", "unittest", "discover", "-v"], "name": "unittest"}
        return {"cmd": [sys.executable, "-m", "pytest", "-v"], "name": "pytest"}

    if (root / "package.json").exists():
        return {"cmd": ["npm", "test", "--", "--verbose"], "name": "npm test"}

    if (root / "Cargo.toml").exists():
        return {"cmd": ["cargo", "test"], "name": "cargo test"}

    if (root / "go.mod").exists():
        return {"cmd": ["go", "test", "./..."], "name": "go test"}

    if (root / "Makefile").exists() or (root / "makefile").exists():
        return {"cmd": ["make", "test"], "name": "make test"}

    if list(root.rglob("test_*.py")) or list(root.rglob("*_test.py")):
        return {"cmd": [sys.executable, "-m", "pytest", "-v"], "name": "pytest"}

    if list(root.rglob("*.test.ts")) or list(root.rglob("*.test.js")):
        return {"cmd": ["npx", "jest", "--verbose"], "name": "jest"}

    return None


def _run_tests(path: str | None = None, test_path: str | None = None,
               framework: str | None = None, timeout: int = 120) -> str:
    """Run tests for the project."""
    root = Path(path) if path else Path(".")
    root = root.resolve()

    if not root.exists():
        return f"Path does not exist: {root}"

    if framework:
        runners = {
            "pytest": [sys.executable, "-m", "pytest", "-v"],
            "unittest": [sys.executable, "-m", "unittest", "discover", "-v"],
            "jest": ["npx", "jest", "--verbose"],
            "cargo": ["cargo", "test"],
            "go": ["go", "test", "./..."],
            "npm": ["npm", "test"],
        }
        cmd = runners.get(framework)
        if not cmd:
            return f"Unknown framework: {framework}. Available: {', '.join(runners.keys())}"
        if test_path:
            cmd = cmd + [test_path]
    else:
        detected = _detect_test_framework(root)
        if not detected:
            return "No test framework detected. Try --framework pytest|jest|cargo|go|npm|unittest"
        cmd = detected["cmd"]
        framework = detected["name"]
        if test_path:
            cmd = cmd + [test_path]

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        return f"⏱ Tests timed out after {timeout}s"
    except FileNotFoundError:
        return f"Command not found: {cmd[0]}"
    except Exception as e:
        return f"Error: {e}"

    output = r.stdout + "\n" + r.stderr
    summary = output[-2000:]

    if r.returncode == 0:
        last = [ln for ln in output.strip().splitlines() if ln][-3:] if output.strip() else []
        return f"✅ {framework} — all tests passed (exit 0)\n" + "\n".join(last) + "\n\n" + summary
    else:
        return f"❌ {framework} — {r.returncode} failure(s)\n\n{summary}"
