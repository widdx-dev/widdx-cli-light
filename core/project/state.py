"""Project state management — session persistence, auto-indexing, and context recovery.

Saves/loads from <project-dir>/.widdx/ :
  session.json  — conversation messages + state
  index.json    — file tree + function/class definitions
"""

import json
import re
import logging
from pathlib import Path

logger = logging.getLogger("widdx.project.state")


# ── paths ────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "exclude_from_index": [],
    "project_instructions": "",
    "auto_commit": True,
}


def _widdx_dir(project_dir: str | Path) -> Path:
    p = Path(project_dir).resolve() / ".widdx"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _session_path(project_dir: str | Path, branch_name: str = "main") -> Path:
    safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in branch_name)
    return _widdx_dir(project_dir) / f"session_{safe_name}.json"


def _branches_path(project_dir: str | Path) -> Path:
    return _widdx_dir(project_dir) / "branches.json"


def list_branches(project_dir: str | Path | None = None) -> list[str]:
    """List all available session branches."""
    if project_dir is None:
        project_dir = Path().resolve()
    branches_path = _branches_path(project_dir)
    if not branches_path.exists():
        return ["main"]
    try:
        import json
        data = json.loads(branches_path.read_text(encoding="utf-8"))
        return data.get("branches", ["main"])
    except Exception as e:
        logger.warning("Failed to list branches: %s", e)
        return ["main"]


def get_current_branch(project_dir: str | Path | None = None) -> str:
    """Get the name of the currently active branch."""
    if project_dir is None:
        project_dir = Path().resolve()
    branches_path = _branches_path(project_dir)
    if not branches_path.exists():
        return "main"
    try:
        import json
        data = json.loads(branches_path.read_text(encoding="utf-8"))
        return data.get("current", "main")
    except Exception as e:
        logger.warning("Failed to get current branch: %s", e)
        return "main"


def set_current_branch(branch_name: str, project_dir: str | Path | None = None) -> bool:
    """Switch to a different branch. Returns True on success."""
    if project_dir is None:
        project_dir = Path().resolve()
    branches_path = _branches_path(project_dir)
    existing = list_branches(project_dir)
    if branch_name not in existing:
        logger.warning("Branch %s does not exist", branch_name)
        return False
    try:
        import json
        if branches_path.exists():
            data = json.loads(branches_path.read_text(encoding="utf-8"))
        else:
            data = {"branches": existing, "current": "main"}
        data["current"] = branch_name
        branches_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning("Failed to switch branches: %s", e)
        return False


def create_branch(new_branch: str, from_branch: str = "main", project_dir: str | Path | None = None) -> bool:
    """Create a new branch as a copy of an existing one. Returns True on success."""
    if project_dir is None:
        project_dir = Path().resolve()
    existing = list_branches(project_dir)
    if new_branch in existing:
        logger.warning("Branch %s already exists", new_branch)
        return False
    # Copy from branch
    src_path = _session_path(project_dir, from_branch)
    dest_path = _session_path(project_dir, new_branch)
    try:
        if src_path.exists():
            dest_path.write_bytes(src_path.read_bytes())
        # Update branches list
        import json
        branches_path = _branches_path(project_dir)
        if branches_path.exists():
            data = json.loads(branches_path.read_text(encoding="utf-8"))
        else:
            data = {"branches": ["main"], "current": "main"}
        if new_branch not in data["branches"]:
            data["branches"].append(new_branch)
        branches_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning("Failed to create branch: %s", e)
        return False


def _index_path(project_dir: str | Path) -> Path:
    return _widdx_dir(project_dir) / "index.json"


def _config_path(project_dir: str | Path) -> Path:
    return _widdx_dir(project_dir) / "config.json"


# ── project config (.widdx/config.json) ───────────────────────────────────

def load_project_config(project_dir: str | Path | None = None) -> dict:
    """Load per-project config from .widdx/config.json. Returns defaults if missing."""
    if project_dir is None:
        project_dir = Path().resolve()
    path = _config_path(project_dir)
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception as e:
        logger.warning("Failed to load project config from %s: %s", path, e)
        return dict(DEFAULT_CONFIG)


def save_project_config(config: dict, project_dir: str | Path | None = None):
    """Save per-project config to .widdx/config.json."""
    if project_dir is None:
        project_dir = Path().resolve()
    path = _config_path(project_dir)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


# ── session persistence ──────────────────────────────────────────────────

def _project_db(project_dir: Path):
    """SQLite database scoped to a project directory."""
    from core.database import Database, get_db_path
    return Database(get_db_path(project_dir))


def _sync_sqlite_session(messages: list, state: dict, project_dir: Path, branch: str):
    """Persist messages to the project-scoped SQLite database."""
    from core.session_v2 import SessionV2, set_current_session

    db = _project_db(project_dir)
    sessions = db.list_sessions(branch=branch, limit=1)
    if sessions:
        sess = SessionV2(session_id=sessions[0]["id"], db=db)
        sess.clear()
    else:
        sess = SessionV2(name=f"session_{branch}", branch=branch, db=db)

    for msg in messages[-50:]:
        role = msg.get("role", "system")
        content = msg.get("content", "")
        tc = msg.get("tool_calls")
        if role in ("user", "assistant", "system", "tool"):
            sess.add_message(role, content, tc)

    sess.save({
        "model": state.get("model", ""),
        "cost": state.get("cost", 0.0),
        "turns": state.get("turns", 0),
        "tools_used": state.get("tools_used", []),
    })

    if project_dir.resolve() == Path.cwd().resolve():
        set_current_session(sess)
    return sess


def save_session(messages: list, state: dict, project_dir: str | Path | None = None, branch: str | None = None):
    """Save conversation messages + runtime state.

    Dual-persistence: SQLite (primary) + JSON (backward compat).
    """
    if project_dir is None:
        project_dir = Path().resolve()
    else:
        project_dir = Path(project_dir).resolve()
    if branch is None:
        branch = get_current_branch(project_dir)

    # ── SQLite persistence (primary) ─────────────────────
    try:
        _sync_sqlite_session(messages, state, project_dir, branch)
    except Exception as e:
        logger.debug("SQLite session save skipped: %s", e)

    # ── JSON persistence (backward compat) ────────────────
    data = {
        "messages": _serializable_messages(messages),
        "state": {
            "model": state.get("model", ""),
            "cost": state.get("cost", 0.0),
            "turns": state.get("turns", 0),
        },
    }
    path = _session_path(project_dir, branch)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_session(project_dir: str | Path | None = None, branch: str | None = None) -> dict | None:
    """Load previous session. Tries SQLite first, falls back to JSON.

    Returns None if no session exists.
    """
    if project_dir is None:
        project_dir = Path().resolve()
    else:
        project_dir = Path(project_dir).resolve()
    if branch is None:
        branch = get_current_branch(project_dir)

    # ── Try SQLite first (project-scoped) ────────────────
    try:
        from core.session_v2 import SessionV2, set_current_session
        db = _project_db(project_dir)
        sessions = db.list_sessions(branch=branch, limit=1)
        if sessions:
            sess = SessionV2(session_id=sessions[0]["id"], db=db)
            msgs = sess.messages
            if msgs:
                if project_dir.resolve() == Path.cwd().resolve():
                    set_current_session(sess)
                return {
                    "messages": msgs,
                    "state": {
                        "model": sess.metadata.get("model", ""),
                        "cost": sess.metadata.get("cost", 0.0),
                        "turns": sess.metadata.get("turns", 0),
                    },
                }
    except Exception as e:
        logger.debug("SQLite session load skipped: %s", e)

    # ── JSON fallback ────────────────────────────────────
    path = _session_path(project_dir, branch)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load session from %s: %s", path, e)
        return None


def has_session(project_dir: str | Path | None = None) -> bool:
    """Check if a previous session exists."""
    if project_dir is None:
        project_dir = Path().resolve()
    return _session_path(project_dir).exists()


# ── project indexing ─────────────────────────────────────────────────────

IGNORE_DIRS = {".widdx", ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
               ".idea", ".vscode", ".DS_Store"}
IGNORE_EXTS = {".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".bin"}


def build_index(project_dir: str | Path, extra_ignore: list | None = None) -> dict:
    """Scan the project directory and build a searchable index.

    Args:
        project_dir: Root directory to scan.
        extra_ignore: Additional directory names to skip (from .widdx/config.json).
    """
    root = Path(project_dir).resolve()
    files = []
    symbols: list[dict] = []

    ignore_dirs = set(IGNORE_DIRS)
    if extra_ignore:
        ignore_dirs.update(extra_ignore)

    for p in sorted(root.rglob("*")):
        # Skip ignored dirs
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts
        if any(part in ignore_dirs for part in parts):
            continue
        try:
            if not p.is_file():
                continue
            if p.suffix in IGNORE_EXTS:
                continue
            st = p.stat()
        except (PermissionError, OSError):
            continue  # skip files/dirs we can't access

        files.append({
            "path": str(rel.as_posix()),
            "size": st.st_size,
            "ext": p.suffix,
        })

        # Extract symbols from text files
        if p.suffix in (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
                        ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
                        ".dart", ".lua", ".r", ".jl", ".cs", ".scala", ".ex", ".exs", ".hs"):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                symbols.extend(_extract_symbols(text, str(rel.as_posix()), p.suffix))
            except Exception as e:
                logger.debug("Symbol extraction failed for %s: %s", p.name, e)

    return {
        "file_count": len(files),
        "files": files,
        "symbols": symbols,
        "symbol_count": len(symbols),
    }


def _extract_symbols(text: str, file_path: str, ext: str) -> list[dict]:
    """Extract function/class definitions from source code."""
    symbols = []
    _KEYWORD_BLACKLIST = frozenset({
        "if", "else", "for", "while", "return", "import", "from",
        "switch", "case", "catch", "finally", "with", "yield",
        "print", "console", "this", "super", "self", "it",
        "describe", "test", "expect", "assert",
        "export", "default", "new", "delete", "typeof",
        "try", "throw", "await",
    })

    # Classes
    for m in re.finditer(r'^\s*(?:public\s+|private\s+|protected\s+|static\s+|abstract\s+)*(?:class|interface|struct|trait|type|enum)\s+(\w+)', text, re.MULTILINE):
        name = m.group(1)
        if name not in _KEYWORD_BLACKLIST:
            symbols.append({
                "kind": "class",
                "name": name,
                "file": file_path,
            })

    # Functions/methods — only explicit definition keywords
    patterns = [
        r'^\s*(?:async\s+)?(?:public\s+|private\s+|protected\s+|static\s+)?(?:def|function|fun|fn|sub)\s+(\w+)',
        r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*[=:]\s*(?:async\s*)?\(.*\)\s*(?:=>|->)',
        r'^\s*(\w+)\s*\([^)]*\)\s*\{',
        # Return-type-first: Dart, Kotlin, TypeScript, Swift
        r'^\s*(?:public\s+|private\s+|protected\s+|static\s+|internal\s+)?'
        r'(?:void|int|str|bool|float|double|String|int\??|bool\??|Future\b.*|async\s+\w+)\s+'
        r'(\w+)\s*\(',
        # R language: name <- function(...)
        r'^\s*(\w+)\s*<-\s*(?:function|reactive)\s*\(',
        # Lua: name = function(...)  or  local name = function(...)
        r'^\s*(?:local\s+)?(\w+)\s*=\s*(?:function)\s*\(',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.MULTILINE):
            name = m.group(1)
            if name and name not in _KEYWORD_BLACKLIST:
                symbols.append({
                    "kind": "function",
                    "name": name,
                    "file": file_path,
                })

    return symbols


def save_index(project_dir: str | Path, extra_ignore: list | None = None):
    """Scan and save project index to .widdx/index.json."""
    index = build_index(project_dir, extra_ignore=extra_ignore)
    path = _index_path(project_dir)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def load_index(project_dir: str | Path | None = None) -> dict | None:
    """Load project index. Returns None if no index exists."""
    if project_dir is None:
        project_dir = Path().resolve()
    path = _index_path(project_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load index from %s: %s", path, e)
        return None


# ── context builder for AI ───────────────────────────────────────────────

def build_project_context(project_dir: str | Path | None = None) -> str | None:
    """Build a rich context string from session + index for the AI.

    Returns None if no project state exists (fresh directory).
    """
    if project_dir is None:
        project_dir = Path().resolve()

    parts: list[str] = []

    # Load index
    index = load_index(project_dir)
    if index:
        parts.append("=== PROJECT INDEX ===")
        parts.append(f"Files: {index['file_count']}")
        if index.get("symbols"):
            # Group by category
            classes = [s for s in index["symbols"] if s["kind"] == "class"]
            funcs = [s for s in index["symbols"] if s["kind"] == "function"]
            if classes:
                parts.append(f"Classes/Interfaces ({len(classes)}):")
                for s in classes[:30]:
                    parts.append(f"  - {s['name']}  ({s['file']})")
            if funcs:
                parts.append(f"Functions/Methods ({len(funcs)}):")
                for s in funcs[:40]:
                    parts.append(f"  - {s['name']}  ({s['file']})")
        # File tree (recent first, top 30)
        files = index.get("files", [])
        if files:
            parts.append(f"\nFiles ({len(files)} total):")
            for f in files[:30]:
                parts.append(f"  {f['path']}  ({f['size']}B)")

    # Load session summary
    session = load_session(project_dir)
    if session:
        msg_count = len(session.get("messages", []))
        st = session.get("state", {})
        parts.append("\n=== PREVIOUS SESSION ===")
        parts.append(f"Messages: {msg_count} | Cost: ${st.get('cost', 0):.4f} | Turns: {st.get('turns', 0)}")
        # Show last exchange
        msgs = session["messages"]
        if msgs:
            last_user = None
            for m in reversed(msgs):
                if m.get("role") == "user":
                    last_user = m["content"][:200]
                    break
            if last_user:
                parts.append(f"Last request: {last_user}")

    if not parts:
        return None

    return "\n".join(parts)


# ── conversation summarizer — sliding window ────────────────────────────

SUMMARY_THRESHOLD_MSGS = 40  # messages — summarize if above this
SUMMARY_THRESHOLD_TOKENS = 8000  # tokens — summarize if we hit this first
KEEP_LAST = 15           # full messages to keep at the end
HEAD_CHARS = 600         # chars to keep from the start of each old message
TAIL_CHARS = 300         # chars to keep from the end of each old message


def _summarize_message(content: str) -> str:
    """Compress a single message: keep head + tail, preserve structure.

    'head tail' is better than truncate because code often has the
    important part at the end (result, error, summary).
    """
    if len(content) <= HEAD_CHARS + TAIL_CHARS + 50:
        return content.replace("\n", " ").strip()

    head = content[:HEAD_CHARS]
    tail = content[-TAIL_CHARS:]
    # Count newlines in head portion to include structure hint
    n_lines = content[:HEAD_CHARS].count("\n")
    return f"{head}\n[... {n_lines} lines ... {len(content)} chars ...]\n{tail}"


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for English)."""
    return max(1, len(text) // 4)


def _count_conversation_tokens(messages: list) -> int:
    """Count approximate total tokens in the conversation."""
    total = 0
    for m in messages:
        content = m.get("content", "")
        if content and isinstance(content, str):
            total += _estimate_tokens(content)
    return total


def summarize_conversation(messages: list, keep_last: int = 15) -> list:
    """Compress old messages with a sliding window, using both message count AND token count.

    Strategy:
      - Keep the last `keep_last` user/assistant/tool messages FULL.
      - Compress older messages by keeping head + tail of each.
      - Preserve ALL system messages (skill prompts, config, instructions).
      - Returns new list if compression saved space.
      - Triggered by either message count or token count thresholds.
    """
    total_tokens = _count_conversation_tokens(messages)
    if len(messages) <= SUMMARY_THRESHOLD_MSGS and total_tokens <= SUMMARY_THRESHOLD_TOKENS:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system_msgs = [m for m in messages if m.get("role") != "system"]

    tail = non_system_msgs[-keep_last:] if non_system_msgs else []
    end_idx = -keep_last if keep_last < len(non_system_msgs) else len(non_system_msgs)
    middle = non_system_msgs[:end_idx] if end_idx != 0 else []

    if not middle:
        return messages

    # Build a smart summary: keep head+tail of each old message
    summary_lines = ["Previous conversation (compressed):"]
    for m in middle:
        role = m.get("role", "?").upper()
        content = m.get("content", "")
        if not isinstance(content, str) or not content:
            continue
        compressed = _summarize_message(content)
        tok = _estimate_tokens(content)
        summary_lines.append(f"  [{role}] ({tok} tokens) {compressed}")

    summary_text = "\n".join(summary_lines)

    new_msgs = list(system_msgs)
    new_msgs.append({"role": "system", "content": summary_text, "_summary": True})
    new_msgs.extend(tail)
    return new_msgs

def _serializable_messages(messages: list) -> list:
    """Strip non-serializable fields from messages for JSON storage.

    Preserves role, content, tool_calls, and internal flags
    (_skill_prompt, _summary) so that session reload is lossless.
    """
    cleaned = []
    for m in messages:
        entry = {"role": m["role"]}
        if m.get("content"):
            entry["content"] = m["content"]
        if m.get("tool_calls"):
            entry["tool_calls"] = m["tool_calls"]
        if m.get("_skill_prompt"):
            entry["_skill_prompt"] = True
        if m.get("_summary"):
            entry["_summary"] = True
        cleaned.append(entry)
    return cleaned
