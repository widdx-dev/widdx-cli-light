"""Project Context System - Advanced Context Management inspired by OpenCode"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("widdx.project_context")


@dataclass
class GitInfo:
    """Git repository information"""
    is_git_repo: bool = False
    current_branch: str = ""
    remote_url: str = ""
    last_commit: str = ""
    last_commit_date: str = ""


@dataclass
class EnvironmentInfo:
    """Environment information"""
    working_directory: str = ""
    platform: str = ""
    python_version: str = ""
    current_time: str = ""


@dataclass
class ProjectFile:
    """Important project file information"""
    path: str
    content: str
    is_important: bool = False


@dataclass
class ProjectContext:
    """Complete project context"""
    environment: EnvironmentInfo = field(default_factory=EnvironmentInfo)
    git: GitInfo = field(default_factory=GitInfo)
    important_files: List[ProjectFile] = field(default_factory=list)
    project_type: str = "unknown"
    project_name: str = "unknown"


# Important files to look for
IMPORTANT_FILES = [
    "README.md",
    "README.txt",
    "README",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    ".gitignore",
    "Dockerfile",
    "docker-compose.yml",
    "Makefile",
    "tsconfig.json",
    "webpack.config.js",
    ".env.example",
    "config.json",
    "settings.py",
    "main.py",
    "app.py",
    "index.js",
    "index.ts",
    "index.tsx",
]


class ProjectContextManager:
    """Manages project context"""
    
    def __init__(self, directory: Optional[str] = None):
        self.directory = Path(directory or os.getcwd())
        self.context = ProjectContext()
        self._load_context()
    
    def _load_context(self):
        """Load complete project context"""
        self._load_environment()
        self._load_git_info()
        self._load_important_files()
        self._detect_project_type()
    
    def _load_environment(self):
        """Load environment information"""
        self.context.environment.working_directory = str(self.directory)
        self.context.environment.platform = os.name
        self.context.environment.current_time = datetime.now().isoformat()
        
        try:
            import sys
            self.context.environment.python_version = sys.version
        except Exception:
            self.context.environment.python_version = "unknown"
    
    def _load_git_info(self):
        """Load git repository information"""
        git_dir = self.directory / ".git"
        self.context.git.is_git_repo = git_dir.exists()
        
        if not self.context.git.is_git_repo:
            return
        
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.directory,
                capture_output=True,
                text=True,
                timeout=5
            )
            self.context.git.current_branch = result.stdout.strip()
            
            # Get remote URL
            try:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=self.directory,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                self.context.git.remote_url = result.stdout.strip()
            except Exception:
                pass
            
            # Get last commit
            try:
                result = subprocess.run(
                    ["git", "log", "-1", "--pretty=%H"],
                    cwd=self.directory,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                self.context.git.last_commit = result.stdout.strip()
                
                result = subprocess.run(
                    ["git", "log", "-1", "--pretty=%ci"],
                    cwd=self.directory,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                self.context.git.last_commit_date = result.stdout.strip()
            except Exception:
                pass
        except Exception:
            pass
    
    def _load_important_files(self):
        """Load important project files"""
        for filename in IMPORTANT_FILES:
            filepath = self.directory / filename
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8", errors="replace")
                    self.context.important_files.append(
                        ProjectFile(
                            path=str(filepath),
                            content=content,
                            is_important=True
                        )
                    )
                except Exception:
                    pass
    
    def _detect_project_type(self):
        """Detect project type"""
        # Check for Python project
        if (self.directory / "pyproject.toml").exists() or \
           (self.directory / "requirements.txt").exists() or \
           (self.directory / "setup.py").exists():
            self.context.project_type = "python"
        
        # Check for Node.js project
        elif (self.directory / "package.json").exists():
            self.context.project_type = "nodejs"
        
        # Check for Docker project
        elif (self.directory / "Dockerfile").exists():
            self.context.project_type = "docker"
        
        # Try to extract project name
        package_json = self.directory / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                if "name" in data:
                    self.context.project_name = data["name"]
            except Exception:
                pass
        
        if self.context.project_name == "unknown":
            self.context.project_name = self.directory.name
    
    def get_context_summary(self) -> str:
        """Get a summary of project context as string"""
        lines = []
        lines.append("<project_context>")
        lines.append("")
        
        # Environment info
        lines.append("<environment>")
        lines.append(f"  Working Directory: {self.context.environment.working_directory}")
        lines.append(f"  Platform: {self.context.environment.platform}")
        lines.append(f"  Python Version: {self.context.environment.python_version}")
        lines.append(f"  Current Time: {self.context.environment.current_time}")
        lines.append("</environment>")
        lines.append("")
        
        # Git info
        lines.append("<git>")
        lines.append(f"  Is Git Repo: {self.context.git.is_git_repo}")
        if self.context.git.is_git_repo:
            lines.append(f"  Branch: {self.context.git.current_branch}")
            if self.context.git.remote_url:
                lines.append(f"  Remote: {self.context.git.remote_url}")
            if self.context.git.last_commit:
                lines.append(f"  Last Commit: {self.context.git.last_commit[:12]}")
                lines.append(f"  Last Commit Date: {self.context.git.last_commit_date}")
        lines.append("</git>")
        lines.append("")
        
        # Project info
        lines.append("<project>")
        lines.append(f"  Name: {self.context.project_name}")
        lines.append(f"  Type: {self.context.project_type}")
        lines.append("</project>")
        lines.append("")
        
        # Important files (summarized)
        lines.append("<important_files>")
        for file_info in self.context.important_files:
            file_path = Path(file_info.path)
            relative_path = file_path.relative_to(self.directory) if file_path.is_absolute() else file_path
            lines.append(f"  - {relative_path}")
            # Add first 500 chars of content
            content_preview = file_info.content[:500]
            if len(file_info.content) > 500:
                content_preview += "..."
            lines.append("    ```")
            lines.append(f"    {content_preview}")
            lines.append("    ```")
        lines.append("</important_files>")
        lines.append("")
        lines.append("</project_context>")
        
        return "\n".join(lines)
    
    def get_file_content(self, filepath: str) -> Optional[str]:
        """Get content of a specific file"""
        try:
            path = Path(filepath)
            if not path.is_absolute():
                path = self.directory / path
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
    
    def refresh(self):
        """Refresh project context"""
        self._load_context()


# Singleton instance
_project_context_manager: Optional[ProjectContextManager] = None


def get_project_context(directory: Optional[str] = None) -> ProjectContextManager:
    """Get or create project context manager"""
    global _project_context_manager
    if _project_context_manager is None or \
       (directory and _project_context_manager.directory != Path(directory)):
        _project_context_manager = ProjectContextManager(directory)
    return _project_context_manager
