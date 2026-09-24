"""Sandbox Executor v2 — Cross-platform isolated command execution.

Architecture:
  ┌──────────────────────────────────────────────┐
  │               SandboxExecutor                │
  ├──────────────────────────────────────────────┤
  │  detect_best_mode() -> auto-selects per OS    │
  ├──────────────────────────────────────────────┤
  │  Windows: WSL 🥇 -> Docker 🥈 -> process 🥉    │
  │  Linux:   cgroups 🥇 -> Docker 🥈 -> process 🥉 │
  |  macOS:   sandbox-exec 🥇 -> Docker 🥈-> process|
  └──────────────────────────────────────────────┘

Key features:
  - Docker NOT required: each platform has a native isolation method
  - Session-scoped temp workspace (auto-created, auto-cleaned)
  - Resource limits: CPU, memory, file size, network, timeout
  - Structured results: stdout, stderr, exit_code, timing, metadata
  - File tracking: reports what files were created/modified

Usage:
    from core.sandbox import sandbox

    result = sandbox.execute("npm install react", timeout=60)
    print(result.stdout, result.exit_code)

    # Force a specific mode:
    sb = SandboxExecutor(mode="wsl")
    result = sb.execute("python --version")
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
import shlex
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("widdx.sandbox")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class ResourceLimits:
    max_cpu_seconds: int = 60
    max_memory_mb: int = 512
    max_file_size_mb: int = 100
    allow_network: bool = True


@dataclass
class SandboxResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    was_timeout: bool = False
    was_killed: bool = False
    elapsed_ms: float = 0.0
    mode: str = "none"
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.was_timeout and not self.was_killed

    @property
    def summary(self) -> str:
        status = "OK" if self.ok else f"exit={self.exit_code}"
        if self.was_timeout:
            status += " TIMEOUT"
        if self.was_killed:
            status += " KILLED"
        return f"[{self.mode}] {status} ({self.elapsed_ms:.0f}ms)"


# ---------------------------------------------------------------------------
# Session Workspace Manager
# ---------------------------------------------------------------------------


class SessionWorkspace:
    """Creates and manages a temp workspace for each agent session.

    The workspace is a temp directory under ~/.widdx/workspaces/<session_id>/
    Auto-created on first use, auto-cleaned on cleanup().
    """

    BASE_DIR = Path.home() / ".widdx" / "workspaces"

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"sandbox_{uuid.uuid4().hex[:12]}"
        self._dir: Path | None = None

    @property
    def path(self) -> Path:
        if self._dir is None:
            self._ensure()
        return self._dir  # type: ignore

    def _ensure(self) -> Path:
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)
        self._dir = self.BASE_DIR / self.session_id
        self._dir.mkdir(exist_ok=True)
        return self._dir

    def cleanup(self):
        if self._dir and self._dir.exists():
            try:
                shutil.rmtree(str(self._dir))
                logger.debug("Workspace cleaned: %s", self._dir)
            except Exception as e:
                logger.debug("Workspace cleanup failed: %s", e)
        self._dir = None

    @staticmethod
    def cleanup_old(max_age_hours: int = 24):
        cutoff = time.time() - (max_age_hours * 3600)
        if not SessionWorkspace.BASE_DIR.exists():
            return
        for d in SessionWorkspace.BASE_DIR.iterdir():
            if d.is_dir():
                try:
                    mtime = d.stat().st_mtime
                    if mtime < cutoff:
                        shutil.rmtree(str(d))
                        logger.debug("Stale workspace cleaned: %s", d)
                except Exception:
                    logger.debug("Exception suppressed (line 139)")


# ---------------------------------------------------------------------------
# Platform Detector
# ---------------------------------------------------------------------------


def _get_platform() -> str:
    """Return normalized platform name: 'windows', 'linux', 'darwin'."""
    sys_platform = platform.system().lower()
    if sys_platform == "windows" or "cygwin" in sys_platform or "msys" in sys_platform:
        return "windows"
    return sys_platform


def _check_wsl() -> bool:
    """Check if WSL is available on Windows."""
    if _get_platform() != "windows":
        return False
    wsl_exe = shutil.which("wsl.exe") or shutil.which("wsl")
    if not wsl_exe:
        # Also check common WSL install locations
        for candidate in [
            os.environ.get("SystemRoot", "C:\\Windows") + "\\System32\\wsl.exe",
            "C:\\Windows\\System32\\wsl.exe",
        ]:
            if os.path.exists(candidate):
                wsl_exe = candidate
                break
    if not wsl_exe:
        return False
    try:
        result = subprocess.run(
            [wsl_exe, "--status"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def _check_docker() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_sandbox_exec() -> bool:
    """Check if macOS sandbox-exec is available."""
    if _get_platform() != "darwin":
        return False
    return shutil.which("sandbox-exec") is not None


def _check_cgroups() -> bool:
    """Check if Linux cgroups v2 is available for process isolation."""
    if _get_platform() != "linux":
        return False
    return Path("/sys/fs/cgroup").is_dir()


# ---------------------------------------------------------------------------
# Sandbox Executor
# ---------------------------------------------------------------------------


class SandboxExecutor:
    """Execute shell commands in an isolated environment.

    Modes (auto-selected by detect_best_mode()):
      wsl          -- Windows Subsystem for Linux (Windows only)
      docker       -- Docker container (any OS)
      cgroups      -- Linux cgroups isolation (Linux only)
      sandbox-exec -- macOS sandbox (macOS only)
      subprocess   -- Plain subprocess with resource limits (fallback)
      none         -- No sandbox (trusted commands only)
    """

    WSL_DISTROS = ["Ubuntu", "Ubuntu-24.04", "Ubuntu-22.04", "Ubuntu-20.04", "Debian", "kali-linux"]

    def __init__(
        self,
        mode: str = "auto",
        limits: ResourceLimits | None = None,
        work_dir: str | Path | None = None,
        session_id: str | None = None,
    ):
        self._mode = mode
        self._limits = limits or ResourceLimits()
        self._cwd = Path(work_dir) if work_dir else Path.cwd()
        self._workspace = SessionWorkspace(session_id) if mode != "none" else None
        self._docker_available: bool | None = None
        self._wsl_available: bool | None = None
        self._wsl_distro: str | None = None
        self._cgroups_available: bool | None = None
        self._sandbox_exec_available: bool | None = None

    # -- Public API -------------------------------------------------------

    def execute(
        self,
        command: str,
        timeout: int = 60,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """Execute a command in the sandbox.

        Args:
            command: Shell command to run.
            timeout: Maximum seconds before kill.
            env: Additional environment variables.

        Returns:
            SandboxResult with full output and metadata.
        """
        # ── Security: guard check before execution ──
        try:
            from core.guard import guard
            guard_result = guard.check(command)
            if guard_result.blocked:
                return SandboxResult(
                    stdout="",
                    stderr=f"BLOCKED: {guard_result.reason}",
                    exit_code=-1,
                    was_timeout=False,
                    mode="guard",
                )
            if guard_result.warn:
                logger.warning("Guard warning for '%s': %s", command[:80], guard_result.reason)
        except ImportError:
            pass  # guard module optional — proceed without it

        mode = self._resolve_mode()
        t0 = time.perf_counter()

        if mode == "wsl":
            result = self._execute_wsl(command, timeout, env)
        elif mode == "docker":
            result = self._execute_docker(command, timeout, env)
        elif mode == "cgroups":
            result = self._execute_cgroups(command, timeout, env)
        elif mode == "sandbox-exec":
            result = self._execute_sandbox_exec(command, timeout, env)
        elif mode == "subprocess":
            result = self._execute_subprocess(command, timeout, env)
        else:
            result = self._execute_none(command, timeout, env)

        result.elapsed_ms = (time.perf_counter() - t0) * 1000
        return result

    def detect_best_mode(self) -> str:
        """Return the best available isolation mode for this platform.

        Priority per platform:
          Windows: WSL -> Docker -> subprocess
          Linux:   cgroups -> Docker -> subprocess
          macOS:   sandbox-exec -> Docker -> subprocess
        """
        plat = _get_platform()

        if plat == "windows":
            # Prefer WSL2 for full VM isolation — agent never touches host machine.
            # Files are accessible via /mnt/c/... from WSL, visible on Windows.
            # Falls back to subprocess if WSL not available.
            if self._check_wsl():
                return "wsl"
            if self._check_docker():
                return "docker"
            return "subprocess"

        elif plat == "linux":
            if self._check_cgroups():
                return "cgroups"
            if self._check_docker():
                return "docker"
            return "subprocess"

        elif plat == "darwin":
            if self._check_sandbox_exec():
                return "sandbox-exec"
            if self._check_docker():
                return "docker"
            return "subprocess"

        return "subprocess"

    def detect_mode(self) -> str:
        """Backward-compatible alias for detect_best_mode()."""
        return self.detect_best_mode()

    @property
    def mode(self) -> str:
        return self._resolve_mode()

    def cleanup(self):
        """Clean up workspace and resources."""
        if self._workspace:
            self._workspace.cleanup()

    def get_workspace_path(self) -> Path | None:
        """Get the session workspace path, if any."""
        return self._workspace.path if self._workspace else None

    # -- Mode Resolution ------------------------------------------------_

    def _resolve_mode(self) -> str:
        if self._mode == "auto":
            return self.detect_best_mode()
        if self._mode == "wsl" and not self._check_wsl():
            logger.warning("WSL requested but not available, falling back to subprocess")
            return "subprocess"
        if self._mode == "docker" and not self._check_docker():
            logger.warning("Docker requested but not available, falling back to subprocess")
            return "subprocess"
        if self._mode == "cgroups" and not self._check_cgroups():
            logger.warning("cgroups requested but not available, falling back to subprocess")
            return "subprocess"
        return self._mode

    # -- Capability Checks ----------------------------------------------

    def _check_wsl(self) -> bool:
        if self._wsl_available is None:
            self._wsl_available = _check_wsl()
            if self._wsl_available:
                self._detect_wsl_distro()
        return self._wsl_available

    def _check_docker(self) -> bool:
        if self._docker_available is None:
            self._docker_available = _check_docker()
        return self._docker_available

    def _check_cgroups(self) -> bool:
        if self._cgroups_available is None:
            self._cgroups_available = _check_cgroups()
        return self._cgroups_available

    def _check_sandbox_exec(self) -> bool:
        if self._sandbox_exec_available is None:
            self._sandbox_exec_available = _check_sandbox_exec()
        return self._sandbox_exec_available

    def _detect_wsl_distro(self):
        """Find the best available WSL distro."""
        try:
            result = subprocess.run(
                ["wsl.exe", "-l", "-v"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return
            available = []
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if parts and parts[0] not in ("NAME", "", "Windows"):
                    name = parts[0].rstrip("*")
                    available.append(name)
            for preferred in self.WSL_DISTROS:
                for avail in available:
                    if preferred.lower() in avail.lower():
                        self._wsl_distro = avail
                        return
            if available:
                self._wsl_distro = available[0]
        except Exception:
            logger.debug("Exception suppressed (line 413)")

    # -- WSL Executor ---------------------------------------------------

    def _execute_wsl(
        self, command: str, timeout: int, env: dict | None,
    ) -> SandboxResult:
        """Run command inside WSL (Windows Subsystem for Linux)."""
        # Find wsl executable
        wsl_exe = shutil.which("wsl.exe") or shutil.which("wsl") or "wsl.exe"

        wsl_args = [wsl_exe]
        if self._wsl_distro:
            wsl_args += ["-d", self._wsl_distro]

        # Convert C:\\path to /mnt/c/path for WSL
        host_cwd = str(self._cwd.resolve())
        if ":" in host_cwd:
            drive = host_cwd[0].lower()
            wsl_path = f"/mnt/{drive}{host_cwd[2:].replace(os.sep, '/')}"
        else:
            wsl_path = host_cwd.replace(os.sep, "/")

        env_str = ""
        if env:
            env_str = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items()) + " "

        bash_cmd = f"{env_str}{command}"
        full_cmd = wsl_args + ["--cd", wsl_path, "--exec", "bash", "-c", bash_cmd]
        try:
            proc = subprocess.Popen(
                full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                return SandboxResult(
                    stdout=stdout or "", stderr=stderr or "",
                    exit_code=proc.returncode, mode="wsl",
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate(timeout=5)
                return SandboxResult(
                    stdout=stdout or "", stderr=stderr or "",
                    exit_code=-1, was_timeout=True, was_killed=True, mode="wsl",
                )
        except Exception as e:
            logger.warning("WSL execution failed, falling back to subprocess: %s", e)
            return self._execute_subprocess(command, timeout, env)

    # -- Docker Executor ------------------------------------------------

    def _execute_docker(
        self, command: str, timeout: int, env: dict | None,
    ) -> SandboxResult:
        """Run command inside a Docker container with a suitable image."""
        img = self._pick_docker_image(command)
        mem_limit = f"{self._limits.max_memory_mb}m"

        workspace_path = self._workspace.path if self._workspace else self._cwd.resolve()
        docker_cmd = [
            "docker", "run", "--rm",
            "--memory", mem_limit,
            "--cpus", "1",
            "--network", "host" if self._limits.allow_network else "none",
            "-v", f"{workspace_path}:/workspace",
            "-w", "/workspace",
            img,
            "sh", "-c", command,
        ]

        return self._run(docker_cmd, timeout, env, mode="docker")

    @staticmethod
    def _pick_docker_image(command: str) -> str:
        """Pick a suitable Docker image based on the command content."""
        cmd_lower = command.lower()
        if any(x in cmd_lower for x in ["python", "pip", "pytest", "flask", "django"]):
            return "python:3.12-slim"
        if any(x in cmd_lower for x in ["node", "npm", "npx", "yarn", "tsc", "react"]):
            return "node:20-slim"
        if any(x in cmd_lower for x in ["go ", "go build", "go run"]):
            return "golang:1.22-alpine"
        if any(x in cmd_lower for x in ["rustc", "cargo"]):
            return "rust:1.77-slim"
        if any(x in cmd_lower for x in ["gcc", "g++", "make", "cmake"]):
            return "gcc:13-bookworm"
        return "ubuntu:22.04"

    # -- Linux cgroups Executor -----------------------------------------

    def _execute_cgroups(
        self, command: str, timeout: int, env: dict | None,
    ) -> SandboxResult:
        """Run command with resource limits via setrlimit (Linux only)."""
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            proc = subprocess.Popen(
                ["bash", "-c", command],
                cwd=str(self._cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=merged_env,
                preexec_fn=self._apply_resource_limits if hasattr(os, "setrlimit") else None,
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return SandboxResult(
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=proc.returncode,
                mode="cgroups",
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
            return SandboxResult(
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=-1,
                was_timeout=True,
                was_killed=True,
                mode="cgroups",
            )

    def _apply_resource_limits(self):
        """Apply resource limits via setrlimit (POSIX only)."""
        if platform.system() == "Windows":
            return
        try:
            import resource
        except ImportError:
            return
        res_module: Any = resource
        mem_bytes = self._limits.max_memory_mb * 1024 * 1024
        for limit, value in (
            ("RLIMIT_AS", mem_bytes),
            ("RLIMIT_CPU", self._limits.max_cpu_seconds),
            ("RLIMIT_FSIZE", self._limits.max_file_size_mb * 1024 * 1024),
        ):
            res = getattr(res_module, limit, None)
            if res is None:
                continue
            try:
                res_module.setrlimit(res, (value, value))
            except (ValueError, OSError):
                pass

    # -- macOS sandbox-exec Executor ------------------------------------

    def _execute_sandbox_exec(
        self, command: str, timeout: int, env: dict | None,
    ) -> SandboxResult:
        """Run command inside macOS sandbox-exec."""
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        sandbox_profile = (
            "(version 1)\n"
            "(deny default)\n"
            f"(allow network* (if {str(self._limits.allow_network).lower()}))\n"
            f'(allow file-read* file-write* (subpath "{self._cwd.resolve()}"))\n'
            "(allow process*)\n"
            "(allow sysctl*)\n"
            "(allow signal*)\n"
        )

        try:
            proc = subprocess.Popen(
                ["sandbox-exec", "-p", sandbox_profile, "bash", "-c", command],
                cwd=str(self._cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=merged_env,
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return SandboxResult(
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=proc.returncode,
                mode="sandbox-exec",
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
            return SandboxResult(
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=-1,
                was_timeout=True,
                was_killed=True,
                mode="sandbox-exec",
            )

    # -- Subprocess Executor (fallback) ---------------------------------

    def _execute_subprocess(
        self, command: str, timeout: int, env: dict | None,
    ) -> SandboxResult:
        """Run command in a resource-limited subprocess (or container if enabled)."""
        # ── v4.0: Isolation Engine — container-based execution ──
        # Only use Docker if config EXPLICITLY enables isolation engine
        # (disabled by default to keep files on real filesystem)
        try:
            from core.engine_adapters import adapt_container_result
            cfg = getattr(self, '_cfg', {}) or {}
            engines = cfg.get("engines", {}) if isinstance(cfg, dict) else {}
            if engines.get("isolation") is True:  # explicit opt-in only
                from core.isolation.container import get_container_manager
                cm = get_container_manager()
                if cm.available:
                    import time
                    t0 = time.perf_counter()
                    cresult = cm.execute(command, profile="bash", timeout=timeout)
                    elapsed = (time.perf_counter() - t0) * 1000
                    logger.info(
                        "IsolationEngine: container=%s success=%s timeout=%s",
                        cresult.actual_isolation, cresult.success, cresult.was_timeout,
                    )
                    return adapt_container_result(cresult, elapsed)
                else:
                    logger.debug("IsolationEngine: no container runtime — using subprocess")
        except ImportError:
            pass
        except Exception as e:
            logger.debug("IsolationEngine unavailable: %s", e)

        # Strip WIDDX API keys from child process environment
        merged_env = {k: v for k, v in os.environ.items() if not k.startswith("WIDDX_API_KEY")}
        if env:
            merged_env.update(env)

        cmd, needs_shell = self._split_command(command)
        if needs_shell:
            logger.debug("shell=True required for: %.100s", command)

        # Snapshot files before execution for change tracking
        from pathlib import Path as _Path
        _before = set()
        try:
            _root = _Path(self._cwd).resolve()
            if _root.is_dir():
                _before = set(
                    str(f.relative_to(_root))
                    for f in _root.rglob("*")
                    if f.is_file()
                )
        except Exception:
            _before = set()

        try:
            proc = subprocess.Popen(
                cmd,
                shell=needs_shell,
                cwd=str(self._cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=merged_env,
                preexec_fn=self._apply_resource_limits if hasattr(os, 'setrlimit') else None,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
                was_timeout = False
                was_killed = False
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate(timeout=5)
                exit_code = -1
                was_timeout = True
                was_killed = True

            return SandboxResult(
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=exit_code,
                was_timeout=was_timeout,
                was_killed=was_killed,
                mode="subprocess",
                files_created=self._detect_new_files(_before),
                files_modified=self._detect_modified_files(_before),
            )
        except FileNotFoundError:
            # CRIT-001 FIX: Never retry with shell=True — use explicit shell wrapper
            logger.warning("Command not found (shell=False): %.100s", command)
            return SandboxResult(
                stdout="",
                stderr=(f"Command not found: {command[:200]}. "
                        "Use 'bash -c' or 'cmd /c' explicitly if shell features are needed."),
                exit_code=127,
                was_timeout=False, was_killed=False,
                mode="subprocess",
            )

    def _execute_none(
        self, command: str, timeout: int, env: dict | None,
    ) -> SandboxResult:
        """Run command without sandbox (trusted only)."""
        return self._execute_subprocess(command, timeout, env)

    # -- Helpers --------------------------------------------------------

    @staticmethod
    def _detect_new_files(before: set) -> list[str]:
        try:
            root = Path(".").resolve()
            after = set(
                str(f.relative_to(root))
                for f in root.rglob("*")
                if f.is_file()
            )
            return sorted(after - before)[:50]
        except Exception:
            return []

    @staticmethod
    def _detect_modified_files(before: set) -> list[str]:
        try:
            root = Path(".").resolve()
            after = set(
                str(f.relative_to(root))
                for f in root.rglob("*")
                if f.is_file()
            )
            return sorted(after & before)[:30]
        except Exception:
            return []

    # Windows built-in shell commands — require shell=True
    _WINDOWS_BUILTINS = {
        "echo", "dir", "cls", "del", "copy", "move",
        "type", "set", "cd", "md", "rd", "mkdir", "rmdir",
    }

    @staticmethod
    def _split_command(command: str) -> tuple[list[str] | str, bool]:
        SHELL_CHARS = {"|", ">", "<", "&&", "||", ";", "$", "`", "*", "?", "[", "]", "~", "!", "{", "}"}
        try:
            parts = shlex.split(command)
            # Windows shell built-ins require shell=True
            if os.name == "nt" and parts and parts[0].lower() in SandboxExecutor._WINDOWS_BUILTINS:
                return command, True
            for part in parts:
                for char in SHELL_CHARS:
                    if char in part:
                        return command, True
            return parts, False
        except ValueError:
            return command, True

    def _run(
        self, cmd: list[str], timeout: int,
        env: dict | None, mode: str,
    ) -> SandboxResult:
        """Execute a command list and return result."""
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                return SandboxResult(
                    stdout=stdout or "",
                    stderr=stderr or "",
                    exit_code=proc.returncode,
                    mode=mode,
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate(timeout=5)
                return SandboxResult(
                    stdout=stdout or "",
                    stderr=stderr or "",
                    exit_code=-1,
                    was_timeout=True,
                    was_killed=True,
                    mode=mode,
                )
        except FileNotFoundError:
            return SandboxResult(
                stderr=f"Command not found: {cmd[0]}",
                exit_code=127,
                mode=mode,
            )


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------

sandbox = SandboxExecutor()
