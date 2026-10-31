import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from company_compass.core.settings import Settings
from company_compass.integrations.agent_tools import build_tools


@pytest.mark.asyncio
async def test_native_mcp_tools_and_local_rag_are_merged_without_wrappers(monkeypatch):
    native = [SimpleNamespace(name="get-schema"), SimpleNamespace(name="read-cypher")]
    discover = AsyncMock(return_value=native)
    monkeypatch.setattr("company_compass.integrations.agent_tools.load_neo4j_tools", discover)
    selected = await build_tools(Settings(_env_file=None), Mock())
    assert selected[0] is native[0]
    assert selected[1] is native[1]
    assert [item.name for item in selected] == [
        "get-schema",
        "read-cypher",
        "company_rag",
        "catalog_search",
    ]
    discover.assert_awaited_once()


@pytest.mark.asyncio
async def test_rag_passes_query_and_preserves_sources_as_an_artifact(monkeypatch):
    monkeypatch.setattr(
        "company_compass.integrations.agent_tools.load_neo4j_tools", AsyncMock(return_value=[])
    )
    knowledge = Mock()
    knowledge.search.return_value = {
        "sources": [{"title": "Company", "text": "Evidence"}],
        "warnings": [],
    }
    selected = await build_tools(Settings(_env_file=None), knowledge)
    message = await selected[0].ainvoke(
        {"type": "tool_call", "id": "rag1", "name": "company_rag", "args": {"query": "services"}}
    )
    knowledge.search.assert_called_once_with("services")
    assert message.artifact["sources"][0]["title"] == "Company"
    assert json.loads(message.content)["sources"][0]["text"] == "Evidence"


@pytest.mark.asyncio
async def test_unconfigured_graph_only_returns_rag_not_a_fake_neo4j_tool():
    selected = await build_tools(Settings(_env_file=None), Mock())
    assert [item.name for item in selected] == ["company_rag"]


@pytest.mark.asyncio
async def test_rag_errors_and_large_results_are_bounded_safe_evidence(monkeypatch):
    monkeypatch.setattr(
        "company_compass.integrations.agent_tools.load_neo4j_tools", AsyncMock(return_value=[])
    )
    knowledge = Mock()
    knowledge.search.side_effect = RuntimeError("private provider detail")
    selected = await build_tools(Settings(_env_file=None), knowledge)
    result = await selected[0].ainvoke({"query": "services"})
    assert "error" in result and "private provider detail" not in result
    knowledge.search.side_effect = None
    knowledge.search.return_value = {"sources": [{"text": '"\\\n' * 100000}]}
    result = await selected[0].ainvoke({"query": "services"})
    assert len(result) <= 32000 and "truncated" in result
