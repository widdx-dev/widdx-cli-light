"""Local embedding computation — zero external API dependencies.

Uses TF-IDF vectorization with cosine similarity by default.
If sentence-transformers is available, uses it for better quality.
But the system MUST work without any external dependencies.

The embeddings are used by the classifier to match user inputs
against known task patterns without calling an LLM.
"""

from __future__ import annotations
import json
import math
import re
from collections import Counter
from pathlib import Path


class TFIDFEmbedder:
    """Pure-Python TF-IDF embedder. Zero dependencies. Fast. Deterministic."""

    def __init__(self):
        self._documents: list[str] = []
        self._df: dict[str, int] = {}  # document frequency
        self._doc_count = 0

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Tokenize text into normalized word tokens."""
        return re.findall(r'\w+', text.lower())

    def index(self, documents: list[str]):
        """Index a corpus of documents for IDF computation."""
        for doc in documents:
            self._doc_count += 1
            tokens = set(self.tokenize(doc))
            for token in tokens:
                self._df[token] = self._df.get(token, 0) + 1
        self._documents.extend(documents)

    def encode(self, text: str) -> dict[str, float]:
        """Encode text into a TF-IDF vector (sparse, as dict)."""
        tokens = self.tokenize(text)
        if not tokens:
            return {}
        tf = Counter(tokens)
        total = len(tokens)
        vec: dict[str, float] = {}
        for term, count in tf.items():
            df = self._df.get(term, 1)  # smooth: unseen terms get df=1
            vec[term] = (count / total) * math.log((self._doc_count + 1) / df)
        return vec

    @staticmethod
    def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
        """Cosine similarity between two sparse vectors."""
        if not a or not b:
            return 0.0
        keys = set(a) | set(b)
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
        norm_a = math.sqrt(sum(v ** 2 for v in a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 5,
               min_score: float = 0.05) -> list[tuple[float, str]]:
        """Search indexed documents for most similar to query.
        Returns list of (score, document) tuples.
        """
        query_vec = self.encode(query)
        if not query_vec:
            return []
        scored = []
        for doc in self._documents:
            doc_vec = self.encode(doc)
            score = self.cosine_similarity(query_vec, doc_vec)
            if score >= min_score:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]


class SentenceEmbedder:
    """Optional sentence-transformers embedder for better quality.
    Falls back to TF-IDF if the library is not available.
    """

    def __init__(self):
        self._model = None
        self._available = False
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            self._available = True
        except (ImportError, OSError):
            pass

    @property
    def available(self) -> bool:
        return self._available

    def encode(self, text: str) -> list[float] | None:
        """Encode text to dense vector. Returns None if unavailable."""
        if not self._available or not self._model:
            return None
        try:
            result = self._model.encode([text], show_progress_bar=False)
            return result[0].tolist()
        except Exception:
            return None

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two dense vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(ai * bi for ai, bi in zip(a, b))
        norm_a = math.sqrt(sum(v ** 2 for v in a))
        norm_b = math.sqrt(sum(v ** 2 for v in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class EmbeddingStore:
    """Persistent store for embeddings. Caches computed embeddings to disk
    so they survive restarts.
    """

    def __init__(self, cache_path: Path | str | None = None):
        self._cache_path = Path(cache_path) if cache_path else None
        self._cache: dict[str, dict[str, float]] = {}
        if self._cache_path and self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def get(self, key: str) -> dict[str, float] | None:
        return self._cache.get(key)

    def set(self, key: str, vector: dict[str, float]):
        self._cache[key] = vector

    def save(self):
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


# Module-level instance
_embedder: TFIDFEmbedder | None = None
_sentence_embedder: SentenceEmbedder | None = None


def get_embedder() -> TFIDFEmbedder:
    """Get or create the global TF-IDF embedder."""
    global _embedder
    if _embedder is None:
        _embedder = TFIDFEmbedder()
    return _embedder


def get_sentence_embedder() -> SentenceEmbedder:
    """Get or create the optional sentence embedder."""
    global _sentence_embedder
    if _sentence_embedder is None:
        _sentence_embedder = SentenceEmbedder()
    return _sentence_embedder


def embed_text(text: str) -> dict[str, float]:
    """Embed text into a vector. Uses TF-IDF (always available)."""
    return get_embedder().encode(text)


def similarity(a: str, b: str) -> float:
    """Compute similarity between two text strings. 0.0 to 1.0."""
    emb = get_embedder()
    va = emb.encode(a)
    vb = emb.encode(b)
    return TFIDFEmbedder.cosine_similarity(va, vb)
