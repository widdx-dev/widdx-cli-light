"""Architecture Decision Records (ADR) — 4.0 #2.

Records every architectural decision with its context, alternatives,
and consequences. Prevents the agent from suggesting solutions that
were already rejected.

Usage:
    from core.adr import adr_manager
    adr_id = adr_manager.record(
        title="Use SQLite for session storage",
        context="Need persistent sessions across restarts",
        decision="SQLite via aiosqlite",
        alternatives=["Redis", "PostgreSQL", "JSON files"],
        consequences="Single-writer limitation, but zero-dependency",
    )
    context = adr_manager.get_context_for_prompt()
    # → inject into system prompt to prevent re-suggesting Redis
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .utils import to_slug

logger = logging.getLogger("widdx.adr")

ADR_DIR_NAME = "adr"


class ADRManager:
    """Manages Architecture Decision Records in .widdx/adr/."""

    def __init__(self, project_dir: str | Path | None = None):
        root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
        self._adr_dir = root / ".widdx" / ADR_DIR_NAME
        self._adr_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        title: str,
        context: str,
        decision: str,
        alternatives: list[str] | None = None,
        consequences: str = "",
    ) -> str:
        """Record a new ADR. Returns the ADR ID."""
        adr_id = f"ADR-{uuid.uuid4().hex[:8]}"
        slug = to_slug(title)
        now = datetime.now(timezone.utc).isoformat()
        alts = "\n".join(f"- {a}" for a in (alternatives or [])) or "(none considered)"

        content = f"""# {title}

- **ID:** {adr_id}
- **Date:** {now[:10]}
- **Status:** accepted

## Context

{context}

## Decision

{decision}

## Alternatives Considered

{alts}

## Consequences

{consequences or "(not documented)"}
"""
        filepath = self._adr_dir / f"{slug}.md"
        filepath.write_text(content, encoding="utf-8")
        logger.info("ADR recorded: %s — %s", adr_id, title[:60])
        return adr_id

    def search(self, query: str) -> list[dict]:
        """Search ADRs by keyword. Returns list of ADR summaries."""
        results: list[dict] = []
        q = query.lower()
        for f in sorted(self._adr_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            if q in text.lower():
                lines = text.split("\n")
                title = lines[0].lstrip("#").strip() if lines else f.stem
                adr_id = ""
                status = ""
                for line in lines:
                    if "**ID:**" in line:
                        adr_id = line.split("**ID:**")[-1].strip()
                    if "**Status:**" in line:
                        status = line.split("**Status:**")[-1].strip()
                results.append({
                    "id": adr_id,
                    "title": title,
                    "status": status,
                    "file": str(f.relative_to(self._adr_dir.parent)),
                })
        return results

    def get_context_for_prompt(self, max_adrs: int = 10) -> str:
        """Return ADR context for injection into system prompt.

        Lists recent decisions so the agent knows what was rejected
        and why — prevents re-suggesting discarded alternatives.
        """
        adrs = sorted(self._adr_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not adrs:
            return ""

        lines = ["<architecture_decisions>"]
        for f in adrs[:max_adrs]:
            text = f.read_text(encoding="utf-8")
            # Extract title, decision, and alternatives
            title = ""
            decision = ""
            alts: list[str] = []
            in_alts = False
            for line in text.split("\n"):
                if line.startswith("# ") and not title:
                    title = line.lstrip("#").strip()
                if "**Decision:**" in line:
                    decision = line.split("**Decision:**")[-1].strip()
                if "## Alternatives Considered" in line:
                    in_alts = True
                    continue
                if in_alts and line.startswith("- "):
                    alts.append(line[2:].strip())
                if in_alts and line.startswith("##"):
                    in_alts = False
            if title:
                lines.append(f"- {title}")
                if decision:
                    lines.append(f"  Decision: {decision}")
                if alts:
                    lines.append(f"  Rejected: {', '.join(alts)}")
        lines.append("</architecture_decisions>")
        return "\n".join(lines)

    def list_all(self) -> list[dict]:
        """List all ADRs."""
        return self.search("")  # search with empty query returns all


# Singleton
adr_manager = ADRManager()
