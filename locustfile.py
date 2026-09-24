"""WIDDX Nexus — Locust Load Testing Script.

Simulates realistic user traffic against the WIDDX REST API.

Usage:
    # Terminal UI mode:
    locust -f locustfile.py --host=http://127.0.0.1:8000

    # Headless mode (CLI):
    locust -f locustfile.py --host=http://127.0.0.1:8000 \
        --headless --users 50 --spawn-rate 5 --run-time 60s

    # Set API key:
    WIDDX_API_KEY=your-key locust -f locustfile.py --host=http://127.0.0.1:8000

Requirements:
    pip install locust
"""

import os
import random
from locust import HttpUser, task, between, constant, SequentialTaskSet


# ── Configuration ──────────────────────────────────────────────

API_KEY = os.environ.get("WIDDX_API_KEY", "")
if not API_KEY:
    print(
        "\n⚠  WIDDX_API_KEY is not set. All requests will fail with 401/503.\n"
        "   Set it: export WIDDX_API_KEY='your-secret-key'\n"
    )

AUTH_HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}


# ======================================================================
# USER CLASS 1 — Lightweight User (browses, checks status)
# ======================================================================

class LightweightUser(HttpUser):
    """
    Simulates a user who browses the API — checks health,
    lists providers, views tools. Low request weight.
    """

    wait_time = between(2, 5)  # seconds between tasks
    weight = 3  # spawn 3x more of these than heavy users

    @task(10)
    def health_check(self):
        """GET /api/health — fastest endpoint."""
        self.client.get("/api/health", headers=AUTH_HEADERS, name="GET /api/health")

    @task(5)
    def list_providers(self):
        """GET /api/providers — lists available providers."""
        self.client.get("/api/providers", headers=AUTH_HEADERS, name="GET /api/providers")

    @task(3)
    def list_tools(self):
        """GET /api/tools — lists available tools."""
        self.client.get("/api/tools", headers=AUTH_HEADERS, name="GET /api/tools")

    @task(2)
    def list_memory(self):
        """GET /api/memory — lists memory facts."""
        self.client.get("/api/memory", headers=AUTH_HEADERS, name="GET /api/memory")

    @task(2)
    def project_status(self):
        """GET /api/project/status — project info."""
        self.client.get("/api/project/status", headers=AUTH_HEADERS, name="GET /api/project/status")

    @task(1)
    def project_docs(self):
        """GET /api/project/docs — project docs."""
        self.client.get("/api/project/docs", headers=AUTH_HEADERS, name="GET /api/project/docs")

    @task(1)
    def session_info(self):
        """GET /api/sessions — session info."""
        self.client.get("/api/sessions", headers=AUTH_HEADERS, name="GET /api/sessions")


# ======================================================================
# USER CLASS 2 — Power User (more operations)
# ======================================================================

class PowerUser(HttpUser):
    """
    Simulates a power user doing CRUD operations on memory,
    managing sessions, and interacting with tools.
    """

    wait_time = between(1, 4)
    weight = 2

    @task(5)
    def health_check(self):
        self.client.get("/api/health", headers=AUTH_HEADERS, name="GET /api/health (power)")

    @task(4)
    def clear_session(self):
        """DELETE /api/sessions — reset conversation."""
        self.client.delete("/api/sessions", headers=AUTH_HEADERS, name="DELETE /api/sessions")

    @task(3)
    def save_memory(self):
        """POST /api/memory — save a memory fact."""
        payload = {
            "name": f"load-test-fact-{random.randint(1, 1000)}",
            "content": f"Auto-generated load test fact at {random.random()}",
            "type": random.choice(["feedback", "note", "insight"]),
        }
        self.client.post(
            "/api/memory",
            json=payload,
            headers=AUTH_HEADERS,
            name="POST /api/memory",
        )

    @task(2)
    def list_tools(self):
        self.client.get("/api/tools", headers=AUTH_HEADERS, name="GET /api/tools (power)")

    @task(1)
    def execute_tool(self):
        """POST /api/tools/execute — attempt tool execution."""
        payload = {
            "name": "execute_command",
            "args": {"command": "echo 'load test'"},
        }
        self.client.post(
            "/api/tools/execute",
            json=payload,
            headers=AUTH_HEADERS,
            name="POST /api/tools/execute",
        )

    @task(1)
    def provider_list(self):
        self.client.get("/api/providers", headers=AUTH_HEADERS, name="GET /api/providers (power)")


# ======================================================================
# USER CLASS 3 — Stress Bot (aggressive, high frequency)
# ======================================================================

class StressBot(HttpUser):
    """
    Aggressive stress bot that fires requests as fast as possible.
    Lower weight so only a few spawn.
    """

    wait_time = constant(0.1)  # 100ms between requests
    weight = 1

    @task(10)
    def fast_health(self):
        self.client.get("/api/health", headers=AUTH_HEADERS, name="STRESS GET /api/health")

    @task(5)
    def fast_clear_session(self):
        self.client.delete("/api/sessions", headers=AUTH_HEADERS, name="STRESS DELETE /api/sessions")

    @task(3)
    def fast_memory_save(self):
        payload = {
            "name": f"stress-fact-{random.randint(1, 10000)}",
            "content": "Stress test payload" * 10,
            "type": "stress",
        }
        self.client.post(
            "/api/memory",
            json=payload,
            headers=AUTH_HEADERS,
            name="STRESS POST /api/memory",
        )

    @task(2)
    def fast_providers(self):
        self.client.get("/api/providers", headers=AUTH_HEADERS, name="STRESS GET /api/providers")

    @task(1)
    def fast_project_status(self):
        self.client.get("/api/project/status", headers=AUTH_HEADERS, name="STRESS GET /api/project/status")


# ======================================================================
# USER CLASS 4 — Sequential Workflow User (realistic scenario)
# ======================================================================

class SequentialWorkflowUser(HttpUser):
    """
    Simulates a realistic user workflow: check health → view providers →
    interact with memory → check status → clear session.
    """

    wait_time = between(3, 8)
    weight = 2

    @task
    class WorkflowSequence(SequentialTaskSet):
        """A realistic multi-step workflow."""

        def on_start(self):
            """Check health first — like a real client would."""
            self.client.get("/api/health", headers=AUTH_HEADERS, name="SEQ GET /api/health")

        @task
        def step_1_list_providers(self):
            self.client.get("/api/providers", headers=AUTH_HEADERS, name="SEQ GET /api/providers")

        @task
        def step_2_list_tools(self):
            self.client.get("/api/tools", headers=AUTH_HEADERS, name="SEQ GET /api/tools")

        @task
        def step_3_save_memory(self):
            payload = {
                "name": f"wf-memory-{random.randint(1, 500)}",
                "content": "Workflow memory fact",
                "type": "workflow",
            }
            self.client.post(
                "/api/memory",
                json=payload,
                headers=AUTH_HEADERS,
                name="SEQ POST /api/memory",
            )

        @task
        def step_4_project_status(self):
            self.client.get("/api/project/status", headers=AUTH_HEADERS, name="SEQ GET /api/project/status")

        @task
        def step_5_clear_session(self):
            self.client.delete("/api/sessions", headers=AUTH_HEADERS, name="SEQ DELETE /api/sessions")
