"""Tests for L3: Checkpoint Manager (core/checkpoint.py)."""
from core.checkpoint import CheckpointManager, checkpoint_manager


def test_checkpoint_manager_creates():
    cpm = CheckpointManager()
    assert cpm is not None
    assert hasattr(cpm, "save")
    assert hasattr(cpm, "list")
    assert hasattr(cpm, "rollback")


def test_checkpoint_manager_no_crash_without_git():
    """Should handle missing git gracefully."""
    cpm = CheckpointManager()
    # If git is available, save should work; if not, it returns None
    result = cpm.save("test checkpoint")
    # Either returns hash (success) or None (git unavailable)
    assert result is None or isinstance(result, str)


def test_checkpoint_list_no_crash():
    cpm = CheckpointManager()
    checkpoints = cpm.list()
    assert isinstance(checkpoints, list)


def test_checkpoint_count():
    cpm = CheckpointManager()
    count = cpm.count()
    assert isinstance(count, int)
    assert count >= 0


def test_singleton_exists():
    assert checkpoint_manager is not None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
