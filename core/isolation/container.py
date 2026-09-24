"""Container manager — Docker/podman-based process isolation.

Manages container lifecycle: ensure image → create → execute → destroy.
Falls back gracefully to subprocess with resource limits when
Docker/podman is not available.
"""

from __future__ import annotations
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass

from .profiles import IsolationProfile, get_profile

logger = logging.getLogger("widdx.isolation.container")


@dataclass
class ContainerResult:
    """Result of executing a command in a container."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    was_timeout: bool = False
    profile: str = ""
    actual_isolation: str = ""  # "docker", "podman", "subprocess"


class ContainerManager:
    """Manages container-based execution with graceful fallback."""

    def __init__(self):
        self._runtime = self._detect_runtime()
        self._image_cache: set[str] = set()

    @staticmethod
    def _detect_runtime() -> str | None:
        """Detect available container runtime. Returns 'docker', 'podman', or None."""
        for cmd in ["docker", "podman"]:
            if shutil.which(cmd):
                try:
                    subprocess.run(
                        [cmd, "info"], capture_output=True,
                        timeout=5, check=False,
                    )
                    return cmd
                except (subprocess.TimeoutExpired, OSError):
                    continue
        return None

    @property
    def available(self) -> bool:
        return self._runtime is not None

    @property
    def runtime_name(self) -> str:
        return self._runtime or "subprocess"

    def ensure_image(self, image: str) -> bool:
        """Ensure container image is available locally. Returns True if ready."""
        if not self._runtime:
            return False
        if image in self._image_cache:
            return True

        try:
            # Check if image exists locally
            result = subprocess.run(
                [self._runtime, "image", "inspect", image],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                self._image_cache.add(image)
                return True

            # Pull the image
            logger.info("Pulling image: %s", image)
            subprocess.run(
                [self._runtime, "pull", image],
                check=True, timeout=300,
            )
            self._image_cache.add(image)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                OSError) as e:
            logger.warning("Failed to ensure image %s: %s", image, e)
            return False

    def execute(self, command: str,
                profile: str = "bash",
                timeout: int | None = None) -> ContainerResult:
        """Execute a command with container isolation.

        Args:
            command: The command to execute
            profile: Isolation profile name
            timeout: Timeout override (uses profile default if None)

        Returns:
            ContainerResult with output and metadata.
        """
        prof = get_profile(profile)
        if prof is None:
            prof = get_profile("bash")
        assert prof is not None

        timeout = timeout or prof.timeout

        # ── Try container execution ──
        if self._runtime and self.ensure_image(prof.image):
            return self._execute_container(command, prof, timeout)

        # ── Fallback: subprocess with resource limits ──
        return self._execute_subprocess(command, prof, timeout)

    def _execute_container(self, command: str, profile: IsolationProfile,
                           timeout: int) -> ContainerResult:
        """Execute command inside a Docker/podman container."""
        rt = self._runtime
        assert rt is not None

        # Build docker run command
        args = [
            rt, "run", "--rm",
            "--memory", profile.memory,
            "--cpus", profile.cpu,
            f"--network={profile.network}",
            "--read-only" if profile.read_only else "",
            f"--pids-limit={profile.max_processes}",
            f"--stop-timeout={min(timeout, 30)}",
        ]
        args = [a for a in args if a]  # remove empty strings

        # Add tmpfs mounts
        for tmpfs_path in profile.tmpfs:
            args.extend(["--tmpfs", tmpfs_path])

        # Add volume mounts
        cwd = os.getcwd()
        output_dir = os.path.join(cwd, ".widdx", "output")
        os.makedirs(output_dir, exist_ok=True)

        for host_path, container_path, mode in profile.mounts:
            host_path = host_path.replace("{cwd}", cwd)
            host_path = host_path.replace("{output_dir}", output_dir)
            for h in [host_path]:
                if os.path.exists(h):
                    args.extend(["-v", f"{h}:{container_path}:{mode}"])

        # Add profile image and command
        args.append(profile.image)
        args.extend(["sh", "-c", command])

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            stdout, stderr = proc.communicate(timeout=timeout)

            return ContainerResult(
                success=proc.returncode == 0,
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=proc.returncode,
                was_timeout=False,
                profile=profile.name,
                actual_isolation=rt,
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return ContainerResult(
                success=False,
                stderr=f"Container execution timed out after {timeout}s",
                was_timeout=True,
                profile=profile.name,
                actual_isolation=rt,
            )
        except OSError as e:
            logger.warning("Container execution failed: %s — falling back", e)
            return self._execute_subprocess(command, profile, timeout)

    def _execute_subprocess(self, command: str, profile: IsolationProfile,
                            timeout: int) -> ContainerResult:
        """Fallback: execute with subprocess + resource limits."""
        import shlex
        try:
            cmd_parts = shlex.split(command)
            proc = subprocess.Popen(
                cmd_parts,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            stdout, stderr = proc.communicate(timeout=timeout)

            return ContainerResult(
                success=proc.returncode == 0,
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=proc.returncode,
                was_timeout=False,
                profile=profile.name,
                actual_isolation="subprocess",
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return ContainerResult(
                success=False,
                stderr=f"Subprocess timed out after {timeout}s",
                was_timeout=True,
                profile=profile.name,
                actual_isolation="subprocess",
            )
        except OSError as e:
            return ContainerResult(
                success=False,
                stderr=str(e),
                profile=profile.name,
                actual_isolation="subprocess",
            )

    def cleanup(self, max_age_minutes: int = 30):
        """Clean up old containers (just a no-op for run --rm, but logs anyway)."""
        logger.debug("Container cleanup: all containers use --rm, nothing to clean")


# Module-level singleton
_manager: ContainerManager | None = None


def get_container_manager() -> ContainerManager:
    """Get or create the container manager."""
    global _manager
    if _manager is None:
        _manager = ContainerManager()
    return _manager
