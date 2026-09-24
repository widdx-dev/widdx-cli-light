"""Tests for L4: Multi-file Editor (core/multi_editor.py)."""
import tempfile
from pathlib import Path
from core.multi_editor import MultiFileEditor, multi_editor


def test_editor_creates():
    editor = MultiFileEditor()
    assert editor.staged_count == 0


def test_add_and_preview():
    editor = MultiFileEditor()
    editor.add("a.py", "new a")
    editor.add("b.py", "new b")
    assert editor.staged_count == 2
    preview = editor.preview()
    assert "a.py" in preview
    assert "b.py" in preview


def test_remove():
    editor = MultiFileEditor()
    editor.add("a.py", "new a")
    editor.add("b.py", "new b")
    editor.remove("a.py")
    assert editor.staged_count == 1


def test_commit_dry_run():
    editor = MultiFileEditor()
    editor.add("/tmp/test_dry.py", "test")
    result = editor.commit(dry_run=True)
    assert result.ok
    assert result.files_written == 0


def test_commit_write():
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / "a.py"
        b = Path(tmp) / "b.py"

        editor = MultiFileEditor()
        editor.add(str(a), "content a")
        editor.add(str(b), "content b")
        result = editor.commit()

        assert result.ok
        assert result.files_written == 2
        assert a.read_text() == "content a"
        assert b.read_text() == "content b"


def test_clear():
    editor = MultiFileEditor()
    editor.add("a.py", "content")
    assert editor.staged_count == 1
    editor.clear()
    assert editor.staged_count == 0


def test_singleton():
    assert multi_editor is not None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
