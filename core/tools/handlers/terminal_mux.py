"""Terminal multiplexer — manage multiple terminal sessions."""

import logging
import os
import shlex
import signal
import subprocess
import threading
import time
from typing import Any

logger = logging.getLogger("widdx.tools.terminal_mux")

_sessions: dict[str, dict[str, Any]] = {}
_sessions_lock = threading.Lock()
_session_counter = 0


def _terminal_mux(action: str = "list", name: str | None = None,
                  command: str | None = None, cwd: str | None = None) -> str:
    """Manage multiple terminal sessions."""
    global _session_counter

    if action == "list":
        with _sessions_lock:
            if not _sessions:
                return "No active terminal sessions"
            buf = ["🖥  Terminal Sessions:", ""]
            for sid, session in sorted(_sessions.items()):
                status = "🟢 running" if session["process"].poll() is None else "🔴 exited"
                started = time.strftime("%H:%M:%S", time.localtime(session["started"]))
                pid = session["process"].pid
                buf.append(f"  [{sid}] {session.get('name', sid)}  {status}  PID:{pid}  started:{started}")
                if session.get("cwd"):
                    buf.append(f"        cwd: {session['cwd']}")
            return "\n".join(buf)

    if action == "create" or action == "run":
        if not command:
            return "command is required"
        with _sessions_lock:
            _session_counter += 1
            sid = f"s{_session_counter}"
            session_name = name or f"session_{sid}"

        try:
            # Avoid shell=True on POSIX: tokenize with shlex so the command is
            # passed to exec directly (no shell injection surface). Windows
            # built-ins still require the shell, so keep it there.
            if os.name == "nt":
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    cwd=cwd or os.getcwd(),
                    text=True,
                    bufsize=1,
                )
            else:
                argv = shlex.split(command)
                if not argv:
                    return "command is required"
                proc = subprocess.Popen(
                    argv,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    cwd=cwd or os.getcwd(),
                    text=True,
                    bufsize=1,
                )
        except Exception as e:
            return f"Failed to start process: {e}"

        with _sessions_lock:
            _sessions[sid] = {
                "name": session_name,
                "process": proc,
                "started": time.time(),
                "cwd": cwd or os.getcwd(),
                "output_buffer": [],
                "running": True,
            }

        def _reader(sid: str):
            session = _sessions.get(sid)
            if not session:
                return
            proc = session["process"]
            try:
                for line in iter(proc.stdout.readline, ""):
                    with _sessions_lock:
                        if sid in _sessions:
                            _sessions[sid]["output_buffer"].append(line.rstrip())
                    if not line:
                        break
            except Exception:
                logger.debug("Exception suppressed (line 100)")
            finally:
                with _sessions_lock:
                    if sid in _sessions:
                        _sessions[sid]["running"] = False

        t = threading.Thread(target=_reader, args=(sid,), daemon=True)
        t.start()

        return f"✅ Created terminal session [{sid}] '{session_name}' (PID: {proc.pid})\nCommand: {command}"

    if action == "output" or action == "read":
        with _sessions_lock:
            entry = _sessions.get(name or "")
            if not entry:
                return f"Session '{name}' not found"
            buf = list(entry["output_buffer"])
            entry["output_buffer"] = []
        if not buf:
            return f"[{name}] No output yet"
        return "\n".join(buf[-100:])

    if action in ("stop", "kill"):
        with _sessions_lock:
            entry = _sessions.get(name or "")
            if not entry:
                return f"Session '{name}' not found"
            proc = entry["process"]
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            logger.debug("Exception suppressed (line 134)")
        with _sessions_lock:
            entry["running"] = False
        return f"✅ Stopped session [{name}]"

    if action == "send":
        if not command:
            return "Input is required (use command=)"
        with _sessions_lock:
            entry = _sessions.get(name or "")
            if not entry:
                return f"Session '{name}' not found"
            proc = entry["process"]
        try:
            proc.stdin.write(command + "\n")
            proc.stdin.flush()
            return f"✅ Sent to [{name}]: {command[:200]}"
        except Exception as e:
            return f"Error sending input: {e}"

    if action == "cleanup":
        with _sessions_lock:
            dead = [sid for sid, s in _sessions.items()
                    if s["process"].poll() is not None and not s["running"]]
            for sid in dead:
                del _sessions[sid]
        return f"Cleaned up {len(dead)} dead session(s). Active: {len(_sessions)}"

    return (f"Unknown action: {action}. "
            f"Available: list, create/run, output/read, stop/kill, send, cleanup")
