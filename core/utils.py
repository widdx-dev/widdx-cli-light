"""Shared utilities used across the WIDDX codebase.

Centralizes helpers that were previously duplicated between modules.
"""

import re
from typing import Optional


def parse_frontmatter(text: str, nested_metadata: bool = False) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from markdown text.

    Args:
        text: Full markdown text with optional frontmatter.
        nested_metadata: If True, parse nested ``metadata:`` keys under a
            ``metadata`` sub-dict. Used by MemoryStore for type/classification.
            If False, return all keys as flat top-level entries.
            Used by SkillManager.

    Returns:
        (metadata_dict, body_text).
    """
    meta: dict = {}
    body = text
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
    if not m:
        return meta, body.strip()

    front = m.group(1)
    body = m.group(2)

    if nested_metadata:
        # MemoryStore-style: nested metadata block
        current_key: Optional[str] = None
        meta["metadata"] = {}
        for line in front.splitlines():
            if line.startswith("metadata:"):
                current_key = "metadata"
            elif current_key == "metadata":
                mm = re.match(r'\s+(\w+):\s*(.*)', line)
                if mm:
                    meta["metadata"][mm.group(1)] = mm.group(2).strip()
            else:
                mm = re.match(r'(\w+):\s*(.*)', line)
                if mm:
                    key, val = mm.group(1), mm.group(2).strip()
                    if key not in ("metadata",):
                        meta[key] = val
    else:
        # SkillManager-style: flat key: value only
        for line in front.strip().split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip()

    return meta, body.strip()


def strip_frontmatter(text: str) -> str:
    """Remove frontmatter, return only the body."""
    m = re.match(r'^---\s*\n.*?\n---\s*\n(.*)', text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def to_slug(name: str, max_len: int = 80) -> str:
    """Convert a name to a kebab-case slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:max_len]


def get_last_turn(messages: list) -> dict | None:
    """Extract the last user+assistant exchange from messages.

    Used by MemoryLearner and other modules that need the most
    recent turn for analysis or extraction.
    """
    last_user = None
    last_assistant = None
    for m in reversed(messages):
        if m.get("role") == "assistant" and last_assistant is None:
            content = (m.get("content") or "").strip()
            if content and not content.startswith("[Agent completed"):
                last_assistant = content
        elif m.get("role") == "user":
            last_user = m.get("content")
            break
    if last_user and last_assistant:
        return {"user": last_user, "assistant": last_assistant}
    return None


def sanitize_error(message: str) -> str:
    """Remove sensitive paths and internal details from error messages.

    Strips absolute Windows paths, Unix paths, and stack traces
    so user-facing error messages don't leak filesystem layout.
    """
    import os as _os
    sanitized = message

    # Replace absolute Windows paths (C:\Users\...\project\file.py)
    sanitized = re.sub(r'[A-Za-z]:\\[^\s,;:"]+', '[PATH]', sanitized)
    # Replace absolute Unix paths (/home/user/project/file.py)
    sanitized = re.sub(r'/[^\s,;:"]+/[^\s,;:"]+\.py', '[PATH]', sanitized)
    # Replace env var values (sensitive)
    for var in ('WIDDX_API_KEY', 'DEEPSEEK_API_KEY', 'GITHUB_TOKEN',
                'GITHUB_WEBHOOK_SECRET'):
        val = _os.environ.get(var, '')
        if val and len(val) > 4:
            sanitized = sanitized.replace(val, '[REDACTED]')

    # Strip tracebacks (keep just the error message)
    if 'Traceback (most recent call last):' in sanitized:
        sanitized = sanitized.split('Traceback (most recent call last):')[0]
        # Try to find the actual error at the end
        for line in reversed(message.splitlines()):
            line = line.strip()
            if line and not line.startswith('File ') and not line.startswith('  '):
                sanitized = sanitized.strip() + '\nError: ' + line
                break

    return sanitized.strip() or 'An unknown error occurred'


def sanitize_log(msg: str) -> str:
    """Redact API keys and tokens from log messages.

    Detects patterns like sk-..., Bearer ..., and key=value with
    known sensitive key names, replacing the value with [REDACTED].
    """
    import re as _re
    sanitized = msg
    # API keys (sk-..., sk-ant-..., etc.)
    sanitized = _re.sub(r'sk-[a-zA-Z0-9_-]{20,}', '[REDACTED_KEY]', sanitized)
    # Bearer tokens
    sanitized = _re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer [REDACTED]', sanitized)
    # key=secret patterns
    for key_name in ('api_key', 'apikey', 'secret', 'token', 'password'):
        sanitized = _re.sub(
            rf'{key_name}["\s:=]+[a-zA-Z0-9_\-\.]{{8,}}',
            f'{key_name}=[REDACTED]',
            sanitized,
            flags=_re.IGNORECASE,
        )
    return sanitized
