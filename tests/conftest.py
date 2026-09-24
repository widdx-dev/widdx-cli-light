"""Shared test fixtures for WIDDX test suite."""
import os
import pytest


@pytest.fixture(autouse=True)
def _reset_task_state():
    """Clear the process-wide TaskState singleton between tests.

    TaskState persists under .widdx/ and makes AutonomousAgent resume a
    previous task (stale PROJECT_DIR, stale steps) instead of starting clean,
    which produced order-dependent failures across the suite.
    """
    try:
        from core.task_state import get_task_state

        get_task_state().clear()
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _set_test_env(tmp_path):
    """Set test environment variables for all tests (always override)."""
    os.environ["WIDDX_API_KEY"] = "test-key-for-api-tests"
    os.environ["WIDDX_ADMIN_KEY"] = "test-admin-key-for-tests"
    os.environ["WIDDX_PERMISSION_LEVEL"] = "permissive"
    os.environ["WIDDX_PROJECT_DIR"] = str(tmp_path)
    # Dependency auto-install runs pip/npm and takes 60+ seconds; never do it
    # during the test suite. Tests must not mutate the host environment.
    os.environ["WIDDX_AUTO_SETUP_DEPS"] = "0"
    yield
