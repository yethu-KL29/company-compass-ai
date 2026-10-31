"""Published document browsing and authenticated ingestion/replacement."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from company_compass.api.dependencies import KnowledgeDependency, require_admin
from company_compass.models.requests import DocumentReplacement, IngestRequest
from company_compass.utils.uploads import MAX_UPLOAD_BYTES, extract_document

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/admin/ingest", dependencies=[Depends(require_admin)])
def ingest(request: IngestRequest, knowledge: KnowledgeDependency):
    return knowledge.ingest(request.urls)


@router.get("/documents")
def documents(knowledge: KnowledgeDependency):
    return knowledge.list_documents()


@router.get("/documents/{document_id}")
def document(document_id: str, knowledge: KnowledgeDependency):
    result = knowledge.get_document(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Published document not found")
    return result


@router.put("/admin/documents/{document_id}", dependencies=[Depends(require_admin)])
def replace_document(
    document_id: str,
    request: DocumentReplacement,
    knowledge: KnowledgeDependency,
):
    if knowledge.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Published document not found")
    return knowledge.replace_document(
        document_id, request.title, request.content, request.expected_revision
    )


@router.post("/admin/documents/upload", status_code=201, dependencies=[Depends(require_admin)])
async def upload_document(
    knowledge: KnowledgeDependency,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=250)],
):
    try:
        payload = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Upload a document of at most 10 MB")
        try:
            content = extract_document(file.filename or "", payload)
            return knowledge.add_document(title, content)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
    finally:
        await file.close()
