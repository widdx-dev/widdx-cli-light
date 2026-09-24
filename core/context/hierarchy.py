"""Hierarchical Context — Multi-level context compression for small models.

Builds a 4-level context pyramid so weak models see the most critical
information first and can request deeper levels on demand:

  L1 ─ Summary     (one-liner project goal + current task)
  L2 ─ Structure   (directory tree of relevant areas)
  L3 ─ Key files   (content of the most relevant files)
  L4 ─ Conversation (recent message history)

Usage:
    from core.context.hierarchy import HierarchicalContext
    hc = HierarchicalContext()
    ctx = hc.build(goal="add user auth", files=["src/routes/auth.py"])
    print(ctx.l1)      # compact summary
    print(ctx.render())  # full context for a small-model prompt
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path


logger = logging.getLogger("widdx.context")


@dataclass
class ContextLevel:
    text: str = ""
    token_estimate: int = 0


@dataclass
class HierarchicalResult:
    l1: ContextLevel = field(default_factory=ContextLevel)
    l2: ContextLevel = field(default_factory=ContextLevel)
    l3: ContextLevel = field(default_factory=ContextLevel)
    l4: ContextLevel = field(default_factory=ContextLevel)

    def render(self, max_level: int = 4) -> str:
        """Render context up to a given level."""
        parts = []
        if self.l1.text:
            parts.append(f"<context_l1_summary>\n{self.l1.text}\n</context_l1_summary>")
        if max_level >= 2 and self.l2.text:
            parts.append(f"<context_l2_structure>\n{self.l2.text}\n</context_l2_structure>")
        if max_level >= 3 and self.l3.text:
            parts.append(f"<context_l3_files>\n{self.l3.text}\n</context_l3_files>")
        if max_level >= 4 and self.l4.text:
            parts.append(f"<context_l4_history>\n{self.l4.text}\n</context_l4_history>")
        return "\n\n".join(parts)


class HierarchicalContext:
    """Builds a 4-level context pyramid from project state + user input."""

    def __init__(self, project_dir: str | Path | None = None):
        self._project_dir = Path(project_dir or Path.cwd()).resolve()

    def build(
        self,
        goal: str = "",
        files: list[str] | None = None,
        messages: list[dict] | None = None,
        max_l3_files: int = 5,
        max_l4_messages: int = 6,
    ) -> HierarchicalResult:
        """Build all 4 context levels.

        Args:
            goal: The current task goal or user request.
            files: Specific file paths relevant to this task.
            messages: Recent conversation messages.
            max_l3_files: Max file contents to include in L3.
            max_l4_messages: Max recent messages to include in L4.
        """
        return HierarchicalResult(
            l1=self._build_l1(goal),
            l2=self._build_l2(files),
            l3=self._build_l3(files or [], max_l3_files),
            l4=self._build_l4(messages or [], max_l4_messages),
        )

    # ── Level 1: One-line summary ──────────────────────────────

    def _build_l1(self, goal: str) -> ContextLevel:
        project_name = self._project_dir.name
        text = f"Project: {project_name}\nGoal: {goal[:200]}"
        return ContextLevel(text=text, token_estimate=len(text) // 4)

    # ── Level 2: Directory structure ───────────────────────────

    def _build_l2(self, files: list[str] | None) -> ContextLevel:
        parts = [f"Project root: {self._project_dir}"]
        relevant_dirs = set()
        if files:
            for f in files:
                p = Path(f)
                relevant_dirs.add(str(p.parent) if p.parent != "." else ".")
        scan_dirs = list(relevant_dirs) if relevant_dirs else ["."]
        for d in scan_dirs[:5]:
            target = self._project_dir / d
            if target.is_dir():
                parts.append(self._format_tree(target, depth=2))
        text = "\n".join(parts)
        return ContextLevel(text=text, token_estimate=len(text) // 4)

    def _format_tree(self, directory: Path, depth: int = 2, prefix: str = "") -> str:
        if depth < 0:
            return ""
        lines = []
        try:
            entries = sorted(
                os.listdir(directory),
                key=lambda e: (not (directory / e).is_dir(), e.lower()),
            )
        except PermissionError:
            return f"{prefix}[permission denied]"

        for i, entry in enumerate(entries):
            if entry.startswith(".") or entry.startswith("__pycache__"):
                continue
            full = directory / entry
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry}")
            if full.is_dir():
                extension = "    " if is_last else "│   "
                lines.append(self._format_tree(full, depth - 1, prefix + extension))
        return "\n".join(lines)

    # ── Level 3: Key file contents ─────────────────────────────

    def _build_l3(self, files: list[str], max_files: int) -> ContextLevel:
        parts = []
        count = 0
        for fp in files:
            if count >= max_files:
                break
            path = self._project_dir / fp if not Path(fp).is_absolute() else Path(fp)
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    short = content[:3000]
                    if len(content) > 3000:
                        short += "\n# ... truncated ..."
                    parts.append(f"--- {fp} ---\n{short}")
                    count += 1
                except Exception as e:
                    parts.append(f"--- {fp} ---\n[error reading: {e}]")
        text = "\n\n".join(parts)
        return ContextLevel(text=text, token_estimate=len(text) // 4)

    # ── Level 4: Recent conversation context ───────────────────

    def _build_l4(self, messages: list[dict], max_msgs: int) -> ContextLevel:
        if not messages:
            return ContextLevel()
        recent = messages[-max_msgs:]
        parts = []
        for msg in recent:
            role = msg.get("role", "unknown")
            content = (msg.get("content") or "")[:500]
            parts.append(f"[{role}]: {content}")
        text = "\n".join(parts)
        return ContextLevel(text=text, token_estimate=len(text) // 4)
