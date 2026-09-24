"""Tests for L3: RAG Pipeline (core/rag.py)."""
from core.rag import RAGStore, rag_store


def test_rag_add_search():
    store = RAGStore()
    store.clear()
    store.add("doc1", "python async programming with asyncio", {"lang": "python"})
    store.add("doc2", "javascript promises and async await", {"lang": "javascript"})
    store.add("doc3", "baking chocolate chip cookies", {"lang": "cooking"})

    results = store.search("async programming", top_k=3, min_score=0.01)
    assert len(results) >= 1
    score, doc = results[0]
    assert "python" in doc["content"] or "javascript" in doc["content"]


def test_rag_count():
    store = RAGStore()
    store.clear()
    store.add("a", "content a")
    store.add("b", "content b")
    assert store.count() == 2


def test_rag_empty_search():
    store = RAGStore()
    store.clear()
    results = store.search("query")
    assert results == []


def test_rag_singleton():
    assert rag_store is not None
    assert hasattr(rag_store, "add")
    assert hasattr(rag_store, "search")


def test_cosine_math():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert RAGStore._cosine(a, b) == 0.0
    assert abs(RAGStore._cosine(a, a) - 1.0) < 0.001


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
