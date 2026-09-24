"""Tests for L3: Linter Auto-Fix (core/linter.py)."""
from core.linter import LinterRunner, LintResult, LintIssue


def test_linter_creates():
    runner = LinterRunner()
    assert runner is not None


def test_detect_language_python():
    from pathlib import Path
    runner = LinterRunner()
    lang = runner.detect_language(Path("test.py"))
    assert lang == "python"


def test_detect_language_js():
    from pathlib import Path
    runner = LinterRunner()
    lang = runner.detect_language(Path("app.js"))
    assert lang == "javascript"


def test_detect_language_unknown():
    from pathlib import Path
    runner = LinterRunner()
    lang = runner.detect_language(Path("data.xyz"))
    assert lang == "unknown"


def test_lint_python_file():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test.py"
        f.write_text("def hello():\n    print('hi')\n")
        runner = LinterRunner()
        result = runner.check(f, auto_fix=False)
        assert result.language == "python"
        # May have errors or not depending on available linters


def test_lint_missing_file():
    runner = LinterRunner()
    result = runner.check("/nonexistent/file.py")
    assert result.language == "missing"


def test_lint_result_format():
    result = LintResult(file_path="x.py", language="python")
    result.errors.append(LintIssue(line=5, message="unused import", rule="F401"))
    formatted = result.format_for_agent()
    assert "ERROR" in formatted
    assert "F401" in formatted


def test_lint_result_ok():
    result = LintResult(file_path="x.py", language="python")
    assert result.ok


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
