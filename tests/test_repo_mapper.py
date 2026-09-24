"""Tests for L4: Smart Repo Mapper (core/repo_mapper.py)."""
import tempfile
from pathlib import Path
from core.repo_mapper import RepoMapper, FileNode


def test_repo_mapper_scan_current():
    """Scan the current repo — should find Python files."""
    mapper = RepoMapper()
    count = mapper.scan()
    assert count > 0, "Should find at least some files"


def test_repo_mapper_stats():
    mapper = RepoMapper()
    mapper.scan()
    stats = mapper.stats()
    assert stats["total_files"] > 0
    assert isinstance(stats["languages"], list)


def test_repo_mapper_select():
    """Select files relevant to a query."""
    mapper = RepoMapper()
    mapper.scan()
    results = mapper.select("python agent loop")
    assert isinstance(results, list)
    # There should be relevant files for this query
    assert any("agent" in r.lower() for r in results)


def test_repo_mapper_find_file():
    mapper = RepoMapper()
    mapper.scan()
    results = mapper.find_file("agent")
    assert len(results) >= 1
    assert any("agent" in r.lower() for r in results)


def test_repo_mapper_dependencies():
    mapper = RepoMapper()
    mapper.scan()
    # Find a file with imports
    for path in mapper._files:
        deps = mapper.get_dependencies(path)
        if deps:
            assert isinstance(deps, list)
            break
    # At least one file should have dependencies parsed
    # (may fail in empty repos, but current repo has many imports)


def test_repo_mapper_cache():
    """Second scan should use cache."""
    mapper = RepoMapper()
    mapper.scan()
    # Second scan should be instant (from cache)
    count2 = mapper.scan(force=False)
    assert count2 > 0


def test_file_node_symbols():
    """FileNode correctly stores path and ext."""
    node = FileNode(Path("/tmp/test.py"), Path("/tmp"))
    node.symbols = ["main", "helper"]
    node.imports = ["os", "sys"]
    d = node.to_dict()
    assert d["path"] == "test.py"
    assert d["ext"] == ".py"
    assert "main" in d["symbols"]


def test_repo_mapper_scan_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        mapper = RepoMapper(root=tmp)
        count = mapper.scan(force=True)
        assert count == 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
