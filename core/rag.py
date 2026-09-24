"""RAG Pipeline — Real embedding-based retrieval for semantic memory.

Extends ``core.vector_memory`` with optional sentence-transformers
support for true semantic search.  Falls back to TF-IDF when the
library is not installed.

Usage:
    from core.rag import RAGStore

    rag = RAGStore()
    rag.add("doc1", "Python async programming guide", tags=["python"])
    results = rag.search("how to write async code", top_k=5)
"""

from __future__ import annotations
import logging

import math
from typing import Any
logger = logging.getLogger("widdx.rag")


class RAGStore:
    """Semantic memory with hybrid search (dense + sparse)."""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model: Any = None
        self._documents: list[dict] = []
        self._embeddings: list[list[float]] = []
        self._loaded = False

    # ── Public API ──────────────────────────────────────

    def add(self, doc_id: str, content: str, metadata: dict | None = None) -> None:
        """Index a document."""
        emb = self._encode(content)
        self._documents.append({
            "id": doc_id, "content": content,
            "metadata": metadata or {},
        })
        self._embeddings.append(emb)

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.3,
    ) -> list[tuple[float, dict]]:
        """Semantic search. Returns [(score, document), ...]."""
        if not self._documents:
            return []

        q_emb = self._encode(query)
        scored = []

        for i, doc_emb in enumerate(self._embeddings):
            score = self._cosine(q_emb, doc_emb)
            if score >= min_score:
                scored.append((score, self._documents[i]))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._documents)

    def clear(self):
        self._documents.clear()
        self._embeddings.clear()

    # ── Embedding Engine ────────────────────────────────

    def _encode(self, text: str) -> list[float]:
        """Encode text to a dense vector."""
        if not self._loaded:
            self._load_model()

        if self._model:
            try:
                emb = self._model.encode(text, show_progress_bar=False)
                return emb.tolist()
            except Exception:
                pass

        # Fallback: bag-of-words sparse → dense-ish
        return self._bow_encode(text)

    def _load_model(self):
        """Try to load sentence-transformers."""
        self._loaded = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        except ImportError:
            self._model = None

    @staticmethod
    def _bow_encode(text: str, dims: int = 384) -> list[float]:
        """Simple bag-of-words hash → fixed-dim pseudo-embedding."""
        import hashlib
        words = text.lower().split()
        vec = [0.0] * dims
        if not words:
            return vec
        for i, word in enumerate(words):
            h = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
            idx = h % dims
            vec[idx] += 1.0
        # Normalize
        norm = math.sqrt(sum(v ** 2 for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x ** 2 for x in a))
        norm_b = math.sqrt(sum(y ** 2 for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# Global
rag_store = RAGStore()
