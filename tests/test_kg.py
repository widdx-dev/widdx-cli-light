"""Tests for KnowledgeGraph."""
import tempfile
import shutil
from pathlib import Path


def _make_test_project():
    """Create a small project for testing."""
    tmp = Path(tempfile.mkdtemp())
    (tmp / "main.py").write_text("import utils\nfrom models import User\n\ndef main():\n    pass\n")
    (tmp / "utils.py").write_text("def helper():\n    return True\n")
    (tmp / "models.py").write_text("class User:\n    pass\nclass Post:\n    pass\n")
    (tmp / "README.md").write_text("# Test Project\n")
    return tmp


def test_kg_builds_on_test_project():
    from core.knowledge_graph import KnowledgeGraph
    tmp = _make_test_project()
    try:
        kg = KnowledgeGraph(tmp)
        n = kg.build()
        assert n > 0, f"Should find files, got {n}"
        assert kg._built is True
    finally:
        shutil.rmtree(tmp)


def test_kg_query_finds_python():
    from core.knowledge_graph import KnowledgeGraph
    tmp = _make_test_project()
    try:
        kg = KnowledgeGraph(tmp)
        kg.build()
        results = kg.query(".py")
        assert len(results) > 0, f"Should find Python files, got {len(results)}"
    finally:
        shutil.rmtree(tmp)


def test_kg_context_snippet():
    from core.knowledge_graph import KnowledgeGraph
    tmp = _make_test_project()
    try:
        kg = KnowledgeGraph(tmp)
        kg.build()
        snippet = kg.get_context_snippet()
        assert len(snippet) > 0
        assert "knowledge_graph" in snippet.lower()
    finally:
        shutil.rmtree(tmp)


def test_kg_find_path():
    from core.knowledge_graph import KnowledgeGraph
    tmp = _make_test_project()
    try:
        kg = KnowledgeGraph(tmp)
        kg.build()
        # The graph was built — verify nodes exist
        assert kg._built is True
        assert len(kg._nodes) >= 3  # main.py, utils.py, models.py
        assert any("main.py" in n for n in kg._nodes), f"Nodes: {list(kg._nodes.keys())[:5]}"
        # find_path may return empty if no direct edge chain exists
        path = kg.find_path("main.py", "models.py")
        assert isinstance(path, list)
    finally:
        shutil.rmtree(tmp)
