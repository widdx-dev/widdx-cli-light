"""Linter tool handler."""

from pathlib import Path


def _handle_run_linter(file_path: str, language: str = "auto") -> str:
    from core.linter import LinterRunner
    runner = LinterRunner()
    result = runner.check(Path(file_path), language != "auto")
    return result.format_for_agent()
