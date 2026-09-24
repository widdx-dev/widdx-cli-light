"""CLI entry point for the `widdx` command.

Bridges the installed package to the new ``cli.app`` runner.
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path when running from any directory
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from core._path import ensure_project_root  # noqa: F401
except ImportError:
    pass


def run() -> None:
    """Main CLI entry point — terminal interface."""
    try:
        from cli.app import CLIApp
        app = CLIApp()
        app.run()
    except ImportError as e:
        print(f"\n❌ Failed to start CLI: {e}")
        print("   Install: pip install widdx-nexus")
        print("   Required: rich, httpx, prompt_toolkit, pygments, python-bidi\n")
        raise
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ CLI error: {e}")
        raise

if __name__ == "__main__":
    run()
