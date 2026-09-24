"""Embedding-based task classifier — classifies user input WITHOUT an LLM.

Uses TF-IDF similarity against a database of ~200 labeled examples.
Falls back to keyword matching (always works).
Never calls an external API. Never needs a GPU. Always deterministic.

Replaces the LLM-dependent path in core/uil/analyzer.py when LLM is
unavailable, slow, or expensive. Can be used as the primary classifier
with LLM as optional enrichment.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field

from .embeddings import TFIDFEmbedder, get_embedder

logger = logging.getLogger("widdx.intelligence.classifier")

# Task type constants (mirrors core/uil/contract.py TaskType values)
TASK_TYPES = [
    "code_read", "code_write", "code_modify", "code_review",
    "research", "browser", "database", "reasoning",
    "chat", "file_ops", "system", "complex", "unknown",
]


@dataclass
class ClassificationResult:
    """Classification output — compatible with UIL ClassificationResult."""
    task_type: str
    confidence: float  # 0.0 - 1.0
    domain: str = ""
    is_fallback: bool = False
    detected_features: list[str] = field(default_factory=list)
    detected_languages: list[str] = field(default_factory=list)
    method: str = "embedding"  # "embedding" | "keyword" | "llm"

    # ── v4.1 Reasoning enhancements ──
    is_confused: bool = False         # top-2 candidates too close → uncertain
    confusion_margin: float = 0.0     # score gap between best and second-best
    runner_up: str = ""               # second-best task type
    sub_intents: list[dict] = field(default_factory=list)  # multi-part query parts
    query_type: str = "command"       # "command" | "question" | "statement" | "multi"


# ═══════════════════════════════════════════════════════════════════════════════
# LABELED TRAINING EXAMPLES
# ═══════════════════════════════════════════════════════════════════════════════

_LABELED_EXAMPLES: list[tuple[str, str, list[str], list[str]]] = [
    # (user_input, task_type, features, languages)
    # ── Code Write ──
    ("build a REST API with FastAPI", "code_write", ["api", "database"], ["python"]),
    ("create a web app with Flask", "code_write", ["web", "database"], ["python"]),
    ("write a Python script that processes CSV files", "code_write", ["data"], ["python"]),
    ("scaffold a Django project with user authentication", "code_write", ["web", "database", "auth"], ["python"]),
    ("implement a web app with Express.js and MongoDB", "code_write", ["web", "api", "database"], ["javascript"]),
    ("build a React component with TypeScript", "code_write", ["web"], ["typescript"]),
    ("create a CLI tool with argparse", "code_write", ["cli"], ["python"]),
    ("generate a full HTML page with CSS styling and JavaScript", "code_write", ["web"], ["html", "css", "javascript"]),
    ("write a bash script", "code_write", ["cli"], ["bash"]),
    ("build a complete SaaS application", "complex", ["web", "api", "database", "auth"], ["python"]),
    ("create a data pipeline with pandas", "code_write", ["data"], ["python"]),
    ("write unit tests for my Python module", "code_write", ["testing"], ["python"]),
    ("Create Dockerfile and docker-compose for microservices", "code_write", ["docker"], []),
    ("Build a Flutter mobile app", "code_write", ["mobile", "api"], ["dart"]),
    ("write a GitHub Actions CI pipeline", "code_write", ["ci"], []),
    ("create an SQLite database schema", "code_write", ["database"], ["sql"]),
    ("develop a GraphQL API with Strawberry", "code_write", ["api", "database"], ["python"]),
    ("set up a CI/CD pipeline with GitLab CI", "code_write", ["ci"], []),
    ("make a Telegram bot with python-telegram-bot", "code_write", ["api", "data"], ["python"]),
    ("generate a PDF report from JSON data", "code_write", ["data"], ["python"]),
    ("write a Rust CLI utility", "code_write", ["cli"], ["rust"]),
    ("create a Go HTTP server", "code_write", ["api"], ["go"]),
    ("build a Vue.js single-page application", "code_write", ["web"], ["javascript", "typescript"]),
    ("implement a WebSocket chat server", "code_write", ["api", "web"], ["python"]),
    ("write an Ansible playbook for server setup", "code_write", [], []),

    # ── Code Modify ──
    ("fix the bug in the authentication module", "code_modify", [], ["python"]),
    ("refactor this function to be more readable", "code_modify", [], []),
    ("update the API endpoint to handle pagination", "code_modify", ["api"], []),
    ("add error handling to the file processing script", "code_modify", [], ["python"]),
    ("optimize this database query", "code_modify", ["database"], ["sql"]),
    ("fix this bug", "code_modify", [], []),
    ("improve the performance of this code", "code_modify", [], []),
    ("update dependencies and fix breaking changes", "code_modify", ["config"], []),
    ("add dark mode to this page", "code_modify", ["web"], ["css", "javascript"]),
    ("patch the security vulnerability in the login endpoint", "code_modify", ["api", "security"], ["python"]),
    ("upgrade the React components to TypeScript", "code_modify", ["web"], ["typescript"]),
    ("replace the ORM with SQLAlchemy", "code_modify", ["database"], ["python"]),
    ("migrate from Flask to FastAPI", "code_modify", ["api"], ["python"]),
    ("downgrade the npm package version to fix compatibility", "code_modify", ["config"], ["javascript"]),
    ("convert the monolithic app to microservices", "code_modify", ["api", "docker"], ["python"]),

    # ── Code Read ──
    ("what does this function do", "code_read", [], []),
    ("explain this code", "code_read", [], []),
    ("show me the content of config.py", "code_read", [], []),
    ("how does the authentication flow work in this project", "code_read", [], []),
    ("list all the API endpoints", "code_read", ["api"], []),
    ("what dependencies does this project use", "code_read", [], []),
    ("find where the error handling is defined", "code_read", [], []),
    ("summarize the architecture of this project", "code_read", [], []),
    ("show me the database schema", "code_read", ["database"], []),
    ("tell me how the CI pipeline is configured", "code_read", ["ci"], []),
    ("read the Dockerfile and explain it", "code_read", ["docker"], []),
    ("what version of Python does this project use", "code_read", [], []),
    ("how are the tests organized in this project", "code_read", ["testing"], []),
    ("find the main entry point of the application", "code_read", [], []),
    ("show me all environment variables used", "code_read", [], []),

    # ── Code Review ──
    ("review this pull request", "code_review", [], []),
    ("check my code for security issues", "code_review", ["security"], []),
    ("are there any bugs in this implementation", "code_review", [], []),
    ("audit the security of this project", "code_review", ["security"], []),
    ("is this code following best practices", "code_review", [], []),
    ("review the API design for RESTful best practices", "code_review", ["api"], []),
    ("check if the database migrations are safe", "code_review", ["database"], []),
    ("review the error handling strategy in this module", "code_review", [], []),
    ("is the test coverage adequate for this project", "code_review", ["testing"], []),
    ("review the Dockerfile for security issues", "code_review", ["docker", "security"], []),

    # ── Research ──
    ("search for the best Python ORM", "research", [], []),
    ("find documentation about FastAPI middleware", "research", ["api"], ["python"]),
    ("research how to implement OAuth2", "research", ["auth"], []),
    ("what is the difference between Redis and Memcached", "research", [], []),
    ("find examples of clean architecture in Node.js", "research", [], ["javascript"]),
    ("investigate memory leaks in Python", "research", [], ["python"]),
    ("analyze this repository structure", "research", [], []),
    ("compare PostgreSQL and MongoDB for real-time analytics", "research", ["data", "database"], []),
    ("find the latest trends in WebAssembly", "research", [], []),
    ("look up best practices for Kubernetes networking", "research", ["docker"], []),
    ("research error monitoring solutions for production", "research", [], []),
    ("compare RabbitMQ vs Kafka for message queues", "research", [], []),
    ("find tutorials on React Server Components", "research", ["web"], ["javascript"]),
    ("investigate the performance of PyPy vs CPython", "research", [], ["python"]),

    # ── Database ──
    ("query all users who registered in the last month", "database", [], ["sql"]),
    ("create a migration for the new table", "database", [], ["sql"]),
    ("design a MongoDB schema for a social media app", "database", [], []),
    ("optimize this slow SQL query", "database", [], ["sql"]),
    ("insert sample data into the users table", "database", [], ["sql"]),
    ("create a database backup script", "database", [], ["sql"]),
    ("set up a read replica for the database", "database", [], []),
    ("run a SELECT JOIN across three tables", "database", [], ["sql"]),
    ("add an index to speed up the queries", "database", [], ["sql"]),
    ("design the database schema for an e-commerce app", "database", [], []),

    # ── Browser ──
    ("open the login page and take a screenshot", "browser", ["web"], []),
    ("scrape the product listings from this website", "browser", ["web"], []),
    ("test the signup form on the staging server", "browser", ["web"], []),
    ("automate the checkout flow on the demo site", "browser", ["web"], []),
    ("take a screenshot of the dashboard page", "browser", ["web"], []),
    ("fill in the contact form and submit", "browser", ["web"], []),
    ("navigate to google.com", "browser", ["web"], []),
    ("go to a website and click a button", "browser", ["web"], []),
    ("visit a URL and extract data", "browser", ["web"], []),

    # ── System ──
    ("check disk usage and alert if below 10%", "system", [], ["bash"]),
    ("monitor CPU and memory on the server", "system", [], ["bash"]),
    ("restart the nginx service", "system", [], ["bash"]),
    ("check all running processes", "system", [], ["bash"]),
    ("list all active network connections", "system", [], ["bash"]),
    ("analyze the system logs for errors", "system", [], ["bash"]),
    ("free up disk space by removing old logs", "system", [], ["bash"]),
    ("check the status of all systemd services", "system", [], ["bash"]),
    ("verify SSL certificate expiry dates", "system", ["security"], ["bash"]),
    ("check firewall rules and open ports", "system", ["security"], ["bash"]),

    # ── File Ops ──
    ("rename all .txt files to .md", "file_ops", [], []),
    ("organize my Downloads folder", "file_ops", [], []),
    ("find all Python files without type hints", "file_ops", [], []),
    ("Delete temporary files older than 7 days", "file_ops", [], []),
    ("copy all images to a backup folder", "file_ops", [], []),
    ("compress the log directory into a zip file", "file_ops", [], []),
    ("merge all CSV files in a directory into one", "file_ops", ["data"], []),
    ("find duplicate files in the project", "file_ops", [], []),
    ("split the large file into 10MB chunks", "file_ops", [], []),
    ("extract all tar.gz archives in this folder", "file_ops", [], []),

    # ── Chat ──
    ("hello", "chat", [], []),
    ("what can you do", "chat", [], []),
    ("thanks for your help", "chat", [], []),
    ("tell me a joke", "chat", [], []),
    ("what is the meaning of life", "chat", [], []),
    ("how are you", "chat", [], []),
    ("good morning", "chat", [], []),
    ("who created you", "chat", [], []),
    ("tell me about yourself", "chat", [], []),
    ("what is the weather like", "chat", [], []),
    ("i need some motivation", "chat", [], []),
    ("say hello to the world", "chat", [], []),
    ("are you sentient", "chat", [], []),
    ("i am bored entertain me", "chat", [], []),
    ("what do you think about AI safety", "chat", [], []),
    ("how does this tool work", "chat", [], []),
    ("explain the project to me in simple terms", "chat", [], []),

    # ── Reasoning ──
    ("solve this math problem step by step", "reasoning", [], []),
    ("debug why the test is failing", "reasoning", ["testing"], []),
    ("figure out why the database connection is dropping", "reasoning", ["database"], []),
    ("trace the root cause of the memory leak", "reasoning", [], []),
    ("compare the time complexity of these two algorithms", "reasoning", [], []),
    ("analyze the trade-offs of using microservices vs monolith", "reasoning", [], []),
    ("why is the API returning 502 errors intermittently", "reasoning", ["api"], []),
    ("determine if this approach will scale to 1M users", "reasoning", [], []),

    # ── Complex ──
    ("design a full e-commerce platform from scratch", "complex", ["web", "api", "database", "auth", "docker"], []),
    ("create a real-time collaboration tool like Figma", "complex", ["web", "api", "database"], []),
    ("build a complete social media platform with chat, feed, and notifications", "complex", ["web", "api", "database", "auth"], []),
    ("architect a multi-tenant SaaS system", "complex", ["web", "api", "database", "docker", "ci"], []),
    ("implement a CI/CD system with automated testing and canary deployments", "complex", ["ci", "docker", "api"], []),
    ("build a distributed task queue with worker pool", "complex", ["api", "data"], []),
    ("create a video streaming platform with transcoding pipeline", "complex", ["web", "api", "data"], []),
    ("develop a monitoring system with alerts and dashboards", "complex", ["web", "api", "data"], []),
    ("build a search engine for code repositories", "complex", ["web", "api", "data"], []),
    ("design a real-time multiplayer game server", "complex", ["api"], []),

    # ── More Code Write ──
    ("write a TypeScript library for date formatting", "code_write", ["web"], ["typescript"]),
    ("create a Python package for JWT authentication", "code_write", ["auth", "api"], ["python"]),
    ("make a desktop app with Electron and React", "code_write", ["web"], ["javascript"]),
    ("code a simple neural network from scratch with NumPy", "code_write", ["data"], ["python"]),
    ("produce a Terraform module for AWS infrastructure", "code_write", ["docker", "ci"], []),
    ("construct a microservice with gRPC in Go", "code_write", ["api"], ["go"]),
    ("build a Chrome extension with manifest v3", "code_write", ["web"], ["javascript"]),
    ("write a REST client SDK in JavaScript", "code_write", ["api"], ["javascript"]),
    ("create a cross-platform CLI tool in Rust", "code_write", ["cli"], ["rust"]),
    ("generate a SonarQube quality gate configuration", "code_write", ["ci"], []),
    ("implement rate limiting middleware for FastAPI", "code_write", ["api", "security"], ["python"]),
    ("build a markdown-to-HTML converter in Python", "code_write", ["cli"], ["python"]),
    ("write a Slack bot with Bolt framework", "code_write", ["api"], ["python"]),
    ("scaffold a Next.js blog with MDX support", "code_write", ["web"], ["typescript"]),
    ("develop an API gateway with Kong configuration", "code_write", ["api"], []),

    # ── More Code Modify ──
    ("add input validation to the signup form", "code_modify", ["web", "auth"], []),
    ("increase the timeout on the database connection pool", "code_modify", ["database"], []),
    ("rename the public API method to follow conventions", "code_modify", ["api"], []),
    ("remove deprecated code from the module", "code_modify", [], []),
    ("revert the last commit and fix the regression", "code_modify", [], []),
    ("reduce memory usage in the image processing loop", "code_modify", [], []),
    ("simplify the nested if-else in the validation logic", "code_modify", [], []),
    ("split the monolithic router into separate modules", "code_modify", ["api"], []),
    ("extract the configuration code into a separate file", "code_modify", [], []),
    ("clean up unused imports across the project", "code_modify", [], []),

    # ── More Code Review ──
    ("does this code introduce any SQL injection vulnerabilities", "code_review", ["security", "database"], []),
    ("check if the error messages expose internal paths", "code_review", ["security"], []),
    ("review this async code for race conditions", "code_review", [], []),
    ("audit the dependencies for known CVEs", "code_review", ["security"], []),
    ("is the pagination implementation correct", "code_review", ["api"], []),
    ("verify the types are correct on this interface", "code_review", [], []),
    ("check for memory leaks in the event handler", "code_review", [], []),

    # ── More Research ──
    ("what are the best practices for API versioning", "research", ["api"], []),
    ("find the official documentation for pandas 2.0", "research", [], ["python"]),
    ("look up how Stripe handles idempotency", "research", ["api"], []),
    ("investigate the pros and cons of WebSockets vs SSE", "research", [], []),
    ("search for benchmark results of Rust vs Go for networking", "research", [], []),

    # ── More Chat ──
    ("tell me a fun fact about space", "chat", [], []),
    ("what is your favorite programming language", "chat", [], []),
    ("do you dream of electric sheep", "chat", [], []),
    ("i need help figuring out what to eat for lunch", "chat", [], []),
    ("how do I stay productive while coding", "chat", [], []),
    ("give me a quote about programming", "chat", [], []),
    ("what is the capital of France", "chat", [], []),
    ("explain recursion in simple terms", "chat", [], []),
    ("read the contents of the README file", "code_read", [], []),
    ("tell me about the classes in the models package", "code_read", [], []),
    ("display the test coverage report", "code_read", ["testing"], []),
    ("run the linter on the src directory", "system", [], ["bash"]),
    ("install the dependencies from requirements.txt", "system", [], ["bash"]),
    ("what are the best books for learning Go", "research", [], []),
    ("find open source alternatives to Slack", "research", [], []),
]


# ═══════════════════════════════════════════════════════════════════════════════
# KEYWORD CLASSIFIER (fallback)
# ═══════════════════════════════════════════════════════════════════════════════

_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    # (task_type, [keywords...])
    ("code_write", ["create", "write", "build", "make", "implement",
                     "develop", "generate", "scaffold", "new project",
                     "start a", "setup", "compose", "produce",
                     "assemble", "construct"]),
    ("code_modify", ["edit", "update", "change", "modify", "fix",
                      "improve", "refactor", "add feature", "patch",
                      "optimize", "enhance", "tweak", "revise",
                      "convert", "migrate", "downgrade", "upgrade",
                      "replace", "upgrade"]),
    ("code_read", ["read", "show", "display", "view", "explain",
                    "describe", "what does", "how does", "list all",
                    "find where", "summarize", "tell me about",
                    "what is this", "show me", "reveal"]),
    ("code_review", ["review", "audit", "check for bugs",
                      "is this code", "security audit",
                      "best practices", "code review", "check if",
                      "is it safe", "code quality"]),
    ("research", ["search", "find", "research", "look up", "investigate",
                   "what is", "how to", "compare", "difference between",
                   "latest", "trends", "tutorials", "documentation for"]),
    ("reasoning", ["solve", "debug why", "figure out", "root cause",
                    "trace the", "why is", "trade-offs", "will this",
                    "determine if", "analyze why"]),
    ("database", ["query", "select from", "insert into", "delete from",
                   "drop table", "database", "sql", "mongodb", "redis",
                   "migration", "schema", "postgres", "backup",
                   "index", "replica", "join"]),
    ("browser", ["open the", "screenshot", "scrape the", "browse",
                  "navigate to", "login page", "form on", "automate",
                  "fill in", "submit", "checkout", "go to", "visit"]),
    ("system", ["check disk", "monitor cpu", "restart the", "process",
                 "service", "daemon", "systemctl", "disk usage",
                 "network", "firewall", "ssl", "certificate",
                 "system logs", "running processes", "free up space"]),
    ("file_ops", ["rename", "organize", "move file", "copy file",
                   "delete file", "find all", "compress", "merge all",
                   "duplicate files", "split the", "extract all",
                   "archive"]),
    ("complex", ["design a full", "complete platform", "end to end",
                  "from scratch", "full stack", "architect",
                  "multi-tenant", "distributed", "real-time"]),
    ("chat", ["hello", "hi", "hey", "thanks", "thank you",
               "what can you do", "how are you", "joke",
               "good morning", "good evening", "who created",
               "tell me about yourself", "weather", "motivation",
               "sentient", "bored", "entertain", "opinion on"]),
]

# Feature detection keywords
_FEATURE_KEYWORDS: dict[str, list[str]] = {
    "api": ["api", "rest", "endpoint", "http", "route", "fastapi",
             "flask", "express", "openapi", "swagger", "graphql",
             "json api", "restful", "websocket", "grpc", "microservice"],
    "database": ["database", "sql", "nosql", "postgres", "sqlite",
                   "mongodb", "redis", "migration", "schema", "orm",
                   "prisma", "sqlalchemy", "model", "index", "replica",
                   "backup", "select", "join"],
    "web": ["web", "html", "css", "frontend", "browser", "page",
             "website", "spa", "react", "tailwind", "javascript",
             "typescript", "dom", "ui", "ux", "responsive", "vue",
             "angular", "nextjs", "ssr"],
    "cli": ["cli", "command line", "terminal", "argparse",
             "click", "bash", "script", "tool", "binary"],
    "auth": ["auth", "login", "register", "jwt", "oauth", "password",
              "session", "token", "rbac", "permission", "authenticate"],
    "data": ["data", "csv", "json", "pandas", "polars", "pipeline",
              "etl", "transform", "analyse", "statistic", "parquet",
              "analytics", "stream"],
    "docker": ["docker", "container", "kubernetes", "k8s",
                "dockerfile", "compose", "podman"],
    "testing": ["test", "pytest", "jest", "unittest", "mock",
                 "coverage", "assert", "spec", "integration test"],
    "security": ["security", "vulnerability", "cve", "injection",
                  "xss", "csrf", "encrypt", "hash", "ssl", "tls"],
    "mobile": ["flutter", "react native", "android", "ios", "mobile app",
                "dart", "swift", "kotlin"],
    "ci": ["ci/cd", "ci", "github actions", "jenkins", "pipeline",
            "deploy", "release", "artifact", "build", "gitlab"],
}

_LANGUAGE_KEYWORDS: dict[str, list[str]] = {
    "python": ["python", "py", "django", "flask", "fastapi", "pytest",
                "pandas", "sqlalchemy", "pydantic"],
    "javascript": ["javascript", "js", "node", "npm", "express",
                    "react", "vue", "next.js", "es6"],
    "typescript": ["typescript", "ts", "tsx", "angular", "prisma",
                    "typeorm", "interface", "type annotation"],
    "html": ["html", "html5", "semantic", "aria", "dom"],
    "css": ["css", "scss", "sass", "tailwind", "bootstrap", "flexbox"],
    "sql": ["sql", "postgresql", "mysql", "sqlite", "query", "table"],
    "bash": ["bash", "sh", "shell", "script", "linux command"],
    "dart": ["dart", "flutter", "pub"],
    "rust": ["rust", "cargo", "crate"],
    "go": ["go", "golang", "go mod"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════════

class LocalClassifier:
    """Classify user input into task type + features WITHOUT an LLM.

    Uses embedding similarity as primary method, keyword matching as fallback.
    Always returns a ClassificationResult — never fails, never None.
    """

    def __init__(self):
        self._embedder: TFIDFEmbedder | None = None
        self._indexed = False

    def _ensure_indexed(self):
        """Index labeled examples for similarity search (lazy, first use)."""
        if self._indexed:
            return
        self._embedder = get_embedder()
        texts = [text for text, _, _, _ in _LABELED_EXAMPLES]
        self._embedder.index(texts)
        self._indexed = True

    def classify(self, user_input: str) -> ClassificationResult:
        """Classify user input. Returns ClassificationResult with confidence.

        v4.1: Detects multi-part queries, confusion, and query type.

        Args:
            user_input: The raw user input text.

        Returns:
            ClassificationResult with task_type, confidence, features, languages.
            is_fallback=True if keyword matching was used.
        """
        if not user_input or not user_input.strip():
            return ClassificationResult(
                task_type="chat", confidence=0.8,
                domain="general", is_fallback=False, method="empty",
                query_type="statement",
            )

        self._ensure_indexed()

        # ── Step 0: Detect query type ──
        query_type = self._detect_query_type(user_input)
        sub_intents = []
        if query_type == "multi":
            sub_intents = self._split_intents(user_input)

        # ── Method 1: Embedding similarity ──
        result = self._classify_by_embedding(user_input)
        if result and result.confidence >= 0.3:
            result.detected_features = self._detect_features(user_input)
            result.detected_languages = self._detect_languages(user_input)
            result.sub_intents = sub_intents
            result.query_type = query_type
            return result

        # ── Method 2: Keyword fallback ──
        result = self._classify_by_keywords(user_input)
        result.sub_intents = sub_intents
        result.query_type = query_type
        return result

    def _classify_by_embedding(self, text: str) -> ClassificationResult | None:
        """Try to classify by embedding similarity against labeled examples.

        v4.1: Tracks runner-up + confusion margin for uncertainty-aware routing.
        """
        try:
            if self._embedder is None:
                return None
            results = self._embedder.search(text, top_k=5, min_score=0.05)
        except Exception:
            return None

        if not results:
            return None

        # Collect votes from top matches, weighted by similarity score
        votes: dict[str, float] = {}
        for score, matched_text in results:
            for example_text, task_type, _, _ in _LABELED_EXAMPLES:
                if example_text == matched_text:
                    votes[task_type] = votes.get(task_type, 0) + score
                    break

        if not votes:
            return None

        # Sort by vote score descending
        sorted_types = sorted(votes.items(), key=lambda kv: kv[1], reverse=True)
        total_score = sum(votes.values())

        best_type = sorted_types[0][0]
        best_score = sorted_types[0][1]

        # ── Confidence calibration using relative margin ──
        if total_score > 0:
            normalized_best = best_score / total_score
            raw_confidence = min(0.9, normalized_best * 2.0)
        else:
            normalized_best = 0
            raw_confidence = 0.0

        # Detect confusion: if runner-up is too close
        runner_up_type = ""
        confusion_margin = 0.0
        is_confused = False
        if len(sorted_types) >= 2:
            runner_up_type = sorted_types[1][0]
            runner_up_score = sorted_types[1][1]
            margin = best_score - runner_up_score
            # Normalize margin relative to total
            if total_score > 0:
                confusion_margin = round(margin / total_score, 3)
            else:
                confusion_margin = 0.0
            # Confused if margin < 0.15 or scores are very close
            is_confused = confusion_margin < 0.15 and len(sorted_types) >= 2

        # Reduce confidence when confused
        adjusted_confidence = raw_confidence
        if is_confused and raw_confidence > 0.3:
            adjusted_confidence = max(0.3, raw_confidence * 0.7)

        return ClassificationResult(
            task_type=best_type,
            confidence=round(adjusted_confidence, 2),
            method="embedding",
            is_confused=is_confused,
            confusion_margin=confusion_margin,
            runner_up=runner_up_type,
        )

    def _classify_by_keywords(self, text: str) -> ClassificationResult:
        """Classify by keyword matching. Always succeeds."""
        lower = text.lower()
        best_type = "chat"
        best_score = 0

        for task_type, keywords in _KEYWORD_RULES:
            score = sum(1 for kw in keywords if kw in lower)
            if score > best_score:
                best_score = score
                best_type = task_type

        confidence = 0.5 if best_score >= 2 else 0.3

        return ClassificationResult(
            task_type=best_type,
            confidence=confidence,
            is_fallback=True,
            detected_features=self._detect_features(text),
            detected_languages=self._detect_languages(text),
            method="keyword",
        )

    def _detect_query_type(self, text: str) -> str:
        """Detect whether input is a question, command, statement, or multi-intent."""
        lower = text.strip().lower()

        question_words = {"what", "how", "why", "when", "where", "who",
                          "which", "is", "are", "does", "can", "could",
                          "would", "should", "do", "did", "has", "have"}
        first_word = lower.split()[0] if lower.split() else ""

        if first_word in question_words or lower.endswith("?"):
            return "question"

        multi_markers = 0
        # "and" between two different task descriptions
        if " and " in lower:
            parts = lower.split(" and ")
            # Only multi if both sides have meaningful task language
            if 2 <= len(parts) <= 4:
                meaningful = [p for p in parts if len(p.split()) >= 2 and not p.startswith("and")]
                if len(meaningful) >= 2:
                    multi_markers += 1

        # Comma-separated tasks
        comma_parts = [p.strip() for p in lower.split(",")]
        meaningful_commands = [p for p in comma_parts
                               if len(p.split()) >= 2 and not any(
                                   w in p for w in {"hello", "hi", "thanks", "please"})]
        if len(meaningful_commands) >= 3:
            multi_markers += 1

        if multi_markers >= 1:
            return "multi"

        command_indicators = {"create", "write", "build", "make", "fix",
                              "show", "read", "list", "find", "run",
                              "delete", "move", "copy", "open", "search",
                              "design", "implement", "generate", "update"}
        if first_word in command_indicators:
            return "command"

        return "command"

    def _split_intents(self, text: str) -> list[dict]:
        """Split multi-intent query into sub-intents with per-part classification.

        Returns list of {"text": str, "task_type": str, "confidence": float}
        """
        lower = text.strip().lower()
        parts = []

        # Split by " and "
        if " and " in lower:
            raw_parts = lower.split(" and ")
        elif "," in lower:
            raw_parts = [p.strip() for p in lower.split(",")]
        else:
            return []

        for part in raw_parts:
            part = part.strip()
            if len(part.split()) < 2:
                continue
            sub = self.classify(part)
            parts.append({
                "text": part,
                "task_type": sub.task_type,
                "confidence": sub.confidence,
            })

        return parts

    def _detect_features(self, text: str) -> list[str]:
        """Detect project features from text keywords."""
        lower = text.lower()
        features = []
        for feat, keywords in _FEATURE_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                features.append(feat)
        return features

    def _detect_languages(self, text: str) -> list[str]:
        """Detect programming languages from text."""
        lower = text.lower()
        langs = []
        for lang, keywords in _LANGUAGE_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                langs.append(lang)
        return langs if langs else ["python"]  # default to python

    def get_confidence(self, task_type: str, user_input: str) -> float:
        """Get confidence score for a specific task type for this input."""
        result = self.classify(user_input)
        if result.task_type == task_type:
            return result.confidence
        return 0.0


# Module-level singleton
_classifier: LocalClassifier | None = None


def get_classifier() -> LocalClassifier:
    """Get or create the global local classifier."""
    global _classifier
    if _classifier is None:
        _classifier = LocalClassifier()
    return _classifier


def classify_input(text: str) -> ClassificationResult:
    """Quick classification without LLM. Always returns a result."""
    return get_classifier().classify(text)
