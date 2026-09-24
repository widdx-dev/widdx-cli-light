"""Tests for L2: Diff Engine (core/diff_engine.py)."""
import tempfile
from pathlib import Path
from core.diff_engine import DiffEngine


def test_generate_simple_diff():
    old = "line1\nline2\nline3\n"
    new = "line1\nline2_modified\nline3\n"
    patch = DiffEngine.generate(old, new, filename="test.py")
    assert "-line2" in patch
    assert "+line2_modified" in patch


def test_generate_no_change():
    text = "hello\nworld\n"
    patch = DiffEngine.generate(text, text)
    assert patch == ""


def test_apply_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test.py"
        f.write_text("old content\n")
        result = DiffEngine.apply(
            f, "old content\n", "new content\n", dry_run=True,
        )
        assert result.ok
        assert result.dry_run
        assert "+new content" in result.patch
        assert f.read_text() == "old content\n"  # unchanged


def test_apply_write():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test.py"
        f.write_text("old\n")
        result = DiffEngine.apply(f, "old\n", "new\n", dry_run=False)
        assert result.ok
        assert f.read_text() == "new\n"


def test_apply_conflict_detection():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test.py"
        f.write_text("actual current content\n")
        result = DiffEngine.apply(
            f, "stale old content\n", "new content\n",
        )
        assert not result.ok
        assert "Conflict" in result.error


def test_apply_new_file():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "newfile.py"
        result = DiffEngine.apply(f, "", "new content\n")
        assert result.ok
        assert f.read_text() == "new content\n"


def test_stats_count():
    old = "line1\nline2\nline3\nline4\n"
    new = "line1\nline2_changed\nline5\n"
    result = DiffEngine.apply(Path("/tmp/test.py"), old, new, dry_run=True)
    assert result.lines_added >= 1
    assert result.lines_removed >= 1


def test_preview():
    preview = DiffEngine.preview("test.py", "old\n", "new\n")
    assert "-old" in preview
    assert "+new" in preview


def test_apply_patch_simple():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test.py"
        f.write_text("line1\nline2\nline3\n")
        patch = "@@ -1,3 +1,3 @@\n line1\n-line2\n+line2_new\n line3\n"
        result = DiffEngine.apply_patch(f, patch)
        assert result.ok
        assert "line2_new" in f.read_text()


def test_apply_patch_conflict():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test.py"
        f.write_text("totally different content\n")
        patch = "@@ -2 +2 @@\n line1\n-line2\n+line2_new\n"
        result = DiffEngine.apply_patch(f, patch)
        assert not result.ok


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
