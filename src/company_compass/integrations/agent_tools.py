"""Merge native MCP tools and the local company-document retrieval tool."""

import asyncio
import json

from langchain_core.tools import tool

from company_compass.core.settings import Settings
from company_compass.integrations.mcp_client import load_neo4j_tools

MAX_RESULT_CHARACTERS = 32_000


def _bounded_json(value) -> str:
    content = json.dumps(value, default=str, ensure_ascii=False)
    if len(content) <= MAX_RESULT_CHARACTERS:
        return content
    return json.dumps(
        {
            "truncated": True,
            "warning": "Result exceeds the tool limit; query fewer fields or fewer products.",
            # JSON escaping can double the serialized excerpt's character count.
            "excerpt": content[: (MAX_RESULT_CHARACTERS - 500) // 2],
        },
        ensure_ascii=False,
    )


async def build_tools(settings: Settings, knowledge) -> list:
    """Give one agent the discovered MCP tools and local RAG tool in one list."""
    mcp_tools = await load_neo4j_tools(settings)

    @tool(response_format="content_and_artifact")
    async def company_rag(query: str) -> tuple[str, dict]:
        """Search ingested company documents for facts, returning passages and source IDs."""
        if not query.strip() or len(query) > 2000:
            result = {"error": "Use a company question of 1 to 2000 characters", "sources": []}
        else:
            try:
                result = await asyncio.to_thread(knowledge.search, query)
            except Exception:
                result = {"error": "Company document retrieval is unavailable", "sources": []}
        return _bounded_json(result), result

    return [*mcp_tools, company_rag]
