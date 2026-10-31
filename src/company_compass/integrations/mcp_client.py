"""Discover the official Neo4j MCP server's native LangChain tools."""

import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient

from company_compass.core.settings import ROOT, Settings

READ_ONLY_TOOLS = {"get-schema", "read-cypher"}


def neo4j_client(settings: Settings) -> MultiServerMCPClient | None:
    """Configure read-only stdio; the MCP SDK supplies the OS process environment."""
    if not settings.neo4j_mcp_command:
        return None
    return MultiServerMCPClient(
        {
            "neo4j": {
                "transport": "stdio",
                "command": settings.neo4j_mcp_command,
                "args": settings.neo4j_mcp_args,
                "cwd": str(ROOT),
                # Do not pass the application's model, tracing or admin credentials.
                "env": {
                    "NEO4J_MCP_URI": settings.neo4j_uri,
                    "NEO4J_MCP_USERNAME": settings.neo4j_username,
                    "NEO4J_MCP_PASSWORD": settings.neo4j_password.get_secret_value(),
                    "NEO4J_MCP_DATABASE": settings.neo4j_database,
                    "NEO4J_MCP_READ_ONLY": "true",
                    "NEO4J_MCP_TOOLS": "get-schema,read-cypher",
                    "NEO4J_MCP_TELEMETRY": "false",
                    "NEO4J_MCP_REQUEST_TIMEOUT": "30s",
                },
            }
        },
        tool_name_prefix=False,
    )


async def load_neo4j_tools(settings: Settings) -> list:
    """Keep discovered names, schemas and executors intact, with no query wrapper.

    MultiServerMCPClient opens and closes a session per discovery/tool invocation.
    It is not an async context manager in the installed adapter version.
    """
    client = neo4j_client(settings)
    if client is None:
        return []
    try:
        tools = await asyncio.wait_for(client.get_tools(), timeout=75)
    except Exception:
        raise RuntimeError(
            "Neo4j MCP tools could not be discovered. Check the server configuration."
        ) from None
    names = [item.name for item in tools]
    if set(names) != READ_ONLY_TOOLS or len(names) != len(READ_ONLY_TOOLS):
        raise RuntimeError("Neo4j MCP must expose only the expected read-only tools")
    return tools
