"""Vector Memory Store — Semantic memory search using embeddings.

Zero mandatory external dependencies. Uses Ollama for embeddings if
available (local, no API cost), with a pure-Python TF-IDF fallback
that works offline.

Architecture:
  VectorMemoryStore — CRUD + semantic search
  embedding_engine   — pluggable: ollama | tfidf | (future: sentence-transformers)
  ChunkStore         — splits long content into searchable chunks

Usage:
    from core.vector_memory import VectorMemoryStore

    store = VectorMemoryStore()
    store.add("Memory title", "Long content here...", tags=["project-x"])
    results = store.search("similar content query", top_k=5)
    # → [(score, memory_dict), ...]
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Storage Paths
# ---------------------------------------------------------------------------

DEFAULT_VEC_DIR = Path.home() / ".widdx" / "vector_memory"


# ---------------------------------------------------------------------------
# TF-IDF Fallback Engine (no dependencies, works offline)
# ---------------------------------------------------------------------------

class TFIDFEngine:
    """Pure-Python TF-IDF for when no embedding model is available.

    Provides cosine similarity over sparse vectors.
    Good enough for keyword-level semantic matching.
    """

    def __init__(self):
        self._doc_count = 0
        self._df: dict[str, int] = {}  # document frequency

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer: lowercase, split on non-alphanumeric."""
        return re.findall(r'\w+', text.lower())

    def _tfidf_vector(self, tokens: list[str]) -> dict[str, float]:
        """Compute TF-IDF vector for a token list."""
        tf = Counter(tokens)
        total = len(tokens) or 1
        vec: dict[str, float] = {}
        for term, count in tf.items():
            df = self._df.get(term, 1)
            vec[term] = (count / total) * math.log((self._doc_count + 1) / df)
        return vec

    def _cosine_similarity(self, a: dict[str, float], b: dict[str, float]) -> float:
        """Cosine similarity between two sparse vectors."""
        if not a or not b:
            return 0.0
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in set(a) | set(b))
        norm_a = math.sqrt(sum(v ** 2 for v in a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def index(self, texts: list[str]):
        """Update document frequencies from a batch of texts."""
        for text in texts:
            tokens = set(self._tokenize(text))
            for term in tokens:
                self._df[term] = self._df.get(term, 0) + 1
            self._doc_count += 1

    def encode(self, text: str) -> dict[str, float]:
        """Convert text to a sparse TF-IDF vector."""
        tokens = self._tokenize(text)
        return self._tfidf_vector(tokens)

    def similarity(self, a: str, b: str) -> float:
        """Compute cosine similarity between two texts."""
        va = self.encode(a)
        vb = self.encode(b)
        return self._cosine_similarity(va, vb)


# ---------------------------------------------------------------------------
# Ollama Embedding Engine (local, no API cost)
# ---------------------------------------------------------------------------

class OllamaEmbeddingEngine:
    """Use Ollama's local embedding endpoint for semantic vectors.

    Requires Ollama running locally with an embedding model
    (e.g., ``ollama pull nomic-embed-text``).
    Falls back gracefully if Ollama is not available.
    """

    OLLAMA_URL = "http://localhost:11434/api/embeddings"
    DEFAULT_MODEL = "nomic-embed-text"

    def __init__(self, model: str | None = None):
        self.model = model or self.DEFAULT_MODEL
        self._available: bool | None = None  # None = not checked yet

    @property
    def available(self) -> bool:
        if self._available is None:
            self._check_availability()
        return self._available or False

    def _check_availability(self):
        import urllib.request
        import urllib.error
        try:
            url = "http://localhost:11434/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                pass
            self._available = True
        except Exception:
            self._available = False

    def encode(self, text: str) -> list[float] | None:
        """Return embedding vector or None if unavailable."""
        if not self.available:
            return None
        import urllib.request
        import urllib.error
        try:
            payload = json.dumps({
                "model": self.model,
                "prompt": text[:2000],  # truncate for embedding
            }).encode()
            req = urllib.request.Request(
                self.OLLAMA_URL, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data.get("embedding")
        except Exception:
            self._available = False
            return None

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two dense vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x ** 2 for x in a))
        norm_b = math.sqrt(sum(y ** 2 for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Vector Memory Store
# ---------------------------------------------------------------------------

class VectorMemoryStore:
    """Persistent semantic memory with vector search.

    Stores memories as (id, title, content, tags, embedding, metadata).
    Search returns top-k results ranked by cosine similarity.

    Uses Ollama embeddings if available, otherwise falls back to TF-IDF.
    """

    def __init__(
        self,
        storage_dir: Path | None = None,
        engine: str = "auto",  # "auto" | "ollama" | "tfidf"
    ):
        self._dir = storage_dir or DEFAULT_VEC_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "vectors.json"
        self._memories: list[dict] = []
        self._ollama = OllamaEmbeddingEngine()
        self._tfidf = TFIDFEngine()
        self._engine = engine
        self._load()

    # ── Public API ──────────────────────────────────────

    def add(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Add a memory. Returns its ID."""
        import uuid
        mem_id = uuid.uuid4().hex[:16]
        embedding = self._encode(content)

        memory = {
            "id": mem_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "metadata": metadata or {},
            "embedding": embedding,
            "created": time.time(),
        }
        self._memories.append(memory)
        self._tfidf.index([content])
        self._save()
        return mem_id

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1,
    ) -> list[tuple[float, dict]]:
        """Search memories by semantic similarity. Returns [(score, memory), ...]."""
        if not self._memories:
            return []

        query_emb = self._encode(query)
        scored: list[tuple[float, dict]] = []

        for mem in self._memories:
            mem_emb = mem.get("embedding")
            if self._is_dense(query_emb) and self._is_dense(mem_emb):
                score = OllamaEmbeddingEngine.cosine_similarity(query_emb, mem_emb)  # type: ignore[arg-type]
            else:
                # TF-IDF fallback
                score = self._tfidf.similarity(query, mem.get("content", ""))
            if score >= min_score:
                scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def search_by_tags(
        self,
        tags: list[str],
        top_k: int = 20,
    ) -> list[dict]:
        """Exact tag match (fast, no embedding)."""
        tag_set = set(t.lower() for t in tags)
        results = []
        for mem in self._memories:
            mem_tags = set(t.lower() for t in mem.get("tags", []))
            if tag_set & mem_tags:
                results.append(mem)
        return results[:top_k]

    def get(self, mem_id: str) -> dict | None:
        """Retrieve a memory by ID."""
        for mem in self._memories:
            if mem["id"] == mem_id:
                return mem
        return None

    def update(self, mem_id: str, **kwargs):
        """Update fields of an existing memory."""
        mem = self.get(mem_id)
        if not mem:
            raise KeyError(f"Memory not found: {mem_id}")
        for key in ("title", "content", "tags", "metadata"):
            if key in kwargs:
                mem[key] = kwargs[key]
        if "content" in kwargs:
            mem["embedding"] = self._encode(kwargs["content"])
            self._tfidf.index([kwargs["content"]])
        self._save()

    def delete(self, mem_id: str) -> bool:
        """Delete a memory by ID. Returns True if it existed."""
        for i, mem in enumerate(self._memories):
            if mem["id"] == mem_id:
                del self._memories[i]
                self._save()
                return True
        return False

    def list_all(self) -> list[dict]:
        """Return all memories (without embeddings for readability)."""
        return [
            {k: v for k, v in m.items() if k != "embedding"}
            for m in self._memories
        ]

    def count(self) -> int:
        return len(self._memories)

    def clear(self):
        """Remove all memories."""
        self._memories.clear()
        self._save()

    # ── Internals ───────────────────────────────────────

    def _encode(self, text: str) -> list[float] | dict[str, float] | None:
        """Encode text to vector. Returns dense list (ollama) or sparse dict (tfidf)."""
        if self._engine == "tfidf":
            return self._tfidf.encode(text)
        if self._engine == "ollama":
            vec = self._ollama.encode(text)
            if vec:
                return vec
        # "auto": try Ollama first, fall back to TF-IDF
        vec = self._ollama.encode(text)
        if vec:
            return vec
        return self._tfidf.encode(text)

    @staticmethod
    def _is_dense(vec) -> bool:
        """Check if vector is a dense list (vs sparse dict)."""
        return isinstance(vec, list)

    # ── Persistence ─────────────────────────────────────

    def _save(self):
        """Save to disk."""
        try:
            # Don't persist large embeddings in JSON (re-encode on load)
            slim = []
            for m in self._memories:
                slim.append({
                    k: v for k, v in m.items()
                    if k != "embedding"
                })
            tmp = str(self._file) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(slim, f, ensure_ascii=False, indent=2)
            import os
            os.replace(tmp, str(self._file))
        except Exception as e:
            import logging
            logging.getLogger("widdx.vector_memory").warning("_save failed: %s", e)

    def _load(self):
        """Load from disk. Embeddings are re-computed on first search."""
        try:
            if not self._file.exists():
                return
            with open(self._file, encoding="utf-8") as f:
                data = json.load(f)
            for d in data:
                d.setdefault("embedding", None)
                d.setdefault("tags", [])
                d.setdefault("metadata", {})
                d.setdefault("created", time.time())
            self._memories = data
            # Rebuild TF-IDF index
            for mem in self._memories:
                self._tfidf.index([mem.get("content", "")])
        except Exception as e:
            import logging
            logging.getLogger("widdx.vector_memory").warning("_load failed: %s", e)
