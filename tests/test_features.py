"""Integration tests for project features (git, config, load, summary, index)."""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def force_rmtree(path):
    def remove_readonly(func, p, _excinfo):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    shutil.rmtree(path, onerror=remove_readonly)


@pytest.fixture
def test_dir(tmp_path):
    """Isolated git project directory for integration tests."""
    work = tmp_path / "workdir"
    work.mkdir()
    subprocess.run(["git", "init"], cwd=str(work), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(work), capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(work), capture_output=True)
    yield work


def test_git_auto_commit_and_undo(test_dir):
    from core.project.git import is_git_repo, has_changes, auto_commit, undo_last_commit

    assert is_git_repo(test_dir)
    status_proc = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(test_dir), capture_output=True, text=True
    )
    assert not has_changes(test_dir), f"Unexpected changes:\n{status_proc.stdout}"

    (test_dir / "test_run.txt").write_text("hello")
    subprocess.run(["git", "add", "test_run.txt"], cwd=str(test_dir), capture_output=True)
    subprocess.run(["git", "commit", "-m", "WIDDX: initial commit"], cwd=str(test_dir), capture_output=True)
    assert not has_changes(test_dir)

    (test_dir / "test_run.txt").write_text("hello v2")
    assert auto_commit(test_dir, "test commit 1")
    assert not has_changes(test_dir)

    (test_dir / "test_run.txt").write_text("hello v3")
    assert auto_commit(test_dir, "test commit 2")

    result = undo_last_commit(test_dir)
    assert "Undone" in result
    assert (test_dir / "test_run.txt").read_text() == "hello v3"

    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=str(test_dir), capture_output=True, text=True, timeout=5,
    )
    assert "test commit 1" in log.stdout


def test_project_config(test_dir):
    from core.project.state import load_project_config, save_project_config

    config = load_project_config(test_dir)
    assert config["auto_commit"] is True
    assert config["project_instructions"] == ""

    config["project_instructions"] = "This is a test project"
    save_project_config(config, test_dir)
    loaded = load_project_config(test_dir)
    assert loaded["project_instructions"] == "This is a test project"


def test_load_command(test_dir):
    from core.commands import handle_load
    from core.project.state import save_session

    provider_mock = type("obj", (object,), {"name": "test", "model": "test"})()
    state = {"model": "test/model", "cost": 0.5, "turns": 3}
    messages = [{"role": "system", "content": "test"}]
    save_session(messages, state, test_dir)

    new_prov, new_state, new_msgs = handle_load(provider_mock, state, messages, str(test_dir))
    assert len(new_msgs) == 1
    assert new_state["cost"] == 0.5
    assert new_prov.name == "test"


def test_auto_summary():
    from core.project.state import summarize_conversation

    long_msgs = [{"role": "system", "content": "sys"}]
    for i in range(50):
        long_msgs.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"message {i}",
        })

    summarized = summarize_conversation(long_msgs, keep_last=10)
    assert len(summarized) < len(long_msgs)
    assert any(m.get("_summary") for m in summarized)
    assert len(summarized) == 12  # system + summary + 10 kept


def test_expert_profile_structure():
    from core.agents.expert import ExpertProfile

    profile = ExpertProfile("test", "Tester", ["test"], "prompt {tool_descriptions}")
    assert profile.name == "test"


def test_build_index_with_extra_ignore(test_dir):
    from core.project.state import build_index

    (test_dir / "ignored_dir").mkdir()
    (test_dir / "ignored_dir" / "temp.txt").write_text("temp")
    (test_dir / "src").mkdir()
    (test_dir / "src" / "main.py").write_text("def hello(): pass")

    index = build_index(test_dir, extra_ignore=["ignored_dir"])
    assert index["file_count"] == 1
    assert index["symbol_count"] >= 1
