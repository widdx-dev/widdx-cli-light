"""Tests for L2: Auto-Commit Manager (core/auto_commit.py)."""
from core.auto_commit import AutoCommitManager, auto_committer


def test_manager_creates():
    acm = AutoCommitManager()
    assert acm is not None


def test_singleton_exists():
    assert auto_committer is not None


def test_watch_snapshots():
    acm = AutoCommitManager()
    acm.watch()
    assert acm._watching


def test_commit_if_success_no_changes():
    acm = AutoCommitManager()
    acm.watch()
    result = acm.commit_if_success("test")
    # No changes = None
    assert result is None


def test_staged_diff():
    acm = AutoCommitManager()
    diff = acm.staged_diff()
    assert isinstance(diff, str)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
