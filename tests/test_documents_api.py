from fastapi.testclient import TestClient

from company_compass.core.settings import Settings
from company_compass.main import create_app
from company_compass.services.knowledge import KnowledgeService

HEADERS = {"X-Admin-Token": "document-admin"}


def document_client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        KnowledgeService, "_fetch", lambda self, url: ("About the company", "Old facts")
    )
    settings = Settings(
        _env_file=None,
        app_mode="local",
        admin_token="document-admin",
        catalog_path=tmp_path / "catalog.json",
        knowledge_path=tmp_path / "knowledge.json",
    )
    return TestClient(create_app(settings))


def test_browse_documents_and_authorized_reingestion(tmp_path, monkeypatch):
    with document_client(tmp_path, monkeypatch) as api:
        assert (
            api.post(
                "/api/admin/ingest", headers=HEADERS, json={"urls": ["https://attoforce.ai/"]}
            ).status_code
            == 200
        )
        listing = api.get("/api/documents")
        assert listing.status_code == 200
        document = listing.json()[0]
        assert document["title"] == "About the company"
        assert document["id"]
        assert "content" not in document
        assert api.get(f"/api/documents/{document['id']}").json()["content"] == "Old facts"
        payload = {
            "title": "Reviewed company overview",
            "content": "Updated facts\nReviewed by admin.",
            "expected_revision": document["revision"],
        }
        url = f"/api/admin/documents/{document['id']}"
        assert api.put(url, json=payload).status_code == 401
        saved = api.put(url, headers=HEADERS, json=payload)
        assert saved.status_code == 200
        assert saved.json()["id"] == document["id"]
        assert saved.json()["revision"] == 2
        assert saved.json()["content"] == payload["content"]
        assert saved.json()["source_kind"] == "admin_edit"
        assert api.put(url, headers=HEADERS, json=payload).status_code == 409


def test_failed_reingestion_preserves_published_document(tmp_path, monkeypatch):
    with document_client(tmp_path, monkeypatch) as api:
        api.post("/api/admin/ingest", headers=HEADERS, json={"urls": ["https://attoforce.ai/"]})
        document = api.get("/api/documents").json()[0]
        monkeypatch.setattr(
            KnowledgeService,
            "_index_chunks",
            lambda *args: (_ for _ in ()).throw(RuntimeError("Provider failed")),
        )
        result = api.put(
            f"/api/admin/documents/{document['id']}",
            headers=HEADERS,
            json={"title": "Replacement", "content": "New facts", "expected_revision": 1},
        )
        assert result.status_code == 502
        active = api.get(f"/api/documents/{document['id']}").json()
        assert active["content"] == "Old facts"
        assert active["revision"] == 1


def test_document_validation_and_missing_ids(tmp_path, monkeypatch):
    with document_client(tmp_path, monkeypatch) as api:
        assert api.get("/api/documents/missing").status_code == 404
        assert (
            api.put(
                "/api/admin/documents/missing",
                headers=HEADERS,
                json={"title": " ", "content": " ", "expected_revision": 1},
            ).status_code
            == 422
        )
