from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from company_compass.core.settings import Settings
from company_compass.integrations.mcp_client import load_neo4j_tools, neo4j_client


def options(**values):
    return Settings(_env_file=None, neo4j_mcp_command="neo4j-mcp", **values)


def test_native_client_uses_read_only_stdio_without_exporting_other_credentials(monkeypatch):
    factory = Mock()
    monkeypatch.setattr("company_compass.integrations.mcp_client.MultiServerMCPClient", factory)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "never-export-langfuse")
    monkeypatch.setenv("ADMIN_TOKEN", "never-export-admin")
    neo4j_client(
        options(neo4j_uri="neo4j+s://example", neo4j_username="test", neo4j_password="db-secret")
    )
    config = factory.call_args.args[0]["neo4j"]
    assert config["transport"] == "stdio"
    assert config["command"] == "neo4j-mcp"
    assert config["env"]["NEO4J_MCP_READ_ONLY"] == "true"
    assert config["env"]["NEO4J_MCP_TOOLS"] == "get-schema,read-cypher"
    assert config["env"]["NEO4J_MCP_REQUEST_TIMEOUT"] == "30s"
    assert "LANGFUSE_SECRET_KEY" not in config["env"]
    assert "ADMIN_TOKEN" not in config["env"]
    assert factory.call_args.kwargs["tool_name_prefix"] is False


def test_unconfigured_client_does_not_create_a_local_graph_substitute():
    assert neo4j_client(Settings(_env_file=None)) is None


@pytest.mark.asyncio
async def test_discovery_preserves_native_objects_and_their_schemas(monkeypatch):
    native = [
        SimpleNamespace(name="get-schema", args_schema={"type": "object", "properties": {}}),
        SimpleNamespace(
            name="read-cypher",
            args_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}, "params": {"type": "object"}},
            },
        ),
    ]
    client = SimpleNamespace(get_tools=AsyncMock(return_value=native))
    monkeypatch.setattr("company_compass.integrations.mcp_client.neo4j_client", lambda _: client)
    tools = await load_neo4j_tools(options())
    client.get_tools.assert_awaited_once()
    assert tools is native
    assert tools[1].args_schema["properties"]["params"] == {"type": "object"}


@pytest.mark.asyncio
async def test_discovery_rejects_unexpected_or_incomplete_server_tools(monkeypatch):
    for names in (
        ["get-schema", "read-cypher", "write-cypher"],
        ["read-cypher"],
        ["get-schema", "read-cypher", "read-cypher"],
    ):
        client = SimpleNamespace(
            get_tools=AsyncMock(return_value=[SimpleNamespace(name=name) for name in names])
        )
        monkeypatch.setattr(
            "company_compass.integrations.mcp_client.neo4j_client", lambda _, client=client: client
        )
        with pytest.raises(RuntimeError, match="read-only"):
            await load_neo4j_tools(options())


@pytest.mark.asyncio
async def test_discovery_failure_is_safe_and_not_silently_ignored(monkeypatch):
    client = SimpleNamespace(
        get_tools=AsyncMock(side_effect=RuntimeError("private credential detail"))
    )
    monkeypatch.setattr("company_compass.integrations.mcp_client.neo4j_client", lambda _: client)
    with pytest.raises(RuntimeError, match="could not be discovered") as error:
        await load_neo4j_tools(options())
    assert "private credential" not in str(error.value)


@pytest.mark.asyncio
async def test_cli_check_does_not_call_an_mcp_error_a_success(monkeypatch, capsys):
    import json

    from langchain_core.messages import ToolMessage

    from company_compass.cli import mcp_check

    schema = SimpleNamespace(
        name="get-schema",
        ainvoke=AsyncMock(
            return_value=ToolMessage(content="Schema", tool_call_id="schema", status="success")
        ),
    )
    read = SimpleNamespace(
        name="read-cypher",
        ainvoke=AsyncMock(
            return_value=ToolMessage(content="Tool failed", tool_call_id="read", status="error")
        ),
    )
    monkeypatch.setattr(
        "company_compass.cli.load_neo4j_tools", AsyncMock(return_value=[schema, read])
    )
    await mcp_check(options())
    result = json.loads(capsys.readouterr().out)
    assert result["schema_received"] is True
    assert result["read_query_completed"] is False


@pytest.mark.asyncio
async def test_real_adapter_discovers_and_invokes_a_local_read_only_mcp_server(tmp_path):
    import sys

    from langchain_core.messages import ToolMessage

    server = tmp_path / "read_only_server.py"
    server.write_text("""from mcp.server.fastmcp import FastMCP
mcp = FastMCP('Test Neo4j')
@mcp.tool(name='get-schema')
def schema() -> str:
    return 'Catalog -> Product'
@mcp.tool(name='read-cypher')
def read(query: str, params: dict | None = None) -> dict:
    return {'received_query': query, 'received_params': params}
if __name__ == '__main__':
    mcp.run(transport='stdio')
""")
    tools = await load_neo4j_tools(
        Settings(_env_file=None, neo4j_mcp_command=sys.executable, neo4j_mcp_args=[str(server)])
    )
    native = {tool.name: tool for tool in tools}
    assert "params" in native["read-cypher"].args_schema["properties"]
    assert "params_json" not in native["read-cypher"].args_schema["properties"]
    result = await native["read-cypher"].ainvoke(
        {
            "type": "tool_call",
            "id": "read-one",
            "name": "read-cypher",
            "args": {"query": "MATCH (n) RETURN n LIMIT 1", "params": {"users": 10}},
        }
    )
    assert isinstance(result, ToolMessage)
    assert result.status == "success"
    assert "MATCH (n) RETURN n LIMIT 1" in str(result.content)
    assert "users" in str(result.content) and "10" in str(result.content)
