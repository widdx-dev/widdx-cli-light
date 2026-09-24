"""Tool Tracer — real-time execution tracing for tool calls.

Records every tool call with timestamps, arguments, results,
exit codes, durations, and created files.

Usage:
    from core.tool_tracer import t

    t.tool_call("bash", {"command": "ls"})
    t.dispatch("bash")
    t.before_sandbox("npx create-react-app")
    t.after_sandbox(exit_code=0, duration=7.2, stdout="...", stderr="...")
    t.file_created("project/package.json")
    t.result("exit_code=0 ...")
    t.print_summary()
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("widdx.tool_tracer")


@dataclass
class ToolTrace:
    index: int
    name: str
    args: dict
    dispatch_time: Optional[float] = None
    handler_time: Optional[float] = None
    sandbox_start: Optional[float] = None
    sandbox_end: Optional[float] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    result_text: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def duration_str(self) -> str:
        if self.duration_ms > 1000:
            return f"{self.duration_ms / 1000:.1f}s"
        return f"{self.duration_ms:.0f}ms"

    @property
    def status_str(self) -> str:
        if self.exit_code is not None:
            return f"exit={self.exit_code}"
        if "Written" in self.result_text or "success" in self.result_text.lower():
            return "success"
        if "error" in self.result_text.lower() or "failed" in self.result_text.lower():
            return "failed"
        return "done"


class ToolTracer:
    def __init__(self):
        self.traces: list[ToolTrace] = []
        self._current: Optional[ToolTrace] = None
        self._start_time: float = 0.0

    def start_session(self):
        self.traces.clear()
        self._current = None
        self._start_time = time.time()

    def tool_call(self, name: str, args: dict):
        ts = time.strftime("%H:%M:%S")
        idx = len(self.traces) + 1
        trace = ToolTrace(index=idx, name=name, args=args)
        self.traces.append(trace)
        self._current = trace
        arg_summary = self._summarize_args(name, args)
        print(f"\n  [{ts}] ──▶ LLM requested tool: {name}({arg_summary})")
        logger.info("LLM requested tool: %s | args: %s", name, arg_summary)

    def dispatch(self, name: str):
        ts = time.strftime("%H:%M:%S")
        if self._current and self._current.name == name:
            self._current.dispatch_time = time.time()
        print(f"  [{ts}]   dispatch.execute('{name}')")
        logger.info("dispatch.execute('%s')", name)

    def handler(self, name: str):
        ts = time.strftime("%H:%M:%S")
        if self._current:
            self._current.handler_time = time.time()
        print(f"  [{ts}]   handler: {name}")
        logger.info("handler: %s", name)

    def before_sandbox(self, command: str):
        ts = time.strftime("%H:%M:%S")
        if self._current:
            self._current.sandbox_start = time.time()
        cmd = command[:120] + ("..." if len(command) > 120 else "")
        print(f"  [{ts}]   SandboxExecutor: executing \"{cmd}\"")
        logger.info("SandboxExecutor: %s", cmd)

    def after_sandbox(self, exit_code: int, duration: float,
                      stdout: str = "", stderr: str = ""):
        ts = time.strftime("%H:%M:%S")
        if self._current:
            self._current.sandbox_end = time.time()
            self._current.exit_code = exit_code
            self._current.duration_ms = duration * 1000
            self._current.stdout = stdout[:300]
            self._current.stderr = stderr[:200]

        dur = f"{duration:.1f}s" if duration > 1 else f"{duration * 1000:.0f}ms"
        print(f"  [{ts}]   exit_code={exit_code} | duration={dur}")

        if stdout:
            short_stdout = stdout[:200].replace("\n", " | ")
            print(f"  [{ts}]   stdout: {short_stdout}")
        if stderr:
            short_stderr = stderr[:200].replace("\n", " | ")
            if exit_code != 0:
                print(f"  [{ts}]   stderr: {short_stderr}")

    def file_created(self, path: str):
        ts = time.strftime("%H:%M:%S")
        if self._current and path not in self._current.files_created:
            self._current.files_created.append(path)
        print(f"  [{ts}]   📄 created: {path}")

    def file_modified(self, path: str):
        time.strftime("%H:%M:%S")
        if self._current and path not in self._current.files_modified:
            self._current.files_modified.append(path)

    def result(self, text: str):
        if self._current:
            self._current.result_text = text[:200]

    def print_summary(self):
        total = len(self.traces)
        sep = "═" * 60

        print(f"\n  {sep}")
        print("           TOOLS EXECUTED")
        print(f"  {sep}")

        if total == 0:
            print("  No tools were executed.")
            print("  The LLM did not call any tools during this session.")
            print("  Possible causes:")
            print("    - The provider does not support tool calling")
            print("    - The task was classified as CHAT (confidence < threshold)")
            print("    - The system prompt did not include tool definitions")
            print("    - The LLM chose to respond in text instead of using tools")
            print(f"  {sep}")
            return

        for trace in self.traces:
            name = trace.name.ljust(8)
            args = self._summarize_args(trace.name, trace.args)
            args = args[:55].ljust(55)
            status = trace.status_str.ljust(12)
            dur = trace.duration_str.rjust(8)
            print(f"  {trace.index}. {name} {args} {status} {dur}")

        print(f"  {sep}")
        print(f"  Total tools executed: {total}")
        print(f"  {sep}")

        files = []
        for trace in self.traces:
            files.extend(trace.files_created)
        if files:
            print("\n  Files created:")
            for f in files:
                print(f"    ✓ {f}")

        if any(t.stderr for t in self.traces if t.exit_code != 0):
            print("\n  Errors:")
            for t in self.traces:
                if t.exit_code != 0 and t.stderr:
                    print(f"    ✗ {t.name}: {t.stderr[:150]}")

    def _summarize_args(self, name: str, args: dict) -> str:
        if name == "bash":
            cmd = args.get("command", "")
            return cmd[:70] + ("..." if len(cmd) > 70 else "")
        elif name == "write":
            return args.get("file_path", "")
        elif name == "read":
            return args.get("file_path", "")
        elif name == "edit":
            return args.get("file_path", "")
        elif name == "glob":
            return args.get("pattern", "")
        elif name == "grep":
            return f"'{args.get('pattern', '')}' in {args.get('path', '.')}"
        elif name == "list_files":
            return args.get("path", ".")
        elif name == "web_fetch":
            return args.get("url", "")[:70]
        else:
            summary = json_dumps_fast(args)
            return summary[:70]

    def find_tool_by_name(self, name: str) -> Optional[ToolTrace]:
        for t in self.traces:
            if t.name == name and t.exit_code == 0:
                return t
        return None


def json_dumps_fast(obj) -> str:
    import json
    try:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(obj)


t: ToolTracer = ToolTracer()
