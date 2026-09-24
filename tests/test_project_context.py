
#!/usr/bin/env python3
"""
Test Project Context System
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_context import get_project_context
from core.project.scanner import ProjectScanner


def test_project_context():
    """Test project context loading"""
    print("=" * 60)
    print("Testing Project Context System")
    print("=" * 60)
    print()

    try:
        ctx = get_project_context()
        print("✅ Project context loaded successfully!")
        print()

        summary = ctx.get_context_summary()
        print("📋 Project Context Summary:")
        print("-" * 60)
        print(summary)
        print()

        print("✅ Project context test passed!")
        assert True
    except Exception as e:
        print(f"❌ Project context test failed: {e}")
        import traceback
        traceback.print_exc()
        raise AssertionError(f"Project context test failed: {e}") from e


def test_project_structure():
    """Test project structure analysis via ProjectScanner.scan()."""
    scanner = ProjectScanner()
    assert scanner is not None

    card = scanner.scan()
    assert card is not None, "scan() should return a ProjectCard"
    assert isinstance(card.file_count, int), "file_count must be int"
    assert card.file_count > 0, f"Expected files in project, got {card.file_count}"
    assert isinstance(card.languages, dict), "languages must be dict"
    assert card.root_name, "root_name must not be empty"


def test_file_search():
    """Test project file discovery via ProjectScanner.scan()."""
    scanner = ProjectScanner()
    card = scanner.scan()

    # Verify common file types are detected in this Python project
    lang_keys = {k.lower() for k in card.languages.keys()}
    expected = {"python", "markdown", "json"}
    found = expected & lang_keys
    assert len(found) >= 2, (
        f"Expected at least 2 of {expected} in project languages, "
        f"got: {list(card.languages.keys())}"
    )

    # Verify framework markers
    assert len(card.frameworks) > 0, (
        f"Expected at least one framework detected, got: {card.frameworks}"
    )


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("WIDDX Project Context System - Test Suite")
    print("=" * 60 + "\n")

    passed = 0
    failed = 0
    for name, func in [("Project Context", test_project_context),
                       ("Project Structure", test_project_structure),
                       ("File Search", test_file_search)]:
        try:
            func()
            passed += 1
            print(f"  {name}: ✅ PASSED")
        except Exception as e:
            failed += 1
            print(f"  {name}: ❌ FAILED — {e}")
        print()

    print("=" * 60)
    if failed == 0:
        print("🎉 All tests passed! Project Context System is working!")
    else:
        print(f"⚠️ {failed} test(s) failed, {passed} passed.")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

