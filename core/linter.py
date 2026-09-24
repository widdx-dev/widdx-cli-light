"""Linter Auto-Fix — Run linters after agent edits and fix issues.

Architecture:
  LinterRunner   — detect language, run linter, return results
  LintResult     — structured output with errors, warnings, fix status

Usage:
    from core.linter import LinterRunner

    runner = LinterRunner()
    result = runner.check("src/main.py")
    if result.errors:
        print(result.format_for_agent())  # feed back to agent for fixing
"""

from __future__ import annotations
import logging

import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
logger = logging.getLogger("widdx.linter")


@dataclass
class LintIssue:
    line: int = 0
    col: int = 0
    message: str = ""
    rule: str = ""
    severity: str = "error"   # "error" | "warning"


@dataclass
class LintResult:
    file_path: str
    language: str = "unknown"
    errors: list[LintIssue] = field(default_factory=list)
    warnings: list[LintIssue] = field(default_factory=list)
    linter_used: str = ""
    fix_applied: bool = False
    raw_output: str = ""

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def format_for_agent(self) -> str:
        """Format issues as a message the agent can understand."""
        if self.ok and not self.warnings:
            return f"Lint ({self.linter_used}): no issues in {self.file_path}"

        lines = [f"Lint ({self.linter_used}) found issues in {self.file_path}:"]
        for e in self.errors[:10]:
            lines.append(f"  ERROR line {e.line}: {e.message} [{e.rule}]")
        for w in self.warnings[:5]:
            lines.append(f"  WARN line {w.line}: {w.message} [{w.rule}]")
        return "\n".join(lines)


class LinterRunner:
    """Run language-appropriate linters on edited files."""

    # Map extensions to language names
    EXT_MAP = {
        ".py": "python", ".pyi": "python",
        ".js": "javascript", ".mjs": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".jsx": "javascript",
        ".css": "css", ".scss": "css", ".less": "css",
        ".html": "html", ".htm": "html",
        ".json": "json",
        ".md": "markdown",
        ".go": "go",
        ".rs": "rust",
    }

    def check(self, file_path: str | Path, auto_fix: bool = True) -> LintResult:
        """Run linter on a file. Returns LintResult."""
        path = Path(file_path)
        if not path.exists():
            return LintResult(file_path=str(path), language="missing")

        lang = self.detect_language(path)
        result = LintResult(file_path=str(path), language=lang)

        if lang == "python":
            result = self._check_python(path, auto_fix)
        elif lang in ("javascript", "typescript"):
            result = self._check_javascript(path, auto_fix)
        elif lang == "css":
            result = self._check_css(path)

        return result

    def detect_language(self, path: Path) -> str:
        return self.EXT_MAP.get(path.suffix.lower(), "unknown")

    # ── Python ──────────────────────────────────────────

    def _check_python(self, path: Path, auto_fix: bool) -> LintResult:
        result = LintResult(file_path=str(path), language="python")

        # Try ruff first (fast, modern)
        ruff = shutil.which("ruff")
        if ruff:
            return self._run_ruff(path, auto_fix, result)

        # Fall back to pyflakes
        pyflakes = shutil.which("pyflakes")
        if pyflakes:
            result.linter_used = "pyflakes"
            try:
                r = subprocess.run(
                    ["pyflakes", str(path)],
                    capture_output=True, text=True, timeout=15,
                )
                result.raw_output = r.stdout + r.stderr
                result.errors = self._parse_pyflakes(r.stdout)
            except Exception:
                pass
            return result

        # Last resort: py_compile
        result.linter_used = "py_compile"
        import py_compile as pc
        try:
            pc.compile(str(path), doraise=True)
        except pc.PyCompileError as e:
            result.errors.append(LintIssue(message=str(e)[:200], rule="compile"))
        return result

    def _run_ruff(self, path: Path, auto_fix: bool, result: LintResult) -> LintResult:
        result.linter_used = "ruff"
        try:
            cmd = ["ruff", "check"]
            if auto_fix:
                cmd.append("--fix")
            cmd.extend(["--output-format", "text", str(path)])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            result.raw_output = r.stdout
            result.fix_applied = auto_fix and r.returncode == 0
            result.errors = self._parse_ruff(r.stdout)
        except Exception:
            pass
        return result

    def _parse_ruff(self, output: str) -> list[LintIssue]:
        issues = []
        for line in output.strip().split("\n"):
            # Format: path:line:col: CODE message
            if ":" not in line:
                continue
            parts = line.split(":", 3)
            if len(parts) >= 4:
                try:
                    issues.append(LintIssue(
                        line=int(parts[1]),
                        col=int(parts[2]) if len(parts) > 2 else 0,
                        message=parts[3].strip(),
                        rule=parts[3].split()[0] if parts[3].strip() else "",
                    ))
                except ValueError:
                    continue
        return issues

    def _parse_pyflakes(self, output: str) -> list[LintIssue]:
        issues = []
        for line in output.strip().split("\n"):
            # Format: path:line: message
            if ":" not in line:
                continue
            parts = line.split(":", 2)
            if len(parts) >= 3:
                try:
                    issues.append(LintIssue(
                        line=int(parts[1]),
                        message=parts[2].strip(),
                    ))
                except ValueError:
                    continue
        return issues

    # ── JavaScript ──────────────────────────────────────

    def _check_javascript(self, path: Path, auto_fix: bool) -> LintResult:
        result = LintResult(file_path=str(path), language="javascript")

        # Node.js syntax check (always available)
        node = shutil.which("node")
        if node:
            result.linter_used = "node --check"
            try:
                r = subprocess.run(
                    [node, "--check", str(path)],
                    capture_output=True, text=True, timeout=15,
                )
                if r.returncode != 0:
                    err = r.stderr or r.stdout
                    # Parse line number from "at line X"
                    import re
                    m = re.search(r'line\s+(\d+)', err)
                    line_no = int(m.group(1)) if m else 1
                    result.errors.append(LintIssue(
                        line=line_no,
                        message=err[:200],
                        rule="syntax",
                    ))
            except Exception:
                pass

        # ESLint if available
        eslint = shutil.which("eslint")
        if eslint:
            result.linter_used = "eslint"
            try:
                cmd = ["eslint", str(path)]
                if auto_fix:
                    cmd.insert(1, "--fix")
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                result.raw_output = r.stdout
                result.fix_applied = auto_fix
            except Exception:
                pass

        return result

    # ── CSS ─────────────────────────────────────────────

    def _check_css(self, path: Path) -> LintResult:
        result = LintResult(file_path=str(path), language="css")
        stylelint = shutil.which("stylelint")
        if stylelint:
            result.linter_used = "stylelint"
            try:
                r = subprocess.run(
                    ["stylelint", str(path)],
                    capture_output=True, text=True, timeout=20,
                )
                result.raw_output = r.stdout
            except Exception:
                pass
        return result


# Global
linter = LinterRunner()
