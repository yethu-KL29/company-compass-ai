import json

import pytest
from fastapi.testclient import TestClient

from company_compass.api.dependencies import get_assistant
from company_compass.core.settings import Settings
from company_compass.main import create_app


@pytest.mark.asyncio
async def test_closing_http_body_closes_the_assistant_stream_immediately():
    from company_compass.api.routes.assistant import stream_chat
    from company_compass.models.requests import ChatRequest

    closed = []

    class Assistant:
        async def stream(self, message, thread_id=None):
            try:
                yield {"type": "session", "thread_id": "test"}
                yield {"type": "token", "text": "unfinished"}
            finally:
                closed.append(True)

    response = await stream_chat(ChatRequest(message="Hello"), Assistant())
    await anext(response.body_iterator)
    await response.body_iterator.aclose()
    assert closed == [True]


def make_client(tmp_path, assistant):
    app = create_app(
        Settings(
            _env_file=None,
            app_mode="local",
            google_cloud_project="",
            catalog_path=tmp_path / "catalog.json",
            knowledge_path=tmp_path / "knowledge.json",
        )
    )
    app.dependency_overrides[get_assistant] = lambda: assistant
    return TestClient(app)


def events(response):
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


def test_stream_endpoint_sends_incremental_events_and_thread_id(tmp_path):
    class Assistant:
        async def stream(self, message, thread_id=None):
            assert message == "Compare these"
            assert thread_id == "f9444192-e538-47d4-a542-6fdd998462ba"
            yield {"type": "session", "thread_id": thread_id}
            yield {"type": "token", "text": "One "}
            yield {"type": "token", "text": "answer"}
            yield {"type": "done", "answer": "One answer", "thread_id": thread_id}

    with make_client(tmp_path, Assistant()) as client:
        response = client.post(
            "/api/chat/stream",
            json={"message": "Compare these", "thread_id": "f9444192-e538-47d4-a542-6fdd998462ba"},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [event["type"] for event in events(response)] == ["session", "token", "token", "done"]


def test_stream_failure_is_safe_terminal_event(tmp_path):
    class Assistant:
        async def stream(self, message, thread_id=None):
            yield {"type": "token", "text": "Partial"}
            raise RuntimeError("private provider details")

    with make_client(tmp_path, Assistant()) as client:
        response = client.post("/api/chat/stream", json={"message": "Hi"})
    values = events(response)
    assert values[-1]["type"] == "error"
    assert "private provider details" not in response.text
    assert not any(value["type"] == "done" for value in values)


def test_request_rejects_history_replay_and_invalid_thread_id(tmp_path):
    with make_client(tmp_path, object()) as client:
        assert (
            client.post("/api/chat/stream", json={"message": "Hi", "history": []}).status_code
            == 422
        )
        assert (
            client.post(
                "/api/chat/stream", json={"message": "Hi", "thread_id": "../bad"}
            ).status_code
            == 422
        )
