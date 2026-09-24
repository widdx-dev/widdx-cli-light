"""Validation Reporter — generates structured quality reports.

Combines multiple validation signals into a single ValidationReport:
- Syntax/runtime check results (from runner.py)
- Code quality signals (pattern detection)
- Output quality signals (length, completeness)
- Computes overall quality score

This replaces the old verifier.py single-pass regex approach.
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field

from typing import Any

from .runner import get_runner

logger = logging.getLogger("widdx.validation.reporter")


@dataclass
class Finding:
    """A single validation finding."""
    severity: str  # "critical", "error", "warning", "info"
    check_name: str
    message: str
    location: str = ""
    suggestion: str = ""
    passed: bool = True


@dataclass
class ValidationReport:
    """Complete validation report with multi-signal quality score."""
    # Scores
    syntax_score: float = 1.0
    runtime_score: float = 1.0
    quality_score: float = 1.0
    overall: float = 1.0

    # Details
    findings: list[Finding] = field(default_factory=list)
    passed: bool = True
    verifier_name: str = "ValidationEngine"
    execution_time: float = 0.0

    # Convenience
    criticas: list[Finding] = field(default_factory=list)
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)

    def __post_init__(self):
        self.criticas = [f for f in self.findings if f.severity == "critical"]
        self.errors = [f for f in self.findings if f.severity == "error"]
        self.warnings = [f for f in self.findings if f.severity == "warning"]

    @property
    def has_criticas(self) -> bool:
        return len(self.criticas) > 0

    def summarize(self) -> str:
        n = len(self.findings)
        n_fail = sum(1 for f in self.findings if not f.passed)
        return f"{n} checks, {n_fail} failed, overall={self.overall:.2f}"


class ValidationReporter:
    """Validates execution results and generates quality reports.

    Uses multiple validation methods:
    1. Syntax check (compile)
    2. Runtime execution (actually runs code)
    3. Code quality patterns (dangerous patterns, style issues)
    4. Output quality (length, completeness, placeholders)
    """

    def __init__(self):
        self._runner = get_runner()

    def validate(self,
                 result: Any,  # ExecutionResult from UIL
                 classification: Any,  # ClassificationResult
                 context: dict | None = None) -> ValidationReport:
        """Validate an execution result.

        Args:
            result: ExecutionResult from the UIL pipeline
            classification: ClassificationResult with task_type
            context: Optional dict with 'code_content', 'html_content',
                    'bash_commands' keys

        Returns:
            ValidationReport with findings and scores.
        """
        context = context or {}
        findings: list[Finding] = []

        # Get the raw text output
        raw_text = ""
        if hasattr(result, 'summary'):
            raw_text = result.summary or ""
        elif isinstance(result, str):
            raw_text = result

        # Determine what kind of content we're validating
        code = context.get("code_content", raw_text)
        html = context.get("html_content", "")
        bash = context.get("bash_commands", "")

        # ── 1. Syntax checks ──
        syntax_findings = self._check_syntax(code, html, bash)
        findings.extend(syntax_findings)
        syntax_score = self._compute_score(syntax_findings)

        # ── 2. Runtime checks (actually execute code) ──
        runtime_findings: list[Finding] = []
        if code and code.strip():
            runtime_findings = self._check_runtime(code, classification)
            findings.extend(runtime_findings)
        runtime_score = self._compute_score(runtime_findings) if runtime_findings else 1.0

        # ── 3. Quality checks ──
        quality_findings = self._check_quality(raw_text, classification)
        findings.extend(quality_findings)
        quality_score = self._compute_score(quality_findings)

        # ── 4. Compute overall ──
        if runtime_findings:
            # Runtime check carries more weight
            overall = syntax_score * 0.2 + runtime_score * 0.5 + quality_score * 0.3
        else:
            overall = syntax_score * 0.4 + quality_score * 0.6

        overall = round(overall, 2)

        return ValidationReport(
            syntax_score=syntax_score,
            runtime_score=runtime_score,
            quality_score=quality_score,
            overall=overall,
            findings=findings,
            passed=overall >= 0.7,
            criticas=[f for f in findings if f.severity == "critical"],
            errors=[f for f in findings if f.severity == "error"],
            warnings=[f for f in findings if f.severity == "warning"],
        )

    def _check_syntax(self, code: str, html: str,
                      bash: str) -> list[Finding]:
        """Syntax-level checks (regex-based, fast)."""
        findings = []

        # Python syntax — only if content looks like code
        _LOOKS_LIKE_CODE = re.compile(
            r'(def\s|class\s|import\s|from\s|print\(|return\s|if\s|for\s|while\s|'
            r'lambda\s|with\s|try:|except|else:|\w+\s*=\s*|\w+\(.*\))'
        )
        if code and code.strip() and _LOOKS_LIKE_CODE.search(code):
            try:
                compile(code, "<validation>", "exec")
                findings.append(Finding(
                    severity="info", check_name="python_syntax",
                    message="Python syntax is valid", passed=True,
                ))
            except SyntaxError as e:
                findings.append(Finding(
                    severity="critical", check_name="python_syntax",
                    message=f"SyntaxError at line {e.lineno}: {e.msg}",
                    passed=False,
                ))

        # HTML structure
        if html and html.strip():
            if "<!DOCTYPE html>" not in html and "<!doctype html>" not in html:
                findings.append(Finding(
                    severity="error", check_name="html_doctype",
                    message="Missing DOCTYPE declaration", passed=False,
                ))
            if "<html" not in html:
                findings.append(Finding(
                    severity="critical", check_name="html_structure",
                    message="Missing <html> tag", passed=False,
                ))
            if "<body" not in html and "<body>" not in html:
                findings.append(Finding(
                    severity="error", check_name="html_body",
                    message="Missing <body> tag", passed=False,
                ))

        # Bash dangerous patterns
        if bash and bash.strip():
            dangerous = [
                (r'\brm\s+-rf\b', "rm -rf"),
                (r'\bchmod\s+777\b', "chmod 777"),
                (r'>\s*/dev/sd[a-z]', "raw disk write"),
            ]
            for pattern, desc in dangerous:
                if re.search(pattern, bash):
                    findings.append(Finding(
                        severity="critical", check_name="bash_dangerous",
                        message=f"Dangerous pattern: {desc}", passed=False,
                    ))

        return findings

    def _check_runtime(self, code: str, classification: object) -> list[Finding]:
        """Actually run the code and check for runtime errors."""
        findings: list[Finding] = []

        task_type = getattr(classification, 'task_type', '')
        if hasattr(task_type, 'value'):
            task_type = task_type.value

        # Only run code for code_write/modify tasks
        if task_type not in ('code_write', 'code_modify', 'complex'):
            return findings

        # Skip if code looks non-executable
        if len(code) < 20:
            return findings

        run_result = self._runner.run_python(code, timeout=10)

        if run_result.success:
            findings.append(Finding(
                severity="info", check_name="runtime_execution",
                message=f"Code executed successfully ({run_result.execution_time:.2f}s)",
                passed=True,
            ))
        else:
            if run_result.was_timeout:
                findings.append(Finding(
                    severity="warning", check_name="runtime_timeout",
                    message="Code execution timed out after 10s",
                    passed=False,
                ))
            elif run_result.errors:
                for err in run_result.errors[:3]:
                    findings.append(Finding(
                        severity="error", check_name="runtime_error",
                        message=err[:150], passed=False,
                    ))
            else:
                findings.append(Finding(
                    severity="error", check_name="runtime_exit",
                    message=f"Exited with code {run_result.exit_code}",
                    passed=False,
                ))

        return findings

    def _check_quality(self, text: str, classification: Any) -> list[Finding]:
        """Check output quality — length, completeness, anti-patterns."""
        findings = []
        if not text or not text.strip():
            findings.append(Finding(
                severity="error", check_name="empty_output",
                message="Output is empty", passed=False,
            ))
            return findings

        # Length check
        if len(text) < 50:
            findings.append(Finding(
                severity="warning", check_name="short_output",
                message=f"Output is very short ({len(text)} chars)",
                passed=False,
            ))

        # Placeholder / incomplete content
        placeholders = [
            "lorem ipsum", "todo:", "your code here",
            "implement this", "add your", "fill in",
        ]
        for ph in placeholders:
            if ph in text.lower():
                findings.append(Finding(
                    severity="warning", check_name="placeholder_content",
                    message=f"Found placeholder: '{ph}'",
                    suggestion="Replace with actual implementation",
                    passed=False,
                ))

        # Hardcoded secrets?
        secret_patterns = [
            (r'(?:api_?key|apikey|secret|password|token)\s*[:=]\s*["\'][\w-]{20,}["\']',
             "possible hardcoded secret"),
        ]
        for pattern, desc in secret_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                findings.append(Finding(
                    severity="error", check_name="hardcoded_secret",
                    message=desc, passed=False,
                ))

        return findings

    @staticmethod
    def _compute_score(findings: list[Finding]) -> float:
        """Compute score from findings. Critical penalty > error > warning."""
        if not findings:
            return 1.0
        score = 1.0
        for f in findings:
            if f.passed:
                continue
            if f.severity == "critical":
                score -= 0.3
            elif f.severity == "error":
                score -= 0.15
            elif f.severity == "warning":
                score -= 0.05
        return max(0.0, round(score, 2))


# Module-level singleton
_reporter: ValidationReporter | None = None


def get_reporter() -> ValidationReporter:
    """Get or create the validation reporter."""
    global _reporter
    if _reporter is None:
        _reporter = ValidationReporter()
    return _reporter


def validate_result(result: Any, classification: Any,
                    context: dict | None = None) -> ValidationReport:
    """Validate an execution result. Main entry point."""
    return get_reporter().validate(result, classification, context)
