"""Project Structure — DEPRECATED compatibility shim.

Use ``core.project.scanner.ProjectScanner`` instead.
This module delegates to the new scanner and is kept for backward compatibility.
"""
import warnings
warnings.warn(
    "core.project_structure is deprecated. Use core.project.scanner instead.",
    DeprecationWarning,
    stacklevel=2,
)

from typing import Optional  # noqa: E402
from core.project.scanner import ProjectScanner  # noqa: E402


class FileNode:
    def __init__(self, name: str = "", path: str = "", is_dir: bool = False,
                 children: Optional[list] = None, size: int = 0, extension: str = ""):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.children = children or []
        self.size = size
        self.extension = extension

    def __repr__(self) -> str:
        return f"FileNode({self.name!r})"


class ProjectStructureAnalyzer:
    def __init__(self, directory: Optional[str] = None):
        self._scanner = ProjectScanner(directory or ".")

    def scan(self) -> list[FileNode]:
        result = self._scanner.scan()
        nodes = []
        for card in result.files if hasattr(result, 'files') else []:
            nodes.append(FileNode(
                name=card.name if hasattr(card, 'name') else "",
                path=card.path if hasattr(card, 'path') else "",
                is_dir=card.is_dir if hasattr(card, 'is_dir') else False,
                size=card.size if hasattr(card, 'size') else 0,
                extension=card.extension if hasattr(card, 'extension') else "",
            ))
        return nodes


_structure_analyzer: Optional[ProjectStructureAnalyzer] = None


def get_structure_analyzer(directory: Optional[str] = None) -> ProjectStructureAnalyzer:
    global _structure_analyzer
    if _structure_analyzer is None:
        _structure_analyzer = ProjectStructureAnalyzer(directory)
    return _structure_analyzer


__all__ = ["ProjectStructureAnalyzer", "FileNode", "get_structure_analyzer"]
