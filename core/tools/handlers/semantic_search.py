"""Semantic search — code search by meaning using TF-IDF and AST analysis."""

import ast
import math
import re
import logging
from typing import Any
from pathlib import Path
from collections import Counter

from ..safety import is_safe_path, get_safe_dir

logger = logging.getLogger("widdx.tools.semantic_search")

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "this", "that", "these", "those", "it", "its", "and", "but", "or",
    "if", "while", "because", "until", "about", "define", "function",
    "class", "return", "import", "from", "def", "self", "None", "True",
    "False", "pass", "raise", "try", "except", "finally", "with", "as",
    "yield", "lambda", "async", "await",
}


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r"[a-zA-Z_]\w*", text)
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _extract_keywords_from_file(filepath: Path) -> list[str]:
    tokens = []
    try:
        text = filepath.read_text("utf-8", errors="ignore")
        tokens.extend(_tokenize(text))

        if filepath.suffix == ".py":
            try:
                tree = ast.parse(text, filename=str(filepath))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        tokens.append(f"func:{node.name}")
                        for d in node.decorator_list:
                            if isinstance(d, ast.Name):
                                tokens.append(f"decorator:{d.id}")
                    elif isinstance(node, ast.ClassDef):
                        tokens.append(f"class:{node.name}")
                        for base in node.bases:
                            if isinstance(base, ast.Name):
                                tokens.append(f"base:{base.id}")
                    elif isinstance(node, ast.Name):
                        tokens.append(f"var:{node.id}")
            except SyntaxError:
                pass

        docstring_matches = re.findall(r'"""(.*?)"""', text, re.DOTALL)
        for ds in docstring_matches:
            tokens.extend(_tokenize(ds))
        comment_matches = re.findall(r'#\s*(.*)', text)
        for c in comment_matches:
            tokens.extend(_tokenize(c))
    except Exception as e:
        logger.debug("semantic: skip %s: %s", filepath.name, e)

    return tokens


def _build_index(root: Path, include: str | None = None) -> dict[str, Any]:
    doc_freq: dict[str, int] = {}
    term_freq: dict[str, dict] = {}
    doc_tokens: dict[Path, list[str]] = {}
    doc_total: dict[Path, int] = {}

    files_iter = root.rglob(include) if include else root.rglob("*")
    for filepath in files_iter:
        if not filepath.is_file() or filepath.stat().st_size > 512000:
            continue
        tokens = _extract_keywords_from_file(filepath)
        if not tokens:
            continue
        doc_tokens[filepath] = tokens
        doc_total[filepath] = len(tokens)
        seen = set()
        counter = Counter(tokens)
        for token, count in counter.items():
            if token not in term_freq:
                term_freq[token] = {}
            term_freq[token][str(filepath)] = count
            if token not in seen:
                doc_freq[token] = doc_freq.get(token, 0) + 1
                seen.add(token)

    return {
        "doc_tokens": doc_tokens,
        "doc_total": doc_total,
        "term_freq": term_freq,
        "doc_freq": doc_freq,
        "num_docs": len(doc_tokens),
    }


def _score(query: str, index: dict, root: Path) -> list[tuple[str, float]]:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    doc_tokens = index["doc_tokens"]
    index["doc_total"]
    term_freq = index["term_freq"]
    doc_freq = index["doc_freq"]
    num_docs = index["num_docs"]

    scores: dict[str, float] = {}
    for filepath in doc_tokens:
        score = 0.0
        file_str = str(filepath)
        for qt in q_tokens:
            tf = term_freq.get(qt, {}).get(file_str, 0)
            if tf == 0:
                for term, tfs in term_freq.items():
                    if qt in term or term in qt:
                        tf = tfs.get(file_str, 0) * 0.5
                        if tf > 0:
                            break
            if tf > 0:
                df = doc_freq.get(qt, 1)
                idf = math.log((num_docs + 1) / (df + 1)) + 1
                score += (1 + math.log(tf)) * idf

        filepath_lower = str(filepath.relative_to(root)).lower()
        if any(qt in filepath_lower for qt in q_tokens):
            score *= 1.5

        bonus = 0.0
        for qt in q_tokens:
            for term in term_freq:
                if qt in term and term.startswith(("func:", "class:")):
                    if term_freq[term].get(file_str, 0) > 0:
                        bonus += 2.0
        score += bonus

        if score > 0:
            scores[file_str] = score

    return sorted(scores.items(), key=lambda x: -x[1])


def _semantic_search(query: str, path: str | None = None,
                     include: str | None = None, top_k: int = 10) -> str:
    """Semantic code search using TF-IDF and AST analysis."""
    root = Path(path) if path else Path(".")
    if not is_safe_path(root):
        return f"Sandbox: search in {path} denied — not inside {get_safe_dir()}"

    index = _build_index(root, include)
    if index["num_docs"] == 0:
        return "No indexable files found"

    results = _score(query, index, root)
    results = results[:top_k]

    if not results:
        return f"No semantic results for '{query}'"

    buf = [f"🔎 Semantic search for '{query}' — {len(results)} result(s):", ""]
    for file_str, score in results:
        filepath = Path(file_str)
        rel = filepath.relative_to(root)
        try:
            text = filepath.read_text("utf-8", errors="ignore")
            lines = text.splitlines()
        except Exception:
            lines = []
        q_tokens = _tokenize(query)
        snippet_lines = []
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(qt in line_lower for qt in q_tokens):
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                snippet = "\n".join(
                    f"  {j + 1}: {lines[j].strip()[:150]}"
                    for j in range(start, end)
                )
                snippet_lines.append(snippet)

        buf.append(f"  📄 {rel}  (score: {score:.2f})")
        for s in snippet_lines[:3]:
            buf.append(s)
        if len(snippet_lines) > 3:
            buf.append(f"     ... and {len(snippet_lines) - 3} more matches")
        buf.append("")

    return "\n".join(buf)
