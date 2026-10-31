"""Health and authenticated authored/live schema diagnostics."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from company_compass.api.dependencies import SettingsDependency, require_admin
from company_compass.core.settings import ROOT
from company_compass.integrations.mcp_client import load_neo4j_tools

router = APIRouter(prefix="/api", tags=["diagnostics"])


@router.get("/health")
def health(settings: SettingsDependency):
    return {
        "status": "ok",
        "mode": settings.app_mode,
        "model_configured": settings.model_configured,
        "model_provider": settings.llm_provider,
        "model": settings.llm_model,
        "reasoning_level": settings.gemini_thinking_level
        if settings.llm_provider == "gemini"
        else None,
        "model_authentication": "Google service account / ADC"
        if settings.llm_provider == "gemini" and settings.gemini_use_vertexai
        else "API key",
        "embedding_model": settings.embedding_model
        if settings.embedding_provider == "vertex"
        else "Snowflake/snowflake-arctic-embed-m-v1.5",
        "embedding_dimensions": settings.embedding_dimensions
        if settings.embedding_provider == "vertex"
        else 768,
        "integrations": {
            "catalog": settings.app_mode,
            "knowledge": settings.app_mode,
            "neo4j_mcp": bool(settings.neo4j_mcp_command),
        },
    }


@router.get("/admin/schema", dependencies=[Depends(require_admin)])
def schema():
    return {
        "schema_version": "assignment-v1",
        "content": (ROOT / "docs/knowledge/catalog/schema.md").read_text(encoding="utf-8"),
    }


@router.get("/admin/live-schema", dependencies=[Depends(require_admin)])
async def live_schema(settings: SettingsDependency):
    tools = await load_neo4j_tools(settings)
    schema_tool = next((tool for tool in tools if tool.name == "get-schema"), None)
    if schema_tool is None:
        raise HTTPException(status_code=503, detail="Official Neo4j MCP is not configured")
    return await asyncio.wait_for(schema_tool.ainvoke({}), timeout=45)
