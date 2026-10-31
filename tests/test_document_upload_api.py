from fastapi.testclient import TestClient

from company_compass.core.settings import Settings
from company_compass.main import create_app


def upload_client(tmp_path):
    return TestClient(
        create_app(
            Settings(
                _env_file=None,
                app_mode="local",
                admin_token="upload-admin",
                catalog_path=tmp_path / "catalog.json",
                knowledge_path=tmp_path / "knowledge.json",
            )
        )
    )


def test_authenticated_file_upload_is_readable_and_editable(tmp_path):
    with upload_client(tmp_path) as client:
        data = {"title": "Company onboarding guide"}
        files = {"file": ("guide.md", b"# Guide\n\nReviewed onboarding process.", "text/markdown")}
        assert client.post("/api/admin/documents/upload", data=data, files=files).status_code == 401
        result = client.post(
            "/api/admin/documents/upload",
            data=data,
            files=files,
            headers={"X-Admin-Token": "upload-admin"},
        )
        assert result.status_code == 201
        document = result.json()
        assert document["title"] == data["title"]
        assert document["source_url"] is None
        assert document["source_kind"] == "admin_upload"
        assert document["content"] == "# Guide\n\nReviewed onboarding process."
        assert client.get(f"/api/documents/{document['id']}").json()["id"] == document["id"]
        saved = client.put(
            f"/api/admin/documents/{document['id']}",
            headers={"X-Admin-Token": "upload-admin"},
            json={
                "title": "Updated guide",
                "content": "New onboarding process.",
                "expected_revision": 1,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["id"] == document["id"]
        assert saved.json()["source_url"] is None
        assert saved.json()["revision"] == 2


def test_invalid_document_upload_returns_readable_error(tmp_path):
    with upload_client(tmp_path) as client:
        result = client.post(
            "/api/admin/documents/upload",
            data={"title": "Bad file"},
            files={"file": ("bad.txt", b"\xff\xfe", "text/plain")},
            headers={"X-Admin-Token": "upload-admin"},
        )
        assert result.status_code == 422
        assert "UTF-8" in result.json()["detail"]
        assert client.get("/api/documents").json() == []
