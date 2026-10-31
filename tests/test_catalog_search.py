import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import ToolMessage

from company_compass.models.catalog import Plan, Product
from company_compass.services.catalog_search import (
    HYBRID_QUERY,
    CatalogSearch,
    lexical_query,
    product_search_text,
    validate_vector,
)


def product():
    return Product(
        id="docs",
        name="Document Suite",
        description="Extract and review business documents.",
        categories=["documents"],
        use_cases=["document_extraction"],
        plans=[Plan(id="basic", name="Basic", use_cases=["invoice_review", "document_extraction"])],
    )


def graph_context():
    return {
        "categories": ["documents"],
        "plans": [{"id": "basic", "use_cases": ["invoice_review"]}],
    }


def service(result=None):
    embeddings = Mock()
    embeddings.embed_query.return_value = [0.6, 0.8]
    tool = SimpleNamespace(ainvoke=AsyncMock(return_value=result if result is not None else "[]"))
    return CatalogSearch(embeddings, tool, model="embedding-model", dimensions=2), embeddings, tool


def test_search_text_covers_description_and_all_use_cases_without_pricing():
    text = product_search_text(product())
    assert text == (
        "Product: Document Suite\n"
        "Description: Extract and review business documents.\n"
        "Use cases: document extraction; invoice review"
    )
    assert text.count("document extraction") == 1
    changed = product().model_copy(deep=True)
    changed.plans[0].price_minor = 999900
    changed.plans[0].max_users = 100
    assert product_search_text(changed) == text


@pytest.mark.parametrize("vector", [[1], [0, 0], [True, 1], [float("nan"), 1], [1, float("inf")]])
def test_invalid_vectors_are_rejected(vector):
    with pytest.raises(ValueError):
        validate_vector(vector, 2)


def test_valid_vectors_and_lexical_query_are_safe():
    assert validate_vector([0.6, 0.8], 2) == [0.6, 0.8]
    assert lexical_query('documents: "invoice" AND (review*) +foo -bar') == (
        '"documents" OR "invoice" OR "AND" OR "review" OR "foo" OR "bar"'
    )
    assert lexical_query("??? ***") == ""


@pytest.mark.asyncio
async def test_search_embeds_then_calls_native_cypher_with_top_five_and_no_raw_vectors():
    dto = product().model_dump()
    rows = [
        {
            "product_id": "docs",
            "fused_score": 0.03,
            "snapshot_json": json.dumps(dto),
            "relationship_context": graph_context(),
        }
    ]
    search, embedding, tool = service(json.dumps(rows))
    result = await search.search("document automation")
    embedding.embed_query.assert_called_once_with("document automation")
    tool.ainvoke.assert_awaited_once_with(
        {
            "query": HYBRID_QUERY,
            "params": {
                "query_vector": [0.6, 0.8],
                "lexical_query": '"document" OR "automation"',
                "dataset": "attoforce-demo-v1",
                "source_k": 25,
                "final_k": 5,
                "model": "embedding-model",
                "dimensions": 2,
            },
        }
    )
    assert result["products"] == [
        {"score": 0.03, "product": dto, "relationship_context": graph_context()}
    ]
    assert result["retrieval"] == {"method": "hybrid_rrf", "limit": 5}
    assert "snapshot_json" not in json.dumps(result)
    assert "search_embedding" not in json.dumps(result)
    assert "db.index.vector.queryNodes" in HYBRID_QUERY
    assert "db.index.fulltext.queryNodes" in HYBRID_QUERY
    assert "CURRENT_REVISION" in HYBRID_QUERY
    assert "sum(contribution)" in HYBRID_QUERY
    assert "HAS_VARIANT" in HYBRID_QUERY and "HAS_ATTRIBUTE" in HYBRID_QUERY


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   ", "x" * 2001, "***"])
async def test_bad_queries_do_not_call_providers(query):
    search, embedding, tool = service()
    result = await search.search(query)
    assert "error" in result and result["products"] == []
    embedding.embed_query.assert_not_called()
    tool.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [{"type": "text", "text": "[]"}],
        ToolMessage(content=[{"type": "text", "text": "[]"}], tool_call_id="test"),
        {"records": []},
    ],
)
async def test_native_mcp_content_forms_are_unwrapped(payload):
    search, _, _ = service(payload)
    assert (await search.search("documents"))["products"] == []
    assert "error" not in await search.search("documents")


@pytest.mark.asyncio
async def test_provider_errors_and_bad_payloads_are_not_empty_successes():
    search, embedding, tool = service()
    embedding.embed_query.side_effect = RuntimeError("private-provider-key")
    assert "private-provider-key" not in json.dumps(await search.search("documents"))
    assert "error" in await search.search("documents")
    embedding.embed_query.side_effect = None
    for payload in [
        "invalid",
        {"unexpected": []},
        '[{"snapshot_json": "bad"}]',
        ToolMessage(content="private detail", tool_call_id="x", status="error"),
    ]:
        tool.ainvoke.return_value = payload
        result = await search.search("documents")
        assert "error" in result and result["products"] == []
        assert "private detail" not in json.dumps(result)


@pytest.mark.asyncio
async def test_tool_evidence_is_bounded_to_five_distinct_current_products():
    rows = []
    for index in range(7):
        item = product().model_copy(update={"id": f"docs-{index}"})
        rows.append(
            {
                "product_id": item.id,
                "fused_score": 0.03,
                "snapshot_json": item.model_dump_json(),
                "relationship_context": graph_context(),
            }
        )
    rows.insert(1, rows[0])
    search, _, _ = service(rows)
    result = await search.search("documents")
    assert [row["product"]["id"] for row in result["products"]] == [
        f"docs-{index}" for index in range(5)
    ]


@pytest.mark.asyncio
async def test_invalid_or_retired_record_fails_without_leaking_unverified_facts():
    for changes in ({"status": "retired"}, {"id": "different"}):
        item = product().model_copy(update=changes)
        search, _, _ = service(
            [{"product_id": "docs", "fused_score": 0.03, "snapshot_json": item.model_dump_json()}]
        )
        result = await search.search("documents")
        assert result["products"] == []
        assert "error" in result
