"""Smart rename — rename symbols across files using AST analysis."""

import ast
import re
import logging
from pathlib import Path

from ..safety import is_safe_path, get_safe_dir

logger = logging.getLogger("widdx.tools.rename")


def _find_python_usages(filepath: Path, symbol: str) -> list[tuple[int, str]]:
    """Find usages of a symbol in a Python file using AST."""
    usages = []
    try:
        text = filepath.read_text("utf-8", errors="ignore")
        tree = ast.parse(text, filename=str(filepath))

        symbol_lower = symbol.lower()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == symbol:
                    usages.append((node.lineno, f"def {node.name}"))
                elif node.name.lower() == symbol_lower:
                    usages.append((node.lineno, f"def {node.name} (case-diff)"))

            elif isinstance(node, ast.ClassDef):
                if node.name == symbol:
                    usages.append((node.lineno, f"class {node.name}"))

            elif isinstance(node, ast.Name):
                if node.id == symbol:
                    usages.append((node.lineno, f"name: {node.id}"))

            elif isinstance(node, ast.Attribute):
                if node.attr == symbol:
                    usages.append((node.lineno, f"attr: {node.attr}"))

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == symbol:
                    usages.append((node.lineno, f"call: {node.func.id}"))

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == symbol:
                        usages.append((node.lineno, f"assign: {target.id}"))

    except SyntaxError:
        pass
    except Exception as e:
        logger.debug("rename: AST error in %s: %s", filepath.name, e)

    return usages


def _find_text_usages(filepath: Path, symbol: str) -> list[tuple[int, str]]:
    """Find usages of a symbol using regex (fallback for non-Python)."""
    usages = []
    try:
        text = filepath.read_text("utf-8", errors="ignore")
        pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                usages.append((i, line.strip()[:120]))
    except Exception as e:
        logger.debug("rename: text search error in %s: %s", filepath.name, e)
    return usages


def _rename_in_file(filepath: Path, symbol: str, new_name: str) -> tuple[int, str]:
    """Rename a symbol in a file. Returns (count, error_or_diff)."""
    try:
        text = filepath.read_text("utf-8", errors="ignore")
        if filepath.suffix == ".py":
            usages = _find_python_usages(filepath, symbol)
            if not usages:
                return 0, ""
            pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
        else:
            usages = _find_text_usages(filepath, symbol)
            if not usages:
                return 0, ""
            pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')

        new_text, count = pattern.subn(new_name, text)
        if count == 0:
            return 0, ""

        lines = new_text.splitlines()
        context_lines = []
        for lineno, context in usages[:5]:
            start = max(0, lineno - 2)
            end = min(len(lines), lineno + 1)
            ctx = "\n".join(
                f"  {j + 1}: {lines[j][:150]}" for j in range(start, end)
            )
            context_lines.append(ctx)

        diff = f"  {count} change(s) in {filepath.name}:\n" + "\n".join(context_lines)
        filepath.write_text(new_text, encoding="utf-8")
        return count, diff
    except Exception as e:
        return 0, f"  Error: {e}"


def _rename_symbol(symbol: str, new_name: str, path: str | None = None,
                   include: str | None = None, preview: bool = True) -> str:
    """Rename a symbol across files using AST analysis."""
    root = Path(path) if path else Path(".")
    if not is_safe_path(root):
        return f"Sandbox: rename in {path} denied — not inside {get_safe_dir()}"

    files_iter = root.rglob(include) if include else root.rglob("*")
    candidates = []

    for filepath in files_iter:
        if not filepath.is_file() or filepath.stat().st_size > 512000:
            continue
        if filepath.suffix in (".pyc", ".pyo", ".so", ".dll", ".dylib", ".bin"):
            continue
        if filepath.suffix == ".py":
            usages = _find_python_usages(filepath, symbol)
        else:
            usages = _find_text_usages(filepath, symbol)
        if usages:
            candidates.append((filepath, usages))

    if not candidates:
        return f"Symbol '{symbol}' not found in any files"

    buf = [f"🔍 Found '{symbol}' in {len(candidates)} file(s):", ""]
    total_count = 0

    for filepath, usages in candidates:
        rel = filepath.relative_to(root)
        buf.append(f"  📄 {rel}")
        for lineno, context in usages[:5]:
            buf.append(f"     L{lineno}: {context[:120]}")
        if len(usages) > 5:
            buf.append(f"     ... and {len(usages) - 5} more usages")
        buf.append("")

    if preview:
        return "\n".join(buf)

    for filepath, usages in candidates:
        count, diff = _rename_in_file(filepath, symbol, new_name)
        total_count += count

    buf.append(f"✅ Renamed '{symbol}' -> '{new_name}' ({total_count} change(s) across {len(candidates)} file(s))")
    return "\n".join(buf)
