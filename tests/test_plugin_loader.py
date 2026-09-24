"""Tests for L3: Plugin Hot-Reload (core/plugin_loader.py)."""
import tempfile
import time
from pathlib import Path
from core.plugin_loader import PluginWatcher, SkillHotReloader, get_hot_reloader


def test_watcher_snapshot():
    """Watcher builds correct mtime snapshot."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "a.md").write_text("# A")
        (d / "b.py").write_text("x=1")
        (d / "c.txt").write_text("txt")  # should be ignored
        (d / "sub").mkdir()
        (d / "sub" / "d.md").write_text("# D")

        w = PluginWatcher(d, patterns=(".md",))
        snapshot = w._snapshot()
        assert "a.md" in snapshot
        assert "sub/d.md" in snapshot
        assert "b.py" not in snapshot  # .py not in patterns
        assert "c.txt" not in snapshot


def test_watcher_detect_added():
    """Watcher fires on_added when a new file appears."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        w = PluginWatcher(d, poll_interval=0.1, patterns=(".md",))
        added = []

        def on_add(p):
            added.append(str(p.relative_to(d)))

        w.on_added = on_add
        w._snapshot = lambda: {"old.md": 0}  # simulate baseline
        w._mtimes = {"old.md": 0}

        # Simulate a new file
        w._snapshot = lambda: {"old.md": 0, "new.md": 100}
        w._scan()

        assert "new.md" in added


def test_watcher_detect_modified():
    """Watcher fires on_modified when mtime increases."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        f = d / "skill.md"
        f.write_text("# v1")
        time.sleep(0.05)

        w = PluginWatcher(d, poll_interval=0.1, patterns=(".md",))
        modified = []

        def on_mod(p):
            modified.append(p.name)

        w.on_modified = on_mod
        w._snapshot = lambda: {"skill.md": os_path_getmtime(f)}
        w._mtimes = {"skill.md": 0}  # old mtime is 0

        w._scan()
        assert "skill.md" in modified


def test_watcher_detect_removed():
    """Watcher fires on_removed when a file disappears."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "gone.md").write_text("# bye")

        w = PluginWatcher(d, poll_interval=0.1, patterns=(".md",))
        removed = []

        def on_rem(p):
            removed.append(p.name)

        w.on_removed = on_rem
        w._snapshot = lambda: {}
        w._mtimes = {"gone.md": 0}

        w._scan()
        assert "gone.md" in removed


def test_watcher_start_stop():
    """Watcher starts and stops cleanly."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        w = PluginWatcher(d, poll_interval=0.1, patterns=(".md",))
        w.start()
        assert w.running
        time.sleep(0.3)  # let it poll a few times
        w.stop()
        assert not w.running


def test_hot_reloader_stats():
    """Hot reloader reports stats correctly."""
    r = SkillHotReloader()
    s = r.stats()
    assert "running" in s
    assert "watch_dir" in s
    assert "reload_count" in s


def test_hot_reloader_reload_all():
    """Force reload doesn't crash."""
    r = SkillHotReloader()
    r.reload_all()
    assert r.stats()["reload_count"] >= 1


def test_get_hot_reloader_singleton():
    """Singleton returns the same instance."""
    r1 = get_hot_reloader(auto_start=False)
    r2 = get_hot_reloader(auto_start=False)
    assert r1 is r2


def os_path_getmtime(p):
    import os
    return os.path.getmtime(str(p))


if __name__ == "__main__":
    print("L3 Plugin Hot-Reload Tests")
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
