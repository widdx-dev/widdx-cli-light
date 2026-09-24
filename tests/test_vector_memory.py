"""Tests for L2: Vector Memory Layer (core/vector_memory.py)."""
from pathlib import Path
from core.vector_memory import (
    VectorMemoryStore, TFIDFEngine, OllamaEmbeddingEngine,
)


def test_tfidf_tokenize():
    engine = TFIDFEngine()
    tokens = engine._tokenize("Hello World 123")
    assert "hello" in tokens
    assert "world" in tokens
    assert "123" in tokens


def test_tfidf_encode():
    engine = TFIDFEngine()
    engine.index(["the cat sat on the mat", "the dog ran in the park"])
    vec = engine.encode("the cat")
    assert "cat" in vec
    assert vec["cat"] > 0


def test_tfidf_cosine():
    engine = TFIDFEngine()
    engine.index(["python machine learning tutorial",
                  "javascript web development guide",
                  "deep learning with python and keras"])
    score = engine.similarity("python ml tutorial", "python machine learning tutorial")
    assert score > 0.1, f"Expected >0.1, got {score}"


def test_tfidf_cosine_unrelated():
    engine = TFIDFEngine()
    engine.index(["baking chocolate cake recipe",
                  "quantum physics explained"])
    score = engine.similarity("cake recipe", "quantum physics")
    assert score < 0.5, f"Expected <0.5 for unrelated, got {score}"


def test_vector_store_add_search_tfidf():
    """Test add + search with TF-IDF fallback (works offline)."""
    store = VectorMemoryStore(
        storage_dir=Path.home() / ".widdx" / "test_vec",
        engine="tfidf",
    )
    store.clear()
    store.add("Python Guide", "how to write python code with classes and functions",
              tags=["python", "guide"])
    store.add("JavaScript Guide", "how to write javascript for web browsers",
              tags=["javascript", "web"])
    store.add("Cooking Recipe", "how to bake a chocolate cake with frosting",
              tags=["cooking"])

    results = store.search("python programming", top_k=2)
    assert len(results) >= 1
    # First result should be Python-related
    best_score, best_mem = results[0]
    assert "python" in best_mem["title"].lower() or "python" in best_mem["content"].lower()


def test_vector_store_search_unrelated():
    store = VectorMemoryStore(
        storage_dir=Path.home() / ".widdx" / "test_vec2",
        engine="tfidf",
    )
    store.clear()
    store.add("Space", "astronomy planets stars galaxies universe cosmos black holes",
              tags=["science"])
    store.add("Cooking", "recipes for dinner parties baking desserts",
              tags=["food"])

    results = store.search("black holes in space", top_k=2, min_score=0.01)
    assert len(results) >= 1
    best_score, best_mem = results[0]
    assert "science" in best_mem.get("tags", [])


def test_vector_store_tag_search():
    store = VectorMemoryStore(
        storage_dir=Path.home() / ".widdx" / "test_vec3",
        engine="tfidf",
    )
    store.clear()
    store.add("A", "content aaa", tags=["project-x", "important"])
    store.add("B", "content bbb", tags=["project-y"])
    store.add("C", "content ccc", tags=["project-x", "urgent"])

    results = store.search_by_tags(["project-x"])
    assert len(results) == 2


def test_vector_store_get_delete():
    store = VectorMemoryStore(
        storage_dir=Path.home() / ".widdx" / "test_vec4",
        engine="tfidf",
    )
    store.clear()
    mem_id = store.add("Test", "test content", tags=["test"])
    mem = store.get(mem_id)
    assert mem is not None
    assert mem["title"] == "Test"
    assert store.delete(mem_id) is True
    assert store.get(mem_id) is None
    assert store.delete(mem_id) is False


def test_vector_store_update():
    store = VectorMemoryStore(
        storage_dir=Path.home() / ".widdx" / "test_vec5",
        engine="tfidf",
    )
    store.clear()
    mem_id = store.add("Old", "old content", tags=["old"])
    store.update(mem_id, title="New", content="new content")
    mem = store.get(mem_id)
    assert mem["title"] == "New"
    assert mem["content"] == "new content"


def test_vector_store_list_count():
    store = VectorMemoryStore(
        storage_dir=Path.home() / ".widdx" / "test_vec6",
        engine="tfidf",
    )
    store.clear()
    store.add("A", "content a")
    store.add("B", "content b")
    all_mems = store.list_all()
    assert len(all_mems) == 2
    assert store.count() == 2


def test_ollama_similarity_math():
    """Test cosine similarity math (no server needed)."""
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert OllamaEmbeddingEngine.cosine_similarity(a, b) == 0.0

    c = [1.0, 1.0]
    d = [1.0, 1.0]
    assert abs(OllamaEmbeddingEngine.cosine_similarity(c, d) - 1.0) < 0.001

    # Empty vectors
    assert OllamaEmbeddingEngine.cosine_similarity([], [1.0]) == 0.0
    assert OllamaEmbeddingEngine.cosine_similarity([1.0], []) == 0.0


if __name__ == "__main__":
    print("L2 Vector Memory Tests")
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
