"""Web Learning Loop — acquires knowledge from the internet when stuck.

Activated only when:
  1. The agent is stuck (no progress after 3 iterations)
  2. A task requires knowledge the system doesn't have
  3. Verification fails and local patterns don't help

Flow:
  Stuck Detection → Query Builder → Web Search → Extract Patterns → Store → Retry

Usage:
    from core.learning.web_learning import WebLearningLoop
    wl = WebLearningLoop()
    knowledge = wl.learn("How to fix WebSocket timeout in Flask")
    # → {"found": True, "patterns": [...], "summary": "..."}
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("widdx.web_learning")


class WebLearningLoop:
    """Acquires new knowledge from the web when the system is stuck."""

    def __init__(self):
        self._searches_today: int = 0
        self._max_daily_searches: int = 20

    def should_search(self, iteration: int, progress_pct: float, has_local_knowledge: bool) -> bool:
        """Decide if web search is needed.

        Returns True only when:
          - Stuck: iteration > 3 AND progress < 20%
          - OR knowledge gap: has_local_knowledge is False
          - AND under daily search limit
        """
        if self._searches_today >= self._max_daily_searches:
            return False

        stuck = iteration > 3 and progress_pct < 20
        knowledge_gap = not has_local_knowledge

        if stuck or knowledge_gap:
            return True
        return False

    def build_query(self, goal: str, error: str = "", task_type: str = "") -> str:
        """Build an effective web search query."""
        parts = []

        if error:
            # Error-driven: "How to fix X error in Y framework"
            parts.append("how to fix")
            parts.append(error[:100])

        if task_type:
            parts.append("in")
            parts.append(task_type.replace("_", " "))

        if goal:
            # Add technology context
            if "flask" in goal.lower():
                parts.append("flask")
            if "react" in goal.lower():
                parts.append("react")
            if "api" in goal.lower():
                parts.append("API development")

        if not parts:
            parts.append(goal[:200])

        return " ".join(parts)[:300]

    def learn(self, query: str, max_results: int = 3) -> dict:
        """Search the web and extract patterns.

        Returns {"found": bool, "patterns": list, "summary": str, "sources": list}
        """
        if self._searches_today >= self._max_daily_searches:
            return {"found": False, "patterns": [], "summary": "Daily search limit reached", "sources": []}

        self._searches_today += 1

        try:
            import urllib.request
            import urllib.parse

            # Use DuckDuckGo HTML search (no API key needed)
            encoded = urllib.parse.quote(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"

            req = urllib.request.Request(url, headers={
                "User-Agent": "WIDDX-Learning/1.0"
            })

            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Extract result snippets
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            if not snippets:
                snippets = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)

            sources = []
            patterns = []

            for snippet in snippets[:max_results]:
                clean = re.sub(r'<[^>]+>', '', snippet).strip()
                if clean and len(clean) > 30:
                    sources.append(clean[:200])
                    # Extract actionable patterns
                    patterns.append(self._extract_pattern(clean, query))

            summary = ""
            if patterns:
                summary = f"Web search '{query[:60]}...' found {len(patterns)} relevant results. "
                summary += " | ".join(p["solution"][:80] for p in patterns[:3])

            # ── Immediate Knowledge Injection ──
            # Store AND immediately inject into runtime context
            context_injection = ""
            if patterns:
                self._store_patterns(patterns, query)
                # Build context for immediate injection into current execution
                context_injection = self._build_injection_context(patterns, query)

            return {
                "found": len(patterns) > 0,
                "patterns": patterns,
                "summary": summary,
                "sources": sources,
                "injection": context_injection,  # ⚡ Immediate context for Planner
            }

        except Exception as e:
            logger.warning("Web search failed: %s", e)
            return {"found": False, "patterns": [], "summary": f"Search unavailable: {e}", "sources": [], "injection": ""}

    def _build_injection_context(self, patterns: list[dict], query: str) -> str:
        """Build immediate context for hot-reload into current Planner execution."""
        lines = ["<web_knowledge_injection>",
                 f"Search: {query[:150]}",
                 "New knowledge acquired — use this NOW:"]
        for p in patterns[:3]:
            lines.append(f"- {p['solution'][:200]}")
        lines.append("</web_knowledge_injection>")
        return "\n".join(lines)

    def _extract_pattern(self, text: str, context: str) -> dict:
        """Extract a learnable pattern from web search result."""
        # Clean HTML
        clean = re.sub(r'<[^>]+>', ' ', text).strip()
        clean = re.sub(r'\s+', ' ', clean)

        # Detect category
        category = "coding"
        if any(w in clean.lower() for w in ("architecture", "design", "pattern", "structure")):
            category = "architectural"
        elif any(w in clean.lower() for w in ("debug", "fix", "error", "bug", "issue")):
            category = "debugging"
        elif any(w in clean.lower() for w in ("plan", "steps", "workflow", "process")):
            category = "planning"

        # Build pattern name from context
        name = context[:50].lower().replace(" ", "-").replace("?", "")

        return {
            "name": f"web-{name[:40]}",
            "category": category,
            "description": clean[:200],
            "solution": clean[:300],
            "source": "web_search",
            "confidence": 0.4,  # Web knowledge starts with lower confidence
        }

    def _store_patterns(self, patterns: list[dict], query: str):
        """Store web-learned patterns in PatternLibrary."""
        try:
            from .pattern_library import PatternLibrary
            pl = PatternLibrary(global_scope=False)
            for p in patterns:
                pl.add(
                    name=p["name"], category=p["category"],
                    description=p["description"], solution=p["solution"],
                    context=f"Learned from web: {query[:100]}",
                    tags=["web-learned", p["category"]],
                    confidence=0.4,
                    source_project="web",
                )
            logger.info("WebLearning: stored %d patterns from search", len(patterns))
        except Exception as e:
            logger.debug("Failed to store web patterns: %s", e)


# Singleton
_wl: WebLearningLoop | None = None


def get_web_learning() -> WebLearningLoop:
    global _wl
    if _wl is None:
        _wl = WebLearningLoop()
    return _wl
