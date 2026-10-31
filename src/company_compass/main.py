"""Application factory: compose services and register the HTTP boundary."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from company_compass.api.errors import register_error_handlers
from company_compass.api.routes import assistant, documents, health, products
from company_compass.core.container import ServiceContainer
from company_compass.core.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    container = ServiceContainer(settings)

    @asynccontextmanager
    async def lifespan(_app):
        try:
            await container.initialize()
            yield
        finally:
            await container.aclose()

    app = FastAPI(title="Company Compass", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.container = container
    register_error_handlers(app)
    for route_module in (health, products, assistant, documents):
        app.include_router(route_module.router)
    return app
