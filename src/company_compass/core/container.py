"""Composition root: choose real cloud storage or explicit local demo storage."""

from company_compass.core.settings import Settings
from company_compass.repositories.catalog import LocalCatalogRepository, Neo4jCatalogRepository
from company_compass.services.catalog import CatalogService


def catalog_service(settings: Settings) -> CatalogService:
    if settings.app_mode == "local":
        repository = LocalCatalogRepository(settings.catalog_path)
    else:
        from company_compass.integrations.embeddings import VertexEmbeddingClient

        if not all(
            (
                settings.neo4j_uri,
                settings.neo4j_username,
                settings.neo4j_password.get_secret_value(),
            )
        ):
            raise ValueError("Cloud catalog credentials are not configured")
        repository = Neo4jCatalogRepository(
            settings.neo4j_uri,
            settings.neo4j_username,
            settings.neo4j_password.get_secret_value(),
            settings.neo4j_database,
            embedding_client=VertexEmbeddingClient(settings),
            embedding_model=settings.embedding_model,
            embedding_dimensions=settings.embedding_dimensions,
        )
    return CatalogService(repository)


def close_catalog(service: CatalogService):
    close = getattr(service.repository, "close", None)
    if close:
        close()


class ServiceContainer:
    """One explicit owner of application services and their resource lifetimes."""

    def __init__(self, settings: Settings):
        from company_compass.integrations.chat_model import create_chat_model
        from company_compass.integrations.observability import Observability
        from company_compass.services.knowledge import KnowledgeService

        self.catalog = catalog_service(settings)
        self.settings = settings
        self.knowledge = KnowledgeService(settings)
        self.model = create_chat_model(settings) if settings.model_configured else None
        self.telemetry = Observability(settings)
        self.assistant = None

    async def initialize(self) -> None:
        """Discover MCP tools, merge local tools and build the single agent once."""
        from company_compass.agents.assistant import Assistant
        from company_compass.integrations.agent_tools import build_tools

        if self.assistant is None:
            all_tools = await build_tools(self.settings, self.knowledge)
            self.assistant = Assistant(self.settings, self.model, all_tools, self.telemetry)

    async def aclose(self) -> None:
        try:
            if self.model is not None:
                await self.model.aclose()
        finally:
            try:
                await self.telemetry.aclose()
            finally:
                self.close()

    def close(self) -> None:
        try:
            close_catalog(self.catalog)
        finally:
            self.knowledge.close()
