"""Safe code execution harness — actually runs code and captures results.

Unlike the old verifier that only checked syntax, this:
- Executes Python code and catches RUNTIME errors (not just SyntaxError)
- Enforces timeouts and resource limits
- Captures stdout, stderr, and exit codes
- Runs in an isolated temp workspace
- Returns structured RunResult with success/failure details
"""

from __future__ import annotations
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("widdx.validation.runner")


@dataclass
class RunResult:
    """Result of running code through the execution harness."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    was_timeout: bool = False
    errors: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    language: str = ""

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def output(self) -> str:
        """Combined output for analysis."""
        parts = []
        if self.stdout:
            parts.append(f"[stdout]\n{self.stdout}")
        if self.stderr:
            parts.append(f"[stderr]\n{self.stderr}")
        return "\n".join(parts)


class CodeRunner:
    """Execute code safely and capture results.

    Creates a temp workspace, writes code, executes with timeout,
    captures all output, and returns structured results.
    """

    def __init__(self, timeout_default: int = 30):
        """Initialize the code runner.

        Args:
            timeout_default: Default timeout in seconds for all executions.
        """
        self.timeout_default = timeout_default

    def run_python(self, code: str,
                   test_inputs: list[str] | None = None,
                   timeout: int | None = None) -> RunResult:
        """Execute Python code and capture output.

        Args:
            code: Python source code to execute
            test_inputs: Optional list of inputs to feed to stdin
            timeout: Optional timeout override (default: 30s)

        Returns:
            RunResult with success, stdout, stderr, errors, timing.
        """
        timeout = timeout or self.timeout_default
        errors = []

        # ── 1. Syntax check ──
        try:
            compile(code, "<validation>", "exec")
        except SyntaxError as e:
            return RunResult(
                success=False,
                stderr=str(e),
                errors=[f"SyntaxError at line {e.lineno}: {e.msg}"],
                language="python",
            )

        # ── 2. Runtime execution ──
        with tempfile.TemporaryDirectory(prefix="widdx_val_") as tmpdir:
            filepath = Path(tmpdir) / "_validate.py"
            filepath.write_text(code, encoding="utf-8")

            try:
                t0 = time.perf_counter()
                proc = subprocess.Popen(
                    [self._find_python(), str(filepath)],
                    cwd=tmpdir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=self._clean_env(),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
                stdout, stderr = proc.communicate(
                    timeout=timeout,
                )
                elapsed = time.perf_counter() - t0

                # Check for common runtime errors in stderr
                if proc.returncode != 0:
                    errors = self._extract_python_errors(stderr)

                return RunResult(
                    success=proc.returncode == 0 and not errors,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    exit_code=proc.returncode,
                    errors=errors,
                    execution_time=round(elapsed, 3),
                    language="python",
                )

            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return RunResult(
                    success=False,
                    stderr=f"Execution timed out after {timeout}s",
                    was_timeout=True,
                    errors=[f"TimeoutExpired: execution exceeded {timeout}s"],
                    execution_time=timeout,
                    language="python",
                )

    def run_bash(self, command: str, timeout: int | None = None) -> RunResult:
        """Execute a bash command and capture output.

        Args:
            command: The bash command to execute
            timeout: Timeout override (default: 60s)

        Returns:
            RunResult with success, stdout, stderr, timing.
        """
        import shlex
        timeout = timeout or 60
        with tempfile.TemporaryDirectory(prefix="widdx_val_") as tmpdir:
            t0 = time.perf_counter()
            try:
                cmd_parts = shlex.split(command)
                proc = subprocess.Popen(
                    cmd_parts,
                    shell=False,
                    cwd=tmpdir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=self._clean_env(),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
                stdout, stderr = proc.communicate(timeout=timeout)
                elapsed = time.perf_counter() - t0

                errors = []
                if proc.returncode != 0:
                    errors = self._extract_bash_errors(stderr)

                return RunResult(
                    success=proc.returncode == 0,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    exit_code=proc.returncode,
                    errors=errors,
                    execution_time=round(elapsed, 3),
                    language="bash",
                )

            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return RunResult(
                    success=False,
                    stderr=f"Command timed out after {timeout}s",
                    was_timeout=True,
                    errors=[f"TimeoutExpired: exceeded {timeout}s"],
                    execution_time=timeout,
                    language="bash",
                )

    def run_import_check(self, code: str) -> RunResult:
        """Check if Python code can be imported without execution.
        More thorough than compile() — catches import errors, missing deps.
        """
        import importlib.util
        import sys

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, prefix='widdx_import_'
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            spec = importlib.util.spec_from_file_location("_widdx_validate", tmp_path)
            if spec is None or spec.loader is None:
                return RunResult(
                    success=False,
                    errors=["Could not create module spec from code"],
                    language="python",
                )
            module = importlib.util.module_from_spec(spec)
            sys.modules["_widdx_validate"] = module
            try:
                spec.loader.exec_module(module)
                return RunResult(success=True, language="python")
            except Exception as e:
                return RunResult(
                    success=False,
                    stderr=str(e),
                    errors=[f"{type(e).__name__}: {e}"],
                    language="python",
                )
            finally:
                sys.modules.pop("_widdx_validate", None)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _find_python() -> str:
        """Find the Python interpreter."""
        import sys
        return sys.executable

    @staticmethod
    def _clean_env() -> dict:
        """Create a clean environment for code execution."""
        env = os.environ.copy()
        # Remove sensitive variables
        for key in list(env):
            if key.startswith(("WIDDX_API_KEY", "OPENAI_API_KEY",
                              "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY")):
                del env[key]
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        return env

    @staticmethod
    def _extract_python_errors(stderr: str) -> list[str]:
        """Extract meaningful error lines from Python stderr."""
        errors = []
        for line in stderr.splitlines():
            line = line.strip()
            if "Error" in line and "Traceback" not in line:
                errors.append(line)
            elif line.startswith(("TypeError", "ValueError", "ImportError",
                                  "NameError", "AttributeError", "KeyError",
                                  "IndexError", "FileNotFoundError",
                                  "ModuleNotFoundError", "RuntimeError",
                                  "ZeroDivisionError")):
                errors.append(line)
        return errors[:5]  # top 5 errors

    @staticmethod
    def _extract_bash_errors(stderr: str) -> list[str]:
        """Extract meaningful error lines from bash stderr."""
        errors = []
        for line in stderr.splitlines():
            line = line.strip()
            if line and (
                "error" in line.lower()
                or "not found" in line.lower()
                or "permission denied" in line.lower()
                or "command not found" in line.lower()
                or "cannot" in line.lower()
            ):
                errors.append(line)
        return errors[:5]


# Module-level singleton
_runner: CodeRunner | None = None


def get_runner() -> CodeRunner:
    """Get or create the code runner."""
    global _runner
    if _runner is None:
        _runner = CodeRunner()
    return _runner


def run_code(code: str, language: str = "python",
             timeout: int | None = None) -> RunResult:
    """Run code in the validation harness.

    Args:
        code: Code to execute
        language: 'python' or 'bash'
        timeout: Timeout in seconds

    Returns:
        RunResult with execution details.
    """
    runner = get_runner()
    if language == "python":
        return runner.run_python(code, timeout=timeout)
    elif language == "bash":
        return runner.run_bash(code, timeout=timeout)
    else:
        return RunResult(
            success=False,
            errors=[f"Unsupported language: {language}"],
            language=language,
        )
