import asyncio
import importlib.util
import sys
import threading
from copy import deepcopy
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WIDDX_API_KEY", "test-key-for-api-tests")

    def module(name, **attrs):
        stub = ModuleType(name)
        stub.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, stub)
        return stub

    provider = SimpleNamespace(name="fake", model="test", base_url="")
    mcp = Mock(server_count=0)
    mcp.get_all_tool_definitions.return_value = []
    scanner = Mock()
    scanner.build_context_block.return_value = ""
    memory = Mock()
    memory.list_all.return_value = []
    memory.total.return_value = 0
    memory.delete.return_value = True
    learner = Mock()
    learner.load_relevant.return_value = ""
    metrics = Mock()
    metrics.report.return_value = {}
    metrics.track_request.return_value = SimpleNamespace(
        __enter__=lambda self: SimpleNamespace(error=False),
        __exit__=lambda *args: None,
    )
    from contextlib import nullcontext
    metrics.track_request.side_effect = lambda *args: nullcontext(SimpleNamespace(error=False))
    monitor = Mock()
    monitor.get_memory_usage.return_value = {}
    monitor.get_cpu_usage.return_value = {}
    tools = module("core.tools", TOOL_DEFINITIONS=[{"name": "fake", "description": "test"}])
    module("core", tools=tools)
    module("core.config")
    module("core.config.settings", load=Mock(return_value={}), save=Mock())
    module("core.providers")
    module("core.providers.providers", create_provider=Mock(return_value=provider),
           get_available_models=Mock(return_value=["test"]))
    module("core.memory", MemoryStore=Mock(return_value=memory))
    module("core.memory_learner", MemoryLearner=Mock(return_value=learner))
    storage = module("core.project.state", save_session=Mock())
    module("core.project", state=storage)
    module("core.project.scanner", ProjectScanner=Mock(return_value=scanner))
    module("core.project_tracker", ensure_docs=Mock(), load_docs=Mock(return_value={}),
           update_doc=Mock(return_value=True), build_context_block=Mock(return_value=""))
    module("core.auto_setup", detect_project_deps=Mock(return_value={}))
    skills = Mock()
    skills.list_all.return_value = []
    module("core.skills", skill_manager=skills)
    module("core.mcp")
    module("core.mcp.client", get_mcp_manager=Mock(return_value=mcp))

    def turn(provider, messages, state, tools, cfg):
        messages.append({"role": "assistant", "content": "reply"})
        state["turns"] += 1
        return messages, state

    module("core.chat", run_stream_turn=Mock(side_effect=turn))
    module("core.monitoring", metrics_collector=metrics, system_monitor=monitor)
    module("core.constants", SYSTEM_PROMPT="Skills: {skills_list}")
    path = Path(__file__).resolve().parents[1] / "scripts" / "api_server.py"
    spec = importlib.util.spec_from_file_location("isolated_api_server", path)
    server = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, server)
    spec.loader.exec_module(server)
    return server


@pytest.fixture
def client(api):
    with TestClient(api.app, headers={"Authorization": "Bearer test-key-for-api-tests"}) as client:
        yield client


@pytest.mark.parametrize("path", ["health", "providers", "sessions", "memory", "tools", "project/docs", "project/status"])
def test_read_endpoints(client, path):
    response = client.get(f"/api/{path}")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_chat_contract(client, api):
    response = client.post("/api/chat", json={
        "message": "Review", "session_id": "shared", "stream": False,
        "context": {"file_path": "example.py", "file_content": "value = 1", "selection": "value"},
    })
    assert response.status_code == 200
    assert response.json() == {"response": "reply", "model": "fake/test", "turns": 1, "cost": 0.0, "session_id": "shared"}
    content = api.state.messages[-2]["content"]
    assert "Review" in content and "example.py" in content and "value = 1" in content
    assert "Selection:\nvalue" in content
    assert client.get("/api/sessions").json()["turns"] == 1


@pytest.mark.parametrize("body", [
    {}, {"message": ""}, {"message": "   "}, {"message": "hello", "stream": True},
    {"message": "hello", "session_id": "other"}, {"message": "hello", "file_path": "ignored.py"},
    {"message": "hello", "context": {"unknown": "value"}},
])
def test_invalid_chat(client, api, body):
    assert client.post("/api/chat", json=body).status_code in (400, 422)
    api.run_stream_turn.assert_not_called()


@pytest.mark.parametrize("token", ["", "Bearer wrong"])
def test_chat_authentication(client, api, token):
    response = client.post("/api/chat", json={"message": "hello"}, headers={"Authorization": token})
    assert response.status_code == 401
    api.run_stream_turn.assert_not_called()


def test_unconfigured_key(client, monkeypatch):
    monkeypatch.delenv("WIDDX_API_KEY")
    assert client.get("/api/sessions").status_code == 503


def test_clear_session(client, api):
    client.post("/api/chat", json={"message": "hello"})
    assert client.delete("/api/sessions").json() == {"status": "cleared", "session_id": "shared"}
    assert api.state.messages == []
    assert api.state.state == {"model": "fake/test", "turns": 0, "cost": 0.0}
    api.project_state.save_session.assert_called_with([], api.state.state)


def test_failed_turn_does_not_mutate_history(client, api):
    client.post("/api/chat", json={"message": "hello"})
    before = deepcopy((api.state.messages, api.state.state))

    def fail(provider, messages, state, tools, cfg):
        messages[0]["content"] = "changed"
        state["turns"] = 99
        raise RuntimeError("private provider details")

    api.run_stream_turn.side_effect = fail
    response = client.post("/api/chat", json={"message": "second"})
    assert response.status_code == 500
    assert "private" not in response.text
    assert (api.state.messages, api.state.state) == before


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["chat", "clear", "switch", "cancel"])
async def test_chat_serializes_mutations(api, operation):
    entered = threading.Event()
    release = threading.Event()
    original = api.run_stream_turn.side_effect
    calls = []

    def blocked(provider, messages, state, tools, cfg):
        calls.append(deepcopy(messages))
        if len(calls) == 1:
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test did not release turn")
        return original(provider, messages, state, tools, cfg)

    api.run_stream_turn.side_effect = blocked
    first = asyncio.create_task(api.chat(api.ChatRequest(message="first")))
    second = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if operation == "chat":
            second = asyncio.create_task(api.chat(api.ChatRequest(message="second")))
        elif operation == "switch":
            second = asyncio.create_task(api.switch_provider(api.ProviderSwitch(name="fake")))
        else:
            if operation == "cancel":
                first.cancel()
            second = asyncio.create_task(api.clear_session())
        await asyncio.sleep(0.05)
        assert not second.done()
        assert len(calls) == 1
        release.set()
        if operation == "cancel":
            with pytest.raises(asyncio.CancelledError):
                await first
        else:
            await first
        await second
        if operation == "chat":
            assert [m["content"] for m in api.state.messages if m["role"] == "user"] == ["first", "second"]
            assert api.state.state["turns"] == 2
            assert calls[1][-2] == {"role": "assistant", "content": "reply"}
        elif operation in ("clear", "cancel"):
            assert api.state.messages == []
            assert api.state.state["turns"] == 0
        else:
            assert api.state.state["turns"] == 1
    finally:
        release.set()
        await asyncio.gather(first, *([second] if second else []), return_exceptions=True)


def test_memory_write_and_delete(client):
    assert client.post("/api/memory", json={"name": "test", "content": "test"}).status_code == 200
    assert client.delete("/api/memory/test").status_code == 200


def test_invalid_doc(client):
    assert client.post("/api/project/docs", json={"doc": "invalid", "content": "test"}).status_code == 400
