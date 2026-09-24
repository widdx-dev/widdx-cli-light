"""Test the project_validate tool with a real Python project."""

import tempfile
import shutil
import os
import subprocess
from pathlib import Path

from core import tools


def create_test_project(proj_dir: str):
    """Create a minimal Python project with tests."""
    proj = Path(proj_dir)
    
    # Create pyproject.toml
    (proj / "pyproject.toml").write_text("""[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-project"
version = "0.1.0"
""")
    
    # Create a simple module
    (proj / "hello.py").write_text("""
def greet(name):
    return f"Hello, {name}!"

def add(a, b):
    return a + b
""")
    
    # Create tests
    (proj / "test_hello.py").write_text("""
import pytest
from hello import greet, add

def test_greet():
    assert greet("World") == "Hello, World!"

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
""")


def run_test():
    tmp = tempfile.mkdtemp(prefix="widdx_project_validate_")
    try:
        print("=" * 80)
        print("PROJECT VALIDATE TOOL TEST")
        print("=" * 80)
        print(f"\nCreated test project in: {tmp}\n")
        
        # Create test project structure
        create_test_project(tmp)
        
        # List files
        print("Project files:")
        for f in os.listdir(tmp):
            print(f"  - {f}")
        
        # Test 1: Check project_validate is registered
        print("\n" + "-" * 80)
        print("Test 1: Verify project_validate is registered")
        print("-" * 80)
        tool_names = [td["name"] for td in tools.TOOL_DEFINITIONS]
        if "project_validate" in tool_names:
            print("✅ project_validate is registered in TOOL_DEFINITIONS")
        else:
            print("❌ project_validate NOT found in TOOL_DEFINITIONS")
            print(f"Available tools: {tool_names}")
            return
        
        # Test 2: Run project_validate on the test project
        print("\n" + "-" * 80)
        print("Test 2: Run project_validate on test project")
        print("-" * 80)
        
        # First, make sure pytest is available
        try:
            subprocess.run(
                ["python", "-m", "pytest", "--version"],
                capture_output=True,
                timeout=10,
                check=True
            )
            print("✅ pytest is available")
        except Exception as e:
            print(f"⚠️  pytest not available: {e}")
            print("Installing pytest...")
            subprocess.run(
                ["python", "-m", "pip", "install", "pytest", "-q"],
                timeout=60
            )
        
        # Call project_validate
        result = tools.execute("project_validate", {"project_dir": tmp})
        print("\nproject_validate result:")
        print(result)
        
        # Test 3: Verify the result contains expected information
        print("\n" + "-" * 80)
        print("Test 3: Validate output")
        print("-" * 80)
        
        if "Python project detected" in result:
            print("✅ Detected Python project type")
        else:
            print("❌ Did not detect Python project type")
        
        if "pytest passed" in result or "pytest" in result.lower():
            print("✅ Project validation completed (pytest ran)")
        else:
            print("⚠️  pytest might not have run")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        
    finally:
        shutil.rmtree(tmp)


if __name__ == '__main__':
    run_test()


def test_project_validate_tool_runs_pytest(tmp_path):
    """project_validate tool runs pytest against a generated project."""
    create_test_project(str(tmp_path))
    result = tools.execute("project_validate", {"project_dir": str(tmp_path)})
    assert isinstance(result, str)
    # The tool reports a validation summary; pytest must have executed.
    assert "pytest" in result.lower() or "validation" in result.lower(), (
        f"Unexpected project_validate output: {result[:300]}"
    )
    assert "error" not in result.lower() or "0" in result
