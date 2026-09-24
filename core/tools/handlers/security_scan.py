"""Security scan — check dependencies for known vulnerabilities."""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("widdx.tools.security_scan")


def _scan_python(root: Path) -> str:
    """Scan Python dependencies for vulnerabilities."""
    results = []
    list(root.rglob("requirements.txt")) + list(root.rglob("pyproject.toml"))

    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "audit"],
            capture_output=True, text=True, timeout=60,
            cwd=str(root),
        )
        if r.returncode == 0:
            results.append("pip-audit: no vulnerabilities found")
        else:
            results.append(f"pip-audit:\n{r.stdout[-1500:]}")
    except FileNotFoundError:
        results.append("pip-audit: not installed (pip install pip-audit)")
    except Exception as e:
        results.append(f"pip-audit error: {e}")

    return "\n".join(results) if results else "No Python security checks available"


def _scan_node(root: Path) -> str:
    """Scan Node.js dependencies for vulnerabilities."""
    if not (root / "package.json").exists():
        return ""

    try:
        r = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True, text=True, timeout=60,
            cwd=str(root),
        )
        if r.returncode == 0:
            return "npm audit: no vulnerabilities found"
        try:
            data = json.loads(r.stdout)
            vulns = data.get("vulnerabilities", {})
            total = sum(v.get("severity", "info") != "info" for v in vulns.values())
            if total == 0:
                return "npm audit: no vulnerabilities found"
            lines = [f"npm audit: {total} vulnerabilities found", ""]
            for pkg, info in vulns.items():
                sev = info.get("severity", "?")
                if sev != "info":
                    lines.append(f"  {sev.upper():7} {pkg} — {info.get('via', '')}")
            return "\n".join(lines[:20])
        except (json.JSONDecodeError, Exception):
            return f"npm audit:\n{r.stdout[-1000:]}"
    except FileNotFoundError:
        return "npm not found"
    except Exception as e:
        return f"npm audit error: {e}"


def _scan_rust(root: Path) -> str:
    """Scan Rust dependencies for vulnerabilities."""
    if not (root / "Cargo.toml").exists():
        return ""

    try:
        r = subprocess.run(
            ["cargo", "audit"],
            capture_output=True, text=True, timeout=120,
            cwd=str(root),
        )
        if r.returncode == 0:
            return "cargo audit: no vulnerabilities found"
        return f"cargo audit:\n{r.stdout[-1500:]}"
    except FileNotFoundError:
        return "cargo-audit: not installed (cargo install cargo-audit)"
    except Exception as e:
        return f"cargo audit error: {e}"


def _check_secrets(root: Path) -> str:
    """Scan for potential secrets/API keys in the codebase."""
    secrets_patterns = [
        (r'api[_-]?key\s*[=:]\s*["\'].+["\']', "API key"),
        (r'secret\s*[=:]\s*["\'].+["\']', "Secret"),
        (r'password\s*[=:]\s*["\'].+["\']', "Password"),
        (r'token\s*[=:]\s*["\'].+["\']', "Token"),
        (r'AKIA[0-9A-Z]{16}', "AWS Access Key"),
        (r'sk-[a-zA-Z0-9]{32,}', "OpenAI Key"),
        (r'ghp_[a-zA-Z0-9]{36}', "GitHub PAT"),
    ]

    findings = []
    for f in root.rglob("*"):
        if not f.is_file() or f.stat().st_size > 102400:
            continue
        if f.suffix in (".pyc", ".so", ".dll", ".png", ".jpg", ".svg", ".lock"):
            continue
        try:
            text = f.read_text("utf-8", errors="ignore")
            for pattern, label in secrets_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for m in matches:
                    rel = f.relative_to(root)
                    findings.append(f"  ⚠️  {label} found in {rel}:{text[:m.start()].count(chr(10)) + 1}")
        except Exception:
            continue

    if not findings:
        return "No secrets detected"

    return "Potential secrets found:\n" + "\n".join(findings[:20])


def _security_scan(path: str | None = None, scan_type: str = "all") -> str:
    """Scan project for security vulnerabilities and secrets."""
    root = Path(path) if path else Path(".")
    root = root.resolve()

    valid_types = {"all", "python", "node", "rust", "secrets"}
    if scan_type not in valid_types:
        return f"Invalid scan_type: {scan_type}. Choose from: {', '.join(sorted(valid_types))}"

    if not root.exists():
        return f"Path does not exist: {root}"

    buf = [f"🔒 Security Scan — {root.name}", ""]

    if scan_type in ("all", "python"):
        has_py = list(root.rglob("requirements.txt")) or list(root.rglob("pyproject.toml"))
        if not has_py and scan_type == "python":
            return "No Python project files found (requirements.txt or pyproject.toml)"
        py_result = _scan_python(root)
        if py_result:
            buf.append("📦 Python Dependencies:")
            buf.append("  " + py_result.replace("\n", "\n  "))
            buf.append("")

    if scan_type in ("all", "node"):
        has_node = root / "package.json"
        if not has_node.exists() and scan_type == "node":
            return f"No Node.js project found at {root}"
        node_result = _scan_node(root)
        if node_result:
            buf.append("📦 Node.js Dependencies:")
            buf.append("  " + node_result.replace("\n", "\n  "))
            buf.append("")

    if scan_type in ("all", "rust"):
        has_rust = root / "Cargo.toml"
        if not has_rust.exists() and scan_type == "rust":
            return f"No Rust project found at {root}"
        rust_result = _scan_rust(root)
        if rust_result:
            buf.append("📦 Rust Dependencies:")
            buf.append("  " + rust_result.replace("\n", "\n  "))
            buf.append("")

    if scan_type in ("all", "secrets"):
        secrets_result = _check_secrets(root)
        buf.append("🔑 Secrets Detection:")
        buf.append("  " + secrets_result.replace("\n", "\n  "))
        buf.append("")

    return "\n".join(buf)
