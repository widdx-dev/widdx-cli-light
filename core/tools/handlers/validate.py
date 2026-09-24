"""Validation tools — syntax checking for multiple languages."""

import json as _json
import logging
import subprocess
from html.parser import HTMLParser
from pathlib import Path

logger = logging.getLogger("widdx.tools.validate")


class HTMLTagValidator(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img",
                 "input", "link", "meta", "param", "source", "track", "wbr"}
    OPTIONAL_CLOSING_TAGS = {"li", "dt", "dd", "p", "rt", "rp", "optgroup",
                              "option", "thead", "tbody", "tfoot", "tr", "td", "th"}

    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID_TAGS:
            return
        self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{tag}>")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                unclosed = self.stack.pop()
                if unclosed not in self.OPTIONAL_CLOSING_TAGS:
                    self.errors.append(f"Unclosed <{unclosed}> before </{tag}>")
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
            return
        self.errors.append(f"Unexpected closing tag </{tag}>")

    def close(self):
        super().close()
        while self.stack:
            unclosed = self.stack.pop()
            if unclosed not in self.OPTIONAL_CLOSING_TAGS:
                self.errors.append(f"Unclosed <{unclosed}>")


def _validate(file_path: str) -> str:
    p = Path(file_path).resolve()
    if not p.exists():
        return f"File not found: {file_path}"
    ext = p.suffix.lower()
    content = p.read_text("utf-8", errors="replace")

    # PHP
    if ext == ".php":
        try:
            r = subprocess.run(["php", "-l", str(p)], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return f"✅ PHP syntax: No errors in {file_path}"
            return f"❌ PHP syntax error:\n{r.stderr.strip()[:500]}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Python
    if ext == ".py":
        try:
            import py_compile
            py_compile.compile(str(p), doraise=True)
            return f"✅ Python syntax: No errors in {file_path}"
        except py_compile.PyCompileError as e:
            return f"❌ Python syntax error:\n{e}"
        except Exception:
            logger.debug("Exception suppressed (line 81)")

    # JavaScript
    if ext in (".js", ".mjs", ".cjs"):
        try:
            r = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return f"✅ JavaScript syntax: No errors in {file_path}"
            return f"❌ JavaScript syntax error:\n{r.stderr.strip()[:500]}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # JSON
    if ext == ".json":
        try:
            _json.loads(content)
            return f"✅ JSON: Valid in {file_path}"
        except _json.JSONDecodeError as e:
            return f"❌ JSON error:\n{e}"

    # TypeScript
    if ext in (".ts", ".tsx"):
        try:
            r = subprocess.run(["npx", "--yes", "typescript", "--noEmit", "--strict", str(p)],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return f"✅ TypeScript: No errors in {file_path}"
            return f"❌ TypeScript error:\n{(r.stderr or r.stdout).strip()[:500]}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Ruby
    if ext == ".rb":
        try:
            r = subprocess.run(["ruby", "-c", str(p)], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return f"✅ Ruby syntax: No errors in {file_path}"
            return f"❌ Ruby syntax error:\n{r.stderr.strip()[:500]}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Go
    if ext == ".go":
        try:
            r = subprocess.run(["gofmt", "-e", str(p)], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return f"✅ Go syntax: No errors in {file_path}"
            return f"❌ Go syntax error:\n{(r.stderr or r.stdout).strip()[:500]}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # C
    if ext in (".c", ".h"):
        for compiler in ("gcc", "clang"):
            try:
                r = subprocess.run([compiler, "-fsyntax-only", "-Wall", "-Werror", str(p)],
                                   capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    return f"✅ C syntax: No errors in {file_path} ({compiler})"
                return f"❌ C syntax error ({compiler}):\n{(r.stderr or r.stdout).strip()[:500]}"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    # C++
    if ext in (".cpp", ".cc", ".cxx", ".hpp"):
        for compiler in ("g++", "clang++"):
            try:
                r = subprocess.run([compiler, "-fsyntax-only", "-Wall", "-Werror", "-std=c++17", str(p)],
                                   capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    return f"✅ C++ syntax: No errors in {file_path} ({compiler})"
                return f"❌ C++ syntax error ({compiler}):\n{(r.stderr or r.stdout).strip()[:500]}"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    # C#
    if ext == ".cs":
        for runner, args in [
            ("csc", ["csc", "-nologo", "-target:exe", str(p)]),
            ("mcs", ["mcs", "-target:exe", str(p)]),
        ]:
            try:
                r = subprocess.run(args, capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    return f"✅ C# syntax: No errors in {file_path} ({runner})"
                return f"❌ C# syntax error ({runner}):\n{(r.stderr or r.stdout).strip()[:500]}"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    # Dart
    if ext == ".dart":
        try:
            r = subprocess.run(["dart", "analyze", "--fatal-infos", str(p)],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return f"✅ Dart: No errors in {file_path}"
            return f"❌ Dart issue:\n{(r.stderr or r.stdout).strip()[:500]}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # CSS
    if ext == ".css":
        try:
            import cssutils
            cssutils.parseString(content)
            return f"✅ CSS: Valid in {file_path}"
        except ImportError:
            if content.count("{") != content.count("}"):
                return f"⚠️  CSS: Brace mismatch ({content.count('{')} vs {content.count('}')})"
            return f"✅ CSS: Brace balance OK in {file_path}"
        except Exception as e:
            return f"❌ CSS error:\n{e}"

    # YAML
    if ext in (".yaml", ".yml"):
        try:
            import yaml
            yaml.safe_load(content)
            return f"✅ YAML: Valid in {file_path}"
        except ImportError:
            pass
        except Exception as e:
            return f"❌ YAML error:\n{e}"

    # HTML
    if ext in (".html", ".htm"):
        parser = HTMLTagValidator()
        try:
            parser.feed(content)
            parser.close()
        except Exception as e:
            return f"❌ HTML parser error in {file_path}: {e}"
        if parser.errors:
            return f"❌ HTML validation errors in {file_path}:\n" + "\n".join(parser.errors[:10])
        return f"✅ HTML: No structure errors in {file_path}"

    # Generic bracket check
    def _count_no_strings(text, char):
        count = 0
        in_single = in_double = False
        i = 0
        while i < len(text):
            if text[i] == "'" and not in_double and (i == 0 or text[i - 1] != '\\\\'):
                in_single = not in_single
            elif text[i] == '"' and not in_single and (i == 0 or text[i - 1] != '\\\\'):
                in_double = not in_double
            elif not in_single and not in_double and text[i] == char:
                count += 1
            i += 1
        return count

    if content.strip():
        issues = []
        for name, op, cl in [("curly braces {}", "{", "}"),
                              ("square brackets []", "[", "]"),
                              ("parentheses ()", "(", ")")]:
            co = _count_no_strings(content, op)
            cc = _count_no_strings(content, cl)
            if co != cc:
                issues.append(f"{name}: {co} opening vs {cc} closing")
        if issues:
            return f"⚠️  Possible issues in {file_path}:\n" + "\n".join(issues)
    lines = content.splitlines()
    return f"ℹ️  {file_path}: {len(lines)} lines, {len(content)} bytes (no validator available)"


def _project_validate(project_dir: str) -> str:
    p = Path(project_dir).resolve()
    if not p.is_dir():
        return f"Project directory not found: {project_dir}"
    from ..safety import is_safe_path, get_safe_dir
    if not is_safe_path(p):
        return f"Sandbox: project_validate denied — {project_dir} not inside {get_safe_dir()}"

    results = []

    # Python
    if (p / "pyproject.toml").exists() or (p / "setup.py").exists() or (p / "requirements.txt").exists():
        results.append("🐍 Python project detected")
        try:
            r = subprocess.run(["python", "-m", "pytest", str(p), "-v", "--tb=short"],
                               capture_output=True, text=True, timeout=60, cwd=str(p))
            if r.returncode == 0:
                results.append("✅ pytest passed")
            else:
                results.append(f"❌ pytest failed:\n{(r.stdout or r.stderr)[:1000]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                r = subprocess.run(["python", "-m", "unittest", "discover", "-s", str(p), "-p", "test_*.py", "-v"],
                                   capture_output=True, text=True, timeout=60, cwd=str(p))
                if r.returncode == 0:
                    results.append("✅ unittest passed")
                else:
                    results.append(f"❌ unittest failed:\n{(r.stdout or r.stderr)[:1000]}")
            except Exception as e:
                results.append(f"⚠️  No Python tests found: {e}")

    # Node.js
    if (p / "package.json").exists():
        results.append("📦 Node.js project detected")
        try:
            r = subprocess.run(["npm", "test"], capture_output=True, text=True, timeout=120, cwd=str(p))
            if r.returncode == 0:
                results.append("✅ npm test passed")
            else:
                results.append(f"❌ npm test failed:\n{(r.stdout or r.stderr)[:1000]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            results.append("⚠️  npm test timed out or not available")

    # Rust
    if (p / "Cargo.toml").exists():
        results.append("🦀 Rust project detected")
        try:
            r = subprocess.run(["cargo", "test"], capture_output=True, text=True, timeout=120, cwd=str(p))
            if r.returncode == 0:
                results.append("✅ cargo test passed")
            else:
                results.append(f"❌ cargo test failed:\n{(r.stdout or r.stderr)[:1000]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            results.append("⚠️  cargo test timed out or not available")

    # Go
    if any((p / f).exists() for f in ["go.mod", "go.sum"]):
        results.append("🐹 Go project detected")
        try:
            r = subprocess.run(["go", "test", "./..."], capture_output=True, text=True, timeout=120, cwd=str(p))
            if r.returncode == 0:
                results.append("✅ go test passed")
            else:
                results.append(f"❌ go test failed:\n{(r.stdout or r.stderr)[:1000]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            results.append("⚠️  go test timed out or not available")

    # Java
    if (p / "pom.xml").exists():
        results.append("☕ Maven project detected")
        try:
            r = subprocess.run(["mvn", "test"], capture_output=True, text=True, timeout=180, cwd=str(p))
            if r.returncode == 0:
                results.append("✅ mvn test passed")
            else:
                results.append(f"❌ mvn test failed:\n{(r.stdout or r.stderr)[:1000]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            results.append("⚠️  mvn test timed out or not available")
    if (p / "build.gradle").exists() or (p / "build.gradle.kts").exists():
        results.append("☕ Gradle project detected")
        try:
            r = subprocess.run(["gradle", "test"], capture_output=True, text=True, timeout=180, cwd=str(p))
            if r.returncode == 0:
                results.append("✅ gradle test passed")
            else:
                results.append(f"❌ gradle test failed:\n{(r.stdout or r.stderr)[:1000]}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            results.append("⚠️  gradle test timed out or not available")

    if not results:
        results.append("ℹ️  No recognized project type (Python, Node, Rust, Go, Java) found")
    return "\n".join(results)
