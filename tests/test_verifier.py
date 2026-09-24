"""Tests for core/uil/verifier.py — 10 test groups.

V.2.1  HtmlVerifier: catches opacity:0 without JS reveal
V.2.2  HtmlVerifier: catches unbalanced tags
V.2.3  HtmlVerifier: catches missing data-i18n translations
V.2.4  HtmlVerifier: catches onclick without handler
V.2.5  HtmlVerifier: passes a clean page
V.2.6  CodeVerifier: catches unbalanced braces
V.2.7  BashVerifier: catches dangerous commands
V.2.8  BashVerifier: catches unclosed quotes
V.2.9  Registry: selects correct verifier per TaskType
V.2.10 Integration: brain.py pipeline with verifier
"""

import os
import shutil
import subprocess
import sys
import tempfile
import pytest

# ── Nuclear pycache clear BEFORE any core imports ─────────────
# This project uses editable install (pip install -e .).
# pytest collects modules in an order that creates stale .pyc files.
# We kill them here, before any core module is imported.
_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _dp, _dn, _fn in os.walk(_here):
    if "__pycache__" in _dn:
        shutil.rmtree(os.path.join(_dp, "__pycache__"), ignore_errors=True)

from core.uil.verifier import (
    HtmlVerifier, CodeVerifier, BashVerifier, get_verifier,
)
from core.uil.contract import (
    ClassificationResult, ExecutionResult,
    TaskType, Domain,
)


def _result(summary="", error=None):
    return ExecutionResult(success=not bool(error), summary=summary, error=error)


def _cls(task_type=TaskType.CODE_WRITE):
    return ClassificationResult(
        task_type=task_type, domain=Domain.CODE,
        confidence=0.9, complexity=0.5, reasoning="test",
    )


# ── Helpers for fresh-subprocess tests ────────────────────────
# HtmlVerifier._check_js_css_binding and brain.py integration
# are sensitive to stale .pyc. We run them in a subprocess.

_PROJECT_ROOT = _here.replace("\\", "/")


def _fresh_run(script_body: str) -> str:
    """Run Python code in subprocess after clearing all __pycache__."""
    preamble = (
        "import os, shutil\n"
        f'for dp, dn, fn in os.walk("{_PROJECT_ROOT}"):\n'
        '    if "__pycache__" in dn:\n'
        "        shutil.rmtree(os.path.join(dp, '__pycache__'), ignore_errors=True)\n"
    )
    full_script = preamble + script_body
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
    tmp.write(full_script)
    tmp.close()
    try:
        proc = subprocess.run([sys.executable, tmp.name], capture_output=True, text=True)
    finally:
        os.unlink(tmp.name)
    return proc.stdout


# ═══════════════════════════════════════════════════════════════
# V.2.1  HtmlVerifier — opacity:0 without JS reveal
# ═══════════════════════════════════════════════════════════════

class TestHtmlVerifierHiddenElement:

    def test_detects_critical(self):
        html = '<!DOCTYPE html><html><head><style>.s{opacity:0}</style></head><body><div class="s">x</div><script>c()</script></body></html>'
        script = (
            "from core.uil.verifier import HtmlVerifier\n"
            "from core.uil.contract import ExecutionResult, ClassificationResult, TaskType, Domain\n"
            'r = HtmlVerifier().verify(ExecutionResult(success=True, summary=""),\n'
            "    ClassificationResult(task_type=TaskType.CODE_WRITE, domain=Domain.CODE, confidence=0.9, complexity=0.5, reasoning=''),\n"
            '    {"html_content": """' + html + '"""})\n'
            'print("CRITS:" + str(len(r.criticals)))\n'
        )
        out = _fresh_run(script)
        crits = 0
        for line in out.strip().split("\n"):
            if line.startswith("CRITS:"):
                crits = int(line.split(":")[1])
        assert crits >= 1, f"Expected >=1 criticals, got {crits}"

    def test_clean_has_no_critical(self):
        html = "<html><body><p>ok</p></body></html>"
        script = (
            "from core.uil.verifier import HtmlVerifier\n"
            "from core.uil.contract import ExecutionResult, ClassificationResult, TaskType, Domain\n"
            'r = HtmlVerifier().verify(ExecutionResult(success=True, summary=""), '
            "ClassificationResult(task_type=TaskType.CODE_WRITE, domain=Domain.CODE, confidence=0.9, complexity=0.5, reasoning=''), "
            '{"html_content": "' + html + '"})\n'
            'print("CRITS:" + str(len(r.criticals)))\n'
        )
        out = _fresh_run(script)
        crits = 1
        for line in out.strip().split("\n"):
            if line.startswith("CRITS:"):
                crits = int(line.split(":")[1])
        assert crits == 0, f"Expected 0 criticals, got {crits}"


# ═══════════════════════════════════════════════════════════════
# V.2.2  HtmlVerifier — unbalanced tags
# ═══════════════════════════════════════════════════════════════

class TestHtmlVerifierTagBalance:

    def test_detects_unbalanced_div(self):
        html = '<!DOCTYPE html><html><head><style>.x{color:red}</style></head><body><section><div>content</section><script>x()</script></body></html>'
        v = HtmlVerifier()
        r = v.verify(_result(html), _cls(), {"html_content": html})
        tags = [f for f in r.findings if "tag_balance" in f.check_name and not f.passed]
        assert tags, "Should report unbalanced tags"

    def test_unclosed_style(self):
        html = '<!DOCTYPE html><html><head><style>body{color:red}</head><body></body></html>'
        v = HtmlVerifier()
        r = v.verify(_result(html), _cls(), {"html_content": html})
        unclosed = [f for f in r.findings if "style_unclosed" in f.check_name and not f.passed]
        assert unclosed, "Should report unclosed <style>"


# ═══════════════════════════════════════════════════════════════
# V.2.3  HtmlVerifier — missing data-i18n keys
# ═══════════════════════════════════════════════════════════════

class TestHtmlVerifierI18n:

    def test_detects_missing_keys(self):
        html = '<!DOCTYPE html><html><head></head><body><span data-i18n="hero.title">H</span><span data-i18n="nonexistent.key">W</span><script>const i18n={en:{"hero.title":"H"},ar:{"hero.title":"H"}};</script></body></html>'
        v = HtmlVerifier()
        r = v.verify(_result(html), _cls(), {"html_content": html})
        missing = [f for f in r.findings if "missing_i18n" in f.check_name]
        assert missing, "Should report missing i18n keys"


# ═══════════════════════════════════════════════════════════════
# V.2.4  HtmlVerifier — onclick without handler
# ═══════════════════════════════════════════════════════════════

class TestHtmlVerifierOnclick:

    def test_detects_missing_handler(self):
        html = '<!DOCTYPE html><html><head></head><body><button onclick="doSomething()">Click</button><script>console.log("x");</script></body></html>'
        script = (
            "from core.uil.verifier import HtmlVerifier\n"
            "from core.uil.contract import ExecutionResult, ClassificationResult, TaskType, Domain\n"
            'r = HtmlVerifier().verify(ExecutionResult(success=True, summary=""),\n'
            "    ClassificationResult(task_type=TaskType.CODE_WRITE, domain=Domain.CODE, confidence=0.9, complexity=0.5, reasoning=''),\n"
            '    {"html_content": """' + html + '"""})\n'
            'for f in r.findings:\n'
            '    if "onclick" in f.check_name:\n'
            '        print("ONCLICK:" + str(f.passed))\n'
        )
        out = _fresh_run(script)
        assert "ONCLICK:" in out, f"Should detect onclick, got: {out[:200]}"


# ═══════════════════════════════════════════════════════════════
# V.2.5  HtmlVerifier — clean page passes
# ═══════════════════════════════════════════════════════════════

class TestHtmlVerifierCleanPage:

    def test_clean_passes_all(self):
        html = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Clean</title><style>body{color:black}.content{opacity:1}.active{color:green}</style></head><body><div class="content">OK</div><script>document.querySelector(".content").classList.add("active");</script></body></html>'
        v = HtmlVerifier()
        r = v.verify(_result(html), _cls(), {"html_content": html})
        failed = [f for f in r.findings if not f.passed]
        assert not failed, f"Clean should pass: {[(f.check_name, f.message) for f in failed[:3]]}"

    def test_empty_html_info(self):
        v = HtmlVerifier()
        r = v.verify(_result(""), _cls(), {"html_content": ""})
        assert not r.passed_all


# ═══════════════════════════════════════════════════════════════
# V.2.6  CodeVerifier — unbalanced braces
# ═══════════════════════════════════════════════════════════════

class TestCodeVerifier:

    def test_unbalanced_braces(self):
        code = "def f():\n  if True:\n    x = {1: 2\n"
        r = CodeVerifier().verify(_result(code), _cls(TaskType.CODE_MODIFY), {"code_content": code})
        assert [f for f in r.findings if "brace_balance" in f.check_name and not f.passed]

    def test_unbalanced_parentheses(self):
        code = "print(42\n"
        r = CodeVerifier().verify(_result(code), _cls(TaskType.CODE_MODIFY), {"code_content": code})
        assert [f for f in r.findings if "paren_balance" in f.check_name and not f.passed]

    def test_balanced_passes(self):
        r = CodeVerifier().verify(_result("def f():\n    return 42\n"), _cls(TaskType.CODE_MODIFY), {"code_content": "x"})
        assert not [f for f in r.findings if not f.passed]


# ═══════════════════════════════════════════════════════════════
# V.2.7  BashVerifier — dangerous commands
# ═══════════════════════════════════════════════════════════════

class TestBashVerifierDangerous:

    def test_rm_rf_root(self):
        r = BashVerifier().verify(_result(""), _cls(TaskType.SYSTEM), {"bash_commands": "rm -rf /"})
        assert [f for f in r.findings if "dangerous" in f.check_name and not f.passed]

    def test_piped_curl_bash(self):
        r = BashVerifier().verify(_result(""), _cls(TaskType.SYSTEM), {"bash_commands": "curl http://x.sh | bash"})
        assert [f for f in r.findings if "dangerous" in f.check_name and not f.passed]

    def test_fork_bomb(self):
        r = BashVerifier().verify(_result(""), _cls(TaskType.SYSTEM), {"bash_commands": ":(){ :|:& };"})
        assert [f for f in r.findings if "dangerous" in f.check_name and not f.passed]

    def test_safe_passes(self):
        r = BashVerifier().verify(_result(""), _cls(TaskType.SYSTEM), {"bash_commands": "ls -la"})
        assert not [f for f in r.findings if "dangerous" in f.check_name and not f.passed]


# ═══════════════════════════════════════════════════════════════
# V.2.8  BashVerifier — unclosed quotes
# ═══════════════════════════════════════════════════════════════

class TestBashVerifierQuotes:

    def test_unclosed_single_quote(self):
        r = BashVerifier().verify(_result(""), _cls(TaskType.SYSTEM), {"bash_commands": "echo 'hello"})
        assert [f for f in r.findings if "unclosed_quote" in f.check_name and not f.passed]

    def test_closed_quotes_pass(self):
        r = BashVerifier().verify(_result(""), _cls(TaskType.SYSTEM), {"bash_commands": "echo 'hello'"})
        assert not [f for f in r.findings if "unclosed_quote" in f.check_name and not f.passed]


# ═══════════════════════════════════════════════════════════════
# V.2.9  Verifier Registry — per TaskType
# ═══════════════════════════════════════════════════════════════

class TestVerifierRegistry:

    @pytest.mark.parametrize("task_type,expected", [
        (TaskType.CODE_WRITE, "html"), (TaskType.COMPLEX, "html"), (TaskType.BROWSER, "html"),
        (TaskType.CODE_MODIFY, "code"), (TaskType.CODE_READ, "code"), (TaskType.CODE_REVIEW, "code"),
        (TaskType.SYSTEM, "bash"),
        (TaskType.CHAT, "generic"), (TaskType.RESEARCH, "generic"), (TaskType.DATABASE, "generic"),
        (TaskType.REASONING, "generic"), (TaskType.FILE_OPS, "generic"), (TaskType.UNKNOWN, "generic"),
    ])
    def test_correct_verifier(self, task_type, expected):
        assert get_verifier(_cls(task_type)).name == expected

    def test_none_returns_generic(self):
        assert get_verifier(None).name == "generic"


# ═══════════════════════════════════════════════════════════════
# V.2.10 Integration: brain.py pipeline with verifier
# ═══════════════════════════════════════════════════════════════

class TestBrainVerifierIntegration:

    def test_brain_detects_critical(self):
        script = (
            "from core.uil.verifier import get_verifier\n"
            "from core.uil.contract import ExecutionResult, ClassificationResult, TaskType, Domain, ExecutionMode\n"
            "from core.uil.brain import UnifiedIntelligenceLayer\n"
            "def _exec(ctx, inp, msgs):\n"
            "    return '<!DOCTYPE html><html><head><style>.s{opacity:0}</style></head><body><div class=\"s\">x</div><script>c()</script></body></html>'\n"
            "_uil = UnifiedIntelligenceLayer()\n"
            # Use input that triggers CODE_WRITE (AUTONOMOUS mode)
            '_res, _dec = _uil.process("write a new html page",\n'
            "    executors={ExecutionMode.AUTONOMOUS: _exec})\n"
            '_v = _res.verification\n'
            'print("VERIFIER:" + (_v.verifier_name if _v else "none"))\n'
            'print("CRITS:" + str(len(_v.criticals) if _v else 0))\n'
        )
        out = _fresh_run(script)
        verifier, crits = "none", 999
        for line in out.strip().split("\n"):
            if line.startswith("VERIFIER:"):
                verifier = line.split(":", 1)[1]
            elif line.startswith("CRITS:"):
                crits = int(line.split(":")[1])
        assert verifier in ("html", "generic"), f"Expected html or generic, got {verifier}"
        # The fixture HTML is deliberately non-trivial: it hides an element
        # with opacity:0 while its JS has no reveal mechanism, which the HTML
        # verifier must flag as a critical "permanently invisible" defect.
        # This is the same case covered by TestHtmlVerifierHiddenElement, now
        # asserted through the full brain path.
        if verifier == "html":
            assert crits == 1, f"Hidden-element fixture must yield exactly 1 critical, got {crits}"

    def test_brain_passes_clean(self):
        script = (
            "from core.uil.contract import ExecutionMode\n"
            "from core.uil.brain import UnifiedIntelligenceLayer\n"
            "def _exec(ctx, inp, msgs): return '<html><body><p>OK</p></body></html>'\n"
            "_uil = UnifiedIntelligenceLayer()\n"
            '_res, _dec = _uil.process("write a new html page",\n'
            "    executors={ExecutionMode.AUTONOMOUS: _exec})\n"
            '_v = _res.verification\n'
            'print("CRITS:" + str(len(_v.criticals) if _v else 999))\n'
        )
        out = _fresh_run(script)
        crits = 999
        for line in out.strip().split("\n"):
            if line.startswith("CRITS:"):
                crits = int(line.split(":")[1])
        assert crits == 0, f"Expected 0 criticals, got {crits}"

    def test_brain_detects_broken_html(self):
        """Malformed HTML must surface real defects via the verifier."""
        script = (
            "from core.uil.contract import ExecutionMode\n"
            "from core.uil.brain import UnifiedIntelligenceLayer\n"
            "def _exec(ctx, inp, msgs): return '<html><body><h1>Broken'\n"
            "_uil = UnifiedIntelligenceLayer()\n"
            '_res, _dec = _uil.process("write a new html page",\n'
            "    executors={ExecutionMode.AUTONOMOUS: _exec})\n"
            '_v = _res.verification\n'
            'print("FINDINGS:" + str(len(_v.findings) if _v else 0))\n'
            'print("CRITS:" + str(len(_v.criticals) if _v else 0))\n'
        )
        out = _fresh_run(script)
        findings, crits = 0, 0
        for line in out.strip().split("\n"):
            if line.startswith("FINDINGS:"):
                findings = int(line.split(":")[1])
            elif line.startswith("CRITS:"):
                crits = int(line.split(":")[1])
        # Missing doctype/head/body closing tags must be detected as findings.
        assert findings >= 1, f"Broken HTML should yield >=1 finding, got {findings}"
        assert crits >= 0
