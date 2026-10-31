"""Request-scoped access to application services and administrator authorization."""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from company_compass.agents.assistant import Assistant
from company_compass.core.container import ServiceContainer
from company_compass.core.settings import Settings
from company_compass.services.catalog import CatalogService
from company_compass.services.knowledge import KnowledgeService


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_catalog(request: Request) -> CatalogService:
    return get_container(request).catalog


def get_knowledge(request: Request) -> KnowledgeService:
    return get_container(request).knowledge


def get_assistant(request: Request) -> Assistant:
    assistant = get_container(request).assistant
    if assistant is None:
        raise HTTPException(status_code=503, detail="The assistant is still initializing")
    return assistant


def require_admin(request: Request, x_admin_token: str = Header(default="")) -> None:
    expected = get_settings(request).admin_token.get_secret_value()
    if not expected or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="A valid admin token is required")


CatalogDependency = Annotated[CatalogService, Depends(get_catalog)]
KnowledgeDependency = Annotated[KnowledgeService, Depends(get_knowledge)]
AssistantDependency = Annotated[Assistant, Depends(get_assistant)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
