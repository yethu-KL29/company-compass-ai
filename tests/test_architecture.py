from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from company_compass.core.settings import ROOT, Settings
from company_compass.main import create_app


@pytest.mark.asyncio
async def test_startup_binds_the_complete_unified_tool_list_once(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from langchain_core.tools import StructuredTool

    from company_compass.core.container import ServiceContainer
    from company_compass.integrations import agent_tools, chat_model

    model = Mock()
    model.aclose = AsyncMock()
    native_schema, native_read, rag = [
        StructuredTool.from_function(lambda: "result", name=name, description=name)
        for name in ("get-schema", "read-cypher", "company_rag")
    ]
    unified = [native_schema, native_read, rag]
    discover = AsyncMock(return_value=unified)
    monkeypatch.setattr(chat_model, "create_chat_model", lambda settings: model)
    monkeypatch.setattr(agent_tools, "build_tools", discover)
    settings = Settings(
        _env_file=None,
        google_cloud_project="test-project",
        catalog_path=tmp_path / "catalog.json",
        knowledge_path=tmp_path / "knowledge.json",
    )
    services = ServiceContainer(settings)
    model.bind_tools.assert_not_called()
    await services.initialize()
    await services.initialize()
    discover.assert_awaited_once_with(settings, services.knowledge)
    model.bind_tools.assert_called_once_with(unified)
    assert model.bind_tools.call_args.args[0][0] is native_schema
    assert model.bind_tools.call_args.args[0][1] is native_read
    await services.aclose()


def test_relocated_settings_find_repository_assets():
    assert ROOT == Path(__file__).resolve().parents[1]
    assert (ROOT / "data/demo-products.json").is_file()
    assert (ROOT / "docs/knowledge/catalog/schema.md").is_file()


def test_main_factory_wires_independent_routes_and_services(tmp_path):
    settings = Settings(
        _env_file=None,
        app_mode="local",
        google_cloud_project="",
        catalog_path=tmp_path / "catalog.json",
        knowledge_path=tmp_path / "knowledge.json",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/products").json() == []
        assert client.get("/api/documents").json() == []
        assert client.get("/api/admin/schema").status_code == 401


def test_application_shutdown_closes_the_async_model_client(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from company_compass.integrations import chat_model

    model = Mock()
    model.aclose = AsyncMock()
    monkeypatch.setattr(chat_model, "create_chat_model", lambda settings: model)
    settings = Settings(
        _env_file=None,
        google_cloud_project="test-project",
        catalog_path=tmp_path / "catalog.json",
        knowledge_path=tmp_path / "knowledge.json",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200
    model.aclose.assert_awaited_once()
