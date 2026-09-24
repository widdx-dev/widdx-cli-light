"""Semantic search with embeddings — uses LLM provider API for real vector search."""

import logging
import math
from pathlib import Path

from ..safety import is_safe_path

logger = logging.getLogger("widdx.tools.embeddings")


def _get_embedding(text: str) -> list[float] | None:
    """Get an embedding vector.

    Uses the Ollama embeddings endpoint when a local Ollama is reachable.
    The previous implementation called ``provider.get_embedding(...)``, which
    no provider implements — it always raised and silently degraded to None,
    disabling every embedding-backed tool. Returns None when no embedder is
    available so callers can fall back to lexical scoring.
    """
    try:
        from core.vector_memory import OllamaEmbeddingEngine

        embedder = OllamaEmbeddingEngine()
        if embedder.available:
            return embedder.encode(text)
    except Exception as e:
        logger.debug("Embedding backend unavailable: %s", e)
    return None


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0
    return dot / (na * nb)


def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Split text into overlapping chunks for embedding."""
    chunks: list[str] = []
    lines = text.splitlines()
    current: list[str] = []
    current_len = 0
    for line in lines:
        if current_len + len(line) > max_chars and current:
            chunks.append("\n".join(current))
            current = current[-2:]
            current_len = sum(len(part) for part in current)
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("\n".join(current))
    return chunks or [text]


def _tfidf_search(query: str, root: Path, include: str | None, top_k: int) -> list[tuple[str, float, str]]:
    """Fallback TF-IDF search when embeddings are unavailable."""
    from .semantic_search import _build_index, _score
    index = _build_index(root, include)
    results = _score(query, index, root)
    out = []
    for file_str, score in results[:top_k]:
        try:
            text = Path(file_str).read_text("utf-8", errors="ignore")
        except Exception:
            text = ""
        out.append((file_str, score, text[:200]))
    return out


def _embedding_search(query: str, root: Path, include: str | None, top_k: int) -> list[tuple[str, float, str]]:
    """Search using real embeddings from the LLM provider."""
    query_emb = _get_embedding(query)
    if query_emb is None:
        raise ValueError("Embeddings not available")

    files_iter = root.rglob(include) if include else root.rglob("*")
    scored_chunks = []

    for filepath in files_iter:
        if not filepath.is_file() or filepath.stat().st_size > 512000:
            continue
        try:
            text = filepath.read_text("utf-8", errors="ignore")
        except Exception:
            continue
        if not text.strip():
            continue

        chunks = _chunk_text(text)
        for chunk in chunks:
            chunk_emb = _get_embedding(chunk)
            if chunk_emb:
                sim = _cosine_sim(query_emb, chunk_emb)
                if sim > 0.3:
                    rel = str(filepath.relative_to(root))
                    scored_chunks.append((rel, sim, chunk[:200]))

    scored_chunks.sort(key=lambda x: -x[1])
    return scored_chunks[:top_k]


def _semantic_embedding(query: str, path: str | None = None,
                         include: str | None = None, top_k: int = 10) -> str:
    """Semantic search using embeddings (with TF-IDF fallback)."""
    root = Path(path) if path else Path(".")
    if not is_safe_path(root):
        return f"Sandbox: search in {path} denied"

    try:
        results = _embedding_search(query, root, include, top_k)
        method = "embeddings (API)"
    except (ValueError, Exception) as e:
        logger.info("Embedding search unavailable, falling back to TF-IDF: %s", e)
        results = _tfidf_search(query, root, include, top_k)
        method = "TF-IDF (fallback)"

    if not results:
        return f"No results for '{query}'"

    buf = [f"🔎 Semantic search for '{query}' — {len(results)} result(s) [{method}]", ""]
    for rel, score, snippet in results:
        buf.append(f"  📄 {rel}  (score: {score:.3f})")
        if snippet:
            buf.append(f"     {snippet[:150]}")
        buf.append("")

    return "\n".join(buf)
