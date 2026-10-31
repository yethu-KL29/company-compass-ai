import math
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from company_compass.core.settings import Settings
from company_compass.integrations.embeddings import VertexEmbeddingClient


def settings(**overrides):
    values = {
        "google_cloud_project": "assignment-project",
        "google_cloud_location": "global",
        "google_embedding_location": "us-central1",
        "google_application_credentials": "",
        "embedding_model": "gemini-embedding-001",
        "embedding_dimensions": 1536,
    }
    return Settings(_env_file=None, **(values | overrides))


def fake_embedding_client(monkeypatch, values=None):
    from google import genai

    vector = values if values is not None else [3.0, 4.0] + [0.0] * 1534
    response = SimpleNamespace(embeddings=[SimpleNamespace(values=vector)])
    embed = Mock(return_value=response)
    close = Mock()
    constructor = Mock(
        return_value=SimpleNamespace(
            models=SimpleNamespace(embed_content=embed),
            close=close,
        )
    )
    monkeypatch.setattr(genai, "Client", constructor)
    return constructor, embed, close


def test_document_embeddings_use_document_task_title_and_one_input_per_request(monkeypatch):
    constructor, embed, close = fake_embedding_client(monkeypatch)
    vectors = VertexEmbeddingClient(settings()).embed_documents(
        [
            {"title": "Overview", "text": "Company overview"},
            {"title": "Services", "text": "Company services"},
        ]
    )
    assert len(vectors) == 2
    assert embed.call_count == 2
    for call in embed.call_args_list:
        assert call.kwargs["model"] == "gemini-embedding-001"
        assert isinstance(call.kwargs["contents"], str)
        assert call.kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"
        assert call.kwargs["config"].output_dimensionality == 1536
    assert embed.call_args_list[0].kwargs["config"].title == "Overview"
    assert embed.call_args_list[1].kwargs["config"].title == "Services"
    assert constructor.call_args.kwargs["vertexai"] is True
    assert constructor.call_args.kwargs["location"] == "us-central1"
    assert "api_key" not in constructor.call_args.kwargs
    close.assert_called_once()


def test_query_embeddings_use_query_task_and_normalize_reduced_vectors(monkeypatch):
    _, embed, close = fake_embedding_client(monkeypatch)
    vector = VertexEmbeddingClient(settings()).embed_query("What services are offered?")
    assert len(vector) == 1536
    assert vector[0] == pytest.approx(0.6)
    assert vector[1] == pytest.approx(0.8)
    assert math.hypot(*vector) == pytest.approx(1.0)
    request = embed.call_args.kwargs
    assert request["contents"] == "What services are offered?"
    assert request["config"].task_type == "RETRIEVAL_QUERY"
    assert request["config"].title is None
    close.assert_called_once()


@pytest.mark.parametrize(
    "values",
    [
        [1.0] * 1535,
        [float("nan")] + [0.0] * 1535,
        [float("inf")] + [0.0] * 1535,
        [0.0] * 1536,
        [],
        ["not numeric"] + [0.0] * 1535,
    ],
    ids=["wrong_dimensions", "nan", "infinity", "zero", "empty", "nonnumeric"],
)
def test_invalid_embedding_vectors_are_rejected_and_client_closes(monkeypatch, values):
    _, _, close = fake_embedding_client(monkeypatch, values)
    with pytest.raises(ValueError, match="embedding|vector"):
        VertexEmbeddingClient(settings()).embed_query("Question")
    close.assert_called_once()


def test_missing_embedding_response_is_rejected_and_client_closes(monkeypatch):
    _, embed, close = fake_embedding_client(monkeypatch)
    embed.return_value = SimpleNamespace(embeddings=[])
    with pytest.raises(ValueError, match="embedding"):
        VertexEmbeddingClient(settings()).embed_query("Question")
    close.assert_called_once()


def test_sdk_error_does_not_leak_open_client(monkeypatch):
    _, embed, close = fake_embedding_client(monkeypatch)
    embed.side_effect = RuntimeError("Provider unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        VertexEmbeddingClient(settings()).embed_query("Question")
    close.assert_called_once()


def test_empty_batch_avoids_network_and_blank_text_is_rejected(monkeypatch):
    constructor, _, _ = fake_embedding_client(monkeypatch)
    client = VertexEmbeddingClient(settings())
    assert client.embed_documents([]) == []
    with pytest.raises(ValueError, match="empty"):
        client.embed_query("   ")
    with pytest.raises(ValueError, match="empty"):
        client.embed_documents([{"title": "Missing", "text": ""}])
    constructor.assert_not_called()


def test_embedding_calls_require_project_without_authentication_side_effects(monkeypatch):
    constructor, _, _ = fake_embedding_client(monkeypatch)
    with pytest.raises(ValueError, match="project|Configure"):
        VertexEmbeddingClient(settings(google_cloud_project="")).embed_query("Question")
    constructor.assert_not_called()
