from unittest.mock import MagicMock, Mock

import pytest

from company_compass.repositories.catalog import Neo4jCatalogRepository
from company_compass.utils.seed import load_demo_products


def repository(monkeypatch):
    driver = MagicMock()
    monkeypatch.setattr("neo4j.GraphDatabase.driver", Mock(return_value=driver))
    embeddings = Mock()
    embeddings.embed_documents.return_value = [[1.0] + [0.0] * 1535]
    repo = Neo4jCatalogRepository(
        "neo4j://example",
        "user",
        "password",
        "neo4j",
        embedding_client=embeddings,
        embedding_model="gemini-embedding-001",
        embedding_dimensions=1536,
    )
    return repo, driver, embeddings


def test_publication_prepares_description_and_use_case_embedding_before_transaction(monkeypatch):
    repo, driver, embeddings = repository(monkeypatch)
    product = load_demo_products()[0]
    repo.publish(product, None)
    document = embeddings.embed_documents.call_args.args[0][0]
    assert product.description in document["text"]
    assert str(product.plans[0].price_minor) not in document["text"]
    args = driver.session.return_value.__enter__.return_value.execute_write.call_args.args
    payload = args[-1]
    assert len(payload["search_embedding"]) == 1536
    assert payload["search_model"] == "gemini-embedding-001"


def test_embedding_failure_does_not_publish_or_replace_current_product(monkeypatch):
    repo, driver, embeddings = repository(monkeypatch)
    embeddings.embed_documents.side_effect = RuntimeError("embedding unavailable")
    with pytest.raises(RuntimeError):
        repo.publish(load_demo_products()[0], None)
    driver.session.assert_not_called()


def test_publication_writes_search_fields_in_same_transaction(monkeypatch):
    repo, _, _ = repository(monkeypatch)
    tx = Mock()
    tx.run.return_value.single.return_value = None
    payload = {
        "search_text": "document automation",
        "search_embedding": [1.0],
        "search_model": "test",
        "search_dimensions": 1,
    }
    repo._publish(tx, load_demo_products()[0], None, payload)
    calls = [call for call in tx.run.call_args_list if call.kwargs.get("search") == payload]
    assert len(calls) == 1
    assert "SET p += $search" in calls[0].args[0]


def test_backfill_checks_revision_before_updating_search_fields(monkeypatch):
    repo, driver, _ = repository(monkeypatch)
    product = load_demo_products()[0].model_copy(update={"revision": 3})
    repo.list_products = Mock(return_value=[product])
    session = driver.session.return_value.__enter__.return_value
    tx = Mock()
    tx.run.return_value.single.return_value = {"updated": 1}
    session.execute_write.side_effect = lambda update: update(tx)
    result = repo.reindex_search()
    assert result["indexed"] == 1
    call = tx.run.call_args
    assert call.kwargs["revision"] == 3
    assert "revision_number" in call.args[0]


def test_retirement_removes_search_entries_without_an_embedding_call(monkeypatch):
    repo, driver, embeddings = repository(monkeypatch)
    product = load_demo_products()[0].model_copy(update={"status": "retired"})
    repo.publish(product, None)
    embeddings.embed_documents.assert_not_called()
    args = driver.session.return_value.__enter__.return_value.execute_write.call_args.args
    assert args[-1]["search_embedding"] is None


def test_invalid_embedding_cannot_publish(monkeypatch):
    repo, driver, embeddings = repository(monkeypatch)
    embeddings.embed_documents.return_value = [[float("nan")] * 1536]
    with pytest.raises(ValueError):
        repo.publish(load_demo_products()[0], None)
    driver.session.assert_not_called()
