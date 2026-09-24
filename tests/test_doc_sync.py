"""Tests for DocSync."""
import tempfile
import shutil
from pathlib import Path
from core.doc_sync import DocSync, DriftWarning, get_doc_sync


def test_doc_sync_creates():
    tmp = Path(tempfile.mkdtemp())
    try:
        ds = DocSync(tmp)
        # Should not crash on empty project
        warnings = ds.detect_drift()
        assert isinstance(warnings, list)
    finally:
        shutil.rmtree(tmp)


def test_drift_warning_dataclass():
    w = DriftWarning(entity="test.py", message="File missing", severity="critical")
    assert w.severity == "critical"
    assert w.entity == "test.py"


def test_get_doc_sync_singleton():
    a = get_doc_sync()
    b = get_doc_sync()
    assert a is b


def test_detect_drift_with_missing_file():
    tmp = Path(tempfile.mkdtemp())
    try:
        widdx = tmp / ".widdx"
        widdx.mkdir()
        (widdx / "DESIGN.md").write_text("# Design\n\nUses `core/old_file.py` for auth")
        ds = DocSync(tmp)
        warnings = ds.detect_drift()
        # DESIGN.md references core/old_file.py which doesn't exist → drift detected
        assert len(warnings) > 0, f"Expected drift warnings, got {len(warnings)}"
    finally:
        shutil.rmtree(tmp)
