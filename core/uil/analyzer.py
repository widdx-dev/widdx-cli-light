"""Task Analyzer — classifies user input into actionable task types.

Uses LLM as primary classifier for accurate intent detection.
Keyword-based classifiers serve as fast-path fallback.
"""

import re
import time

from .contract import (
    ClassificationResult, DecisionStep, TaskType, Domain,
)

# -------------------------------------------------------------------
# LLM Classifier — primary classifier
# -------------------------------------------------------------------

_LLM_CLASSIFIER_PROMPT = (
    "You are WIDDX Nexus, a task classifier for an AI agent system.\n"
    "\n"
    "Given a user message, classify into:\n"
    "1. TASK TYPE: code_read, code_write, code_modify, code_review, research, browser, database, reasoning, chat, file_ops, complex\n"
    "2. EXECUTION MODE: direct, background, cron, delegation\n"
    "3. COMPLEXITY: simple, medium, complex\n"
    "4. FEATURES: web, api, database, cli, testing\n"
    "\n"
    "RULES - TASK TYPE:\n"
    "- code_read: user wants to read, view, explain existing code\n"
    "- code_write: user wants to write/create new code, file, script, project\n"
    "- code_modify: user wants to change, update, edit, fix existing code\n"
    "- code_review: user wants review, audit, quality check\n"
    "- research: user wants to search, find information, investigate\n"
    "- browser: user wants browser automation, navigate, scrape, screenshot\n"
    "- database: user wants database/queries/sql operations\n"
    "- reasoning: user wants analysis, comparison, evaluation, thinking\n"
    "- file_ops: user wants file operations (copy, move, rename)\n"
    "- chat: user is greeting, thanking, or having casual conversation\n"
    "- complex: user wants a full project, multi-step task, or application\n"
    "\n"
    "RULES - EXECUTION MODE:\n"
    "- direct: simple task, run immediately\n"
    "- background: long task (install, build, backup, download) - user can continue chatting\n"
    "- cron: scheduled/recurring task (every day, daily, كل يوم, كل اسبوع)\n"
    "- delegation: complex task needing sub-agents (ابني, create full app, multi-step, complete project)\n"
    "\n"
    "RULES - COMPLEXITY:\n"
    "- simple: 1-2 steps, can be done directly\n"
    "- medium: 3-8 steps, needs an agent\n"
    "- complex: 8+ steps, needs delegation/sub-agents\n"
    "\n"
    "RULES - FEATURES (include all that apply, comma-separated from: web, api, database, cli, testing):\n"
    "- web: if user mentions web, frontend, UI, HTML, CSS, JavaScript, website, موقع\n"
    "- api: if user mentions API, REST, endpoint, backend server\n"
    "- database: if user mentions database, SQL, storage, DB, data persistence\n"
    "- cli: if user mentions CLI, command-line, terminal, console\n"
    "- testing: if user mentions tests, testing, unittest, pytest, اختبار\n"
    "\n"
    "Respond with EXACTLY 4 lines:\n"
    "Line 1: task_type (one word)\n"
    "Line 2: execution_mode (one word)\n"
    "Line 3: complexity (one word)\n"
    "Line 4: features (comma-separated, or 'none')"
)


def _parse_features_from_string(features_str: str) -> dict[str, bool]:
    """Parse a comma-separated feature string into detected_features dict.

    Handles: "web, api, database", "none", "web,api", empty string.
    """
    known_features = {"web", "api", "database", "cli", "testing"}
    result = {f: False for f in known_features}
    if not features_str or features_str.strip() in ("", "none"):
        return result
    parts = [p.strip() for p in features_str.split(",") if p.strip()]
    for part in parts:
        if part in known_features:
            result[part] = True
    return result


def _infer_features_from_text(text: str) -> dict[str, bool]:
    """Infer detected_features from raw user text via keyword matching.

    Used when LLM is unavailable (fallback path).
    """
    lower = text.lower()
    return {
        "web": any(w in lower for w in ["web", "frontend", "ui", "html", "css", "javascript", "website", "موقع", "واجهة"]),
        "api": any(w in lower for w in ["api", "rest", "endpoint", "backend"]),
        "database": any(w in lower for w in ["database", "sql", "storage", "db", "data", "قاعدة بيانات"]),
        "cli": any(w in lower for w in ["cli", "command-line", "terminal", "console"]),
        "testing": any(w in lower for w in ["test", "testing", "unittest", "pytest", "اختبار"]),
    }


class LLMClassifier:
    """Classifier that uses the LLM to determine task type AND execution mode.

    This is the PRIMARY classifier. It detects:
    - Task type (what to do)
    - Execution mode (background, cron, delegation, direct)
    - Complexity (simple, medium, complex)

    Falls back to keyword classifiers when LLM is unavailable.
    """

    def __init__(self, provider=None):
        self.provider = provider
        self._cache: dict[str, tuple[float, str]] = {}
        self._cache_ttl = 60.0  # cache classification for 60 seconds

    def _cache_key(self, text: str) -> str:
        """Generate a deterministic cache key from user input."""
        return str(hash(text.lower().strip()))

    def _get_cached(self, text: str) -> str | None:
        """Retrieve a cached classification result if still within TTL."""
        key = self._cache_key(text)
        entry = self._cache.get(key)
        if entry and (time.time() - entry[0]) < self._cache_ttl:
            return entry[1]
        return None

    def _set_cached(self, text: str, result: str):
        """Store a classification result in cache with current timestamp."""
        key = self._cache_key(text)
        self._cache[key] = (time.time(), result)

    def classify(self, user_input: str,
                 best_result: ClassificationResult | None = None
                 ) -> tuple[ClassificationResult, list[DecisionStep]] | None:
        """Use LLM to classify the user input.

        Returns (ClassificationResult, [DecisionStep]) or None if provider is not set.
        """
        if self.provider is None:
            return None

        try:
            # Check cache
            cached = self._get_cached(user_input)
            if cached:
                content = cached
            else:
                messages = [
                    {"role": "system", "content": _LLM_CLASSIFIER_PROMPT},
                    {"role": "user", "content": user_input[:500]},
                ]
                raw, _ = self.provider.chat(messages, [], temperature=0.1)
                if not raw:
                    return None
                # Strip any [thinking] tags
                content = raw
                th_start = content.find("[thinking]")
                th_end = content.find("[ing]")
                if th_start >= 0 and th_end > th_start:
                    content = (content[:th_start] + content[th_end + len("[ing]")]).strip()
                self._set_cached(user_input, content)

            lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
            if len(lines) < 3:
                return None

            task_type_str = lines[0].lower().strip()
            execution_mode = lines[1].lower().strip()
            complexity_str = lines[2].lower().strip()

            # Parse optional 4th line: features (web, api, database, cli, testing)
            features_line = lines[3].lower().strip() if len(lines) >= 4 else ""
            parsed_features = _parse_features_from_string(features_line)

            # Map task type
            type_map = {
                "code_read": TaskType.CODE_READ,
                "code_write": TaskType.CODE_WRITE,
                "code_modify": TaskType.CODE_MODIFY,
                "code_review": TaskType.CODE_REVIEW,
                "research": TaskType.RESEARCH,
                "browser": TaskType.BROWSER,
                "database": TaskType.DATABASE,
                "reasoning": TaskType.REASONING,
                "chat": TaskType.CHAT,
                "file_ops": TaskType.FILE_OPS,
                "complex": TaskType.COMPLEX,
            }
            task_type = type_map.get(task_type_str)
            if task_type is None:
                return None

            # Map domain
            domain_map = {
                TaskType.CODE_READ: Domain.CODE,
                TaskType.CODE_WRITE: Domain.CODE,
                TaskType.CODE_MODIFY: Domain.CODE,
                TaskType.CODE_REVIEW: Domain.CODE,
                TaskType.RESEARCH: Domain.RESEARCH,
                TaskType.BROWSER: Domain.BROWSER,
                TaskType.DATABASE: Domain.DATABASE,
                TaskType.REASONING: Domain.REASONING,
                TaskType.CHAT: Domain.CHAT,
                TaskType.FILE_OPS: Domain.CHAT,
                TaskType.COMPLEX: Domain.CODE,
            }
            domain = domain_map.get(task_type, Domain.CHAT)

            # Calculate confidence based on execution mode clarity
            confidence = 0.85
            complexity_score = {"simple": 0.2, "medium": 0.5, "complex": 0.9}.get(complexity_str, 0.5)

            step = DecisionStep(
                component="LLMClassifier",
                input_summary=user_input[:80],
                output=f"{task_type_str} | mode={execution_mode} | complexity={complexity_str}",
                score=confidence,
                detail=f"LLM classified: {task_type_str} (mode={execution_mode}, complexity={complexity_str})",
            )
            result = ClassificationResult(
                task_type=task_type,
                domain=domain,
                confidence=round(confidence, 2),
                complexity=round(complexity_score, 2),
                reasoning=f"LLMClassifier: {task_type_str} in {execution_mode} mode ({complexity_str})",
                keywords=[task_type_str, execution_mode, complexity_str],
                detected_features={
                    "execution_mode": execution_mode,
                    "is_complex": str(task_type == TaskType.COMPLEX).lower(),
                    "is_background": str(execution_mode == "background").lower(),
                    "is_cron": str(execution_mode == "cron").lower(),
                    "is_delegation": str(execution_mode == "delegation").lower(),
                    "web": str(parsed_features.get("web", False)).lower(),
                    "api": str(parsed_features.get("api", False)).lower(),
                    "database": str(parsed_features.get("database", False)).lower(),
                    "cli": str(parsed_features.get("cli", False)).lower(),
                    "testing": str(parsed_features.get("testing", False)).lower(),
                },
                decision_path=[step],
                is_fallback=False,
            )
            return result, [step]

        except Exception as e:
            import logging
            logging.getLogger("widdx.uil").debug("LLMClassifier failed: %s", e)
            return None


class TaskAnalyzer:
    """Backward-compatible wrapper around LLMClassifier.

    The old analyzer used keyword matching + LLM fallback.
    The new analyzer uses LLM as primary with execution_mode detection.
    This class maintains the same interface for backward compatibility.
    """

    def __init__(self, provider=None):
        """Initialize the TaskAnalyzer with an optional LLM provider.

        Args:
            provider: Optional provider instance for LLM-based classification.
                      If None, falls back to keyword matching only.
        """
        self.provider = provider
        self._llm = LLMClassifier(provider=provider)

    @staticmethod
    def _cross_validate(user_input: str,
                        classification: ClassificationResult
                        ) -> ClassificationResult:
        """Cross-validate classification against user input keywords.

        Checks for obvious mismatches between input language and
        classified task type. Adjusts confidence and may reclassify.
        """
        lower = user_input.lower()

        # Keywords that strongly suggest specific task types
        write_keywords = ["create", "write", "build", "make", "implement",
                          "new", "develop", "generate", "scaffold",
                          "أنشئ", "اكتب", "ابن", "ابني", "طور", "صمم", "أضف"]
        read_keywords = ["read", "show", "display", "view", "open", "explain",
                         "tell me about", "what is", "اقرأ", "أظهر", "اعرض"]
        modify_keywords = ["edit", "update", "change", "modify", "fix",
                           "update", "improve", "refactor",
                           "عدل", "غير", "أصلح", "حسن"]
        research_keywords = ["search", "find", "research", "look up",
                             "investigate", "what is", "how to",
                             "ابحث", "ادرس", "استقص"]

        # Compute keyword match scores for reclassification hints
        write_score = sum(1 for w in write_keywords if w in lower)
        read_score = sum(1 for w in read_keywords if w in lower)
        modify_score = sum(1 for w in modify_keywords if w in lower)
        research_score = sum(1 for w in research_keywords if w in lower)

        # If classified as CHAT but has ANY intent keywords -> likely misclassification
        if classification.task_type == TaskType.CHAT:
            total_intent = write_score + read_score + modify_score + research_score
            if total_intent >= 1:
                # Likely misclassification - reduce confidence so downstream can flag
                reduction = 0.3 if total_intent >= 2 else 0.6
                classification.confidence = round(classification.confidence * reduction, 2)
                classification.reasoning += (
                    f" | CROSS-VALIDATION: classified as CHAT but input has "
                    f"{total_intent} intent keywords — confidence ×{reduction}"
                )

        # If write-like but classified as read
        if (classification.task_type == TaskType.CODE_READ
                and write_score > read_score):
            classification.confidence = round(classification.confidence * 0.5, 2)
            classification.reasoning += (
                f" | CROSS-VALIDATION: classified as CODE_READ but "
                f"write keywords ({write_score}) > read keywords ({read_score})"
            )

        # If write-like but classified as modify
        if (classification.task_type == TaskType.CODE_MODIFY
                and write_score >= 2 and modify_score == 0):
            classification.confidence = round(classification.confidence * 0.6, 2)
            classification.reasoning += (
                f" | CROSS-VALIDATION: classified as CODE_MODIFY but "
                f"write keywords ({write_score}) found with no modify keywords"
            )

        return classification

    def analyze(self, user_input: str, context: dict | None = None,
                ) -> ClassificationResult:
        """Analyze user input and return a classification result.

        This is the main entry point called by the UIL brain.
        Returns ClassificationResult with task_type, domain, confidence, etc.
        """
        result = self._llm.classify(user_input)
        if result:
            cls_result, steps = result
            cls_result.decision_path = steps
            # Cross-validate LLM classification
            cls_result = self._cross_validate(user_input, cls_result)
            return cls_result

        # Fallback: keyword-based with extended matching + feature detection
        lower = user_input.lower()

        # Detect features from text (web, api, database, cli, testing)
        fallback_features = _infer_features_from_text(user_input)

        # Determine task type via extended keyword matching
        # Order matters: check most specific first
        if any(w in lower for w in [
            "create", "write", "build", "make", "implement",
            "new", "develop", "generate", "scaffold",
            "أنشئ", "اكتب", "ابن", "ابني", "طور", "صمم",
        ]):
            task_type = TaskType.CODE_WRITE
            domain = Domain.CODE
            reasoning = "Fallback: keyword CODE_WRITE"
        elif any(w in lower for w in [
            "edit", "update", "change", "modify", "fix", "improve",
            "refactor", "add feature", "patch",
            "عدل", "غير", "أصلح", "حسن", "طور",
        ]):
            task_type = TaskType.CODE_MODIFY
            domain = Domain.CODE
            reasoning = "Fallback: keyword CODE_MODIFY"
        elif any(w in lower for w in [
            "read", "show", "display", "view", "open", "explain",
            "tell me about", "what is",
            "اقرأ", "أظهر", "اعرض", "صف",
        ]):
            task_type = TaskType.CODE_READ
            domain = Domain.CODE
            reasoning = "Fallback: keyword CODE_READ"
        elif any(w in lower for w in [
            "navigate", "browser", "playwright", "scrape", "screenshot",
            "open url", "open website", "go to", "visit", "chrome",
        ]):
            task_type = TaskType.BROWSER
            domain = Domain.BROWSER
            reasoning = "Fallback: keyword BROWSER"
        elif any(w in lower for w in [
            "search", "find", "research", "look up", "investigate",
            "what is", "how to",
            "ابحث", "ادرس", "استقص",
        ]):
            task_type = TaskType.RESEARCH
            domain = Domain.RESEARCH
            reasoning = "Fallback: keyword RESEARCH"
        elif any(w in lower for w in [
            "query", "select", "insert into", "delete from", "drop table",
            "database", "sql", "mongodb", "redis",
            "استعلام", "قاعدة بيانات",
        ]) or re.search(r'\b(db|sql)\b', lower):
            task_type = TaskType.DATABASE
            domain = Domain.DATABASE
            reasoning = "Fallback: keyword DATABASE"
        elif fallback_features.get("web") or fallback_features.get("api") or fallback_features.get("database"):
            # Has development features but no explicit keyword - treat as complex
            task_type = TaskType.COMPLEX
            domain = Domain.CODE
            reasoning = "Fallback: inferred COMPLEX from features"
        else:
            task_type = TaskType.CHAT
            domain = Domain.CHAT
            reasoning = "Fallback: LLM classifier unavailable"

        complexity = 0.7 if task_type in (TaskType.CODE_WRITE, TaskType.COMPLEX) else (
            0.5 if task_type == TaskType.CODE_MODIFY else 0.1
        )

        step = DecisionStep(
            component="TaskAnalyzer",
            input_summary=user_input[:80],
            output=f"FALLBACK -> {task_type.value}",
            score=0.5,
            detail=f"LLM unavailable, keyword fallback to {task_type.value}",
        )
        return ClassificationResult(
            task_type=task_type,
            domain=domain,
            confidence=0.5,
            complexity=complexity,
            reasoning=reasoning,
            keywords=[],
            detected_features={
                "execution_mode": "direct",
                "is_complex": str(task_type == TaskType.COMPLEX).lower(),
                "is_background": "false",
                "is_cron": "false",
                "is_delegation": str(task_type == TaskType.COMPLEX).lower(),
                **{k: str(v).lower() for k, v in fallback_features.items()},
            },
            is_fallback=True,
            decision_path=[step],
        )
