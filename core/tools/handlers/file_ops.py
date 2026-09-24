"""File operation tools — read, write, edit, glob, grep, list_files."""

import difflib
import logging
import re
from pathlib import Path

from ..safety import is_safe_path, get_safe_dir
from ..registry import TOOL_DEFINITIONS
from core.tool_tracer import t as tool_tracer

logger = logging.getLogger("widdx.tools.file_ops")


def _read(file_path: str, offset: int = 0, limit: int = 0) -> str:
    tool_tracer.handler("read")
    p = Path(file_path)
    if not is_safe_path(p):
        return f"Sandbox: read of {file_path} denied — not inside {get_safe_dir()}"
    p = p.resolve()
    if not p.exists():
        return f"File not found: {file_path}"
    if p.stat().st_size > 1024 * 1024:
        return f"File too large ({p.stat().st_size // 1024} KB); max 1 MB"
    try:
        lines = p.read_text("utf-8", errors="replace").splitlines()
        total = len(lines)
        if offset > 0:
            start = max(0, offset - 1)
        elif offset < 0:
            start = max(0, total + offset)
        else:
            start = 0
        end = min(total, start + limit) if limit > 0 else total
        selected = lines[start:end]
        buf = [f"📄 {file_path}  ({total} lines, showing {start + 1}-{end})", ""]
        pad = len(str(end))
        for i, line in enumerate(selected, start + 1):
            buf.append(f"  {str(i).rjust(pad)}│{line}")
        buf.append("")
        if end < total:
            buf.append(f"  ... {total - end} more lines (use offset={end + 1} to continue)")
        return "\n".join(buf)
    except Exception as e:
        return f"Error reading {file_path}: {e}"


def _write(file_path: str, content: str):
    tool_tracer.handler("write")
    p = Path(file_path)
    if not is_safe_path(p):
        return f"Sandbox: write to {file_path} denied — not inside {get_safe_dir()}"
    p = p.resolve()
    try:
        from core.runtime_guard import TransactionalWrite, get_runtime_guard
        guard = get_runtime_guard()
        if not guard.before_write(p):
            return f"❌ Disk full — cannot write to {file_path}"
        with TransactionalWrite(p) as tx:
            tx.write(content)
        if not guard.after_write(p, len(content.encode('utf-8'))):
            return f"❌ Write verification failed for {file_path}"
        tool_tracer.file_created(file_path)
        return f"Written {len(content.encode('utf-8'))} bytes to {file_path}"
    except ImportError:
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(content, encoding="utf-8")
            tool_tracer.file_created(file_path)
            return f"Written {len(content.encode('utf-8'))} bytes to {file_path}"
        except Exception as e:
            return f"Error writing {file_path}: {e}"


def _edit(file_path: str, old_string: str, new_string: str,
          replace_all: bool = False, preview: bool = False):
    tool_tracer.handler("edit")
    p = Path(file_path)
    if not is_safe_path(p):
        return f"Sandbox: edit of {file_path} denied — not inside {get_safe_dir()}"
    p = p.resolve()
    if not p.exists():
        return f"File not found: {file_path}"
    try:
        text = p.read_text("utf-8")
        if old_string not in text:
            return f"old_string not found in {file_path}"
        count = text.count(old_string)
        if count > 1 and not replace_all:
            return (f"old_string appears {count} times in {file_path}. "
                    f"Set replace_all=true to replace all, or make old_string more specific.")
        new_text = text.replace(old_string, new_string, count if replace_all else 1)
        replaced_count = count if replace_all else 1
        old_lines = text.splitlines(True)
        new_lines = new_text.splitlines(True)
        diff_lines = _generate_unified_diff(file_path, old_lines, new_lines)
        if preview:
            return f"📝 PREVIEW — would replace {replaced_count} occurrence(s) in {file_path}:\n\n{diff_lines}"
        p.write_text(new_text, encoding="utf-8")
        return f"✅ Edited {file_path} ({replaced_count} replacement(s))\n{diff_lines}"
    except Exception as e:
        return f"Error editing {file_path}: {e}"


def _generate_unified_diff(filename: str, old_lines: list[str], new_lines: list[str], context: int = 3) -> str:
    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=filename, tofile=filename,
        n=context
    ))
    if not diff:
        return "  (no changes)"
    return "".join(diff[:100]) + ("... (truncated)" if len(diff) > 100 else "")


def _generate_diff(old_lines, new_lines):
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    buf = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            buf.append(f"  ... ({i2 - i1} unchanged lines)" if i2 - i1 > 3
                       else "\n".join(f"  {old_lines[k].rstrip()}" for k in range(i1, i2)))
        elif op == "replace":
            for k in range(i1, i2):
                buf.append(f"- {old_lines[k].rstrip()}")
            for k in range(j1, j2):
                buf.append(f"+ {new_lines[k].rstrip()}")
        elif op == "delete":
            for k in range(i1, i2):
                buf.append(f"- {old_lines[k].rstrip()}")
        elif op == "insert":
            for k in range(j1, j2):
                buf.append(f"+ {new_lines[k].rstrip()}")
    return "\n".join(buf[:50]) + ("\n... (truncated)" if len(buf) > 50 else "")


def _glob(pattern: str, path: str | None = None):
    p = Path(path) if path else Path(".")
    if not is_safe_path(p):
        return f"Sandbox: glob in {path} denied — not inside {get_safe_dir()}"
    matches = sorted(p.rglob(pattern))
    if not matches:
        return f"No files matching '{pattern}'"
    result = [str(m.relative_to(p)) for m in matches[:50]]
    return f"{len(matches)} result(s):\n" + "\n".join(result)


def _grep(pattern: str, path: str | None = None, include: str | None = None):
    p = Path(path) if path else Path(".")
    if not is_safe_path(p):
        return f"Sandbox: grep in {path} denied — not inside {get_safe_dir()}"
    results = []
    files_iter = p.rglob(include) if include else p.rglob("*")
    for f in files_iter:
        if not f.is_file() or f.stat().st_size > 102400:
            continue
        try:
            with f.open("r", encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    if re.search(pattern, line, re.I):
                        results.append(f"{f.relative_to(p)}:{i}: {line.strip()[:120]}")
        except Exception as e:
            logger.debug("grep: skip %s: %s", f.name, e)
    if not results:
        return f"No results for '{pattern}'"
    return f"{len(results)} result(s):\n" + "\n".join(results[:50])


def _list_files(path: str = ".") -> str:
    p = Path(path).resolve()
    if not is_safe_path(p):
        return f"Sandbox: list of {path} denied — not inside {get_safe_dir()}"
    if not p.is_dir():
        return f"Not a directory: {path}"
    lines = []
    for entry in sorted(p.iterdir()):
        prefix = "  "
        name = entry.name
        if entry.is_dir():
            lines.append(f"{prefix}{name}/")
        else:
            size = entry.stat().st_size if entry.is_file() else ""
            lines.append(f"{prefix}{name}  ({size} bytes)")
    return f"Contents of {path}:\n" + "\n".join(lines)


def _search_replace(pattern: str, replacement: str, include: str | None = None,
                     path: str | None = None, preview: bool = True) -> str:
    """Search and replace text across multiple files."""
    tool_tracer.handler("search_replace")
    root = Path(path) if path else Path(".")
    if not is_safe_path(root):
        return f"Sandbox: search in {path} denied — not inside {get_safe_dir()}"
    matched_files = []
    files_iter = root.rglob(include) if include else root.rglob("*")
    for f in files_iter:
        if not f.is_file() or f.stat().st_size > 512000:
            continue
        try:
            text = f.read_text("utf-8", errors="ignore")
            if pattern not in text:
                continue
            count = text.count(pattern)
            matched_files.append((f, text, count))
        except Exception:
            continue

    if not matched_files:
        return f"No matches for '{pattern}'"

    total_replaced = 0
    buf = [f"🔍 Found '{pattern}' in {len(matched_files)} file(s):", ""]
    for f, text, count in matched_files:
        rel = f.relative_to(root)
        new_text = text.replace(pattern, replacement)
        lines = text.splitlines()
        preview_lines = []
        for i, line in enumerate(lines):
            if pattern in line:
                ctx_start = max(0, i - 1)
                ctx_end = min(len(lines), i + 2)
                snippet = "\n".join(f"  {j + 1}:{lines[j]}" for j in range(ctx_start, ctx_end))
                preview_lines.append(snippet)
        buf.append(f"  📄 {rel} ({count} occurrence(s))")
        for p in preview_lines[:3]:
            buf.append(p)
        if len(preview_lines) > 3:
            buf.append(f"     ... and {len(preview_lines) - 3} more lines")

    if preview:
        return "\n".join(buf)

    for f, text, count in matched_files:
        new_text = text.replace(pattern, replacement)
        f.write_text(new_text, encoding="utf-8")
        total_replaced += count

    buf.append(f"\n✅ Replaced {total_replaced} occurrence(s) across {len(matched_files)} file(s)")
    return "\n".join(buf)


def get_tool_helpers() -> dict:
    """Return dict of helper functions for tool definition access."""
    return {
        "get_read_tool_def": lambda: next(
            (td for td in TOOL_DEFINITIONS if td["name"] == "read"), {}
        ),
        "get_write_tool_def": lambda: next(
            (td for td in TOOL_DEFINITIONS if td["name"] == "write"), {}
        ),
        "get_bash_tool_def": lambda: next(
            (td for td in TOOL_DEFINITIONS if td["name"] == "bash"), {}
        ),
    }
