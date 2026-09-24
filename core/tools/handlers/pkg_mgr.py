"""Package manager — install, update, remove packages (npm, pip, cargo, go)."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("widdx.tools.pkg_mgr")


def _detect_pkg_managers(path: str | Path | None = None) -> dict[str, Path]:
    """Detect which package managers are available in the project."""
    root = Path(path) if path else Path(".")
    detected = {}
    if (root / "package.json").exists():
        detected["npm"] = root / "package.json"
    if (root / "yarn.lock").exists() or (root / "yarn.json").exists():
        detected["yarn"] = root
    if (root / "pnpm-lock.yaml").exists():
        detected["pnpm"] = root
    if (root / "requirements.txt").exists():
        detected["pip"] = root / "requirements.txt"
    if (root / "pyproject.toml").exists():
        detected["pip"] = root / "pyproject.toml"
    if (root / "Cargo.toml").exists():
        detected["cargo"] = root / "Cargo.toml"
    if (root / "go.mod").exists():
        detected["go"] = root / "go.mod"
    return detected


def _run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[str, int]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        out = (r.stdout + "\n" + r.stderr).strip()
        return out[-2000:], r.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out", -1
    except FileNotFoundError:
        return f"Command not found: {cmd[0]}", -1
    except Exception as e:
        return str(e), -1


def _pkg_mgr(action: str = "detect", package: str = "", pkg_manager: str = "auto",
             path: str | None = None) -> str:
    """Manage packages using the project's package manager."""
    root = Path(path) if path else Path(".")
    detected = _detect_pkg_managers(root)

    if action == "detect":
        if not detected:
            return "No package manager detected in project"
        buf = ["📦 Detected package managers:"]
        for mgr, config_file in detected.items():
            buf.append(f"  - {mgr} ({config_file})")
        return "\n".join(buf)

    if pkg_manager == "auto":
        if "pnpm" in detected:
            pkg_manager = "pnpm"
        elif "yarn" in detected:
            pkg_manager = "yarn"
        elif "npm" in detected:
            pkg_manager = "npm"
        elif "pip" in detected:
            pkg_manager = "pip"
        elif "cargo" in detected:
            pkg_manager = "cargo"
        elif "go" in detected:
            pkg_manager = "go"
        else:
            return "No package manager detected. Specify one: npm, pip, cargo, go"

    cmds = {
        "npm": {"install": ["npm", "install"], "add": ["npm", "install", package], "remove": ["npm", "uninstall", package], "update": ["npm", "update"], "list": ["npm", "list", "--depth=0"]},
        "yarn": {"install": ["yarn", "install"], "add": ["yarn", "add", package], "remove": ["yarn", "remove", package], "update": ["yarn", "upgrade"], "list": ["yarn", "list", "--depth=0"]},
        "pnpm": {"install": ["pnpm", "install"], "add": ["pnpm", "add", package], "remove": ["pnpm", "remove", package], "update": ["pnpm", "update"], "list": ["pnpm", "list", "--depth=0"]},
        "pip": {"install": ["pip", "install", "-r", "requirements.txt"] if (root / "requirements.txt").exists() else ["pip", "install", "."], "add": ["pip", "install", package], "remove": ["pip", "uninstall", "-y", package], "update": ["pip", "install", "--upgrade", package] if package else ["pip", "list", "--outdated"], "list": ["pip", "list"]},
        "cargo": {"install": ["cargo", "build"], "add": ["cargo", "add", package], "remove": ["cargo", "remove", package], "update": ["cargo", "update"], "list": ["cargo", "tree", "--depth", "1"]},
        "go": {"install": ["go", "mod", "download"], "add": ["go", "get", package], "remove": ["go", "mod", "tidy"], "update": ["go", "get", "-u"] + ([package] if package else []), "list": ["go", "list", "-m", "all"]},
    }

    mgr_cmds = cmds.get(pkg_manager)
    if not mgr_cmds:
        return f"Unknown package manager: {pkg_manager}. Supported: npm, yarn, pnpm, pip, cargo, go"

    cmd = mgr_cmds.get(action)
    if not cmd:
        return f"Unknown action: {action}. Available: install, add, remove, update, list"

    out, rc = _run_cmd(cmd, cwd=root)
    if rc == 0:
        return f"✅ {pkg_manager} {action} completed\n{out[-1500:]}"
    return f"❌ {pkg_manager} {action} failed (code {rc})\n{out[-1500:]}"
