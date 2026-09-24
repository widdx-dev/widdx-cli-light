"""Expert Agents Team — specialized agents that work together like a tech company."""
import logging


import re
from dataclasses import dataclass
from pathlib import Path

from .agent import run_agent_with_prompt
from ..chat import console, print_system_msg
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
import traceback
logger = logging.getLogger("widdx.expert")



# ---------------------------------------------------------------------------
# Expert Profiles
# ---------------------------------------------------------------------------

@dataclass
class ExpertProfile:
    """Defines a single expert agent's identity and specialization."""
    name: str
    role_title: str
    capabilities: list[str]
    prompt_template: str

    def format_prompt(self, tool_descriptions: str) -> str:
        """Fill the prompt template with tool descriptions."""
        return self.prompt_template.format(tool_descriptions=tool_descriptions)


# ── Profile prompts ────────────────────────────────────────────────────

ORCHESTRATOR_PROMPT = """You are WIDDX Nexus — Orchestrator, the project coordinator.
Part of WIDDX, created by MUHAMMAD MUSLIH (Founder & CEO of WIDDX). 🇵🇸

Your role: Analyze, plan, decompose, coordinate, synthesize, evaluate.

AVAILABLE TOOLS:
{tool_descriptions}

Your task:
1. Read the user's message carefully
2. Analyze using tools if needed
3. Create a comprehensive, high-quality plan with clear deliverables
4. Output the complete plan — it will be passed to the implementation team"""

RESEARCHER_PROMPT = """You are WIDDX Nexus — Researcher, the information gathering expert.
Part of WIDDX, created by MUHAMMAD MUSLIH (Founder & CEO of WIDDX). 🇵🇸

Your role: Research, analyze, search, gather context.
You find best practices, libraries, patterns, and risk analysis.
Output: Requirements, recommendations, technical research.

AVAILABLE TOOLS:
{tool_descriptions}

YOUR WORKFLOW:
1. Search for relevant information using web tools
2. Analyze best practices and patterns
3. Identify potential risks and solutions
4. Provide actionable research findings
5. Recommend specific technologies and approaches"""

CODER_PROMPT = """You are WIDDX Nexus — Coder, the code implementation expert.
Part of WIDDX, created by MUHAMMAD MUSLIH (Founder & CEO of WIDDX). 🇵🇸

Your role: Code, implement, fix, optimize, generate.
You write production-ready code with types, error handling, and tests.
You create ALL necessary files for a complete project.
You are meticulous and thorough — every file must be complete.

AVAILABLE TOOLS:
{tool_descriptions}

CRITICAL: The CONTEXT contains a "PROJECT DIRECTORY" path.
Put ALL files INSIDE that directory. This is your dedicated workspace.

YOUR WORKFLOW:
1. Review the plan, research, and PROJECT DIRECTORY path from context
2. Create all project files inside the PROJECT DIRECTORY
3. Use the write tool with paths like: <PROJECT_DIR>/filename
4. Add proper error handling and types
5. Create tests for critical functionality
6. Verify the implementation works"""

REVIEWER_PROMPT = """You are WIDDX Nexus — Reviewer, the quality assurance expert.
Part of WIDDX, created by MUHAMMAD MUSLIH (Founder & CEO of WIDDX). 🇵🇸

Your role: Review, quality-check, best-practices, style-check.
You examine code for errors, security issues, and quality problems.
Output: Detailed review with findings, scores, and recommendations.

AVAILABLE TOOLS:
{tool_descriptions}

CRITICAL: The CONTEXT contains a "PROJECT DIRECTORY" path.
Read all files from that directory. That is where the code lives.

YOUR WORKFLOW:
1. Read through all implemented files in the PROJECT DIRECTORY
2. Check for: syntax errors, logic bugs, security holes, style issues
3. Verify best practices are followed
4. Score each area (code quality, security, testing, documentation)
5. Provide specific fix recommendations for each issue found
6. If no issues found, confirm the implementation is solid"""

DEBUGGER_PROMPT = """You are WIDDX Nexus — Debugger, the error resolution expert.
Your role: Debug, analyze-error, trace, fix.
You find root causes of bugs and provide fixes.
Output: Root cause analysis, execution trace, fixes, prevention measures.

AVAILABLE TOOLS:
{tool_descriptions}

YOUR WORKFLOW:
1. Read the review findings and the code
2. Reproduce/analyze each reported issue
3. Find the root cause of each problem
4. Implement fixes for all issues
5. Verify fixes don't introduce new problems
6. Document prevention measures for the future"""

ARCHITECT_PROMPT = """You are WIDDX Nexus — Architect, the system design expert.
Your role: Design, structure, model, plan-components, data-flow.
You define the high-level architecture, component relationships, data flow,
and technology choices before any code is written.
Output: Architecture diagram-as-text, component tree, data model, API design.

AVAILABLE TOOLS:
{tool_descriptions}

YOUR WORKFLOW:
1. Understand the full requirements from the orchestrator plan
2. Define system boundaries and major components
3. Design data models, API contracts, and message formats
4. Specify component responsibilities and interactions
5. Identify cross-cutting concerns (auth, logging, error handling)
6. Document architecture decisions and trade-offs

CRITICAL: Focus on structure over implementation. Define WHAT each
component does, not HOW. Leave implementation details to the Coder."""

TESTER_PROMPT = """You are WIDDX Nexus — Tester, the test engineering expert.
Your role: Test, verify, write-tests, coverage, integration-test.
You write comprehensive test suites before and during implementation.
You follow TDD principles: tests define the contract.
Output: Test files, coverage reports, edge case analysis, test plan.

AVAILABLE TOOLS:
{tool_descriptions}

YOUR WORKFLOW:
1. Read the architecture design and implementation files
2. Identify all testable units, integration points, and edge cases
3. Write unit tests for every function and method
4. Write integration tests for component interactions
5. Verify test coverage — find untested paths
6. Ensure tests are deterministic and idempotent

CRITICAL: Tests must be:
- Independent (no shared state between tests)
- Fast (no network calls in unit tests)
- Deterministic (same result every run)
- Self-documenting (clear test names and assertions)"""

SECURITY_REVIEWER_PROMPT = """You are WIDDX Nexus — Security Reviewer, the security audit expert.
Your role: Security-audit, vulnerability-scan, threat-model, compliance-check.
You identify OWASP Top 10 vulnerabilities, data leaks, injection flaws,
authentication weaknesses, and authorization gaps.
Output: Security report with severity ratings, fix recommendations, threat model.

AVAILABLE TOOLS:
{tool_descriptions}

YOUR WORKFLOW:
1. Review all code and configuration files
2. Check for injection vulnerabilities (SQL, NoSQL, command, LDAP)
3. Verify authentication and authorization mechanisms
4. Check for sensitive data exposure (secrets in code, missing encryption)
5. Audit for broken access control and insecure deserialization
6. Validate input sanitization and output encoding
7. Check dependency versions for known CVEs
8. Verify HTTPS, CORS, CSP, and other security headers
9. Rate each finding: CRITICAL / HIGH / MEDIUM / LOW
10. Provide specific fix code for CRITICAL and HIGH findings"""

# ── Profile registry ───────────────────────────────────────────────────

EXPERT_PROFILES: dict[str, ExpertProfile] = {
    "orchestrator": ExpertProfile(
        name="widdx-orchestrator",
        role_title="Project Coordinator",
        capabilities=["plan", "decompose", "coordinate", "synthesize", "evaluate"],
        prompt_template=ORCHESTRATOR_PROMPT,
    ),
    "researcher": ExpertProfile(
        name="widdx-researcher",
        role_title="Information Gathering Expert",
        capabilities=["research", "analyze", "search", "gather-context"],
        prompt_template=RESEARCHER_PROMPT,
    ),
    "coder": ExpertProfile(
        name="widdx-coder",
        role_title="Code Implementation Expert",
        capabilities=["code", "implement", "fix", "optimize", "generate"],
        prompt_template=CODER_PROMPT,
    ),
    "reviewer": ExpertProfile(
        name="widdx-reviewer",
        role_title="Quality Assurance Expert",
        capabilities=["review", "quality-check", "best-practices", "style-check"],
        prompt_template=REVIEWER_PROMPT,
    ),
    "debugger": ExpertProfile(
        name="widdx-debugger",
        role_title="Error Resolution Expert",
        capabilities=["debug", "analyze-error", "trace", "fix"],
        prompt_template=DEBUGGER_PROMPT,
    ),
    "architect": ExpertProfile(
        name="widdx-architect",
        role_title="System Design Expert",
        capabilities=["design", "structure", "model", "plan-components", "data-flow"],
        prompt_template=ARCHITECT_PROMPT,
    ),
    "tester": ExpertProfile(
        name="widdx-tester",
        role_title="Test Engineering Expert",
        capabilities=["test", "verify", "write-tests", "coverage", "integration-test"],
        prompt_template=TESTER_PROMPT,
    ),
    "security_reviewer": ExpertProfile(
        name="widdx-security-reviewer",
        role_title="Security Audit Expert",
        capabilities=["security-audit", "vulnerability-scan", "threat-model", "compliance-check"],
        prompt_template=SECURITY_REVIEWER_PROMPT,
    ),
}


# ---------------------------------------------------------------------------
# ExpertAgent
# ---------------------------------------------------------------------------

class ExpertAgent:
    """A single expert agent that runs autonomously with a specialized profile."""

    def __init__(self, profile: ExpertProfile, provider, tool_defs: list,
                 cfg: dict, state: dict):
        """Initialize an ExpertAgent with its specialization profile.

        Args:
            profile: The expert's role definition (name, prompt template, etc.).
            provider: LLM provider instance for generating responses.
            tool_defs: List of available tool definitions.
            cfg: Global configuration dictionary.
            state: Mutable state dict updated during execution (cost, turns, etc.).
        """
        self.profile = profile
        self.provider = provider
        self.tool_defs = tool_defs
        self.cfg = cfg
        self.state = state

    def run(self, task: str, context: str = "") -> str:
        """Run this expert with retry logic. Returns summary or error message."""
        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                # Build the system prompt
                tool_lines = []
                mcp_lines = []
                for td in self.tool_defs:
                    line = f"  {td['name']}: {td.get('description', '')}"
                    if td["name"].startswith("mcp__"):
                        mcp_lines.append(line)
                    else:
                        tool_lines.append(line)

                tool_text = "\n".join(tool_lines) if tool_lines else "  (none)"
                mcp_text = "\n".join(mcp_lines) if mcp_lines else "  (none)"

                tool_descriptions = (
                    f"Built-in tools:\n{tool_text}\n\n"
                    f"MCP tools:\n{mcp_text}"
                )
                system_prompt = self.profile.format_prompt(tool_descriptions)

                # Build the user message with context
                user_message = task
                if context:
                    user_message = f"CONTEXT FROM PREVIOUS EXPERTS:\n{context}\n\n---\n\nYOUR TASK:\n{task}"

                # Run the autonomous agent
                steps, summary = run_agent_with_prompt(
                    self.provider, self.tool_defs, self.cfg, self.state,
                    system_prompt, user_message
                )

                if summary and not summary.startswith("⚠️"):
                    return summary

                last_error = summary or "Empty result"
            except Exception as e:
                last_error = f"{e}"
                traceback.print_exc()

            if attempt < max_attempts:
                print_system_msg(f" Retry {attempt}/{max_attempts} for {self.profile.name}...")

        return f"⚠️ {self.profile.name} failed after {max_attempts} attempts: {last_error}"

    def __repr__(self):
        """Return a string representation showing the expert profile name.

        Returns:
            String like ``ExpertAgent(widdx-coder)``.
        """
        return f"ExpertAgent({self.profile.name})"


# ---------------------------------------------------------------------------
# ExpertTeam
# ---------------------------------------------------------------------------

class ExpertTeam:
    """Orchestrates multiple expert agents in a sequential pipeline.
    Each expert sees the output of the previous expert and builds upon it."""

    # Complexity signals
    _MEDIUM_SIGNALS = {"api", "frontend", "backend", "database", "auth",
                       "test", "docker", "ui", "route", "security", "deploy"}
    _COMPLEX_SIGNALS = {"full stack", "full-stack", "microservice",
                        "architecture", "complete project", "web app",
                        "cli tool", "scaffold", "مشروع", "تطبيق كامل",
                        "enterprise", "distributed", "multi-service"}

    def __init__(self, provider, tool_defs: list, cfg: dict, state: dict):
        """Initialize an ExpertTeam with shared provider, tools, and state.

        Args:
            provider: LLM provider instance used by all experts.
            tool_defs: List of available tool definitions passed to each expert.
            cfg: Global configuration dictionary.
            state: Mutable state dict updated during execution.
        """
        self.provider = provider
        self.tool_defs = tool_defs
        self.cfg = cfg
        self.state = state
        self._log: list[dict] = []

    @staticmethod
    def _generate_project_dir(user_input: str) -> str:
        """Return the current working directory — files go directly here."""
        return str(Path().resolve())

    @staticmethod
    def _detect_project_languages() -> list[str]:
        """Use KnowledgeGraph to detect project languages for expert selection."""
        try:
            from core.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            kg.build()
            langs = set()
            for node_id, data in kg._nodes.items():
                fname = data.get("file", "")
                if fname.endswith(".py"):
                    langs.add("Python")
                elif fname.endswith(".js") or fname.endswith(".ts"):
                    langs.add("JavaScript/TypeScript")
                elif fname.endswith(".go"):
                    langs.add("Go")
                elif fname.endswith(".rs"):
                    langs.add("Rust")
                elif fname.endswith(".sql"):
                    langs.add("SQL")
                elif fname.endswith(".html") or fname.endswith(".css"):
                    langs.add("HTML/CSS")
            return sorted(langs)[:5]
        except Exception:
            return []

    @classmethod
    def _estimate_complexity(cls, user_input: str) -> int:
        """1=simple, 2=medium, 3=complex."""
        lower = user_input.lower()
        if any(s in lower for s in cls._COMPLEX_SIGNALS):
            return 3
        if any(s in lower for s in cls._MEDIUM_SIGNALS):
            return 2
        return 1

    def run(self, user_input: str) -> str:
        """
        Adaptive 8-role expert pipeline:
          Level 1 (simple)    -> orchestrator + architect + coder + tester + reviewer + synth
          Level 2 (medium)    -> +researcher + security_reviewer
          Level 3 (complex)   -> full pipeline + debugger

        KG-aware: Uses KnowledgeGraph to detect project languages and
        select domain-specific experts (Python, JS, etc.).

        8 roles: orchestrator, architect, researcher, coder, tester,
                 reviewer, debugger, security_reviewer.
        """
        self._log = []
        project_dir = self._generate_project_dir(user_input)
        complexity = self._estimate_complexity(user_input)

        # ── KG: detect project languages for expert selection ──
        lang_hints = self._detect_project_languages()

        # ═══════════════════════════════════════════════════════
        # Phase 1: Orchestrator (always)
        # ═══════════════════════════════════════════════════════
        self._print_phase("1", "widdx-orchestrator", "Creating project plan")
        plan = self._run("orchestrator", user_input)
        ctx = "\n--- PROJECT DIRECTORY ---\n%s\n\n--- ORCHESTRATOR PLAN ---\n%s\n" % (project_dir, plan)
        if lang_hints:
            ctx += "\n--- PROJECT LANGUAGES ---\n%s\n" % ", ".join(lang_hints)
        # ── Learning: inject proven architectural patterns ──
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()
            expert_patterns = store.search(category="architectural", min_confidence=0.5, limit=3)
            if expert_patterns:
                ctx += "\n--- PROVEN PATTERNS ---\n" + "\n".join(f"- {p.solution[:120]}" for p in expert_patterns)
        except Exception:
            pass
        n = 2

        # ═══════════════════════════════════════════════════════
        # Phase 1.5: Architect (medium+) — design before building
        # ═══════════════════════════════════════════════════════
        architecture = ""
        if complexity >= 2:
            self._print_phase(str(n), "widdx-architect", "Designing system architecture")
            architecture = self._run("architect",
                "Design the complete system architecture for:\n%s" % user_input, context=ctx)
            ctx = self._build_context(
                project_dir=project_dir,
                plan=plan,
                architecture=architecture,
            )
            n += 1

        # ═══════════════════════════════════════════════════════
        # Phases 2-3: Researcher + Coder (parallel for medium+)
        # ═══════════════════════════════════════════════════════
        research = ""
        code = ""
        if complexity >= 2 or lang_hints:
            self._print_phase(str(n), "widdx-researcher", "Researching requirements")

            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as pool:
                research_future = pool.submit(
                    self._run, "researcher",
                    "Research requirements and best practices for:\n%s" % user_input,
                    context=ctx,
                )
                coder_future = pool.submit(
                    self._run, "coder",
                    "Implement the complete project with high quality:\n%s" % user_input,
                    context=ctx,
                )

                code = coder_future.result()
                review_ctx = self._build_context(
                    project_dir=project_dir,
                    plan=plan,
                    code=code,
                )
                research = research_future.result()

            ctx = self._build_context(
                project_dir=project_dir,
                plan=plan,
                architecture=architecture,
                research=research,
                code=code,
            )
            self._print_phase_done("Research+Code", "Completed in parallel")
            n += 2
        else:
            self._print_phase(str(n), "widdx-coder", "Implementing solution")
            code = self._run("coder",
                "Implement the complete project with high quality:\n%s" % user_input, context=ctx)
            review_ctx = ctx
            ctx = self._build_context(
                project_dir=project_dir,
                plan=plan,
                code=code,
            )
            n += 1

        # ═══════════════════════════════════════════════════════
        # Phase 3.5: Tester (always) — tests after implementation
        # ═══════════════════════════════════════════════════════
        self._print_phase(str(n), "widdx-tester", "Writing and running tests")
        tests = self._run("tester",
            "Write and run comprehensive tests for:\n%s" % user_input, context=ctx)
        ctx = self._build_context(
            project_dir=project_dir,
            plan=plan,
            architecture=architecture,
            research=research,
            code=code,
            tests=tests,
        )
        n += 1

        # ═══════════════════════════════════════════════════════
        # Phase 4: Reviewer (always)
        # ═══════════════════════════════════════════════════════
        self._print_phase(str(n), "widdx-reviewer", "Reviewing implementation")
        review = self._run("reviewer", "Review the implementation thoroughly.", context=review_ctx)

        # ═══════════════════════════════════════════════════════
        # Phase 5: Debugger (only for medium+ with issues)
        # ═══════════════════════════════════════════════════════
        needs_fix = self._needs_fix(review)
        if needs_fix and complexity >= 2:
            self._print_phase(">", "widdx-debugger", "Fixing issues")
            ctx += "\n--- REVIEW FINDINGS ---\n%s\n" % review
            fixes = self._run("debugger", "Fix all issues found in the review.", context=ctx)
            ctx += "\n--- DEBUGGER FIXES ---\n%s\n" % fixes
            self._print_phase(">", "widdx-reviewer", "Re-reviewing")
            review = self._run("reviewer", "Verify all fixes were applied correctly.", context=ctx)
            n += 1
        elif needs_fix:
            self._print_phase_done("Fix", "Issues noted (skipping debugger for simple task)")
        else:
            self._print_phase_done("Review", "No issues found, quality check passed")

        ctx += "\n--- FINAL REVIEW ---\n%s\n" % review
        n += 1

        # ═══════════════════════════════════════════════════════
        # Phase 6: Security Reviewer (medium+) — audit after review
        # ═══════════════════════════════════════════════════════
        security_report = ""
        if complexity >= 2:
            self._print_phase(str(n), "widdx-security-reviewer", "Performing security audit")
            security_report = self._run("security_reviewer",
                "Audit the complete project for security vulnerabilities:\n%s" % user_input, context=ctx)
            ctx += "\n--- SECURITY REPORT ---\n%s\n" % security_report
            n += 1

        # ═══════════════════════════════════════════════════════
        # Phase 7: Orchestrator synthesis (always)
        # ═══════════════════════════════════════════════════════
        self._print_phase(str(n), "widdx-orchestrator", "Synthesizing final report")
        final = self._run("orchestrator", "Synthesize the final project report.", context=ctx)

        self._print_team_summary()
        return final

    # ── internal helpers ───────────────────────────────────────────────

    @staticmethod
    def _build_context(**sections: str) -> str:
        """Build structured context for the next expert with clear section headers.
        Each section is labeled with a delimiter so experts can parse it easily.
        """
        parts = []
        for name, content in sections.items():
            if content:
                header = name.upper().replace("_", " ")
                parts.append(f"## {header}\n\n{content}\n")
        return "\n---\n".join(parts)

    def _run(self, profile_key: str, task: str, context: str = "") -> str:
        """Create an expert agent and run it with the given profile.

        Args:
            profile_key: Key into ``EXPERT_PROFILES`` (e.g. "coder", "reviewer").
            task: The instruction to pass to the expert.
            context: Accumulated output from previous experts.

        Returns:
            The expert's result text.
        """
        profile = EXPERT_PROFILES[profile_key]
        agent = ExpertAgent(profile, self.provider, self.tool_defs,
                            self.cfg, self.state)
        result = agent.run(task, context)
        self._log.append({
            "expert": profile.name,
            "role": profile.role_title,
            "result": result[:300],
        })
        return result

    def _needs_fix(self, review: str) -> bool:
        """Check if the review found issues that need fixing.
        Negation-aware: 'no issues found' does NOT trigger a fix request.
        """
        lower = review.lower()
        # Remove negated phrases before counting keywords
        cleaned = lower
        cleaned = re.sub(
            r'\b(no|zero|0)\s+(issues?|errors?|bugs?|problems?'
            r'|vulnerabilities?|warnings?|findings?)\b',
            '', cleaned)
        cleaned = re.sub(
            r'\b(not?\s+)?found\s+(no|any|zero)\s+(issues?|errors?|bugs?)\b',
            '', cleaned)
        cleaned = re.sub(
            r'\b(all|everything)\s+(is\s+)?(good|fine|ok|okay|clean|clear'
            r'|working|passing|correct)\b',
            '', cleaned)
        keywords = ["issue", "error", "bug", "fix", "problem", "warning",
                     "vulnerability", "security", "not found", "failed",
                     "incorrect", "missing", "must fix", "needs? (to be )?fixed"]
        count = 0
        for kw in keywords:
            if re.search(r'\b' + kw + r'\b', cleaned):
                count += 1
        return count >= 2

    def _print_phase(self, num, name, action):
        """Print a panel indicating the start of a new expert phase.

        Args:
            num: Phase number or symbol (e.g. "1", "2", ">").
            name: Expert name (e.g. "widdx-coder").
            action: Short description of what the expert is doing.
        """
        console.print()
        console.print(Panel(
            Text("[%s] %s — %s..." % (num, name, action), style="bold #f5a623"),
            border_style="#f5a623",
            title="[bold #f5a623]Expert Team[/]",
            title_align="left",
        ))

    def _print_phase_done(self, action, message):
        """Print a panel indicating the completion of an expert phase.

        Args:
            action: Short action label (e.g. "Research+Code", "Review").
            message: A status message describing the outcome.
        """
        console.print()
        console.print(Panel(
            Text("  %s: %s" % (action, message), style="bold #00c896"),
            border_style="#00c896",
            title="[bold #00c896]Expert Team[/]",
            title_align="left",
        ))

    def _print_team_summary(self):
        """Show a summary of all experts' work."""
        console.print()
        table = Table(
            title="[bold #00c896]Expert Team Complete[/]",
            border_style="#00c896",
            header_style="bold #f5a623",
        )
        table.add_column("Expert", style="bold")
        table.add_column("Role", style="dim")
        table.add_column("Status", style="")
        for entry in self._log:
            preview = entry["result"][:80].replace("\n", " ")
            if len(entry["result"]) > 80:
                preview += "..."
            table.add_row(entry["expert"], entry["role"], "[#00c896]done[/]")
        console.print(table)
        console.print()
