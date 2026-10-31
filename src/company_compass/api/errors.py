"""Map domain/integration failures to stable HTTP responses without leaking secrets."""

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from company_compass.repositories.catalog import RevisionConflict
from company_compass.services.knowledge import DocumentConflict, DocumentIndexingError

logger = logging.getLogger(__name__)


async def catalog_conflict(_request, _error):
    return JSONResponse(status_code=409, content={"detail": "Catalog changed. Reload and retry."})


async def document_conflict(_request, _error):
    return JSONResponse(
        status_code=409,
        content={"detail": "This document changed. Reload the published version before saving."},
    )


async def document_indexing_failed(_request, _error):
    return JSONResponse(
        status_code=502,
        content={
            "detail": "Re-ingestion failed. The previous published document remains available."
        },
    )


async def unexpected_error(_request, error):
    logger.error("Request failed: %s", type(error).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "A configured integration is unavailable. Check the setup diagnostics."},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RevisionConflict, catalog_conflict)
    app.add_exception_handler(DocumentConflict, document_conflict)
    app.add_exception_handler(DocumentIndexingError, document_indexing_failed)
    app.add_exception_handler(Exception, unexpected_error)
