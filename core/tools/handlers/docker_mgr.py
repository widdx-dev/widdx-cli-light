"""Docker management — build, run, stop, list containers and images."""

import json
import logging
import subprocess

logger = logging.getLogger("widdx.tools.docker")


def _check_docker() -> str | None:
    try:
        r = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def _docker_exec(args: list[str], timeout: int = 60) -> tuple[str, str, int]:
    try:
        r = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except FileNotFoundError:
        return "", "Docker not found. Install Docker first.", -1
    except Exception as e:
        return "", str(e), -1


def _docker_list(what: str = "containers", all: bool = True) -> str:
    version = _check_docker()
    if not version:
        return "❌ Docker not available"

    if what == "containers":
        args = ["ps", "--format", "{{json .}}"]
        if all:
            args.insert(1, "-a")
    elif what == "images":
        args = ["images", "--format", "{{json .}}"]
    elif what == "volumes":
        args = ["volume", "ls", "--format", "{{json .}}"]
    else:
        return f"Unknown: {what}. Use: containers, images, volumes"

    stdout, stderr, rc = _docker_exec(args)
    if rc != 0:
        return f"Error: {stderr}"

    entries = [json.loads(line) for line in stdout.splitlines() if line.strip().startswith("{")]
    if not entries:
        return f"No {what} found"

    buf = [f"🐳 Docker {what.title()} ({len(entries)}):", ""]
    for e in entries[:30]:
        if what == "containers":
            names = e.get("Names", "?")
            state = e.get("State", "?")
            image = e.get("Image", "?")[:30]
            ports = e.get("Ports", "")[:20]
            buf.append(f"  {e.get('ID', '?')[:12]}  {state:<8}  {image:<30}  {ports:<20}  {names}")
        elif what == "images":
            buf.append(f"  {e.get('Repository', '?'):<30}  {e.get('Tag', '?'):<15}  {e.get('ID', '?')[:12]}  {e.get('Size', '?')}")
        elif what == "volumes":
            buf.append(f"  {e.get('Name', '?')}")
    if len(entries) > 30:
        buf.append(f"  ... and {len(entries) - 30} more")
    return "\n".join(buf)


def _docker_build(path: str, tag: str = "latest", dockerfile: str | None = None) -> str:
    version = _check_docker()
    if not version:
        return "❌ Docker not available"

    args = ["build", "-t", tag, path]
    if dockerfile:
        args.extend(["-f", dockerfile])
    stdout, stderr, rc = _docker_exec(args, timeout=300)
    if rc != 0:
        return f"Build failed:\n{stderr[-500:]}"
    return f"✅ Built image {tag} ({path})"


def _docker_run(image: str, name: str | None = None, ports: str | None = None,
                detach: bool = True, command: str | None = None) -> str:
    version = _check_docker()
    if not version:
        return "❌ Docker not available"

    args = ["run"]
    if detach:
        args.append("-d")
    if name:
        args.extend(["--name", name])
    if ports:
        for p in ports.split(","):
            p = p.strip()
            if p:
                args.extend(["-p", p])
    args.append(image)
    if command:
        args.extend(command.split())

    stdout, stderr, rc = _docker_exec(args)
    if rc != 0:
        return f"Run failed:\n{stderr[-500:]}"
    return f"✅ Container started: {stdout[:20]}"


def _docker_stop(container_id: str) -> str:
    stdout, stderr, rc = _docker_exec(["stop", container_id])
    return f"✅ Stopped {container_id}" if rc == 0 else f"Error: {stderr}"


def _docker_remove(container_id: str, force: bool = False) -> str:
    args = ["rm"]
    if force:
        args.append("-f")
    args.append(container_id)
    stdout, stderr, rc = _docker_exec(args)
    return f"✅ Removed {container_id}" if rc == 0 else f"Error: {stderr}"


def _docker_logs(container_id: str, tail: int = 50) -> str:
    stdout, stderr, rc = _docker_exec(["logs", "--tail", str(tail), container_id])
    return stdout[-3000:] if rc == 0 else f"Error: {stderr}"


def _docker_compose(compose_file: str | None = None, action: str = "up") -> str:
    args = ["compose"]
    if compose_file:
        args.extend(["-f", compose_file])
    args.append(action)
    if action == "up":
        args.append("-d")
    stdout, stderr, rc = _docker_exec(args, timeout=120)
    if rc != 0:
        return f"Compose {action} failed:\n{stderr[-500:]}"
    return f"✅ Compose {action} completed"


def _docker_mgr(action: str = "list", **kwargs) -> str:
    """Docker container/image management."""
    actions = {
        "list": lambda: _docker_list(kwargs.get("what", "containers"), kwargs.get("all", True)),
        "ps": lambda: _docker_list("containers", True),
        "images": lambda: _docker_list("images"),
        "build": lambda: _docker_build(kwargs.get("path", "."), kwargs.get("tag", "latest"), kwargs.get("dockerfile")),
        "run": lambda: _docker_run(kwargs.get("image", ""), kwargs.get("name"), kwargs.get("ports"), kwargs.get("detach", True), kwargs.get("command")),
        "stop": lambda: _docker_stop(kwargs.get("container_id", "")),
        "rm": lambda: _docker_remove(kwargs.get("container_id", ""), kwargs.get("force", False)),
        "logs": lambda: _docker_logs(kwargs.get("container_id", ""), kwargs.get("tail", 50)),
        "compose": lambda: _docker_compose(kwargs.get("compose_file"), kwargs.get("compose_action", "up")),
    }
    handler = actions.get(action)
    if not handler:
        return f"Unknown action: {action}. Available: {', '.join(actions.keys())}"
    return handler()
